from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, ProgrammingError, connection, transaction
from django.test import Client


def test_live_never_queries_database(client: Client) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response["Cache-Control"] == "no-store"


def test_ready_database_failure_is_generic(client: Client) -> None:
    with patch("core.views.connection.cursor", side_effect=OperationalError("sensitive detail")):
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert b"sensitive" not in response.content


@pytest.mark.django_db
def test_ready_requires_all_migrations(client: Client) -> None:
    assert client.get("/health/ready").json() == {"status": "ready"}
    with patch("core.views.MigrationExecutor.migration_plan", return_value=[("pending", False)]):
        assert client.get("/health/ready").status_code == 503


@pytest.mark.django_db
def test_runtime_cannot_escalate_or_create_tables() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb "
            "FROM pg_roles WHERE rolname=current_user"
        )
        assert cursor.fetchone() == (False, False, False, False)
        cursor.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
        assert cursor.fetchone() == (False,)
    with pytest.raises(ProgrammingError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("CREATE TABLE forbidden_table (id integer)")
    with pytest.raises(ProgrammingError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("CREATE TEMPORARY TABLE forbidden_temp_table (id integer)")


def test_e0_has_no_operational_endpoints(client: Client) -> None:
    assert client.get("/v1/capabilities").json()["pickup_enabled"] is False
    for path in [
        "/admin/",
        "/v1/me/students",
        "/v1/guard/confirm-pickup",
        "/v1/school/pickup-records",
    ]:
        assert client.get(path).status_code == 404
        assert client.post(path, {}).status_code == 404
    assert client.post("/health/live").status_code == 405


def test_home_is_synthetic_and_worker_is_blocked(client: Client) -> None:
    assert "no está habilitado" in client.get("/").content.decode()
    with pytest.raises(CommandError, match="bloqueado"):
        call_command("worker")


def test_external_configuration_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import runpy

    from django.core.exceptions import ImproperlyConfigured

    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        runpy.run_path("apps/backend/config/settings.py")
    monkeypatch.setenv("DJANGO_SECRET_KEY", "x" * 64)
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "*")
    with pytest.raises(ImproperlyConfigured, match="hosts"):
        runpy.run_path("apps/backend/config/settings.py")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "synthetic.example.invalid")
    for key in ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]:
        monkeypatch.setenv(key, "synthetic-value")
    monkeypatch.setenv("DB_SSLMODE", "require")
    with pytest.raises(ImproperlyConfigured, match="verify-full"):
        runpy.run_path("apps/backend/config/settings.py")
    monkeypatch.setenv("DB_SSLMODE", "verify-full")
    config = runpy.run_path("apps/backend/config/settings.py")
    assert config["PICKUP_ENABLED"] is False
    assert config["SESSION_COOKIE_SECURE"] is True
    assert config["DEBUG"] is False
