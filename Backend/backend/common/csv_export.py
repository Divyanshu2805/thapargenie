"""CSV downloads for the admin.

Cells a spreadsheet would read as a formula (starting with = + - @, tab or CR) are
prefixed with an apostrophe: students write the questions and comments that end up here.
"""

import csv
from datetime import date, datetime

from django.http import HttpResponse
from django.utils import timezone

MAX_ROWS = 5000
FORMULA_START = ('=', '+', '-', '@', '\t', '\r')


def safe_cell(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime('%Y-%m-%d %H:%M')
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    return f"'{text}" if text.startswith(FORMULA_START) else text


def csv_response(filename, header, rows):
    """`rows` is an iterable of sequences; at most MAX_ROWS are written."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'no-store'
    response.write('﻿')  # so Excel reads the file as UTF-8
    writer = csv.writer(response)
    writer.writerow(header)
    count = 0
    for row in rows:
        if count >= MAX_ROWS:
            break
        writer.writerow([safe_cell(value) for value in row])
        count += 1
    response.rows_written = count
    return response
