"""Private RF18 command. An interpretation never grants a handover permission."""

import json
import os
import uuid
from pathlib import Path
from typing import Any

import psycopg
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser


class Command(BaseCommand):
    help = "Append an approved historical correction using the isolated importer identity."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--file", required=True, help="Private JSON; see E4 runbook")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            raw = Path(options["file"]).read_bytes()
            if len(raw) > 8192:
                raise ValueError()
            data = json.loads(raw)
            if set(data) != {"operation_id", "id", "operator", "approval", "reason", "outcome"}:
                raise ValueError()
            with psycopg.connect(os.environ["IMPORT_DATABASE_URL"], connect_timeout=3) as db:
                if db.execute("SELECT current_user").fetchone() != ("retiro_importer",):
                    raise ValueError()
                if (
                    settings.APP_ENV in {"staging", "production"}
                    and db.info.get_parameters().get("sslmode") != "verify-full"
                ):
                    raise ValueError()
                row = db.execute(
                    "SELECT public.e4_correct(%s,%s,%s,%s,%s,%s)",
                    (
                        uuid.UUID(data["operation_id"]),
                        uuid.UUID(data["id"]),
                        data["operator"],
                        data["approval"],
                        data["reason"],
                        data["outcome"],
                    ),
                ).fetchone()
                if not row:
                    raise ValueError()
            self.stdout.write(json.dumps(row[0]))
        except Exception:
            raise CommandError(
                "Correction rejected; inspect private input and configuration"
            ) from None
