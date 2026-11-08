"""Serialize migrations in PostgreSQL even if an external CI waiter times out."""

from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection

LOCK_ID = 728491650217


class Command(BaseCommand):
    help = "Run forward migrations under a database session advisory lock."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--noinput", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            if cursor.fetchone() != ("retiro_migrator",):
                raise CommandError("BLOCKED: separate migration SQL identity required")
            cursor.execute("""SELECT expected.name FROM (VALUES
                ('retiro_runtime'), ('retiro_evidence_writer'), ('retiro_school_read'),
                ('retiro_system_read'), ('retiro_importer'), ('retiro_archiver'),
                ('retiro_notifier')) AS expected(name)
                LEFT JOIN pg_roles role ON role.rolname=expected.name
                WHERE role.oid IS NULL OR role.rolsuper OR role.rolbypassrls
                  OR role.rolcreatedb OR role.rolcreaterole
                  OR (expected.name='retiro_evidence_writer' AND role.rolcanlogin)
            """)
            if cursor.fetchall():
                raise CommandError("BLOCKED: commission safe E1 SQL identities before migration")
            cursor.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            try:
                call_command("migrate", interactive=False, stdout=self.stdout, stderr=self.stderr)
            finally:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
