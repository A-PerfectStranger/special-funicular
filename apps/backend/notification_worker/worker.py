"""Leased notification outbox; no SQL transaction spans provider network calls."""

import os
import uuid
from typing import Any

import psycopg

from notification_worker.provider import ExpoPush


def connection() -> psycopg.Connection[Any]:
    dsn = os.environ.get("NOTIFICATION_DATABASE_URL", "")
    if not dsn and os.environ.get("PGUSER") != "retiro_notifier":
        raise RuntimeError("BLOCKED: isolated notification SQL identity required")
    db = psycopg.connect(dsn, autocommit=True, connect_timeout=3)
    if db.execute("SELECT current_user").fetchone() != ("retiro_notifier",):
        db.close()
        raise RuntimeError("BLOCKED: wrong notification SQL identity")
    if (
        os.environ.get("APP_ENV") in {"staging", "production"}
        and db.info.get_parameters().get("sslmode") != "verify-full"
    ):
        db.close()
        raise RuntimeError("BLOCKED: verified notification SQL TLS required")
    return db


def process_batch(provider: ExpoPush, batch: int = 1) -> dict[str, int]:
    # A serial batch stays below its 60 s lease, even when every RPC times out.
    if not 1 <= batch <= 3:
        raise ValueError("Notification batches are bounded to three")
    lease = uuid.uuid4()
    with connection() as db:
        jobs = db.execute(
            "SELECT * FROM public.e4_claim_notifications(%s,%s)", (batch, lease)
        ).fetchall()
    counts = {"claimed": len(jobs), "accepted": 0, "failed": 0, "receipts": 0}
    for attempt, notification, token in jobs:
        result = provider.send(token, notification)
        with connection() as db:
            committed = db.execute(
                "SELECT public.e4_notification_result(%s,%s,%s,%s,%s)",
                (attempt, lease, result.ticket, result.failure, result.retry_after_seconds),
            ).fetchone()
        counts["accepted" if result.ticket and committed == (True,) else "failed"] += 1
    with connection() as db:
        receipts = db.execute(
            "SELECT * FROM public.e4_claim_receipts(%s,%s)", (batch, lease)
        ).fetchall()
    for attempt, ticket in receipts:
        result_code = provider.receipt(ticket)
        with connection() as db:
            committed = db.execute(
                "SELECT public.e4_notification_receipt(%s,%s,%s)", (attempt, lease, result_code)
            ).fetchone()
        if committed == (True,) and result_code == "OK":
            counts["receipts"] += 1
    return counts


def status() -> dict[str, Any]:
    with connection() as db:
        row = db.execute("SELECT public.e4_notification_status()").fetchone()
    if not row:
        raise RuntimeError("Notification status unavailable")
    return dict(row[0])
