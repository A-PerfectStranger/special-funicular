"""Read-only external acceptance command. Run with an independent AWS identity."""

import json
import os
from pathlib import Path
from typing import Any

import boto3
from archive_worker.verifier import ExternalVerifier
from archive_worker.verify_cli import load_snapshot
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Verify external evidence without connecting to PostgreSQL."
    requires_system_checks: list[str] = []

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--minimum-sequence", type=int, required=True)
        parser.add_argument("--database-snapshot", type=Path)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            minimum = options["minimum_sequence"]
            if minimum < 1:
                raise ValueError()
            verifier = ExternalVerifier(
                boto3.client("s3"),
                boto3.client("kms"),
                os.environ["ARCHIVE_BUCKET"],
                os.environ["MANIFEST_KMS_KEY_ARN"],
                os.environ["ARCHIVE_KMS_KEY_ARN"],
            )
            snapshot = load_snapshot(options["database_snapshot"])
            self.stdout.write(json.dumps(verifier.verify(minimum, snapshot)))
        except Exception:
            raise CommandError("INTEGRITY_FAILURE: archive verification did not pass") from None
