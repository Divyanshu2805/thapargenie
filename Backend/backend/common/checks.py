"""Deploy checks for settings that only fail under load."""

import os

from django.conf import settings
from django.core.checks import Tags, Warning, register

# Supabase's free and Micro compute allow this many direct connections.
DIRECT_CONNECTION_LIMIT = 60


@register(Tags.database, deploy=True)
def connection_budget(app_configs, **kwargs):
    """Each worker thread keeps a connection, and an open answer stream uses a second."""
    if settings.DATABASE_TRANSACTION_POOLING:
        return []
    workers = int(os.getenv('WEB_CONCURRENCY', '2'))
    threads = int(os.getenv('GUNICORN_THREADS', '8'))
    peak = workers * threads * 2
    if peak <= DIRECT_CONNECTION_LIMIT:
        return []
    return [Warning(
        f'{workers} workers x {threads} threads can open about {peak} database connections, '
        f'above the {DIRECT_CONNECTION_LIMIT} a small Supabase compute allows directly.',
        hint='Use the transaction pooler (port 6543) with DATABASE_TRANSACTION_POOLING=true, '
             'or fewer threads.',
        id='common.W001',
    )]
