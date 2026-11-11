"""Approved retry of an exhausted logical notice, without changing the physical fact."""

import json
import os
import uuid
from pathlib import Path
from typing import Any

import psycopg
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser


class Command(BaseCommand):
    help = "Reconcile an exhausted notice with isolated importer credentials and approval."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "operation", choices=["retry", "device-hashes"], nargs="?", default="retry"
        )
        parser.add_argument("--file", required=True)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            raw = Path(options["file"]).read_bytes()
            if len(raw) > 8192:
                raise ValueError()
            data = json.loads(raw)
            target = "account_id" if options["operation"] == "device-hashes" else "notification_id"
            if set(data) != {target, "id", "operator", "approval", "reason"}:
                raise ValueError()
            with psycopg.connect(os.environ["IMPORT_DATABASE_URL"], connect_timeout=3) as db:
                if db.execute("SELECT current_user").fetchone() != ("retiro_importer",):
                    raise ValueError()
                if (
                    settings.APP_ENV in {"staging", "production"}
                    and db.info.get_parameters().get("sslmode") != "verify-full"
                ):
                    raise ValueError()
                sql = (
                    "SELECT public.e4_notification_device_hashes(%s,%s,%s,%s,%s)"
                    if options["operation"] == "device-hashes"
                    else "SELECT public.e4_retry_notification(%s,%s,%s,%s,%s)"
                )
                row = db.execute(
                    sql,
                    (
                        uuid.UUID(data[target]),
                        uuid.UUID(data["id"]),
                        data["operator"],
                        data["approval"],
                        data["reason"],
                    ),
                ).fetchone()
                if not row:
                    raise ValueError()
            result = (
                row[0]
                if options["operation"] == "device-hashes"
                else {"event_id": str(row[0]), "protected": False}
            )
            self.stdout.write(json.dumps(result))
        except Exception:
            raise CommandError(
                "Notification reconciliation rejected; inspect private input"
            ) from None
