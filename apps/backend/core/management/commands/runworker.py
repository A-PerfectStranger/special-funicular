"""Explicit isolated worker entrypoints; no universal service credential."""

import json
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run one isolated worker: --archive or --notifications."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--check", action="store_true")
        parser.add_argument("--archive", action="store_true")
        parser.add_argument("--notifications", action="store_true")
        parser.add_argument("--once", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["notifications"]:
            if options["archive"]:
                raise CommandError("BLOCKED: select one isolated worker identity")
            from notification_worker.provider import ExpoPush
            from notification_worker.worker import process_batch as notify_batch
            from notification_worker.worker import status as notify_status

            try:
                provider = ExpoPush.configured()
                try:
                    if options["check"]:
                        self.stdout.write(
                            json.dumps({"notification_handlers": 1, **notify_status()})
                        )
                        return
                    while True:
                        result = notify_batch(provider)
                        if result["claimed"] or result["receipts"] or options["once"]:
                            self.stdout.write(json.dumps(result))
                        if options["once"]:
                            if result["failed"]:
                                raise CommandError("Notification failed; retry remains durable")
                            return
                        if not result["claimed"]:
                            time.sleep(0.5)
                finally:
                    provider.client.close()
            except Exception:
                raise CommandError(
                    "BLOCKED: isolated notification configuration or provider unavailable"
                ) from None
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
