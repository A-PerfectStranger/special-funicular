"""AT01/02/04 E2 on PostgreSQL with restricted importer/runtime credentials."""

import base64
import io
import ipaddress
import json
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import psycopg
import pytest
from django.test import Client, override_settings
from PIL import Image

from tests.integration.e1_support import connect, digest, login, roster

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def runtime_database(django_db_blocker: Any) -> Any:
    with django_db_blocker.unblock():
        yield


def windows() -> list[dict[str, Any]]:
    return [
        {
            "weekday": d,
            "from": "07:00",
            "until": "18:00",
            "start_date": "2026-01-01",
            "end_date": "2030-12-31",
        }
        for d in range(1, 8)
    ]


def batch(scope: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = scope or roster()
    student, parent, secondary = (str(uuid.uuid4()) for _ in range(3))
    return {
        "schema_version": 1,
        "id": str(uuid.uuid4()),
        "school_id": str(scope["school"]),
        "parents": [
            {"id": parent, "contact": f"{parent}@example.invalid"},
            {"id": secondary, "contact": f"{secondary}@example.invalid"},
        ],
        "students": [
            {
                "id": student,
                "site_id": str(scope["site"]),
                "name": "Synthetic E2 student",
                "windows": windows(),
                "blocked": False,
            }
        ],
        "links": [
            {"student_id": student, "parent_id": parent, "principal": True},
            {"student_id": student, "parent_id": secondary, "principal": False},
        ],
    }


def import_batch(data: dict[str, Any], promote: bool = True) -> tuple[str, str]:
    raw = json.dumps(data)
    hashed = digest(raw)
    with connect("importer") as db:
        db.execute(
            "SELECT e2_import('STAGE',%s,%s,%s,'synthetic-operator','')", (data["id"], raw, hashed)
        )
        if promote:
            db.execute(
                "SELECT e2_import('APPROVE',%s,'',%s,'synthetic-operator','SCHOOL-APPROVAL')",
                (data["id"], hashed),
            )
            db.execute(
                "SELECT e2_import('PROMOTE',%s,'',%s,'synthetic-operator','')", (data["id"], hashed)
            )
    return raw, hashed


def technical(
    operation: str,
    data: dict[str, Any],
    school: Any,
    target: Any,
    correlation: uuid.UUID | None = None,
) -> None:
    with connect("importer") as db:
        db.execute(
            "SELECT e2_technical(%s,%s,%s,%s,%s::jsonb,"
            "'synthetic-operator','SCHOOL-APPROVAL','synthetic test')",
            (operation, correlation or uuid.uuid4(), school, target, json.dumps(data)),
        )


def policy(scope: dict[str, Any]) -> None:
    technical(
        "SET_POLICY", {"windows": windows(), "blocked": False}, scope["school"], scope["student"]
    )


def photo() -> str:
    image = Image.new("RGB", (12, 12), "blue")
    output = io.BytesIO()
    image.save(output, "JPEG")
    return base64.b64encode(output.getvalue()).decode()


def command(
    access: str, op: str, payload: dict[str, Any], key: uuid.UUID | None = None
) -> dict[str, Any]:
    with connect() as db, db.transaction():
        db.execute("SELECT set_config('app.session_hash',%s,true)", (digest(access),))
        row = db.execute(
            "SELECT e2_family_command(%s,%s,%s::jsonb)",
            (op, key or uuid.uuid4(), json.dumps(payload)),
        ).fetchone()
        assert row
        return row[0]


def caregiver(access: str, scope: dict[str, Any]) -> str:
    return command(
        access,
        "CREATE_CAREGIVER",
        {
            "student_id": str(scope["student"]),
            "name": "Synthetic Caregiver",
            "document": "SYNTHETIC-123",
            "photo": photo(),
        },
    )["id"]


def tomorrow() -> list[dict[str, str]]:
    day = datetime.now(UTC).date() + timedelta(days=1)
    return [{"from": f"{day}T18:00:00+00:00", "until": f"{day}T18:15:00+00:00"}]


def test_bulk_approval_hash_replay_and_private_boundary() -> None:
    data = batch()
    raw, hashed = import_batch(data, False)
    with connect("importer") as db:
        assert db.execute(
            "SELECT count(*) FROM school_roster_student WHERE id=%s", (data["students"][0]["id"],)
        ).fetchone() == (0,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT e2_import('PROMOTE',%s,'',%s,'operator','')", (data["id"], hashed))
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            db.execute(
                "SELECT e2_import('APPROVE',%s,'',%s,'operator','approval')", (data["id"], "0" * 64)
            )
    import_batch(data)
    import_batch(data)
    with connect("importer") as db:
        assert db.execute(
            "SELECT count(*) FROM school_roster_student WHERE id=%s", (data["students"][0]["id"],)
        ).fetchone() == (1,)
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            db.execute(
                "SELECT e2_import('STAGE',%s,%s,%s,'operator','')",
                (data["id"], raw + " ", digest(raw + " ")),
            )
    with connect() as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("SELECT e2_import('STAGE',%s,%s,%s,'operator','')", (uuid.uuid4(), raw, hashed))


@pytest.mark.parametrize(
    "damage",
    ["cross_site", "double_principal", "reference", "duplicate", "unlinked", "invalid_windows"],
)
def test_invalid_batch_never_activates_any_row(damage: str) -> None:
    data = batch()
    if damage == "cross_site":
        data["students"][0]["site_id"] = str(roster()["site"])
    if damage == "double_principal":
        data["links"][1]["principal"] = True
    if damage == "reference":
        data["links"][1]["student_id"] = str(uuid.uuid4())
    if damage == "duplicate":
        data["parents"].append(data["parents"][0])
    if damage == "unlinked":
        data["links"].pop()
    if damage == "invalid_windows":
        data["students"][0]["windows"][0]["from"] = "19:00"
    with pytest.raises(psycopg.Error):
        import_batch(data)
    with connect("importer") as db:
        assert db.execute(
            "SELECT count(*) FROM school_roster_student WHERE id=%s", (data["students"][0]["id"],)
        ).fetchone() == (0,)


def test_promotion_revalidates_and_rolls_back_after_staging() -> None:
    data = batch()
    _, hashed = import_batch(data, False)
    with connect("importer") as db:
        db.execute(
            "SELECT e2_import('APPROVE',%s,'',%s,'operator','approval')", (data["id"], hashed)
        )
        # A contact conflict introduced after validation must roll back the whole promotion.
        conflict = batch()
        conflict["parents"][1]["contact"] = data["parents"][1]["contact"]
        import_batch(conflict)
        with pytest.raises(psycopg.errors.UniqueViolation):
            db.execute("SELECT e2_import('PROMOTE',%s,'',%s,'operator','')", (data["id"], hashed))
        assert db.execute(
            "SELECT count(*) FROM school_roster_parent WHERE id=%s", (data["parents"][0]["id"],)
        ).fetchone() == (0,)


def issue(data: dict[str, Any]) -> str:
    token = secrets.token_urlsafe(32)
    with connect("importer") as db:
        db.execute(
            "SELECT e2_invite(%s,%s,'operator','school approval',%s)",
            (data["parents"][0]["id"], digest(token), uuid.uuid4()),
        )
    return token


def activation_login() -> uuid.UUID:
    from identity.models import LoginRequest

    from tests.integration.test_e1_identity import pending_login

    state, _, _ = pending_login()
    login_request = LoginRequest.objects.get(state_hash=digest(state))
    login_request.purpose = "activate"
    login_request.consumed_at = datetime.now(UTC)
    login_request.save()
    return login_request.id


def redeem(
    data: dict[str, Any], token: str, contact: str | None = None, subject: str | None = None
) -> str:
    sub = subject or str(uuid.uuid4())
    with connect() as db:
        db.execute(
            "SELECT e2_redeem(%s,%s,'https://idp.example',%s,%s,%s)",
            (
                activation_login(),
                digest(token),
                sub,
                contact or data["parents"][0]["contact"],
                datetime.now(UTC),
            ),
        )
    return sub


def test_invitation_exact_contact_one_use_and_oidc_association() -> None:
    data = batch()
    import_batch(data)
    token = issue(data)
    with pytest.raises(psycopg.errors.InvalidAuthorizationSpecification):
        redeem(data, token, "someone-else@example.invalid")
    sub = redeem(data, token)
    with pytest.raises(psycopg.errors.InvalidAuthorizationSpecification):
        redeem(data, token, subject=sub)
    with connect("importer") as db:
        rows = db.execute(
            "SELECT p.id,a.subject FROM school_roster_parent p "
            "JOIN identity_account a ON a.id=p.account_id WHERE p.id IN (%s,%s)",
            tuple(p["id"] for p in data["parents"]),
        ).fetchall()
        assert rows == [(uuid.UUID(data["parents"][0]["id"]), sub)]


def test_reissue_and_revocation_invalidate_invitation() -> None:
    data = batch()
    import_batch(data)
    old, new = issue(data), issue(data)
    with pytest.raises(psycopg.errors.InvalidAuthorizationSpecification):
        redeem(data, old)
    with connect("importer") as db:
        # Use narrow operation; importer cannot freely mutate invitation records.
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("UPDATE identity_invitation SET expires_at=now()")
    redeem(data, new)


def test_concurrent_redemption_associates_one_account() -> None:
    data = batch()
    import_batch(data)
    token = issue(data)
    lids = [activation_login() for _ in range(8)]

    def attempt(lid: uuid.UUID) -> bool:
        try:
            with connect() as db:
                db.execute(
                    "SELECT e2_redeem(%s,%s,'https://idp.example',%s,%s,%s)",
                    (
                        lid,
                        digest(token),
                        str(uuid.uuid4()),
                        data["parents"][0]["contact"],
                        datetime.now(UTC),
                    ),
                )
            return True
        except psycopg.errors.InvalidAuthorizationSpecification:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, lids)) == 1


