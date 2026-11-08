"""Web BFF and mobile transport. Authorization remains in shared services/SQL."""

import ipaddress
import json
import os
import secrets
import time
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from datetime import time as date_time
from functools import wraps
from typing import Any

import psycopg
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from identity import services
from identity.oidc import IdentityRejected, pkce_challenge, sha256


def origin(request: HttpRequest) -> str:
    from django.conf import settings

    value = request.META.get("REMOTE_ADDR", "")
    if settings.TRUSTED_INGRESS == "ecs-express":
        # ALB appends the real origin at the right, after any user-supplied values.
        value = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return "unknown"


def error(status: int = 401) -> JsonResponse:
    code = (
        "unavailable" if status == 503 else "invalid_request" if status == 400 else "access_denied"
    )
    return JsonResponse({"error": code}, status=status)


def safe_endpoint(
    function: Callable[[HttpRequest], HttpResponse],
) -> Callable[[HttpRequest], HttpResponse]:
    @wraps(function)
    def guarded(request: HttpRequest) -> HttpResponse:
        try:
            return function(request)
        except IdentityRejected:
            return error()
        except (ValueError, TypeError, KeyError):
            return error(400)
        except (DatabaseError, psycopg.Error):
            return error(503)

    return guarded


def body(request: HttpRequest) -> dict[str, Any]:
    if len(request.body) > 8192 or request.content_type != "application/json":
        raise IdentityRejected()
    data = json.loads(request.body)
    if not isinstance(data, dict) or any(not isinstance(value, str) for value in data.values()):
        raise IdentityRejected()
    return data


def bearer(request: HttpRequest) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise IdentityRejected()
    return header[7:]


def web_secret(request: HttpRequest) -> str:
    secret = request.session.get("identity_secret")
    if not isinstance(secret, str):
        raise IdentityRejected()
    return secret


def principal(request: HttpRequest) -> services.Principal:
    token = bearer(request) if request.headers.get("Authorization") else web_secret(request)
    account = services.authenticate(token)
    if request.headers.get("Authorization") and account.channel != "mobile":
        raise IdentityRejected()
    if not request.headers.get("Authorization") and account.channel != "web":
        raise IdentityRejected()
    return account


@csrf_exempt
@require_POST
@safe_endpoint
def mobile_start(request: HttpRequest) -> JsonResponse:
    data = body(request)
    key = services.bucket("mobile-login", "", origin(request))
    services.check_limit(key)
    try:
        existing = principal(request) if data.get("purpose") == "reauth" else None
        binding = secrets.token_urlsafe(32)
        activate = data.get("purpose") == "activate"
        from django.conf import settings

        if activate and not settings.E2_FAMILY_ENABLED:
            raise IdentityRejected()
        result = services.begin_login("mobile", data["code_challenge"], binding, existing, activate)
        return JsonResponse({**result, "exchange_key": binding})
    except IdentityRejected:
        services.failed_entry(key)
        raise


@csrf_exempt
@require_POST
@safe_endpoint
def mobile_exchange(request: HttpRequest) -> JsonResponse:
    data = body(request)
    key = services.bucket("mobile-login", "", origin(request))
    services.check_limit(key)
    try:
        result = services.finish_login(
            data["state"], data["exchange_key"], data["code"], data["code_verifier"], "mobile"
        )
        # Only session credentials/role leave the BFF; IdP tokens are never returned.
        if result.get("reauthenticated"):
            return JsonResponse(result)
        return JsonResponse(
            {key: result[key] for key in ["access_token", "refresh_token", "expires_in", "role"]}
        )
    except (IdentityRejected, DatabaseError):
        services.failed_entry(key)
        raise IdentityRejected() from None


@csrf_exempt
@require_POST
@safe_endpoint
def mobile_refresh(request: HttpRequest) -> JsonResponse:
    key = services.bucket("mobile-refresh", "", origin(request))
    services.check_limit(key)
    try:
        return JsonResponse(services.refresh(body(request)["refresh_token"]))
    except IdentityRejected:
        services.failed_entry(key)
        raise


@csrf_exempt
@require_POST
@safe_endpoint
def mobile_logout(request: HttpRequest) -> JsonResponse:
    token = body(request).get("refresh_token") if request.body else bearer(request)
    if not isinstance(token, str) or len(token) != 43:
        raise IdentityRejected()
    services.logout(token)
    return JsonResponse({"status": "revoked"})


@require_GET
@safe_endpoint
def me(request: HttpRequest) -> JsonResponse:
    account = principal(request)
    return JsonResponse(
        {
            "role": account.role,
            "school_id": account.school_id,
            "site_id": account.site_id,
            "pickup_enabled": False,
        }
    )


