"""AT03/05/07, CA-F07–10/15/19, CA-S04–06/11–16/22.

PostgreSQL/RLS and concurrent restricted runtime commands are real. Receipt fields
here are explicitly SIMULATED; they do not accredit AWS WORM acceptance.
"""

import json
import os
import secrets
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from django.test import Client, override_settings

from tests.integration.e1_support import connect, digest, login, roster
from tests.integration.test_e2_family import caregiver, command, technical

pytestmark = pytest.mark.integration
CHECKS = {"student": True, "caregiver": True, "document": True}


@pytest.fixture(autouse=True)
def runtime_database(django_db_blocker: Any) -> Any:
    with django_db_blocker.unblock():
        yield


def owner(sql: str, params: tuple[Any, ...] = ()) -> Any:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as db:
        db.execute("SET ROLE retiro_evidence_writer")
        row = db.execute(sql, params)
        return row.fetchall() if row.description else None


def clock() -> None:
    with connect("archiver") as db:
        assert db.execute("SELECT e3_clock_sample(clock_timestamp(),0)").fetchone() == (True,)


def call(access: str, sql: str, params: tuple[Any, ...]) -> Any:
    with connect() as db, db.transaction():
        db.execute("SELECT e1_authenticate(%s,true)", (digest(access),))
        row = db.execute(sql, params).fetchone()
        assert row
        return row[0]


def issue(
    access: str, authorization: str, when: str, key: uuid.UUID | None = None
) -> tuple[str, dict[str, Any]]:
    raw = secrets.token_urlsafe(32)
    result = call(
        access,
        "SELECT e3_issue('ISSUE',%s,%s,%s,%s,NULL,%s)",
        (key or uuid.uuid4(), authorization, when, digest(raw), digest("synthetic-origin")),
    )
    return raw, result


def resolve(access: str, raw: str, photo: bool = False) -> dict[str, Any]:
    return call(
        access, "SELECT e3_resolve(%s,%s,%s)", (digest(raw), digest("synthetic-origin"), photo)
    )


def confirm(
    access: str, raw: str, key: uuid.UUID | None = None, checks: dict[str, bool] | None = None
) -> dict[str, Any]:
    return call(
        access,
        "SELECT e3_confirm(%s,%s,%s::jsonb)",
        (key or uuid.uuid4(), digest(raw), json.dumps(CHECKS if checks is None else checks)),
    )


def operation(access: str, oid: str) -> dict[str, Any]:
    return call(access, "SELECT e3_get_operation(%s)", (oid,))


def receipt(oid: str) -> None:
    # The private test identity schedules only this operational job, then the real
    # archiver lease/completion functions check the matching digest and lease.
    eid = owner("SELECT event_id FROM pickup_operation WHERE id=%s", (oid,))[0][0]
    owner(
        "UPDATE evidence_archivejob SET available_at='2000-01-01T00:00:00Z' WHERE event_id=%s",
        (eid,),
    )
    lease = uuid.uuid4()
    with connect("archiver") as db:
        jobs = db.execute("SELECT * FROM e1_claim_archive(100,%s)", (lease,)).fetchall()
        job = next((j for j in jobs if j[0] == eid), None)
        assert job and job[0] == eid
        assert db.execute(
            "SELECT "
            "e1_archive_completed(%s,%s,'SIMULATED','SIMULATED','SIMULATED',%s,%s,'SIMULATED','SIMULATED')",
            (eid, lease, job[3], datetime.now(UTC) + timedelta(days=7)),
        ).fetchone() == (True,)


