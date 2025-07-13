"""Identify uploads by content, never by extension or client-sent MIME type."""

import io
import zipfile

from knowledge.models import SourceType


class UnsupportedFile(ValueError):
    pass


MIME_TYPES = {
    SourceType.PDF: 'application/pdf',
    SourceType.DOCX: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    SourceType.XLSX: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    SourceType.CSV: 'text/csv',
    SourceType.HTML: 'text/html',
    SourceType.TEXT: 'text/plain',
}

EXTENSIONS = {
    SourceType.PDF: 'pdf',
    SourceType.DOCX: 'docx',
    SourceType.XLSX: 'xlsx',
    SourceType.CSV: 'csv',
    SourceType.HTML: 'html',
    SourceType.TEXT: 'txt',
}


def _office_type(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise UnsupportedFile('The file looks like a damaged Office document.') from exc
    if '[Content_Types].xml' not in names:
        raise UnsupportedFile('Unsupported archive format.')
    if any(name.startswith('word/') for name in names):
        return SourceType.DOCX
    if any(name.startswith('xl/') for name in names):
        return SourceType.XLSX
    raise UnsupportedFile('Only Word (.docx) and Excel (.xlsx) Office files are supported.')


def decode_text(data):
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnsupportedFile('The text file is not UTF-8 or Windows-1252 encoded.')


def detect(data, filename=''):
    """Return the SourceType for raw upload bytes, or raise UnsupportedFile."""
    if not data:
        raise UnsupportedFile('The file is empty.')
    head = data[:1024]
    if head.startswith(b'%PDF-'):
        return SourceType.PDF
    if head.startswith(b'PK\x03\x04'):
        return _office_type(data)
    if b'\x00' in head:
        raise UnsupportedFile('Binary files of this type are not supported.')
    text = decode_text(head).lstrip().lower()
    if text.startswith(('<!doctype html', '<html')) or '<body' in text:
        return SourceType.HTML
    if filename.lower().endswith('.csv'):
        return SourceType.CSV
    return SourceType.TEXT
