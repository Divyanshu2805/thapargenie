from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase

from common.management.commands.secure_database import exposed_grants, public_tables


class SecureDatabaseTests(TestCase):
    """Simulates Supabase's API roles and checks they end up with no access."""

    def setUp(self):
        with connection.cursor() as cursor:
            for role in ('anon', 'authenticated'):
                cursor.execute(
                    f"DO $$ BEGIN CREATE ROLE {role} NOLOGIN; "
                    f"EXCEPTION WHEN duplicate_object THEN NULL; END $$"
                )
            cursor.execute('ALTER TABLE userauths_user DISABLE ROW LEVEL SECURITY')
            cursor.execute('GRANT SELECT, INSERT ON userauths_user TO anon')
            cursor.execute('GRANT SELECT ON api_auditevent TO authenticated')

    def test_check_fails_while_exposed(self):
        with self.assertRaisesRegex(CommandError, 'Exposed'):
            call_command('secure_database', '--check', stdout=_Null())

    def test_lockdown_enables_rls_and_revokes_grants(self):
        call_command('secure_database', stdout=_Null())
        with connection.cursor() as cursor:
            self.assertTrue(all(rls for _, rls in public_tables(cursor)))
            self.assertEqual(exposed_grants(cursor, ['anon', 'authenticated']), [])
        call_command('secure_database', '--check', stdout=_Null())

    def test_is_idempotent(self):
        call_command('secure_database', stdout=_Null())
        call_command('secure_database', stdout=_Null())
        call_command('secure_database', '--check', stdout=_Null())


class _Null:
    def write(self, *_args, **_kwargs):
        pass

    def flush(self):
        pass
