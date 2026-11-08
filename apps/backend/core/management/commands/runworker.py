"""Archive process entrypoint; notification handling is deferred to E4."""

import json
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run the isolated E1 archive worker. No notification handler."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--check", action="store_true")
        parser.add_argument("--archive", action="store_true")
        parser.add_argument("--once", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["check"] and not options["archive"]:
            self.stdout.write("worker_handlers=0 pickup_enabled=false")
            return
        if not options["archive"]:
            raise CommandError("BLOCKED: explicitly select --archive with isolated credentials")
        from archive_worker.storage import ArchiveUnavailable, WormArchive
        from archive_worker.worker import process_batch, status

        try:
            archive = WormArchive.configured()
            if options["check"]:
                self.stdout.write(json.dumps({"archive_handlers": 1, **status()}))
                return
            while True:
                result = process_batch(archive)
                if result["claimed"] or options["once"]:
                    self.stdout.write(json.dumps(result))
                if options["once"]:
                    if result["failed"]:
                        raise CommandError("Archive batch failed; retry remains durable")
                    return
                if not result["claimed"]:
                    time.sleep(0.2)
        except (ArchiveUnavailable, RuntimeError) as exc:
            raise CommandError("BLOCKED: archive configuration or integrity unavailable") from exc
