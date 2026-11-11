"""AT02/05/07: real restricted PostgreSQL. Receipts below are SIMULATED only."""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from django.test import Client, override_settings
from django.urls import include, path
from jsonschema import Draft202012Validator

from tests.integration.e1_support import connect, digest, login, roster
from tests.integration.test_e1_school_access import fake_receipt
from tests.integration.test_e3_pickup import (
    call,
    clock,
    confirm,
    operation,
    owner,
    receipt,
)
from tests.integration.test_e3_pickup import (
    pickup as e3_pickup,
)

pytestmark = pytest.mark.integration
pickup = e3_pickup


@pytest.fixture(autouse=True)
def runtime_database(django_db_blocker: Any) -> Any:
    with django_db_blocker.unblock():
        yield


def report(p: dict[str, Any], delivered: bool = True) -> tuple[str, str]:
    clock()
    oid = confirm(p["guard_access"], p["raw"])["operation_id"]
    receipt(oid)
    info = operation(p["guard_access"], oid)
    assert info["may_handover"]
    result = call(
        p["guard_access"],
        "SELECT e3_report(%s,%s,%s,clock_timestamp(),'synthetic report')",
        (oid, uuid.uuid4(), delivered),
    )
    return oid, result["report_event_id"]


def school_login(scope: dict[str, Any]) -> str:
    access, _, meta = login(scope["accounts"]["ADMIN_ESCUELA"], "web")
    fake_receipt(meta["event_id"])
    with connect() as db:
        assert db.execute("SELECT e1_enable_school_session(%s)", (digest(access),)).fetchone() == (
            True,
        )
    return access


def school_records(access: str, *args: Any) -> dict[str, Any]:
    with connect("school_read") as db, db.transaction():
        db.execute("SELECT set_config('app.session_hash',%s,true)", (digest(access),))
        row = db.execute(
            "SELECT e4_school_records(%s,%s,%s,%s,%s)", args or (25, None, None, None, None)
        ).fetchone()
        assert row
        return row[0]


def correct(oid: str, key: uuid.UUID, outcome: str = "NOT_DELIVERED") -> dict[str, Any]:
    with connect("importer") as db:
        row = db.execute(
            "SELECT e4_correct(%s,%s,'synthetic-operator',"
            "'synthetic-school-approval','synthetic correction',%s)",
            (oid, key, outcome),
        ).fetchone()
        assert row
        return row[0]


def test_school_and_family_queries_are_minimal_scoped_and_read_only(pickup: dict[str, Any]) -> None:
    p = pickup
    oid, eid = report(p)
    access = school_login(p)
    own = school_records(access)
    assert len(own["records"]) == 1
    item = own["records"][0]
    assert item["operation_id"] == oid and item["report_result"] == "DELIVERED"
    assert item["report_protected"] is False
    fake_receipt(eid)
    assert school_records(access)["records"][0]["report_protected"] is True
    assert school_records(school_login(roster()))["records"] == []
    assert school_records(access, 25, None, str(uuid.uuid4()), None, None)["records"] == []
    assert school_records(access, 25, None, None, "2000-01-01", "2000-01-02")["records"] == []
    first = school_records(access, 1, None, None, None, None)
    assert first["next_cursor"] == item["sequence"]
    assert school_records(access, 1, first["next_cursor"], None, None, None)["records"] == []
    assert not {"photo", "document", "caregiver", "token", "canonical"} & item.keys()
    for parent in [p["parent_access"], login(p["other_parent"])[0]]:
        family = call(parent, "SELECT e4_parent_records(25,NULL,NULL,NULL,NULL)", ())
        assert len(family["records"]) == 1
    other = login(roster()["accounts"]["PADRE"])[0]
    assert call(other, "SELECT e4_parent_records(25,NULL,NULL,NULL,NULL)", ())["records"] == []
    for role in ["runtime", "school_read", "system_read", "notifier", "importer", "archiver"]:
        with connect(role) as db:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute("UPDATE pickup_correction SET outcome='DELIVERED'")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute("SELECT * FROM pickup_operation")
    system = login(p["accounts"]["ADMIN_SISTEMA"], "web")[0]
    for rejected in [system, p["parent_access"], p["guard_access"]]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            school_records(rejected)