@require_http_methods(["GET", "POST"])
@safe_endpoint
def web_login(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        return render(request, "identity/login.html")
    key = services.bucket("web-login", "", origin(request))
    services.check_limit(key)
    verifier, binding = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    existing = principal(request) if request.POST.get("purpose") == "reauth" else None
    result = services.begin_login("web", pkce_challenge(verifier), binding, existing)
    request.session["oidc"] = {"verifier": verifier, "binding": binding, "state": result["state"]}
    return redirect(result["authorization_url"])


def protected_school_login(result: dict[str, Any]) -> None:
    deadline = datetime.fromisoformat(result["deadline"])
    from django.utils import timezone

    while True:
        if services.scalar(
            "SELECT public.e1_enable_school_session(%s)", (sha256(result["access_token"]),)
        ):
            return
        remaining = (deadline - timezone.now()).total_seconds()
        if remaining <= 0:
            # Persist the terminal denial even when an archive receipt arrives later.
            services.scalar(
                "SELECT public.e1_enable_school_session(%s)", (sha256(result["access_token"]),)
            )
            raise IdentityRejected()
        time.sleep(min(0.05, remaining))


@require_GET
@safe_endpoint
def web_callback(request: HttpRequest) -> HttpResponse:
    key = services.bucket("web-login", "", origin(request))
    services.check_limit(key)
    pending = request.session.pop("oidc", None)
    if not pending or request.GET.get("state") != pending["state"] or request.GET.get("error"):
        services.failed_entry(key)
        raise IdentityRejected()
    try:
        result = services.finish_login(
            request.GET.get("state", ""),
            pending["binding"],
            request.GET.get("code", ""),
            pending["verifier"],
            "web",
        )
        if result.get("reauthenticated"):
            return redirect("identity-portal")
        if result.get("pending_protection"):
            protected_school_login(result)
        request.session.cycle_key()
        request.session["identity_secret"] = result["access_token"]
        return redirect("identity-portal")
    except IdentityRejected:
        services.failed_entry(key)
        raise


@require_POST
@safe_endpoint
def web_logout(request: HttpRequest) -> HttpResponse:
    services.logout(web_secret(request))
    request.session.flush()
    return redirect("identity-login")


@require_GET
@safe_endpoint
def portal(request: HttpRequest) -> HttpResponse:
    account = principal(request)
    if account.channel != "web" or account.role not in {"ADMIN_ESCUELA", "ADMIN_SISTEMA"}:
        return error(403)
    if account.role == "ADMIN_ESCUELA":
        return render(request, "identity/school.html")
    records, next_cursor = read_access_records(request)
    return render(
        request, "identity/accesses.html", {"records": records, "next_cursor": next_cursor}
    )


def read_access_records(request: HttpRequest) -> tuple[list[dict[str, Any]], int | None]:
    if principal(request).role != "ADMIN_SISTEMA":
        raise IdentityRejected()
    maximum = int(request.GET.get("limit", "25"))
    before = int(request.GET["before"]) if request.GET.get("before") else None
    school = uuid.UUID(request.GET["school"]) if request.GET.get("school") else None
    since = (
        datetime.combine(date.fromisoformat(request.GET["from"]), date_time.min, UTC)
        if request.GET.get("from")
        else None
    )
    until = (
        datetime.combine(
            date.fromisoformat(request.GET["to"]) + timedelta(days=1), date_time.min, UTC
        )
        if request.GET.get("to")
        else None
    )
    if not 1 <= maximum <= 100 or (before is not None and before < 1):
        raise IdentityRejected()
    if since and until and since >= until:
        raise ValueError("Invalid date range")
    token = web_secret(request)
    dsn = os.environ.get("SYSTEM_READ_DATABASE_URL", "")
    password = os.environ.get("SYSTEM_READ_PASSWORD")
    if not dsn and not password:
        raise IdentityRejected()
    db = (
        psycopg.connect(dsn, connect_timeout=3)
        if dsn
        else psycopg.connect(user="retiro_system_read", password=password, connect_timeout=3)
    )
    with db, db.cursor() as cursor:
        cursor.execute("SELECT current_user")
        if cursor.fetchone() != ("retiro_system_read",):
            raise IdentityRejected()
        cursor.execute("SELECT set_config('app.session_hash',%s,true)", (sha256(token),))
        # Reading and auditing commit together; failure returns no records.
        cursor.execute("SELECT public.e1_audit_access_read(%s)", (uuid.uuid4(),))
        cursor.execute(
            "SELECT * FROM public.e1_access_records(%s,%s,%s,%s,%s)",
            (maximum, before, school, since, until),
        )
        columns = [col.name for col in cursor.description or []]
        records = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    return records, int(records[-1]["sequence"]) if len(records) == maximum else None


@require_GET
@safe_endpoint
def access_records(request: HttpRequest) -> JsonResponse:
    if principal(request).role != "ADMIN_SISTEMA":
        return error(403)
    records, cursor = read_access_records(request)
    return JsonResponse({"records": records, "next_cursor": cursor})
