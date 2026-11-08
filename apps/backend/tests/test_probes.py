from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError
from django.test import Client


def test_public_surface_is_technical_only() -> None:
    client = Client()
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/v1/capabilities").json() == {
        "api_version": "v1",
        "pickup_enabled": False,
    }
    for path in [
        "/admin/",
        "/v1/guard/confirm-pickup",
        "/v1/me/students",
        "/v1/students",
        "/v1/family/capabilities",
        "/v1/activation/redeem",
    ]:
        assert client.get(path).status_code == 404
    assert "Retiros deshabilitados" in client.get("/").content.decode()


def test_readiness_fails_without_leaking_database_error() -> None:
    with patch("core.views.connection.cursor", side_effect=OperationalError("sensitive-dsn")):
        response = Client().get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert b"sensitive" not in response.content


def test_probes_reject_writes_and_disable_cache() -> None:
    client = Client()
    for path in ["/health/live", "/health/ready", "/v1/capabilities"]:
        assert client.post(path).status_code == 405
    response = client.get("/health/live")
    assert response["Cache-Control"] == "no-store"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response["Content-Security-Policy"]


def test_worker_cannot_claim_to_process_unimplemented_outbox() -> None:
    output = StringIO()
    call_command("runworker", "--check", stdout=output)
    assert "worker_handlers=0" in output.getvalue()
    with pytest.raises(CommandError, match="BLOCKED"):
        call_command("runworker")
