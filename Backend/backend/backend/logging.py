"""Logging helpers that keep common credential shapes out of application logs."""

import logging
import re


class RedactSecretsFilter(logging.Filter):
    patterns = (
        re.compile(r'(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+'),
        re.compile(r'(?i)((?:password|token|secret|api[_-]?key)\s*[:=]\s*)[^\s,;]+'),
    )

    def filter(self, record):
        message = record.getMessage()
        for pattern in self.patterns:
            message = pattern.sub(r'\1[REDACTED]', message)
        record.msg = message
        record.args = ()
        if not hasattr(record, 'request_id'):
            record.request_id = '-'
        return True
