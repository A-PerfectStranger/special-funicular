"""AT05 SQL gate with simulated receipts. Actual AWS protection remains a separate check."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from tests.integration.e1_support import connect, digest, login, roster

pytestmark = pytest.mark.integration


def owner_sql(statement: str, params: tuple[Any, ...]) -> None:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as owner:
        owner.execute("SET ROLE retiro_evidence_writer")
        owner.execute(statement, params)


def fake_receipt(event_id: str) -> None:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as owner:
        owner.execute("SET ROLE retiro_evidence_writer")
        owner.execute(
            "INSERT INTO evidence_receipt(event_id,bucket,key,version_id,digest,retained_until,"
            "verified_at,manifest_key,manifest_version) "
            "SELECT id,'SIMULATED','SIMULATED','SIMULATED',digest,%s,clock_timestamp(),"
            "'SIMULATED','SIMULATED' FROM evidence_event WHERE id=%s",
            (datetime.now(UTC) + timedelta(days=7), event_id),
        )
        # Simulate the whole archive commit, not an inconsistent receipt without its projection.
        owner.execute(
            "UPDATE evidence_archivejob SET completed_at=clock_timestamp(),lease_id=NULL,"
            "lease_until=NULL WHERE event_id=%s",
            (event_id,),
        )


def test_three_logins_protected_gate_and_minimal_system_projection() -> None:
    data = roster()
    school_sessions = [login(data["accounts"]["ADMIN_ESCUELA"], "web") for _ in range(3)]
    with connect() as runtime:
        for access, _, meta in school_sessions:
            assert runtime.execute(
                "SELECT e1_authenticate(%s,true)", (digest(access),)
            ).fetchone() == (None,)
            fake_receipt(meta["event_id"])
            assert runtime.execute(
                "SELECT e1_enable_school_session(%s)", (digest(access),)
            ).fetchone() == (True,)
            # Repeated completion/refresh cannot create another login event.
            assert runtime.execute(
                "SELECT e1_enable_school_session(%s)", (digest(access),)
            ).fetchone() == (True,)
            assert (
                runtime.execute("SELECT e1_authenticate(%s,true)", (digest(access),)).fetchone()[0][
                    "role"
                ]
                == "ADMIN_ESCUELA"
            )
    system, _, _ = login(data["accounts"]["ADMIN_SISTEMA"], "web")
    with connect("system_read") as reader, reader.transaction():
        reader.execute("SELECT set_config('app.session_hash',%s,true)", (digest(system),))
        reader.execute("SELECT e1_audit_access_read(%s)", (uuid.uuid4(),))
        result = reader.execute("SELECT * FROM e1_access_records(25,NULL,%s)", (data["school"],))
        assert [col.name for col in result.description] == [
            "sequence",
            "event_id",
            "actor_id",
            "school_id",
            "occurred_at",
            "result",
        ]
        rows = result.fetchall()
        assert len(rows) == 3 and {row[-1] for row in rows} == {"OPENED"}
        assert {row[2] for row in rows} == {data["accounts"]["ADMIN_ESCUELA"]}
    with connect("system_read") as reader:
        assert reader.execute("SELECT * FROM e1_access_records(25,NULL,NULL)").fetchall() == []


def test_late_receipt_never_reopens_school_session() -> None:
    data = roster()
    access, _, meta = login(data["accounts"]["ADMIN_ESCUELA"], "web")
    owner_sql(
        "UPDATE identity_session SET protection_deadline=%s WHERE id=%s",
        (
            datetime.now(UTC) - timedelta(seconds=1),
            meta["session_id"],
        ),
    )
    with connect() as runtime:
        assert runtime.execute(
            "SELECT e1_enable_school_session(%s)", (digest(access),)
        ).fetchone() == (False,)
        fake_receipt(meta["event_id"])
        assert runtime.execute(
            "SELECT e1_enable_school_session(%s)", (digest(access),)
        ).fetchone() == (False,)
        assert runtime.execute("SELECT e1_authenticate(%s,true)", (digest(access),)).fetchone() == (
            None,
        )


@pytest.mark.parametrize("role,idle", [("GUARDIA", 5), ("PADRE", 15)])
def test_idle_and_access_expiration_are_enforced_in_database(role: str, idle: int) -> None:
    data = roster()
    access, refresh, meta = login(data["accounts"][role])
    owner_sql(
        "UPDATE identity_session SET last_seen_at=%s WHERE id=%s",
        (
            datetime.now(UTC) - timedelta(minutes=idle, seconds=1),
            meta["session_id"],
        ),
    )
    with connect() as runtime:
        assert runtime.execute("SELECT e1_authenticate(%s,true)", (digest(access),)).fetchone() == (
            None,
        )
        assert runtime.execute(
            "SELECT e1_refresh(%s,%s,%s)",
            (digest(refresh), digest(str(uuid.uuid4())), digest(str(uuid.uuid4()))),
        ).fetchone() == (False,)
    access, _, meta = login(data["accounts"][role])
    owner_sql(
        "UPDATE identity_session SET access_expires_at=%s WHERE id=%s",
        (
            datetime.now(UTC) - timedelta(seconds=1),
            meta["session_id"],
        ),
    )
    with connect() as runtime:
        assert runtime.execute("SELECT e1_authenticate(%s,true)", (digest(access),)).fetchone() == (
            None,
        )


def test_concurrent_refresh_only_one_consumes_old_credential() -> None:
    data = roster()
    _, refresh, _ = login(data["accounts"]["PADRE"])

    def attempt(_: int) -> bool:
        with connect() as runtime:
            return runtime.execute(
                "SELECT e1_refresh(%s,%s,%s)",
                (
                    digest(refresh),
                    digest(str(uuid.uuid4())),
                    digest(str(uuid.uuid4())),
                ),
            ).fetchone() == (True,)

    with ThreadPoolExecutor(max_workers=10) as pool:
        assert sum(pool.map(attempt, range(10))) == 1
