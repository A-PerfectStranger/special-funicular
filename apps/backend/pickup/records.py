"""RF03/13: bounded read projections, shared by JSON and Django templates."""

import os
import uuid
from datetime import date
from typing import Any
from urllib.parse import urlencode

import psycopg
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from identity import services
from identity.oidc import sha256
from identity.views import principal, web_secret

from pickup.views import endpoint


@require_GET
def capabilities(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"operations_enabled": True})


def filters(request: HttpRequest) -> tuple[Any, ...]:
    if set(request.GET) - {"limit", "before", "student", "from", "to"} or any(
        len(request.GET.getlist(key)) != 1 for key in request.GET
    ):
        raise ValueError()
    maximum = int(request.GET.get("limit", "25"))
    before = int(request.GET["before"]) if request.GET.get("before") else None
    student = uuid.UUID(request.GET["student"]) if request.GET.get("student") else None
    since = date.fromisoformat(request.GET["from"]) if request.GET.get("from") else None
    until = date.fromisoformat(request.GET["to"]) if request.GET.get("to") else None
    if not 1 <= maximum <= 100 or (before is not None and before < 1):
        raise ValueError()
    if since and until and since > until:
        raise ValueError()
    return maximum, before, student, since, until


def read_school(request: HttpRequest) -> dict[str, Any]:
    account = principal(request)
    if account.role != "ADMIN_ESCUELA" or account.channel != "web":
        raise PermissionDenied()
    args = filters(request)
    dsn = os.environ.get("SCHOOL_READ_DATABASE_URL", "")
    password = os.environ.get("SCHOOL_READ_PASSWORD", "")
    if not dsn and not password:
        raise DatabaseError("BLOCKED: isolated school reader required")
    db = (
        psycopg.connect(dsn, connect_timeout=3)
        if dsn
        else psycopg.connect(user="retiro_school_read", password=password, connect_timeout=3)
    )
    with db:
        if db.execute("SELECT current_user").fetchone() != ("retiro_school_read",):
            raise PermissionDenied()
        from django.conf import settings

        if (
            settings.APP_ENV in {"staging", "production"}
            and db.info.get_parameters().get("sslmode") != "verify-full"
        ):
            raise DatabaseError("BLOCKED: verified school reader TLS required")
        db.execute("SELECT set_config('app.session_hash',%s,true)", (sha256(web_secret(request)),))
        row = db.execute("SELECT public.e4_school_records(%s,%s,%s,%s,%s)", args).fetchone()
        if not row:
            raise DatabaseError("School projection unavailable")
        result: dict[str, Any] = row[0]
    return result


@require_GET
@endpoint
def school_records(request: HttpRequest) -> JsonResponse:
    return JsonResponse(read_school(request))


@require_GET
@endpoint
def parent_records(request: HttpRequest) -> JsonResponse:
    args = filters(request)
    with transaction.atomic():
        account = principal(request)
        if account.role != "PADRE" or account.channel != "mobile":
            raise PermissionDenied()
        result = services.scalar("SELECT public.e4_parent_records(%s,%s,%s,%s,%s)", args)
    return JsonResponse(result)


def school_page(request: HttpRequest) -> HttpResponse:
    result = read_school(request)
    students = {item["student_id"]: item["student_name"] for item in result["records"]}
    if request.GET.get("student") and request.GET["student"] not in students:
        students[request.GET["student"]] = "Estudiante seleccionado"
    query = request.GET.copy()
    query["before"] = str(result["next_cursor"])
    return render(
        request,
        "pickup/school_records.html",
        {**result, "filters": request.GET, "students": students, "next_query": urlencode(query)},
    )
