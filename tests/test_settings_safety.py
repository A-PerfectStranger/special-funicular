import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "override",
    [
        {"DJANGO_SECRET_KEY": ""},
        {"DJANGO_ALLOWED_HOSTS": "*"},
        {"APP_ENV": "unknown"},
        {"APP_ENV": "production", "DJANGO_DEBUG": "true"},
        {"APP_ENV": "staging", "PGSSLMODE": "prefer"},
    ],
)
def test_invalid_settings_cannot_start(override: dict[str, str]) -> None:
    env = os.environ.copy()
    # Make the other cloud settings valid so each override exercises its own barrier.
    env.update(
        {
            "DJANGO_SECRET_KEY": "test-only-key-0123456789012345678901234567890123456789",
            "DJANGO_ALLOWED_HOSTS": "localhost",
            "APP_ENV": "production",
            "DJANGO_DEBUG": "false",
            "PGSSLMODE": "verify-full",
        }
    )
    env.update(override)
    result = subprocess.run(
        [sys.executable, "apps/backend/manage.py", "check"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr


def test_only_explicit_verified_ingress_can_trust_forwarded_proto() -> None:
    from django.test import Client, override_settings

    with override_settings(SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=None):
        assert Client().get("/v1/capabilities", HTTP_X_FORWARDED_PROTO="https").status_code == 301
    with override_settings(
        SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https")
    ):
        response = Client().get("/v1/capabilities", HTTP_X_FORWARDED_PROTO="https")
        assert response.status_code == 200
        assert response.json()["pickup_enabled"] is False


def test_alb_private_ip_liveness_does_not_relax_other_host_validation() -> None:
    from django.test import Client, override_settings

    with override_settings(
        ALLOWED_HOSTS=["stage.example"], SECURE_SSL_REDIRECT=True, TRUSTED_INGRESS="ecs-express"
    ):
        client = Client()
        response = client.get(
            "/health/live", HTTP_HOST="10.61.0.25:8000", HTTP_USER_AGENT="ELB-HealthChecker/2.0"
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert response["Cache-Control"] == "no-store"
        assert not response.cookies
        for path in ["/health/ready", "/v1/capabilities", "/v1/me/students"]:
            assert client.get(path, secure=True, HTTP_HOST="untrusted.example").status_code == 400
        assert (
            client.post("/health/live", secure=True, HTTP_HOST="untrusted.example").status_code
            == 400
        )
    with override_settings(ALLOWED_HOSTS=["stage.example"], TRUSTED_INGRESS=""):
        assert Client().get("/health/live", HTTP_HOST="10.61.0.25:8000").status_code == 400
