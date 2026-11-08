"""Authenticated E2 transport. No object identifier or client claim grants a capability."""

import json
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from identity import services as identity
from identity.oidc import IdentityRejected, Provider, sha256
from identity.views import bearer, error, origin

from authorization import services


def endpoint(function: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    @wraps(function)
    def guarded(request: HttpRequest, **kwargs: Any) -> HttpResponse:
        try:
            return function(request, **kwargs)
        except IdentityRejected:
            return error(401)
        except (ValueError, TypeError, KeyError):
            return error(400)
        except DatabaseError as exc:
            code = getattr(exc.__cause__, "sqlstate", None)
            return error(
                401
                if code in {"28000", "42501"}
                else 400
                if code in {"22023", "22P02", "23505", "23514"}
                else 503
            )

    return guarded


def data(request: HttpRequest) -> dict[str, Any]:
    if len(request.body) > 420000 or request.content_type != "application/json":
        raise ValueError()
    result = json.loads(request.body)
    if not isinstance(result, dict):
        raise ValueError()
    return result


def family(request: HttpRequest) -> None:
    account = identity.authenticate(bearer(request))
    if account.role != "PADRE" or account.channel != "mobile":
        raise IdentityRejected()


@csrf_exempt
@require_POST
@endpoint
def redeem(request: HttpRequest) -> JsonResponse:
    key = identity.bucket("activation", "", origin(request))
    identity.check_limit(key)
    try:
        body = data(request)
        if (
            set(body) != {"state", "exchange_key", "code", "code_verifier", "invitation"}
            or any(not isinstance(v, str) for v in body.values())
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}", body["invitation"])
            or not 1 <= len(body["code"]) <= 4096
        ):
            raise IdentityRejected()
        login = identity.consume_login(
            body["state"], body["exchange_key"], body["code_verifier"], "mobile"
        )
        if login.purpose != "activate":
            raise IdentityRejected()
        verified = Provider.configured().exchange(
            "mobile", body["code"], body["code_verifier"], login.nonce
        )
        if not verified.verified_contact:
            raise IdentityRejected()
        with transaction.atomic():
            identity.scalar(
                "SELECT public.e2_redeem(%s,%s,%s,%s,%s,%s)",
                (
                    login.id,
                    sha256(body["invitation"]),
                    verified.issuer,
                    verified.subject,
                    verified.verified_contact,
                    datetime.fromtimestamp(verified.authenticated_at, UTC),
                ),
            )
        # A fresh ordinary login opens the session; activation itself discloses no child data.
        return JsonResponse({"status": "activated"})
    except (IdentityRejected, DatabaseError):
        identity.failed_entry(key)
        raise IdentityRejected() from None


@require_GET
@endpoint
def students(request: HttpRequest) -> JsonResponse:
    with transaction.atomic():
        family(request)
        return JsonResponse({"students": identity.scalar("SELECT public.e2_students()", ())})


@require_GET
@endpoint
def records(request: HttpRequest, student_id: uuid.UUID) -> JsonResponse:
    with transaction.atomic():
        family(request)
        return JsonResponse(identity.scalar("SELECT public.e2_family_records(%s)", (student_id,)))


@require_GET
@endpoint
def photo(request: HttpRequest, caregiver_id: uuid.UUID) -> HttpResponse:
    with transaction.atomic():
        family(request)
        raw = identity.scalar("SELECT public.e2_caregiver_photo(%s)", (caregiver_id,))
        if raw is None:
            raise IdentityRejected()
        return HttpResponse(bytes(raw), content_type="image/jpeg")


def mutate(
    request: HttpRequest, operation: str, object_id: uuid.UUID | None = None
) -> JsonResponse:
    correlation = str(uuid.UUID(request.headers.get("Idempotency-Key", "")))
    body = data(request)
    if object_id:
        if "id" in body:
            raise ValueError()
        body["id"] = str(object_id)
    with transaction.atomic():
        family(request)
        return JsonResponse(services.command(operation, correlation, body))


@csrf_exempt
@require_POST
@endpoint
def create_caregiver(request: HttpRequest) -> JsonResponse:
    return mutate(request, "CREATE_CAREGIVER")


@csrf_exempt
@require_POST
@endpoint
def update_caregiver(request: HttpRequest, caregiver_id: uuid.UUID) -> JsonResponse:
    return mutate(request, "UPDATE_CAREGIVER", caregiver_id)


@csrf_exempt
@require_POST
@endpoint
def create_authorization(request: HttpRequest) -> JsonResponse:
    return mutate(request, "CREATE_AUTHORIZATION")


@csrf_exempt
@require_POST
@endpoint
def revoke(request: HttpRequest, authorization_id: uuid.UUID) -> JsonResponse:
    return mutate(request, "REVOKE_AUTHORIZATION", authorization_id)


@require_GET
def capabilities(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"family_enabled": True, "pickup_enabled": False})
