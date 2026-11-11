"""AT07/AB12/16/23: actual PostgreSQL roles; synthetic provider receipts only."""

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import psycopg
import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import include, path
from notification_worker.provider import ExpoPush
from notification_worker.worker import process_batch

from tests.integration.e1_support import connect, digest, login
from tests.integration.test_e1_school_access import fake_receipt
from tests.integration.test_e3_pickup import call, owner, resolve
from tests.integration.test_e3_pickup import pickup as e3_pickup
from tests.integration.test_e4_operations import report

pytestmark = pytest.mark.integration
pickup = e3_pickup


def test_device_enrolment_is_parent_only_bounded_and_exports_hashes_not_tokens(
    pickup: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    import io

    p = pickup
    routes = type("Routes", (), {"urlpatterns": [path("v1/", include("notification_worker.urls"))]})
    token = f"ExpoPushToken[{uuid.uuid4().hex}]"
    client = Client()
    with override_settings(ROOT_URLCONF=routes):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {p['parent_access']}"}
        assert client.post(
            "/v1/me/notification-device",
            {"token": token, "enabled": True},
            content_type="application/json",
            **headers,
        ).json() == {"registered": True}
        assert (
            client.post(
                "/v1/me/notification-device",
                {"token": token, "enabled": True, "recipient": str(p["other_parent"])},
                content_type="application/json",
                **headers,
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/v1/me/notification-device",
                {"token": token, "enabled": True},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {p['guard_access']}",
            ).status_code
            == 403
        )
        for _ in range(9):
            assert (
                client.post(
                    "/v1/me/notification-device",
                    {"token": token, "enabled": True},
                    content_type="application/json",
                    **headers,
                ).status_code
                == 200
            )
        assert (
            client.post(
                "/v1/me/notification-device",
                {"token": token, "enabled": True},
                content_type="application/json",
                **headers,
            ).status_code
            == 429
        )
    monkeypatch.setenv(
        "IMPORT_DATABASE_URL",
        psycopg.conninfo.make_conninfo(
            user="retiro_importer",
            password="synthetic-importer-only",
            host="127.0.0.1",
            port=os.environ.get("PGPORT", "5432"),
            dbname=os.environ.get("PGDATABASE", "retiro"),
        ),
    )
    data = {
        "account_id": str(p["accounts"]["PADRE"]),
        "id": str(uuid.uuid4()),
        "operator": "synthetic",
        "approval": "synthetic",
        "reason": "team device",
    }
    file = tmp_path / "device.json"
    file.write_text(json.dumps(data))
    output = io.StringIO()
    call_command("notification_ops", "device-hashes", file=str(file), stdout=output)
    assert json.loads(output.getvalue())["hashes"] == [digest(token)]
    assert token not in output.getvalue()
    with connect() as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute(
            "SELECT e4_notification_device_hashes(%s,%s,'a','b','c')",
            (p["accounts"]["PADRE"], uuid.uuid4()),
        )


def test_worker_commits_outbox_before_network_and_uses_real_notifier_identity(
    pickup: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = pickup
    register(p["parent_access"])
    _, eid, did = notice(p)
    before = bytes(owner("SELECT canonical FROM evidence_event WHERE id=%s", (eid,))[0][0])
    owner(
        "UPDATE notification_worker_delivery SET available_at='2000-01-01T00:00:00Z' WHERE id=%s",
        (did,),
    )
    monkeypatch.setenv(
        "NOTIFICATION_DATABASE_URL",
        psycopg.conninfo.make_conninfo(
            user="retiro_notifier",
            password="synthetic-notifier-only",
            host="127.0.0.1",
            port=os.environ.get("PGPORT", "5432"),
            dbname=os.environ.get("PGDATABASE", "retiro"),
        ),
    )
    sent = []

    def network(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        with connect("notifier") as db:
            assert db.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE usename=current_user "
                "AND state='idle in transaction'"
            ).fetchone() == (0,)
        return httpx.Response(
            200, json={"data": {"status": "ok", "id": f"SIMULATED-{uuid.uuid4()}"}}
        )

    with httpx.Client(
        base_url="https://exp.host/--/api/v2/push/", transport=httpx.MockTransport(network)
    ) as client:
        result = process_batch(ExpoPush(client), batch=3)
    assert result["accepted"] >= 1
    assert any(item["data"] == {"notification_id": str(did)} for item in sent)
    assert (
        owner("SELECT state FROM notification_worker_delivery WHERE id=%s", (did,))[0][0]
        == "PROVIDER_ACCEPTED"
    )
    assert bytes(owner("SELECT canonical FROM evidence_event WHERE id=%s", (eid,))[0][0]) == before


@pytest.fixture(autouse=True)
def runtime_database(django_db_blocker: Any) -> Any:
    with django_db_blocker.unblock():
        yield


def register(access: str) -> str:
    token = f"ExpoPushToken[{uuid.uuid4().hex}]"
    assert call(access, "SELECT e4_endpoint(%s,true)", (token,)) == {"registered": True}
    return token


def claim() -> tuple[uuid.UUID, list[Any]]:
    lease = uuid.uuid4()
    with connect("notifier") as db:
        return lease, db.execute(
            "SELECT * FROM e4_claim_notifications(100,%s)", (lease,)
        ).fetchall()


def notice(p: dict[str, Any], protected: bool = True) -> tuple[str, str, uuid.UUID]:
    oid, eid = report(p)
    did = owner(
        "SELECT id FROM notification_worker_delivery WHERE event_id=%s AND recipient_id=%s",
        (eid, p["accounts"]["PADRE"]),
    )[0][0]
    if protected:
        fake_receipt(eid)
    return oid, eid, did


def complete(aid: uuid.UUID, lease: uuid.UUID, ticket: str | None, failure: str = "") -> bool:
    with connect("notifier") as db:
        return bool(
            db.execute(
                "SELECT e4_notification_result(%s,%s,%s,%s)", (aid, lease, ticket, failure)
            ).fetchone()[0]
        )


def due(did: uuid.UUID) -> None:
    owner(
        "UPDATE notification_worker_delivery SET "
        "available_at=clock_timestamp()-interval '1 second' WHERE id=%s",
        (did,),
    )


def test_only_delivered_report_creates_notice_and_protection_gates_send(
    pickup: dict[str, Any],
) -> None:
    p = pickup
    register(p["parent_access"])
    resolve(p["guard_access"], p["raw"])
    assert (
        owner(
            "SELECT d.id FROM notification_worker_delivery d JOIN pickup_operation o ON "
            "o.id=d.operation_id JOIN pickup_episode ep ON ep.id=o.episode_id WHERE "
            "ep.student_id=%s",
            (p["student"],),
        )
        == []
    )
    oid, eid, did = notice(p, protected=False)
    assert len(owner("SELECT id FROM notification_worker_delivery WHERE event_id=%s", (eid,))) == 2
    assert not any(row[1] == did for row in claim()[1])
    fake_receipt(eid)
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: claim(), range(10)))
    matching = [(lease, job) for lease, jobs in results for job in jobs if job[1] == did]
    assert len(matching) == 1
    lease, job = matching[0]
    assert complete(job[0], uuid.uuid4(), "SIMULATED-ticket") is False
    assert complete(job[0], lease, f"SIMULATED-{uuid.uuid4()}") is True
    assert not any(row[1] == did for row in claim()[1])
    assert complete(job[0], lease, f"SIMULATED-{uuid.uuid4()}") is False
    assert (
        owner(
            "SELECT count(*) FROM notification_worker_delivery WHERE event_id=%s AND "
            "recipient_id=%s",
            (eid, p["accounts"]["PADRE"]),
        )[0][0]
        == 1
    )
    assert (
        owner(
            "SELECT count(*) FROM evidence_event WHERE kind='ENTREGA_FISICA_REPORTADA' "
            "AND correlation_id=%s",
            (oid,),
        )[0][0]
        == 1
    )


