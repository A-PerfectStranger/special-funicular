"""AT05: transactional rollback and crash/reclaim of the real SQL outbox.

Receipt fields are simulated here; only the WORM adapter/live suite proves AWS.
"""

import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from tests.integration.e1_support import connect, digest, login, roster

pytestmark = pytest.mark.integration


def test_session_event_head_and_outbox_rollback_together() -> None:
    data = roster()
    login_id, access, refresh = uuid.uuid4(), secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    with connect() as runtime:
        runtime.execute(
            "INSERT INTO identity_loginrequest(id,state_hash,binding_hash,nonce,challenge,channel,"
            "purpose,expires_at,consumed_at) VALUES(%s,%s,%s,'n','c','web','login',%s,%s)",
            (
                login_id,
                secrets.token_hex(32),
                secrets.token_hex(32),
                now + timedelta(minutes=5),
                now,
            ),
        )
        with pytest.raises(RuntimeError), runtime.transaction():
            assert runtime.execute(
                "SELECT e1_open_session(%s,'https://idp.example',%s,%s,%s,%s)",
                (
                    login_id,
                    str(data["accounts"]["ADMIN_ESCUELA"]),
                    digest(access),
                    digest(refresh),
                    now,
                ),
            ).fetchone()
            raise RuntimeError("Injected response failure before commit")
        assert runtime.execute("SELECT e1_authenticate(%s,true)", (digest(access),)).fetchone() == (
            None,
        )
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as owner:
        owner.execute("SET ROLE retiro_evidence_writer")
        assert owner.execute(
            "SELECT count(*) FROM evidence_event WHERE correlation_id=%s", (login_id,)
        ).fetchone() == (0,)
        assert owner.execute(
            "SELECT count(*) FROM identity_session WHERE login_id=%s", (login_id,)
        ).fetchone() == (0,)
        # Every committed event has its outbox row and the transactional head has no gaps.
        assert owner.execute(
            "SELECT count(*) FROM evidence_event e LEFT JOIN evidence_archivejob j "
            "ON j.event_id=e.id WHERE j.event_id IS NULL"
        ).fetchone() == (0,)
        assert owner.execute(
            "SELECT (SELECT sequence FROM evidence_head WHERE id=1)=count(*) FROM evidence_event"
        ).fetchone() == (True,)


def test_crash_reclaims_identical_bytes_and_stale_lease_cannot_complete() -> None:
    login(roster()["accounts"]["PADRE"])
    old, new = uuid.uuid4(), uuid.uuid4()
    with connect("archiver") as archive:
        first = archive.execute("SELECT * FROM e1_claim_archive(1,%s)", (old,)).fetchone()
    assert first is not None
    eid, _, _, hash_value, _ = first
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as owner:
        owner.execute("SET ROLE retiro_evidence_writer")
        owner.execute(
            "UPDATE evidence_archivejob SET lease_until=clock_timestamp()-interval '1 second' "
            "WHERE event_id=%s",
            (eid,),
        )
    with connect("archiver") as archive:
        assert archive.execute("SELECT * FROM e1_claim_archive(1,%s)", (new,)).fetchone() == first
        params = (
            eid,
            old,
            "SIMULATED",
            "SIMULATED",
            "SIMULATED",
            hash_value,
            datetime.now(UTC) + timedelta(days=7),
            "SIMULATED",
            "SIMULATED",
        )
        assert archive.execute(
            "SELECT e1_archive_completed(%s,%s,%s,%s,%s,%s,%s,%s,%s)", params
        ).fetchone() == (False,)
        archive.execute("SELECT e1_archive_failed(%s,%s,'ARCHIVE_UNAVAILABLE')", (eid, new))
        assert archive.execute("SELECT e1_archive_status()").fetchone()[0]["failed"] >= 1


def test_verified_receipt_completion_is_unique() -> None:
    _, _, meta = login(roster()["accounts"]["ADMIN_ESCUELA"], "web")
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as owner:
        owner.execute("SET ROLE retiro_evidence_writer")
        owner.execute(
            "UPDATE evidence_archivejob SET available_at='2000-01-01T00:00:00Z' WHERE event_id=%s",
            (meta["event_id"],),
        )
    lease = uuid.uuid4()
    with connect("archiver") as archive:
        job = archive.execute("SELECT * FROM e1_claim_archive(1,%s)", (lease,)).fetchone()
        assert job is not None and job[0] == uuid.UUID(meta["event_id"])
        params = (
            job[0],
            lease,
            "SIMULATED",
            "SIMULATED",
            "SIMULATED",
            job[3],
            datetime.now(UTC) + timedelta(days=7),
            "SIMULATED",
            "SIMULATED",
        )
        statement = "SELECT e1_archive_completed(%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        assert archive.execute(statement, params).fetchone() == (True,)
        assert archive.execute(statement, params).fetchone() == (False,)