@pytest.fixture
def pickup() -> dict[str, Any]:
    scope = roster()
    # Keep this synthetic day away from midnight for reproducible boundary tests.
    with connect("importer") as db:
        db.execute(
            "UPDATE school_roster_site SET timezone=%s WHERE id=%s",
            ("UTC" if datetime.now(UTC).hour < 12 else "America/Bogota", scope["site"]),
        )
    windows = [
        {
            "weekday": d,
            "from": "00:00",
            "until": "23:59",
            "start_date": "2026-01-01",
            "end_date": "2030-12-31",
        }
        for d in range(1, 8)
    ]
    technical(
        "SET_POLICY", {"windows": windows, "blocked": False}, scope["school"], scope["student"]
    )
    parent = login(scope["accounts"]["PADRE"])[0]
    guard = login(scope["accounts"]["GUARDIA"])[0]
    cg = caregiver(parent, scope)
    start = datetime.now(UTC) + timedelta(seconds=1)
    end = start + timedelta(minutes=10)
    au = command(
        parent,
        "CREATE_AUTHORIZATION",
        {
            "student_id": str(scope["student"]),
            "caregiver_id": cg,
            "schedule": [{"from": start.isoformat(), "until": end.isoformat()}],
        },
    )["id"]
    clock()
    raw, result = issue(parent, au, start.isoformat())
    assert "error" not in result, result
    time.sleep(max(0, (start - datetime.now(UTC)).total_seconds()) + 0.01)
    return {
        **scope,
        "parent_access": parent,
        "guard_access": guard,
        "raw": raw,
        "issued": result,
        "authorization": au,
        "start": start.isoformat(),
    }


def test_resolve_is_minimal_does_not_consume_and_photo_is_guard_scoped(
    pickup: dict[str, Any],
) -> None:
    p = pickup
    for _ in range(2):
        data = resolve(p["guard_access"], p["raw"])
        assert data["student_name"] == "Synthetic student"
        assert data["caregiver"]["document"] == "SYNTHETIC-123"
        assert "photo" not in data and "token" not in data
    assert resolve(p["guard_access"], p["raw"], True)["photo"]
    assert resolve(login(roster()["accounts"]["GUARDIA"])[0], p["raw"]) == {"error": "DENIED"}
    for role in ["PADRE", "ADMIN_SISTEMA", "ADMIN_ESCUELA"]:
        access = login(p["accounts"][role], "web" if role.startswith("ADMIN") else "mobile")[0]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            resolve(access, p["raw"])


def test_fifty_confirmations_two_guards_one_decision(pickup: dict[str, Any]) -> None:
    p = pickup
    second_id = uuid.uuid4()
    technical(
        "PROVISION",
        {
            "role": "GUARDIA",
            "issuer": "https://idp.example",
            "subject": str(second_id),
            "site_id": str(p["site"]),
        },
        p["school"],
        second_id,
    )
    guards = [p["guard_access"], login(second_id)[0]]
    clock()
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda n: confirm(guards[n % 2], p["raw"]), range(50)))
    winners = [r for r in results if "operation_id" in r]
    assert len(winners) == 1
    assert owner(
        "SELECT count(*) FROM pickup_operation o JOIN pickup_episode ep ON "
        "ep.id=o.episode_id WHERE ep.student_id=%s",
        (p["student"],),
    ) == [(1,)]
    assert owner(
        "SELECT count(*) FROM evidence_event WHERE kind='SALIDA_CONFIRMADA' AND correlation_id=%s",
        (winners[0]["operation_id"],),
    ) == [(1,)]
    assert issue(p["parent_access"], p["authorization"], p["start"])[1]["error"] == "CLOSED"


