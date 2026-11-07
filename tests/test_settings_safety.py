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