def test_corrections_are_linked_idempotent_serialized_and_never_reopen(
    pickup: dict[str, Any],
) -> None:
    p = pickup
    oid, eid = report(p)
    before = owner("SELECT canonical FROM evidence_event WHERE id=%s", (eid,))[0][0]
    original = owner(
        "SELECT state,report_event_id,report_result FROM pickup_operation WHERE id=%s", (oid,)
    )[0]
    key = uuid.uuid4()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: correct(oid, key), range(8)))
    assert len({r["event_id"] for r in results}) == 1
    first = results[0]["event_id"]
    second = correct(oid, uuid.uuid4(), "UNRESOLVED")["event_id"]
    assert owner("SELECT related_event_id FROM pickup_correction WHERE event_id=%s", (second,))[0][
        0
    ] == uuid.UUID(first)
    assert bytes(owner("SELECT canonical FROM evidence_event WHERE id=%s", (eid,))[0][0]) == bytes(
        before
    )
    assert (
        owner(
            "SELECT state,report_event_id,report_result FROM pickup_operation WHERE id=%s", (oid,)
        )[0]
        == original
    )
    assert operation(p["guard_access"], oid)["may_handover"] is False
    with pytest.raises(psycopg.errors.UniqueViolation):
        correct(oid, key, "DELIVERED")
    row = school_records(school_login(p))["records"][0]
    assert len(row["corrections"]) == 2 and not any(c["protected"] for c in row["corrections"])
    fake_receipt(first)
    assert school_records(school_login(p))["records"][0]["corrections"][0]["protected"] is True
    for role in ["runtime", "school_read", "system_read", "notifier", "archiver"]:
        with connect(role) as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT e4_correct(%s,%s,'a','b','c','DELIVERED')", (oid, uuid.uuid4()))


def test_query_transport_limits_channels_and_http_methods(
    pickup: dict[str, Any], monkeypatch: Any
) -> None:
    p = pickup
    report(p)
    routes = type(
        "Routes",
        (),
        {
            "urlpatterns": [
                path("v1/", include("pickup.record_urls")),
                path("", include("identity.urls")),
            ]
        },
    )
    monkeypatch.setenv("SCHOOL_READ_PASSWORD", "synthetic-school-read-only")
    client = Client()
    with override_settings(ROOT_URLCONF=routes, E4_OPERATIONS_ENABLED=True):
        assert client.get("/v1/me/pickups").status_code == 401
        for query in [
            "limit=101",
            "before=0",
            "student=bad",
            "school=arbitrary",
            "limit=1&limit=2",
            "from=2026-02-02&to=2026-01-01",
        ]:
            assert (
                client.get(
                    f"/v1/me/pickups?{query}", HTTP_AUTHORIZATION=f"Bearer {p['parent_access']}"
                ).status_code
                == 400
            )
        assert (
            client.get(
                "/v1/me/pickups", HTTP_AUTHORIZATION=f"Bearer {p['guard_access']}"
            ).status_code
            == 403
        )
        response = client.get("/v1/me/pickups", HTTP_AUTHORIZATION=f"Bearer {p['parent_access']}")
        assert response.status_code == 200 and response["Cache-Control"] == "no-store"
        assert "Synthetic student" in json.dumps(response.json())
        spec = yaml.safe_load(Path("tests/contracts/openapi.yaml").read_text())
        Draft202012Validator(
            {"$ref": "#/components/schemas/RecordPage", "components": spec["components"]}
        ).validate(response.json())
        session = client.session
        session["identity_secret"] = school_login(p)
        session.save()
        assert client.get("/v1/school/pickup-records").status_code == 200
        assert client.post("/v1/school/pickup-records", {}).status_code == 405
        page = client.get("/portal/")
        assert page.status_code == 200 and b"Salidas e incidencias" in page.content
        assert b"Pendiente de" in page.content