def test_pending_receipt_enable_and_single_physical_report(pickup: dict[str, Any]) -> None:
    p = pickup
    key = uuid.uuid4()
    oid = confirm(p["guard_access"], p["raw"], key)["operation_id"]
    assert confirm(p["guard_access"], p["raw"], key)["operation_id"] == oid
    assert operation(p["guard_access"], oid)["state"] == "PENDIENTE_ARCHIVO"
    receipt(oid)
    enabled = operation(p["guard_access"], oid)
    assert enabled["may_handover"] and enabled["state"] == "HABILITADA"
    expiry = datetime.fromisoformat(enabled["permission_expires_at"])
    assert 28 <= (expiry - datetime.fromisoformat(enabled["server_now"])).total_seconds() <= 30
    report_key = uuid.uuid4()
    params = (oid, report_key, True, datetime.now(UTC), "Synthetic physical handover")
    result = call(p["guard_access"], "SELECT e3_report(%s,%s,%s,%s,%s)", params)
    assert call(p["guard_access"], "SELECT e3_report(%s,%s,%s,%s,%s)", params) == result
    final = operation(p["guard_access"], oid)
    assert final["state"] == "ENTREGA_REPORTADA" and not final["may_handover"]
    assert final["report_result"] == "DELIVERED" and not final["report_protected"]
    assert owner(
        "SELECT count(*) FROM evidence_event WHERE kind='ENTREGA_FISICA_REPORTADA' "
        "AND correlation_id=%s",
        (oid,),
    ) == [(1,)]
    assert (
        call(
            p["guard_access"],
            "SELECT e3_report(%s,%s,false,%s,'different')",
            (oid, uuid.uuid4(), datetime.now(UTC)),
        )["error"]
        == "CONFLICT"
    )


def test_timeout_late_archive_and_late_report_never_reenable(pickup: dict[str, Any]) -> None:
    p = pickup
    oid = confirm(p["guard_access"], p["raw"])["operation_id"]
    owner(
        "UPDATE pickup_operation SET protection_deadline=clock_timestamp()-interval "
        "'1 second' WHERE id=%s",
        (oid,),
    )
    with connect("archiver") as db:
        db.execute("SELECT e3_sweep()")
    assert operation(p["guard_access"], oid)["state"] == "INCIDENCIA"
    receipt(oid)
    assert not operation(p["guard_access"], oid)["may_handover"]
    call(
        p["guard_access"],
        "SELECT e3_report(%s,%s,true,%s,'late observed fact')",
        (oid, uuid.uuid4(), datetime.now(UTC)),
    )
    assert operation(p["guard_access"], oid)["state"] == "INCIDENCIA"
    assert confirm(p["guard_access"], p["raw"])["error"] == "DENIED"


@pytest.mark.parametrize("change", ["revocation", "caregiver", "principal", "policy", "guard"])
def test_block_after_decision_creates_incident(pickup: dict[str, Any], change: str) -> None:
    p = pickup
    oid = confirm(p["guard_access"], p["raw"])["operation_id"]
    receipt(oid)
    assert operation(p["guard_access"], oid)["may_handover"]
    if change == "revocation":
        command(
            p["parent_access"],
            "REVOKE_AUTHORIZATION",
            {"id": p["authorization"], "student_id": str(p["student"])},
        )
    elif change == "caregiver":
        from tests.integration.test_e2_family import photo

        cg = owner(
            "SELECT caregiver_id FROM authorization_authorization WHERE id=%s",
            (p["authorization"],),
        )[0][0]
        command(
            p["parent_access"],
            "UPDATE_CAREGIVER",
            {
                "id": str(cg),
                "student_id": str(p["student"]),
                "version": 1,
                "name": "Changed",
                "document": "SYNTHETIC",
                "photo": photo(),
            },
        )
    elif change == "principal":
        technical("CHANGE_PRINCIPAL", {"parent_id": str(p["secondary"])}, p["school"], p["student"])
    elif change == "policy":
        technical(
            "SET_POLICY",
            {
                "windows": [
                    {
                        "weekday": 1,
                        "from": "07:00",
                        "until": "18:00",
                        "start_date": "2026-01-01",
                        "end_date": "2030-12-31",
                    }
                ],
                "blocked": True,
            },
            p["school"],
            p["student"],
        )
    else:
        technical("DEACTIVATE", {}, p["school"], p["accounts"]["GUARDIA"])
    assert owner("SELECT state FROM pickup_operation WHERE id=%s", (oid,)) == [("INCIDENCIA",)]
    assert owner(
        "SELECT count(*) FROM evidence_event WHERE kind='SALIDA_CONFIRMADA' AND correlation_id=%s",
        (oid,),
    ) == [(1,)]


