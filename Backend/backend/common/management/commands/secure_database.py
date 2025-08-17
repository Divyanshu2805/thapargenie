"""Lock the public schema away from Supabase's auto-generated REST API.

Supabase exposes `public` through PostgREST to the `anon` and `authenticated`
roles. This app never uses that API, so every table gets row level security with
no policies and those roles lose all privileges. Django connects as the table
owner, which bypasses RLS, so the app itself is unaffected.

Idempotent: run after every `migrate`. `--check` reports without changing anything.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from psycopg import sql

API_ROLES = ('anon', 'authenticated')


def public_tables(cursor):
    cursor.execute(
        """
        SELECT c.relname, c.relrowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
        ORDER BY c.relname
        """
    )
    return cursor.fetchall()


def existing_roles(cursor):
    cursor.execute('SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)', [list(API_ROLES)])
    return [row[0] for row in cursor.fetchall()]


def exposed_grants(cursor, roles):
    if not roles:
        return []
    cursor.execute(
        """
        SELECT grantee, table_name, privilege_type
        FROM information_schema.role_table_grants
        WHERE table_schema = 'public' AND grantee = ANY(%s)
        ORDER BY table_name
        """,
        [roles],
    )
    return cursor.fetchall()


class Command(BaseCommand):
    help = 'Enable RLS on all public tables and revoke Supabase API role access.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Exit non-zero if anything is exposed; make no changes.',
        )

    def handle(self, *args, check=False, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('secure_database only supports PostgreSQL.')

        with connection.cursor() as cursor:
            tables = public_tables(cursor)
            roles = existing_roles(cursor)
            open_tables = [name for name, rls in tables if not rls]
            grants = exposed_grants(cursor, roles)

            if check:
                if open_tables or grants:
                    raise CommandError(
                        f'Exposed: {len(open_tables)} table(s) without RLS, '
                        f'{len(grants)} API role grant(s).'
                    )
                self.stdout.write(self.style.SUCCESS(f'{len(tables)} tables locked down.'))
                return

            with transaction.atomic():
                for name in open_tables:
                    cursor.execute(
                        sql.SQL('ALTER TABLE public.{} ENABLE ROW LEVEL SECURITY').format(
                            sql.Identifier(name)
                        )
                    )
                for role in roles:
                    ident = sql.Identifier(role)
                    for statement in (
                        'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}',
                        'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {}',
                        'REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM {}',
                        'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {}',
                        'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {}',
                        'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM {}',
                    ):
                        cursor.execute(sql.SQL(statement).format(ident))

        self.stdout.write(
            self.style.SUCCESS(
                f'RLS enabled on {len(open_tables)} table(s); '
                f'{len(tables)} total. Revoked API access for: {", ".join(roles) or "none"}.'
            )
        )
