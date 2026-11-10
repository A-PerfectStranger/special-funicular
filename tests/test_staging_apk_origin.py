"""A staging APK must embed the verified release origin, not a retired bootstrap hint."""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.verify_staging_apk import verify

ORIGIN = "https://current.ecs.us-east-1.on.aws"
OLD = "https://retired.ecs.us-east-1.on.aws"


def apk(path: Path, origin: str = ORIGIN) -> Path:
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr(
            "assets/index.android.bundle", origin + " retiro-seguro-staging://auth/callback"
        )
        bundle.writestr(
            "AndroidManifest.xml",
            "org.retiroseguro.staging retiro-seguro-staging".encode("utf-16-le"),
        )
    return path


def test_verified_origin_passes_without_reading_a_bootstrap_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STAGING_RELEASE_ORIGIN", ORIGIN)
    monkeypatch.setenv("EXPO_PUBLIC_API_URL", ORIGIN)
    verify(apk(tmp_path / "valid.apk"))


@pytest.mark.parametrize("environment,bundle", [(OLD, OLD), (ORIGIN, OLD)])
def test_stale_environment_or_bundle_cannot_pass(
    environment: str,
    bundle: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("STAGING_RELEASE_ORIGIN", ORIGIN)
    monkeypatch.setenv("EXPO_PUBLIC_API_URL", environment)
    with pytest.raises(RuntimeError):
        verify(apk(tmp_path / "stale.apk", bundle))


def test_module_entrypoint_used_by_the_real_build_is_importable(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.verify_staging_apk", str(apk(tmp_path / "cli.apk"))],
        env={**os.environ, "STAGING_RELEASE_ORIGIN": ORIGIN, "EXPO_PUBLIC_API_URL": ORIGIN},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0 and "Actual staging APK" in result.stdout