def test_family_scope_idempotency_revocation_and_changes() -> None:
    scope, other = roster(), roster()
    policy(scope)
    access, _, _ = login(scope["accounts"]["PADRE"])
    secondary, _, _ = login(scope["other_parent"])
    outsider, _, _ = login(other["accounts"]["PADRE"])
    payload = {
        "student_id": str(scope["student"]),
        "name": "Synthetic",
        "document": "TEST-123",
        "photo": photo(),
    }
    key = uuid.uuid4()
    cg = command(access, "CREATE_CAREGIVER", payload, key)["id"]
    assert command(access, "CREATE_CAREGIVER", payload, key)["id"] == cg
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        command(access, "CREATE_CAREGIVER", {**payload, "name": "changed"}, key)
    for denied in [secondary, outsider]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            command(denied, "CREATE_CAREGIVER", payload)
    au = command(
        access,
        "CREATE_AUTHORIZATION",
        {"student_id": str(scope["student"]), "caregiver_id": cg, "schedule": tomorrow()},
    )["id"]
    command(access, "UPDATE_CAREGIVER", {**payload, "id": cg, "version": 1, "document": "CHANGED"})
    with connect() as db, db.transaction():
        db.execute("SELECT set_config('app.session_hash',%s,true)", (digest(access),))
        records = db.execute("SELECT e2_family_records(%s)", (scope["student"],)).fetchone()[0]
        assert records["authorizations"][0]["id"] == au
        assert records["authorizations"][0]["revoked"]
        assert records["caregivers"][0]["version"] == 2
    technical(
        "CHANGE_PRINCIPAL",
        {"parent_id": str(scope["secondary"])},
        scope["school"],
        scope["student"],
    )
    with connect() as db:
        assert db.execute("SELECT e1_authenticate(%s,true)", (digest(access),)).fetchone() == (
            None,
        )
    new_access, _, _ = login(scope["other_parent"])
    caregiver(new_access, scope)
    previous, _, _ = login(scope["accounts"]["PADRE"])
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        caregiver(previous, scope)