def test_revocation_committed_first_and_renewal_invalidate_old_tokens(
    pickup: dict[str, Any],
) -> None:
    p = pickup
    fresh, result = issue(p["parent_access"], p["authorization"], p["start"])
    assert result["expires_at"] == p["issued"]["expires_at"]
    assert resolve(p["guard_access"], p["raw"])["error"] == "DENIED"
    command(
        p["parent_access"],
        "REVOKE_AUTHORIZATION",
        {"id": p["authorization"], "student_id": str(p["student"])},
    )
    assert confirm(p["guard_access"], fresh)["error"] == "DENIED"


def test_idempotency_is_bound_to_actor_and_body(pickup: dict[str, Any]) -> None:
    p = pickup
    key = uuid.uuid4()
    assert "operation_id" in confirm(p["guard_access"], p["raw"], key)
    assert (
        confirm(p["guard_access"], p["raw"], key, {**CHECKS, "document": False})["error"]
        == "CONFLICT"
    )


@pytest.mark.parametrize("field", ["student", "caregiver", "document"])
def test_each_physical_mismatch_is_incident_without_permission(
    pickup: dict[str, Any], field: str
) -> None:
    p = pickup
    oid = confirm(p["guard_access"], p["raw"], checks={**CHECKS, field: False})["operation_id"]
    receipt(oid)
    result = operation(p["guard_access"], oid)
    assert result["state"] == "INCIDENCIA" and not result["may_handover"]


def test_clock_missing_skew_and_expired_screen_fail_closed(pickup: dict[str, Any]) -> None:
    p = pickup
    with connect("archiver") as db:
        assert db.execute(
            "SELECT e3_clock_sample(clock_timestamp()+interval '1 hour',0)"
        ).fetchone() == (False,)
    assert confirm(p["guard_access"], p["raw"])["error"] == "DENIED"
    clock()
    oid = confirm(p["guard_access"], p["raw"])["operation_id"]
    receipt(oid)
    owner(
        "UPDATE pickup_operation SET permission_expires_at=clock_timestamp()-interval "
        "'1 second' WHERE id=%s",
        (oid,),
    )
    assert operation(p["guard_access"], oid)["state"] == "INCIDENCIA"
    assert not operation(p["guard_access"], oid)["may_handover"]


def test_window_boundaries_and_no_photo_before_start(pickup: dict[str, Any]) -> None:
    p = pickup
    owner(
        "UPDATE pickup_token SET valid_from=clock_timestamp()+interval '1 minute' "
        "WHERE episode_id=%s",
        (p["issued"]["episode_id"],),
    )
    assert resolve(p["guard_access"], p["raw"], True)["error"] == "DENIED"
    owner(
        "UPDATE pickup_token SET valid_from=clock_timestamp()-interval '15 "
        "minutes',expires_at=statement_timestamp() WHERE episode_id=%s",
        (p["issued"]["episode_id"],),
    )
    assert resolve(p["guard_access"], p["raw"])["error"] == "DENIED"


def test_issue_replay_returns_no_secret_and_runtime_cannot_read_or_mutate_tables(
    pickup: dict[str, Any],
) -> None:
    p = pickup
    key = uuid.uuid4()
    raw, first = issue(p["parent_access"], p["authorization"], p["start"], key)
    _, replay = issue(p["parent_access"], p["authorization"], p["start"], key)
    assert first["issued"] and replay == {**first, "issued": False}
    assert raw not in json.dumps(replay) and "token_hash" not in json.dumps(replay)
    for role in ["runtime", "school_read", "system_read", "notifier", "archiver"]:
        with connect(role) as db:
            for table in [
                "pickup_token",
                "pickup_operation",
                "pickup_episode",
                "pickup_command",
                "pickup_clock",
            ]:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    db.execute(f"SELECT * FROM {table}")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    db.execute(f"UPDATE {table} SET id=id")
    with connect() as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("SELECT e3_clock_sample(clock_timestamp(),0)")


