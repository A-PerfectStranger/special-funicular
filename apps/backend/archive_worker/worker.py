"""Leased outbox; no SQL transaction spans WORM/KMS network calls."""

import os
import uuid
from typing import Any

import psycopg

from archive_worker.storage import IntegrityFailure, WormArchive


def connection() -> psycopg.Connection[Any]:
    dsn = os.environ.get("ARCHIVE_DATABASE_URL", "")
    if not dsn and os.environ.get("PGUSER") != "retiro_archiver":
        raise RuntimeError("BLOCKED: isolated archive SQL identity required")
    db = psycopg.connect(dsn, autocommit=True, connect_timeout=3)
    if db.execute("SELECT current_user").fetchone() != ("retiro_archiver",):
        db.close()
        raise RuntimeError("BLOCKED: wrong archive SQL identity")
    return db


def process_batch(archive: WormArchive, batch: int = 1) -> dict[str, int]:
    lease = uuid.uuid4()
    with connection() as db:
        jobs = db.execute("SELECT * FROM public.e1_claim_archive(%s,%s)", (batch, lease)).fetchall()
    counts = {"claimed": len(jobs), "completed": 0, "failed": 0}
    for eid, sequence, canonical, digest, _ in jobs:
        try:
            protected, manifest = archive.archive(bytes(canonical), digest, sequence)
            with connection() as db:
                result = db.execute(
                    "SELECT public.e1_archive_completed(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        eid,
                        lease,
                        archive.config.bucket,
                        protected.key,
                        protected.version,
                        digest,
                        protected.retained_until,
                        manifest.key,
                        manifest.version,
                    ),
                ).fetchone()
            if result != (True,):
                raise IntegrityFailure()
            counts["completed"] += 1
        except Exception as exc:
            # Retry state is durable, error code is allowlisted, provider text is discarded.
            code = (
                "INTEGRITY_FAILURE" if isinstance(exc, IntegrityFailure) else "ARCHIVE_UNAVAILABLE"
            )
            with connection() as db:
                db.execute("SELECT public.e1_archive_failed(%s,%s,%s)", (eid, lease, code))
            counts["failed"] += 1
    return counts


def status() -> dict[str, Any]:
    with connection() as db:
        row = db.execute("SELECT public.e1_archive_status()").fetchone()
    if not row:
        raise RuntimeError("Archive status unavailable")
    return dict(row[0])
