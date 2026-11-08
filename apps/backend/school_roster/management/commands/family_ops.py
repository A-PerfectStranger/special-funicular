"""Private E2 operations. Never expose this credential to API/web/worker processes."""

import hashlib
import json
import os
import secrets
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from jsonschema import Draft202012Validator, FormatChecker

UUID = {"type": "string", "format": "uuid"}
TEXT = {"type": "string", "minLength": 1, "maxLength": 160}
WINDOWS: dict[str, Any] = {
    "type": "array",
    "minItems": 1,
    "maxItems": 32,
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["weekday", "from", "until", "start_date", "end_date"],
        "properties": {
            "weekday": {"type": "integer", "minimum": 1, "maximum": 7},
            "from": {"type": "string", "pattern": r"^([01]\d|2[0-3]):[0-5]\d$"},
            "until": {"type": "string", "pattern": r"^([01]\d|2[0-3]):[0-5]\d$"},
            "start_date": {"type": "string", "format": "date"},
            "end_date": {"type": "string", "format": "date"},
        },
    },
}
BATCH: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "id", "school_id", "parents", "students", "links"],
    "properties": {
        "schema_version": {"const": 1},
        "id": UUID,
        "school_id": UUID,
        "parents": {
            "type": "array",
            "minItems": 1,
            "maxItems": 2000,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "contact"],
                "properties": {
                    "id": UUID,
                    "contact": {"type": "string", "format": "email", "maxLength": 254},
                },
            },
        },
        "students": {
            "type": "array",
            "minItems": 1,
            "maxItems": 1000,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "site_id", "name", "windows", "blocked"],
                "properties": {
                    "id": UUID,
                    "site_id": UUID,
                    "name": TEXT,
                    "windows": WINDOWS,
                    "blocked": {"type": "boolean"},
                },
            },
        },
        "links": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4000,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["student_id", "parent_id", "principal"],
                "properties": {
                    "student_id": UUID,
                    "parent_id": UUID,
                    "principal": {"type": "boolean"},
                },
            },
        },
    },
}


def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def read_batch(path: str) -> tuple[str, dict[str, Any]]:
    raw = Path(path).read_bytes()
    if not 1 <= len(raw) <= 4000000:
        raise ValueError()
    text = raw.decode("utf-8")
    data = json.loads(text, object_pairs_hook=unique_keys)
    if not Draft202012Validator(BATCH, format_checker=FormatChecker()).is_valid(data):
        raise ValueError()
    return text, data


class Command(BaseCommand):
    help = "Private approved E2 operations; IMPORT_DATABASE_URL is separate from runtime."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "operation", choices=["stage", "approve", "promote", "invite", "technical"]
        )
        parser.add_argument(
            "--id", required=True, help="Batch, parent or technical correlation UUID"
        )
        parser.add_argument("--operator", required=True)
        parser.add_argument("--approval", default="")
        parser.add_argument("--sha256", default="")
        parser.add_argument("--file", help="Private UTF-8 input JSON")
        parser.add_argument("--output", help="New mode-0600 invitation file; never printed")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            self.execute_operation(options)
        except Exception:
            # Do not echo SQL/provider exceptions, payload, contact, token or URL.
            raise CommandError(
                "E2 operation rejected; check private input, approval and database configuration"
            ) from None

    def execute_operation(self, options: dict[str, Any]) -> None:
        dsn = os.environ.get("IMPORT_DATABASE_URL", "")
        url = urlsplit(dsn)
        if url.scheme not in {"postgres", "postgresql"} or url.username != "retiro_importer":
            raise ValueError()
        if settings.APP_ENV in {"staging", "production"} and "sslmode=verify-full" not in url.query:
            raise ValueError()
        operation, ident = options["operation"], uuid.UUID(options["id"])
        operator, approval = options["operator"], options["approval"]
        with psycopg.connect(dsn) as db:
            if operation == "stage":
                raw, body = read_batch(options["file"])
                if uuid.UUID(body["id"]) != ident:
                    raise ValueError()
                digest = hashlib.sha256(raw.encode()).hexdigest()
                if digest != options["sha256"]:
                    raise ValueError()
                db.execute(
                    "SELECT public.e2_import('STAGE',%s,%s,%s,%s,'')",
                    (ident, raw, digest, operator),
                )
            elif operation in {"approve", "promote"}:
                db.execute(
                    "SELECT public.e2_import(%s,%s,'',%s,%s,%s)",
                    (operation.upper(), ident, options["sha256"], operator, approval),
                )
            elif operation == "invite":
                if not options["output"]:
                    raise ValueError()
                # Reserve a private file before minting; a failed commit leaves no invitation.
                path = Path(options["output"])
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                try:
                    token = secrets.token_urlsafe(32)
                    db.execute(
                        "SELECT public.e2_invite(%s,%s,%s,%s,%s)",
                        (
                            ident,
                            hashlib.sha256(token.encode()).hexdigest(),
                            operator,
                            approval,
                            uuid.uuid4(),
                        ),
                    )
                    with os.fdopen(descriptor, "w") as output:
                        output.write(token)
                        output.flush()
                        os.fsync(output.fileno())
                    db.commit()
                except Exception:
                    path.unlink(missing_ok=True)
                    raise
            else:
                payload = json.loads(Path(options["file"]).read_text())
                if set(payload) != {"operation", "school_id", "target", "data", "reason"}:
                    raise ValueError()
                db.execute(
                    "SELECT public.e2_technical(%s,%s,%s,%s,%s::jsonb,%s,%s,%s)",
                    (
                        payload["operation"],
                        ident,
                        payload["school_id"],
                        payload["target"],
                        json.dumps(payload["data"]),
                        operator,
                        approval,
                        payload["reason"],
                    ),
                )
        self.stdout.write("E2 command committed. Evidence protection must be verified separately.")
