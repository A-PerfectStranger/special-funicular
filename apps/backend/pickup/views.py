"""E3 transport: commit the decision before waiting for a separate WORM worker."""

import base64
import json
import re
import secrets
import uuid
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any

from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from identity import services as identity
from identity.oidc import IdentityRejected, sha256
from identity.views import bearer, error, origin


def endpoint(function: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    @wraps(function)
    def guarded(request: HttpRequest, **kwargs: Any) -> HttpResponse:
        try:
            return function(request, **kwargs)
        except IdentityRejected:
            return error(401)
        except (ValueError, TypeError, KeyError, OverflowError):
            return error(400)
        except DatabaseError as exc:
            code = getattr(exc.__cause__, "sqlstate", None)
            return error(403 if code == "42501" else 400 if code in {"22023", "22P02"} else 503)

    return guarded


def body(request: HttpRequest, fields: set[str]) -> dict[str, Any]:
    if request.content_type != "application/json" or len(request.body) > 4096:
        raise ValueError()
    data = json.loads(request.body)
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError()
    return data


def instant(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError()
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError()
    return parsed


def token(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", value):
        raise ValueError()
    return sha256(value)


def command(request: HttpRequest, role: str, sql: str, params: tuple[Any, ...]) -> dict[str, Any]:
    # Retry the whole SQL transaction, including online identity. Never retry a network effect.
    for attempt in range(3):
        try:
            with transaction.atomic():
                principal = identity.authenticate(bearer(request))
                if principal.role != role or principal.channel != "mobile":
                    raise IdentityRejected()
                result: dict[str, Any] = identity.scalar(sql, params)
            return result
        except DatabaseError as exc:
            if getattr(exc.__cause__, "sqlstate", None) not in {"40001", "40P01"} or attempt == 2:
                raise
    raise RuntimeError("Unreachable")


def response(data: dict[str, Any]) -> JsonResponse:
    failure = data.get("error")
    return JsonResponse(
        data,
        status=429
        if failure == "RATE_LIMITED"
        else 403
        if failure == "DENIED"
        else 409
        if failure
        else 200,
    )


def correlation(request: HttpRequest) -> uuid.UUID:
    return uuid.UUID(request.headers.get("Idempotency-Key", ""))


def origin_hash(request: HttpRequest) -> str:
    return identity.bucket("pickup", "", origin(request))


def issue(request: HttpRequest, authorization_id: uuid.UUID, action: str) -> JsonResponse:
    data = body(request, {"valid_from", "episode_id"} if action == "RESCHEDULE" else {"valid_from"})
    secret = secrets.token_urlsafe(32)
    result = command(
        request,
        "PADRE",
        "SELECT public.e3_issue(%s,%s,%s,%s,%s,%s,%s)",
        (
            action,
            correlation(request),
            authorization_id,
            instant(data["valid_from"]),
            sha256(secret),
            uuid.UUID(data["episode_id"]) if action == "RESCHEDULE" else None,
            origin_hash(request),
        ),
    )
    if not result.get("error"):
        result["qr"] = secret if result["issued"] else None
    return response(result)


@csrf_exempt
@require_POST
@endpoint
def issue_qr(request: HttpRequest, authorization_id: uuid.UUID) -> JsonResponse:
    return issue(request, authorization_id, "ISSUE")


@csrf_exempt
@require_POST
@endpoint
def reschedule(request: HttpRequest, authorization_id: uuid.UUID) -> JsonResponse:
    return issue(request, authorization_id, "RESCHEDULE")


@csrf_exempt
@require_POST
@endpoint
def resolve(request: HttpRequest) -> JsonResponse:
    data = body(request, {"token"})
    return response(
        command(
            request,
            "GUARDIA",
            "SELECT public.e3_resolve(%s,%s,false)",
            (token(data["token"]), origin_hash(request)),
        )
    )


@csrf_exempt
@require_POST
@endpoint
def photo(request: HttpRequest) -> HttpResponse:
    data = body(request, {"token"})
    result = command(
        request,
        "GUARDIA",
        "SELECT public.e3_resolve(%s,%s,true)",
        (token(data["token"]), origin_hash(request)),
    )
    if result.get("error"):
        return response(result)
    return HttpResponse(base64.b64decode(result["photo"], validate=True), content_type="image/jpeg")


@csrf_exempt
@require_POST
@endpoint
def confirm(request: HttpRequest) -> JsonResponse:
    data = body(request, {"token", "checks"})
    if (
        not isinstance(data["checks"], dict)
        or set(data["checks"]) != {"student", "caregiver", "document"}
        or any(type(v) is not bool for v in data["checks"].values())
    ):
        raise ValueError()
    result = command(
        request,
        "GUARDIA",
        "SELECT public.e3_confirm(%s,%s,%s::jsonb)",
        (correlation(request), token(data["token"]), json.dumps(data["checks"])),
    )
    if result.get("error"):
        return response(result)
    return response(
        command(request, "GUARDIA", "SELECT public.e3_get_operation(%s)", (result["operation_id"],))
    )


@require_GET
@endpoint
def operation(request: HttpRequest, operation_id: uuid.UUID) -> JsonResponse:
    return response(
        command(request, "GUARDIA", "SELECT public.e3_get_operation(%s)", (operation_id,))
    )


@csrf_exempt
@require_POST
@endpoint
def report(request: HttpRequest, operation_id: uuid.UUID) -> JsonResponse:
    data = body(request, {"delivered", "witnessed_at", "reason"})
    if (
        type(data["delivered"]) is not bool
        or not isinstance(data["reason"], str)
        or not 1 <= len(data["reason"].strip()) <= 500
    ):
        raise ValueError()
    result = command(
        request,
        "GUARDIA",
        "SELECT public.e3_report(%s,%s,%s,%s,%s,%s)",
        (
            operation_id,
            correlation(request),
            data["delivered"],
            instant(data["witnessed_at"]),
            data["reason"],
        ),
    )
    return response(result)


@require_GET
@endpoint
def capabilities(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"pickup_enabled": True, "synthetic_only": True})
