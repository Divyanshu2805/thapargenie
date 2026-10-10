# 0006. The model reads scanned and table-heavy PDFs

## Context

Many official documents are scans or fee tables that lose their structure as plain
text. The server has 512 MB of memory.

## Decision

PDFs with a usable text layer are read with `pypdf`. Pages with too little text,
or documents an admin marks for "smart" parsing, are sent to the model in 20-page windows
with an instruction to return Markdown, tables included.

## Consequences

- OCR and table reconstruction without native libraries on a small server.
- It costs model calls, so it is used only where the text layer fails.
- A page limit per file (300) bounds the cost of one upload.
- Output is not deterministic; admins can view and edit every passage afterwards.

## Alternatives considered

- **PyMuPDF**: better extraction, but AGPL-licensed.
- **Tesseract**: heavy on memory, weaker on tables.
