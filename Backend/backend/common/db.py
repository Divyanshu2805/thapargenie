"""Per-connection session settings.

Connection poolers (Supabase's Supavisor) drop the libpq `options` startup parameter,
so `-c statement_timeout=…` in DATABASES never reached the server there. These are set
with one SET statement when Django opens a connection instead; the session pooler keeps
them for that connection. In transaction-pooling mode session state is not kept, so the
settings are skipped there (DATABASE_TRANSACTION_POOLING) and vector search sets its own
per query (rag/retrieve.py).
"""

from django.conf import settings

# pgvector: a wider HNSW candidate list, and keep scanning when the `is_searchable`
# filter drops rows. Read by rag/retrieve.py for its per-query fallback too.
HNSW_EF_SEARCH = 100


def session_statement():
    return (
        f'SET statement_timeout = {int(settings.DATABASE_STATEMENT_TIMEOUT_MS)}; '
        f'SET lock_timeout = {int(settings.DATABASE_LOCK_TIMEOUT_MS)}; '
        f'SET hnsw.ef_search = {HNSW_EF_SEARCH}; '
        "SET hnsw.iterative_scan = 'relaxed_order'"
    )


def apply_session_settings(sender, connection, **kwargs):
    """`connection_created` receiver."""
    if connection.vendor != 'postgresql' or settings.DATABASE_TRANSACTION_POOLING:
        return
    with connection.cursor() as cursor:
        cursor.execute(session_statement())
