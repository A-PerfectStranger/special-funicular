"""AT04/05 integration of the command boundary and Django BFF; IdP adapter mocked."""

import secrets
import uuid
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from django.db import transaction
from django.test import Client, override_settings
from django.utils import timezone
from identity import services
from identity.models import LoginRequest
from identity.oidc import IdentityRejected, Provider, VerifiedIdentity, pkce_challenge, sha256

from tests.integration.e1_support import digest, login, roster

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def runtime_database(django_db_blocker: Any) -> Any:
    # No migration-owner test DB, no flush of immutable evidence.
    with django_db_blocker.unblock():
        yield


def verified(aid: uuid.UUID) -> VerifiedIdentity:
    return VerifiedIdentity("https://idp.example", str(aid), int(timezone.now().timestamp()))


def pending_login(channel: str = "mobile") -> tuple[str, str, str]:
    verifier, binding, state = (secrets.token_urlsafe(32) for _ in range(3))
    LoginRequest.objects.create(
        state_hash=sha256(state),
        binding_hash=sha256(binding),
        nonce="server-nonce",
        challenge=pkce_challenge(verifier),
        channel=channel,
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    return state, binding, verifier


def test_callback_one_use_pkce_binding_and_claimed_role_ignored() -> None:
    data = roster()
    state, binding, verifier = pending_login()
    with patch.object(Provider, "configured") as provider:
        provider.return_value.exchange.return_value = verified(data["accounts"]["PADRE"])
        with pytest.raises(IdentityRejected):
            services.finish_login(state, "wrong-binding", "code", verifier, "mobile")
        with pytest.raises(IdentityRejected):
            services.finish_login(state, binding, "code", "a" * 43, "mobile")
        result = services.finish_login(state, binding, "code", verifier, "mobile")
        assert services.authenticate(result["access_token"]).role == "PADRE"
        with pytest.raises(IdentityRejected):
            services.finish_login(state, binding, "replay", verifier, "mobile")
        assert provider.return_value.exchange.call_count == 1


@pytest.mark.parametrize(
    "channel,role", [("web", "PADRE"), ("mobile", "ADMIN_SISTEMA"), ("web", None)]
)
def test_verified_idp_identity_still_needs_local_account_and_channel(
    channel: str, role: str | None
) -> None:
    data = roster()
    state, binding, verifier = pending_login(channel)
    account = data["accounts"][role] if role else uuid.uuid4()
    with patch.object(Provider, "configured") as provider:
        provider.return_value.exchange.return_value = verified(account)
        with pytest.raises(IdentityRejected):
            services.finish_login(state, binding, "code", verifier, channel)


def test_entrypoint_five_failures_block_fifteen_minutes_per_origin() -> None:
    key = services.bucket("login", "synthetic-account", str(uuid.uuid4()))
    for _ in range(5):
        services.check_limit(key)
        services.failed_entry(key)
    with pytest.raises(IdentityRejected):
        services.check_limit(key)
    services.check_limit(services.bucket("login", "synthetic-account", "other-origin"))
    services.check_limit(services.bucket("refresh", "synthetic-account", "same-origin"))
    with patch(
        "identity.services.timezone.now", return_value=timezone.now() + timedelta(minutes=16)
    ):
        services.check_limit(key)


def test_mfa_recency_and_logout_revokes_refresh() -> None:
    data = roster()
    access, refresh, _ = login(data["accounts"]["PADRE"])
    account = services.authenticate(access)
    account.require_recent_mfa()
    with patch(
        "identity.services.timezone.now", return_value=timezone.now() + timedelta(minutes=6)
    ):
        with pytest.raises(IdentityRejected):
            account.require_recent_mfa()
    services.logout(refresh)
    with pytest.raises(IdentityRejected):
        services.authenticate(access)
    with pytest.raises(IdentityRejected):
        services.refresh(refresh)


def test_logout_with_pre_rotation_credential_revokes_the_current_session() -> None:
    data = roster()
    access, refresh, _ = login(data["accounts"]["PADRE"])
    rotated = services.refresh(refresh)
    assert services.authenticate(rotated["access_token"]).role == "PADRE"
    # A response can be lost, or refresh can win a race with device logout.
    services.logout(refresh)
    with pytest.raises(IdentityRejected):
        services.authenticate(rotated["access_token"])
    with pytest.raises(IdentityRejected):
        services.refresh(rotated["refresh_token"])


def test_rls_session_context_rolls_back_after_exception() -> None:
    data = roster()
    access, _, _ = login(data["accounts"]["PADRE"])
    with pytest.raises(ValueError), transaction.atomic():
        services.scalar("SELECT set_config('app.session_hash',%s,true)", (sha256(access),))
        assert services.scalar("SELECT count(*) FROM school_roster_student", ()) == 1
        raise ValueError()
    assert services.scalar("SELECT count(*) FROM school_roster_student", ()) == 0


@override_settings(ROOT_URLCONF="identity.urls", E1_IDENTITY_ENABLED=True)
def test_web_login_csrf_and_cookie_security() -> None:
    client = Client(enforce_csrf_checks=True)
    response = client.get("/auth/login", secure=True)
    assert response.status_code == 200
    assert response["Referrer-Policy"] == "same-origin"
    assert client.post("/auth/login", secure=True).status_code == 403
    with patch(
        "identity.services.begin_login",
        return_value={
            "authorization_url": "https://idp.example/authorize",
            "state": "s" * 43,
        },
    ):
        response = client.post(
            "/auth/login",
            secure=True,
            HTTP_REFERER="https://testserver/auth/login",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
    assert response.status_code == 302
    cookie = response.cookies["sessionid"]
    assert cookie["secure"] and cookie["httponly"] and cookie["samesite"] == "Lax"
    assert "identity_secret" not in client.session


@override_settings(ROOT_URLCONF="identity.urls")
def test_mobile_bearer_and_web_role_separation() -> None:
    data = roster()
    token, _, _ = login(data["accounts"]["GUARDIA"])
    client = Client()
    assert client.get("/v1/me", secure=True).status_code == 401
    response = client.get("/v1/me", secure=True, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    assert response.json()["role"] == "GUARDIA"
    assert (
        client.get(
            "/v1/system/school-access-records", secure=True, HTTP_AUTHORIZATION=f"Bearer {token}"
        ).status_code
        == 403
    )
    assert (
        client.get("/portal/", secure=True, HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 403
    )
    assert (
        client.post(
            "/v1/auth/logout",
            data={"refresh_token": "z" * 43},
            content_type="application/json",
            secure=True,
        ).status_code
        == 200
    )


def test_school_login_fails_closed_without_receipt_and_late_archive_does_not_enable() -> None:
    data = roster()
    access, _, meta = login(data["accounts"]["ADMIN_ESCUELA"], "web")
    with pytest.raises(IdentityRejected):
        services.authenticate(access)

    assert services.scalar("SELECT e1_enable_school_session(%s)", (digest(access),)) is False
    # Advance only this operational session using the no-login owner via the migration role.
    # Test clock injection must not grant any such capability to runtime.
    from os import environ

    import psycopg

    with psycopg.connect(environ["MIGRATION_DATABASE_URL"], autocommit=True) as owner:
        owner.execute("SET ROLE retiro_evidence_writer")
        owner.execute(
            "UPDATE identity_session SET protection_deadline=clock_timestamp()-interval '1 second' "
            "WHERE id=%s",
            (meta["session_id"],),
        )
    assert services.scalar("SELECT e1_enable_school_session(%s)", (digest(access),)) is False
    with pytest.raises(IdentityRejected):
        services.authenticate(access)


@override_settings(ROOT_URLCONF="identity.urls")
def test_identity_contract_and_isolated_system_date_filter() -> None:
    import os
    from pathlib import Path

    import yaml
    from jsonschema import Draft202012Validator, FormatChecker

    spec = yaml.safe_load(Path("tests/contracts/openapi.yaml").read_text())

    def validate(name: str, value: Any) -> None:
        Draft202012Validator(
            {"$ref": f"#/components/schemas/{name}", "components": spec["components"]},
            format_checker=FormatChecker(),
        ).validate(value)

    data = roster()
    token, _, _ = login(data["accounts"]["PADRE"])
    response = Client().get("/v1/me", secure=True, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    validate("Me", response.json())
    login(data["accounts"]["ADMIN_ESCUELA"], "web")
    token, _, _ = login(data["accounts"]["ADMIN_SISTEMA"], "web")
    client = Client()
    session = client.session
    session["identity_secret"] = token
    session.save()
    with patch.dict(
        os.environ,
        {
            "SYSTEM_READ_DATABASE_URL": (
                "postgresql://retiro_system_read:synthetic-system-read-only@127.0.0.1:5432/"
                + os.environ.get("PGDATABASE", "retiro")
            )
        },
    ):
        response = client.get(
            "/v1/system/school-access-records",
            {"school": str(data["school"]), "limit": 1},
            secure=True,
        )
        assert response.status_code == 200 and len(response.json()["records"]) == 1
        validate("AccessPage", response.json())
        response = client.get(
            "/v1/system/school-access-records",
            {"school": str(data["school"]), "from": "2099-01-01"},
            secure=True,
        )
        assert response.status_code == 200 and response.json()["records"] == []
        response = client.get("/v1/system/school-access-records", {"limit": "invalid"}, secure=True)
        assert response.status_code == 400
        validate("Error", response.json())
