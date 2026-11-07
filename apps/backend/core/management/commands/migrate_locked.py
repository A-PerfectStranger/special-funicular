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
            cursor.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            try:
                call_command("migrate", interactive=False, stdout=self.stdout, stderr=self.stderr)
            finally:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