def test_no_handover_report_never_notifies(pickup: dict[str, Any]) -> None:
    p = pickup
    oid, eid = report(p, delivered=False)
    fake_receipt(eid)
    assert owner("SELECT id FROM notification_worker_delivery WHERE operation_id=%s", (oid,)) == []


def test_failures_retry_with_contract_schedule_then_escalate(pickup: dict[str, Any]) -> None:
    p = pickup
    register(p["parent_access"])
    _, eid, did = notice(p)
    for number, delay in enumerate([30, 120, 300, 900, 900], start=1):
        due(did)
        lease, jobs = claim()
        job = next(row for row in jobs if row[1] == did)
        assert complete(job[0], lease, None, "PROVIDER_UNAVAILABLE")
        state, attempts, seconds, escalated = owner(
            "SELECT state,attempts,extract(epoch FROM "
            "available_at-clock_timestamp()),escalated_at FROM "
            "notification_worker_delivery WHERE id=%s",
            (did,),
        )[0]
        assert attempts == number and delay - 2 < seconds <= delay
        assert state == ("PENDING_REVIEW" if number == 5 else "PENDING")
        assert (escalated is not None) == (number == 5)
    due(did)
    assert not any(row[1] == did for row in claim()[1])
    assert (
        owner("SELECT count(*) FROM notification_worker_attempt WHERE delivery_id=%s", (did,))[0][0]
        == 5
    )
    assert (
        owner(
            "SELECT count(*) FROM notification_worker_delivery WHERE event_id=%s AND "
            "recipient_id=%s",
            (eid, p["accounts"]["PADRE"]),
        )[0][0]
        == 1
    )
    correlation = uuid.uuid4()
    with connect("importer") as db:
        params = (
            did,
            correlation,
            "synthetic-operator",
            "synthetic-approval",
            "provider recovered",
        )
        first = db.execute("SELECT e4_retry_notification(%s,%s,%s,%s,%s)", params).fetchone()
        assert (
            db.execute("SELECT e4_retry_notification(%s,%s,%s,%s,%s)", params).fetchone() == first
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            db.execute(
                "SELECT e4_retry_notification(%s,%s,%s,%s,%s)", (*params[:-1], "changed reason")
            )
    state, attempts = owner(
        "SELECT state,attempts FROM notification_worker_delivery WHERE id=%s", (did,)
    )[0]
    assert (state, attempts) == ("PENDING", 0)
    assert (
        owner("SELECT count(*) FROM notification_worker_attempt WHERE delivery_id=%s", (did,))[0][0]
        == 5
    )


def test_receipts_are_ticket_correlated_and_never_claim_read(pickup: dict[str, Any]) -> None:
    p = pickup
    register(p["parent_access"])
    _, _, did = notice(p)
    lease, jobs = claim()
    aid = next(row[0] for row in jobs if row[1] == did)
    ticket = f"SIMULATED-{uuid.uuid4()}"
    assert complete(aid, lease, ticket)
    owner(
        "UPDATE notification_worker_attempt SET receipt_available_at=clock_timestamp() WHERE id=%s",
        (aid,),
    )
    with connect("notifier") as db:
        receipt_lease = uuid.uuid4()
        rows = db.execute("SELECT * FROM e4_claim_receipts(100,%s)", (receipt_lease,)).fetchall()
        assert (aid, ticket) in rows
        assert db.execute(
            "SELECT e4_notification_receipt(%s,%s,'OK')", (aid, uuid.uuid4())
        ).fetchone() == (False,)
        assert db.execute(
            "SELECT e4_notification_receipt(%s,%s,'PENDING')", (aid, receipt_lease)
        ).fetchone() == (True,)
        assert (
            owner("SELECT state FROM notification_worker_delivery WHERE id=%s", (did,))[0][0]
            == "PROVIDER_ACCEPTED"
        )
        owner(
            "UPDATE notification_worker_attempt SET "
            "receipt_available_at=clock_timestamp() WHERE id=%s",
            (aid,),
        )
        db.execute("SELECT * FROM e4_claim_receipts(100,%s)", (receipt_lease,)).fetchall()
        assert db.execute(
            "SELECT e4_notification_receipt(%s,%s,'OK')", (aid, receipt_lease)
        ).fetchone() == (True,)
        assert db.execute(
            "SELECT e4_notification_receipt(%s,%s,'OK')", (aid, receipt_lease)
        ).fetchone() == (False,)
    assert (
        owner("SELECT state FROM notification_worker_delivery WHERE id=%s", (did,))[0][0]
        == "PROVIDER_RECEIPT"
    )


def test_revoked_recipients_and_unregistered_devices_do_not_send(pickup: dict[str, Any]) -> None:
    p = pickup
    token = register(p["parent_access"])
    _, _, did = notice(p)
    call(p["parent_access"], "SELECT e4_endpoint(%s,false)", (token,))
    assert not any(row[1] == did for row in claim()[1])
    assert (
        owner("SELECT state FROM notification_worker_delivery WHERE id=%s", (did,))[0][0]
        == "PENDING_DEVICE"
    )
    with connect("importer") as db:
        db.execute(
            "UPDATE identity_account SET active=false WHERE id=%s", (p["accounts"]["PADRE"],)
        )
    due(did)
    assert not any(row[1] == did for row in claim()[1])
    assert (
        owner("SELECT state FROM notification_worker_delivery WHERE id=%s", (did,))[0][0]
        == "SUPPRESSED"
    )


def test_notification_credentials_cannot_mutate_facts_or_fake_callbacks(
    pickup: dict[str, Any],
) -> None:
    p = pickup
    for role in ["runtime", "school_read", "system_read", "importer", "archiver", "notifier"]:
        with connect(role) as db:
            for sql in [
                "UPDATE evidence_event SET kind='bad'",
                "DELETE FROM notification_worker_delivery",
                "SELECT * FROM notification_worker_endpoint",
                "UPDATE pickup_operation SET report_result='DELIVERED'",
            ]:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    db.execute(sql)
    for role in ["runtime", "school_read", "system_read", "importer", "archiver"]:
        with connect(role) as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT * FROM e4_claim_notifications(1,%s)", (uuid.uuid4(),))
    for account in [p["accounts"]["GUARDIA"], p["accounts"]["ADMIN_SISTEMA"]]:
        access = login(account, "web" if account == p["accounts"]["ADMIN_SISTEMA"] else "mobile")[0]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            call(access, "SELECT e4_endpoint(%s,true)", (f"ExpoPushToken[{uuid.uuid4().hex}]",))
