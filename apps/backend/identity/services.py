"""Identity command boundary: local scope, one-time correlation, server-side sessions."""

import hashlib
import hmac
import json
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from identity.models import EntryLimit, LoginRequest
from identity.oidc import IdentityRejected, Provider, pkce_challenge, sha256


@dataclass(frozen=True)
class Principal:
    account_id: uuid.UUID
    role: str
    school_id: uuid.UUID | None
    site_id: uuid.UUID | None
    session_id: uuid.UUID
    authenticated_at: datetime
    channel: str

    @classmethod
    def from_row(cls, data: dict[str, Any]) -> "Principal":
        return cls(
            uuid.UUID(data["account_id"]),
            data["role"],
            uuid.UUID(data["school_id"]) if data["school_id"] else None,
            uuid.UUID(data["site_id"]) if data["site_id"] else None,
            uuid.UUID(data["session_id"]),
            datetime.fromisoformat(data["authenticated_at"]),
            data["channel"],
        )

    def require_recent_mfa(self) -> None:
        if not timezone.now() - timedelta(minutes=5) <= self.authenticated_at <= timezone.now():
            raise IdentityRejected()


def scalar(sql: str, params: tuple[Any, ...]) -> Any:
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if row and cursor.description and cursor.description[0].type_code == 3802:
            # Django leaves jsonb textual for its ORM JSONField converter.
            return json.loads(row[0]) if isinstance(row[0], str) else row[0]
        return row[0] if row else None


def authenticate(secret: str, touch: bool = True) -> Principal:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", secret):
        raise IdentityRejected()
    data = scalar("SELECT public.e1_authenticate(%s,%s)", (sha256(secret), touch))
    if not data:
        raise IdentityRejected()
    return Principal.from_row(data)


def bucket(entry: str, account: str, origin: str) -> str:
    # A guessed username never blocks the account globally or another point of entry.
    return hmac.new(
        settings.SECRET_KEY.encode(), f"{entry}\0{account}\0{origin}".encode(), hashlib.sha256
    ).hexdigest()


def check_limit(key: str) -> None:
    limit = EntryLimit.objects.filter(key=key).first()
    if limit and limit.blocked_until and limit.blocked_until > timezone.now():
        raise IdentityRejected()


def failed_entry(key: str) -> None:
    now = timezone.now()
    with transaction.atomic():
        EntryLimit.objects.get_or_create(key=key, defaults={"window_started_at": now})
        limit = EntryLimit.objects.select_for_update().get(key=key)
        if now - limit.window_started_at >= timedelta(minutes=15):
            limit.window_started_at, limit.failures, limit.blocked_until = now, 0, None
        limit.failures += 1
        if limit.failures >= 5:
            limit.blocked_until = now + timedelta(minutes=15)
        limit.save()
        scalar("SELECT public.e1_login_failed(%s,%s)", (key, uuid.uuid4()))


def begin_login(
    channel: str, challenge: str, binding: str, principal: Principal | None = None
) -> dict[str, str]:
    if channel not in {"web", "mobile"} or not re.fullmatch(r"[A-Za-z0-9_-]{43}", challenge):
        raise IdentityRejected()
    provider = Provider.configured()
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    authorization_url = provider.authorize_url(channel, state, nonce, challenge)
    LoginRequest.objects.create(
        state_hash=sha256(state),
        binding_hash=sha256(binding),
        nonce=nonce,
        challenge=challenge,
        channel=channel,
        purpose="reauth" if principal else "login",
        session_id=principal.session_id if principal else None,
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    return {"authorization_url": authorization_url, "state": state}


def consume_login(state: str, binding: str, verifier: str, channel: str) -> LoginRequest:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", state) or not re.fullmatch(
        r"[A-Za-z0-9._~-]{43,128}", verifier
    ):
        raise IdentityRejected()
    with transaction.atomic():
        login = LoginRequest.objects.select_for_update().filter(state_hash=sha256(state)).first()
        if (
            not login
            or login.consumed_at
            or login.expires_at <= timezone.now()
            or login.channel != channel
            or not hmac.compare_digest(login.binding_hash, sha256(binding))
            or not hmac.compare_digest(login.challenge, pkce_challenge(verifier))
        ):
            raise IdentityRejected()
        login.consumed_at = timezone.now()
        login.save(update_fields=["consumed_at"])
        return login


def finish_login(
    state: str, binding: str, code: str, verifier: str, channel: str
) -> dict[str, Any]:
    if not 1 <= len(code) <= 4096:
        raise IdentityRejected()
    login = consume_login(state, binding, verifier, channel)
    verified = Provider.configured().exchange(channel, code, verifier, login.nonce)
    authenticated_at = datetime.fromtimestamp(verified.authenticated_at, UTC)
    if login.purpose == "reauth":
        if not scalar(
            "SELECT public.e1_reauthenticate(%s,%s,%s,%s)",
            (login.id, verified.issuer, verified.subject, authenticated_at),
        ):
            raise IdentityRejected()
        return {"reauthenticated": True}
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    data = scalar(
        "SELECT public.e1_open_session(%s,%s,%s,%s,%s,%s)",
        (
            login.id,
            verified.issuer,
            verified.subject,
            sha256(access),
            sha256(refresh),
            authenticated_at,
        ),
    )
    if data["role"] == "ADMIN_ESCUELA":
        # A separate archive process must finish before the original five-second deadline.
        # No network call occurs while holding a SQL lock.
        return {
            **data,
            "access_token": access,
            "refresh_token": refresh,
            "pending_protection": True,
        }
    return {**data, "access_token": access, "refresh_token": refresh, "expires_in": 300}


def refresh(secret: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", secret):
        raise IdentityRejected()
    access, refresh_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    if not scalar(
        "SELECT public.e1_refresh(%s,%s,%s)",
        (sha256(secret), sha256(access), sha256(refresh_token)),
    ):
        raise IdentityRejected()
    return {"access_token": access, "refresh_token": refresh_token, "expires_in": 300}


def logout(secret: str) -> None:
    scalar("SELECT public.e1_logout(%s)", (sha256(secret),))
