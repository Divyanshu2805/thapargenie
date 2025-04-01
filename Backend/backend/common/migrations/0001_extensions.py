"""Postgres extensions every app relies on.

Supabase keeps extensions in the `extensions` schema (already on the search path);
a plain Postgres install has no such schema, so they go to the default schema there.
"""

from django.db import migrations

EXTENSIONS = ('vector', 'pg_trgm')


def create_extensions(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_namespace WHERE nspname = 'extensions'")
        in_schema = ' WITH SCHEMA extensions' if cursor.fetchone() else ''
        for name in EXTENSIONS:
            cursor.execute(f'CREATE EXTENSION IF NOT EXISTS {name}{in_schema}')


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    run_before = [('knowledge', '0001_initial')]

    operations = [migrations.RunPython(create_extensions, migrations.RunPython.noop)]
