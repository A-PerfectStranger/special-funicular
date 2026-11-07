from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection


class Command(BaseCommand):
    help = "Comprueba la conectividad del futuro worker. No procesa evidencia ni avisos en E0."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--check", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["check"]:
            raise CommandError("Worker bloqueado: handlers de outbox pendientes en E1/E4")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        self.stdout.write("Conexion PostgreSQL verificada; procesamiento no implementado (E0).")