@pytest.mark.parametrize("bad", ["outside", "past", "empty", "cross_caregiver"])
def test_authorization_rejects_invalid_window_or_object(bad: str) -> None:
    scope = roster()
    policy(scope)
    access, _, _ = login(scope["accounts"]["PADRE"])
    cg = caregiver(access, scope)
    dates = tomorrow()
    if bad == "outside":
        dates[0]["until"] = dates[0]["until"].replace("18:15", "23:15")
    if bad == "past":
        dates = [{"from": "2020-01-01T18:00:00Z", "until": "2020-01-01T18:15:00Z"}]
    if bad == "empty":
        dates = []
    if bad == "cross_caregiver":
        cg = str(uuid.uuid4())
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        command(
            access,
            "CREATE_AUTHORIZATION",
            {"student_id": str(scope["student"]), "caregiver_id": cg, "schedule": dates},
        )


def test_family_api_photo_metadata_roles_and_no_store() -> None:
    scope = roster()
    policy(scope)
    access, _, _ = login(scope["accounts"]["PADRE"])
    from authorization import urls

    with override_settings(ROOT_URLCONF=urls):
        # ROOT_URLCONF omits the /v1 prefix for this transport fixture.
        client = Client(
            REMOTE_ADDR=str(
                ipaddress.IPv6Address((0x20010DB8 << 96) | (uuid.uuid4().int & ((1 << 96) - 1)))
            )
        )
        response = client.get("/students", HTTP_AUTHORIZATION=f"Bearer {access}")
        assert response.status_code == 200
        assert response.json()["students"][0]["principal"] is True
        payload = {
            "student_id": str(scope["student"]),
            "name": "Synthetic",
            "document": "TEST-123",
            "photo": photo(),
        }
        response = client.post(
            "/caregivers",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        assert response.status_code == 200
        cg = response.json()["id"]
        image = client.get(f"/caregivers/{cg}/photo", HTTP_AUTHORIZATION=f"Bearer {access}")
        assert image.status_code == 200 and image["Content-Type"] == "image/jpeg"
        assert "no-store" in image["Cache-Control"]
        assert client.get(f"/caregivers/{cg}/photo").status_code == 401
        for role in ["GUARDIA", "ADMIN_ESCUELA", "ADMIN_SISTEMA"]:
            token, _, _ = login(scope["accounts"][role], "mobile" if role == "GUARDIA" else "web")
            assert client.get("/students", HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 401
        response = client.post(
            "/caregivers",
            json.dumps({**payload, "photo": base64.b64encode(b"not an image").decode()}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        assert response.status_code == 400


def test_sensitive_mfa_age_is_checked_inside_sql() -> None:
    scope = roster()
    policy(scope)
    access, _, _ = login(scope["accounts"]["PADRE"])
    # Use migrator only to advance the fixture's auth age, never application permissions.
    import os

    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as db:
        db.execute("SET ROLE retiro_evidence_writer")
        db.execute(
            "UPDATE identity_session SET authenticated_at=now()-interval '6 minutes' "
            "WHERE access_hash=%s",
            (digest(access),),
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        caregiver(access, scope)


def test_existing_parent_can_import_another_child_without_rebinding_identity() -> None:
    first = batch()
    import_batch(first)
    token = issue(first)
    sub = redeem(first, token)
    second = batch(
        {
            "school": uuid.UUID(first["school_id"]),
            "site": uuid.UUID(first["students"][0]["site_id"]),
        }
    )
    second["parents"] = first["parents"]
    for link, parent in zip(second["links"], first["parents"], strict=True):
        link["parent_id"] = parent["id"]
    import_batch(second)
    with connect("importer") as db:
        assert db.execute(
            "SELECT count(*) FROM school_roster_link WHERE parent_id=%s",
            (first["parents"][0]["id"],),
        ).fetchone() == (2,)
        assert db.execute(
            "SELECT a.subject FROM identity_account a "
            "JOIN school_roster_parent p ON p.account_id=a.id WHERE p.id=%s",
            (first["parents"][0]["id"],),
        ).fetchone() == (sub,)


def test_activation_transport_uses_pkce_and_contact_from_provider_only() -> None:
    from authorization import urls
    from identity.models import LoginRequest
    from identity.oidc import Provider, VerifiedIdentity

    from tests.integration.test_e1_identity import pending_login

    data = batch()
    import_batch(data)
    invite = issue(data)
    state, binding, verifier = pending_login()
    LoginRequest.objects.filter(state_hash=digest(state)).update(purpose="activate")
    body = {
        "state": state,
        "exchange_key": binding,
        "code": "one-use-code",
        "code_verifier": verifier,
        "invitation": invite,
    }
    with override_settings(ROOT_URLCONF=urls), patch.object(Provider, "configured") as provider:
        provider.return_value.exchange.return_value = VerifiedIdentity(
            "https://idp.example",
            str(uuid.uuid4()),
            int(datetime.now(UTC).timestamp()),
            data["parents"][0]["contact"],
        )
        client = Client(
            REMOTE_ADDR=str(
                ipaddress.IPv6Address((0x20010DB8 << 96) | (uuid.uuid4().int & ((1 << 96) - 1)))
            )
        )
        # A caller-supplied verified contact is rejected before code redemption.
        response = client.post(
            "/activation/redeem",
            json.dumps({**body, "email_verified": True}),
            content_type="application/json",
        )
        assert response.status_code == 401
        provider.return_value.exchange.assert_not_called()
        response = client.post(
            "/activation/redeem", json.dumps(body), content_type="application/json"
        )
        assert response.status_code == 200 and response.json() == {"status": "activated"}
        assert (
            client.post(
                "/activation/redeem", json.dumps(body), content_type="application/json"
            ).status_code
            == 401
        )


def test_activation_without_verified_provider_contact_never_binds() -> None:
    from authorization import urls
    from identity.models import LoginRequest
    from identity.oidc import Provider, VerifiedIdentity

    from tests.integration.test_e1_identity import pending_login

    data = batch()
    import_batch(data)
    invite = issue(data)
    state, binding, verifier = pending_login()
    LoginRequest.objects.filter(state_hash=digest(state)).update(purpose="activate")
    body = {
        "state": state,
        "exchange_key": binding,
        "code": "one-use-code",
        "code_verifier": verifier,
        "invitation": invite,
    }
    with override_settings(ROOT_URLCONF=urls), patch.object(Provider, "configured") as provider:
        provider.return_value.exchange.return_value = VerifiedIdentity(
            "https://idp.example", str(uuid.uuid4()), int(datetime.now(UTC).timestamp())
        )
        assert (
            Client()
            .post("/activation/redeem", json.dumps(body), content_type="application/json")
            .status_code
            == 401
        )
    with connect("importer") as db:
        assert db.execute(
            "SELECT account_id FROM school_roster_parent WHERE id=%s", (data["parents"][0]["id"],)
        ).fetchone() == (None,)


def test_expiry_boundary_and_technical_invitation_revoke() -> None:
    import os

    data = batch()
    import_batch(data)
    invite = issue(data)
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as db:
        db.execute("SET ROLE retiro_evidence_writer")
        db.execute(
            "UPDATE identity_invitation SET expires_at=clock_timestamp() WHERE token_hash=%s",
            (digest(invite),),
        )
    with pytest.raises(psycopg.errors.InvalidAuthorizationSpecification):
        redeem(data, invite)
    invite = issue(data)
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as db:
        db.execute("SET ROLE retiro_evidence_writer")
        ident = db.execute(
            "SELECT id FROM identity_invitation WHERE token_hash=%s", (digest(invite),)
        ).fetchone()[0]
    technical("REVOKE_INVITATION", {}, data["school_id"], ident)
    with pytest.raises(psycopg.errors.InvalidAuthorizationSpecification):
        redeem(data, invite)


def test_concurrent_same_command_and_principal_change_serialization() -> None:
    scope = roster()
    policy(scope)
    access, _, _ = login(scope["accounts"]["PADRE"])
    payload = {
        "student_id": str(scope["student"]),
        "name": "Synthetic",
        "document": "SYNTHETIC-123",
        "photo": photo(),
    }
    key = uuid.uuid4()
    with ThreadPoolExecutor(max_workers=10) as pool:
        ids = list(
            pool.map(lambda _: command(access, "CREATE_CAREGIVER", payload, key)["id"], range(20))
        )
    assert len(set(ids)) == 1
    # A queued old session rechecks the principal after acquiring the student lock.
    with connect("importer") as db, db.transaction():
        db.execute(
            "SELECT id FROM school_roster_student WHERE id=%s FOR UPDATE", (scope["student"],)
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            queued = pool.submit(command, access, "CREATE_CAREGIVER", payload)
            db.execute(
                "SELECT e2_technical('CHANGE_PRINCIPAL',%s,%s,%s,%s::jsonb,"
                "'operator','approval','synthetic race')",
                (
                    uuid.uuid4(),
                    scope["school"],
                    scope["student"],
                    json.dumps({"parent_id": str(scope["secondary"])}),
                ),
            )
            db.execute("COMMIT")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                queued.result(timeout=5)


def test_policy_revoke_and_personnel_deactivation_are_audited_and_idempotent() -> None:
    scope = roster()
    policy(scope)
    access, _, _ = login(scope["accounts"]["PADRE"])
    cg = caregiver(access, scope)
    au = command(
        access,
        "CREATE_AUTHORIZATION",
        {"student_id": str(scope["student"]), "caregiver_id": cg, "schedule": tomorrow()},
    )["id"]
    command(access, "REVOKE_AUTHORIZATION", {"student_id": str(scope["student"]), "id": au})
    key = uuid.uuid4()
    technical(
        "SET_POLICY",
        {"windows": windows(), "blocked": True},
        scope["school"],
        scope["student"],
        key,
    )
    technical(
        "SET_POLICY",
        {"windows": windows(), "blocked": True},
        scope["school"],
        scope["student"],
        key,
    )
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        technical(
            "SET_POLICY",
            {"windows": windows(), "blocked": False},
            scope["school"],
            scope["student"],
            key,
        )
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        technical(
            "CHANGE_PRINCIPAL",
            {"parent_id": str(scope["secondary"])},
            scope["school"],
            scope["student"],
            key,
        )
    access, _, _ = login(scope["accounts"]["PADRE"])
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        command(
            access,
            "CREATE_AUTHORIZATION",
            {"student_id": str(scope["student"]), "caregiver_id": cg, "schedule": tomorrow()},
        )
    target = uuid.uuid4()
    technical(
        "PROVISION",
        {
            "role": "GUARDIA",
            "issuer": "https://idp.example",
            "subject": str(target),
            "site_id": str(scope["site"]),
        },
        scope["school"],
        target,
    )
    guard, _, _ = login(target)
    technical("DEACTIVATE", {}, scope["school"], target)
    with connect() as db:
        assert db.execute("SELECT e1_authenticate(%s,true)", (digest(guard),)).fetchone() == (None,)


def test_e2_rls_and_free_writes_are_denied_to_every_application_role() -> None:
    for role in ["runtime", "system_read", "school_read", "archiver", "notifier", "importer"]:
        with connect(role) as db:
            for table in [
                "authorization_caregiver",
                "authorization_authorization",
                "authorization_command",
                "authorization_policy",
                "school_roster_enrollment",
                "school_roster_importbatch",
                "identity_invitation",
            ]:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    db.execute(f"SELECT * FROM {table}")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    db.execute(
                        f"UPDATE {table} SET id=gen_random_uuid()"
                        if table not in ["authorization_policy", "school_roster_enrollment"]
                        else f"DELETE FROM {table}"
                    )
                assert db.execute(
                    "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                    "WHERE oid=%s::regclass",
                    (table,),
                ).fetchone() == (True, True)


def test_e2_contract_validates_actual_student_family_and_command_responses() -> None:
    from pathlib import Path

    import yaml
    from authorization import urls
    from jsonschema import Draft202012Validator

    scope = roster()
    policy(scope)
    access, _, _ = login(scope["accounts"]["PADRE"])
    spec = yaml.safe_load(Path("tests/contracts/openapi.yaml").read_text())

    def validate(name: str, payload: Any) -> None:
        Draft202012Validator(
            {"$ref": "#/components/schemas/" + name, "components": spec["components"]}
        ).validate(payload)

    with override_settings(ROOT_URLCONF=urls):
        client = Client(HTTP_AUTHORIZATION=f"Bearer {access}")
        validate("Students", client.get("/students").json())
        response = client.post(
            "/caregivers",
            json.dumps(
                {
                    "student_id": str(scope["student"]),
                    "name": "Synthetic",
                    "document": "SYNTHETIC-123",
                    "photo": photo(),
                }
            ),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        assert response.status_code == 200
        validate("Applied", response.json())
        validate("Family", client.get(f"/students/{scope['student']}/family").json())