def test_scan_rate_is_per_guard_with_burst_ten(pickup: dict[str, Any]) -> None:
    p = pickup
    outcomes = [resolve(p["guard_access"], secrets.token_urlsafe(32)) for _ in range(11)]
    assert outcomes[-1]["error"] == "RATE_LIMITED"
    assert outcomes[0]["error"] == "DENIED"
    other = login(roster()["accounts"]["GUARDIA"])[0]
    assert resolve(other, secrets.token_urlsafe(32))["error"] == "DENIED"


def test_transport_auth_validation_no_store_and_ambiguous_operation_recovery(
    pickup: dict[str, Any],
) -> None:
    from django.urls import include, path
    from pickup import views

    p = pickup
    routes = type("Routes", (), {"urlpatterns": [path("v1/", include("pickup.urls"))]})
    client = Client()
    with override_settings(ROOT_URLCONF=routes):
        assert (
            client.post(
                "/v1/guard/resolve-qr",
                data=json.dumps({"token": p["raw"]}),
                content_type="application/json",
            ).status_code
            == 401
        )
        key = str(uuid.uuid4())
        response = client.post(
            "/v1/guard/confirm-pickup",
            data=json.dumps({"token": p["raw"], "checks": CHECKS}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {p['guard_access']}",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        assert response.status_code == 200, response.content
        assert response.json()["operation_id"] == key
        assert "no-store" in response.headers["Cache-Control"]
        recovered = client.get(
            f"/v1/guard/operations/{key}", HTTP_AUTHORIZATION=f"Bearer {p['guard_access']}"
        )
        assert recovered.json()["state"] == "PENDIENTE_ARCHIVO"
        assert (
            client.get(
                f"/v1/guard/operations/{key}", HTTP_AUTHORIZATION=f"Bearer {p['parent_access']}"
            ).status_code
            == 401
        )
        assert views.instant("2026-11-08T13:00:00-05:00").utcoffset() == timedelta(hours=-5)


def test_ten_thousand_invalid_tokens_reveal_no_data_without_entropy_claim(
    pickup: dict[str, Any],
) -> None:
    p = pickup
    with connect() as db, db.transaction():
        db.execute("SELECT e1_authenticate(%s,true)", (digest(p["guard_access"]),))
        for _ in range(10000):
            value = db.execute(
                "SELECT e3_resolve(%s,%s,false)",
                (digest(secrets.token_urlsafe(32)), digest("synthetic-origin")),
            ).fetchone()[0]
            assert set(value) == {"error"} and value["error"] in {"DENIED", "RATE_LIMITED"}


def test_reschedule_revalidates_window_and_old_tokens_stay_dead(pickup: dict[str, Any]) -> None:
    p = pickup
    key = uuid.uuid4()
    new_raw = secrets.token_urlsafe(32)
    # Within the existing authorization, explicitly move the same stable episode.
    future = datetime.now(UTC) + timedelta(seconds=3)
    params = (
        key,
        p["authorization"],
        future,
        digest(new_raw),
        p["issued"]["episode_id"],
        digest("synthetic-origin"),
    )
    result = call(p["parent_access"], "SELECT e3_issue('RESCHEDULE',%s,%s,%s,%s,%s,%s)", params)
    assert result["episode_id"] == p["issued"]["episode_id"]
    assert resolve(p["guard_access"], p["raw"])["error"] == "DENIED"
    assert resolve(p["guard_access"], new_raw)["error"] == "DENIED"
    _, denied = issue(
        p["parent_access"], p["authorization"], (future + timedelta(days=2)).isoformat()
    )
    assert denied["error"] == "INVALID_WINDOW"


def test_revocation_race_is_ordered_by_student_lock(pickup: dict[str, Any]) -> None:
    p = pickup
    with connect() as db:
        db.execute("BEGIN")
        db.execute("SELECT set_config('app.session_hash',%s,true)", (digest(p["parent_access"]),))
        db.execute(
            "SELECT e2_family_command('REVOKE_AUTHORIZATION',%s,%s::jsonb)",
            (uuid.uuid4(), json.dumps({"id": p["authorization"], "student_id": str(p["student"])})),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(confirm, p["guard_access"], p["raw"])
            try:
                time.sleep(0.1)
                assert not pending.done()
            finally:
                db.execute("COMMIT")
            assert pending.result(timeout=5) == {"error": "DENIED"}


def test_second_authorization_cannot_reopen_same_student_day(pickup: dict[str, Any]) -> None:
    p = pickup
    confirm(p["guard_access"], p["raw"])
    cg = caregiver(p["parent_access"], p)
    future = datetime.now(UTC) + timedelta(minutes=1)
    au = command(
        p["parent_access"],
        "CREATE_AUTHORIZATION",
        {
            "student_id": str(p["student"]),
            "caregiver_id": cg,
            "schedule": [
                {"from": future.isoformat(), "until": (future + timedelta(minutes=5)).isoformat()}
            ],
        },
    )["id"]
    assert issue(p["parent_access"], au, future.isoformat())[1]["error"] == "CLOSED"


def test_bounded_real_queue_fault_only_accepts_explicit_synthetic_import(
    pickup: dict[str, Any],
) -> None:
    from scripts.seed_e2_roster import CohortUsed, seed
    from tests.integration.test_e2_family import batch

    with connect("importer") as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT e3_trial_hold(%s)", (pickup["student"],))
    approved = batch()
    child = approved["students"][0]
    child["name"] = "E3 synthetic timeout"
    for w in child["windows"]:
        w.update({"from": "00:00", "until": "23:59"})
    data = {"action": "e3-seed", "e3_batch": approved}
    with connect("importer") as db:
        seed(db, data)
        with pytest.raises(CohortUsed):
            seed(db, data)
        seed(db, {**data, "action": "e3-hold"})
        with pytest.raises(psycopg.errors.UniqueViolation):
            seed(db, {**data, "action": "e3-hold"})
    assert owner(
        "SELECT until>clock_timestamp() FROM pickup_trialhold WHERE student_id=%s", (child["id"],)
    ) == [(True,)]
    with connect() as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("SELECT e3_trial_hold(%s)", (child["id"],))


def test_clock_sample_expiry_and_network_duration_are_fail_closed(pickup: dict[str, Any]) -> None:
    p = pickup
    with connect("archiver") as db:
        assert db.execute("SELECT e3_clock_sample(clock_timestamp(),2001)").fetchone() == (False,)
    assert confirm(p["guard_access"], p["raw"])["error"] == "DENIED"
    clock()
    owner("UPDATE pickup_clock SET trusted_until=clock_timestamp()-interval '1 second' WHERE id=1")
    assert confirm(p["guard_access"], p["raw"])["error"] == "DENIED"


def test_e3_openapi_validates_actual_operation_response(pickup: dict[str, Any]) -> None:
    from pathlib import Path

    import yaml
    from jsonschema import Draft202012Validator

    p = pickup
    schemas = yaml.safe_load(Path("tests/contracts/openapi.yaml").read_text())["components"][
        "schemas"
    ]
    Draft202012Validator(schemas["ResolvedQR"]).validate(resolve(p["guard_access"], p["raw"]))
    oid = confirm(p["guard_access"], p["raw"])["operation_id"]
    Draft202012Validator(schemas["PickupOperation"]).validate(operation(p["guard_access"], oid))


def test_denied_confirmation_key_cannot_be_rebound_to_a_new_token(pickup: dict[str, Any]) -> None:
    p = pickup
    fresh, _ = issue(p["parent_access"], p["authorization"], p["start"])
    key = uuid.uuid4()
    assert confirm(p["guard_access"], p["raw"], key) == {"error": "DENIED"}
    assert confirm(p["guard_access"], p["raw"], key) == {"error": "DENIED"}
    assert confirm(p["guard_access"], fresh, key) == {"error": "CONFLICT"}
