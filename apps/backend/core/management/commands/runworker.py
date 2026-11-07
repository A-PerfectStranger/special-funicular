"""Reserved process entrypoint; never pretends to process unimplemented outboxes."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "E0 worker diagnostic (no archive/notification handlers yet)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--check", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["check"]:
            self.stdout.write("worker_handlers=0 pickup_enabled=false")
            return
        raise CommandError("BLOCKED: E1/E4 outbox handlers are not implemented")
