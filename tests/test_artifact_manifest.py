"""The APK attestation identifies its configured origin and content-addressed custody."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.private_mobile import validate_manifest

SHA = "a" * 40
ROOT = Path(__file__).resolve().parents[1]


def test_standalone_staging_manifest_matches_private_storage_contract(tmp_path: Path) -> None:
    apk = tmp_path / f"mobile-staging-{SHA}.apk"
    apk.write_bytes(b"synthetic binary")
    firebase = tmp_path / "google-services.json"
    firebase.write_text('{"project_id":"synthetic-client-config"}')
    env = {
        **os.environ,
        "ANDROID_GOOGLE_SERVICES_FILE": str(firebase),
        "STAGING_RELEASE_ORIGIN": "https://reviewed.ecs.us-east-1.on.aws",
    }
    env.pop("PYTHONPATH", None)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/artifact_manifest.py"),
            str(apk),
            "--kind",
            "staging-apk",
            "--sha",
            SHA,
        ],
        env=env,
        cwd=tmp_path,
        check=True,
    )
    report = json.loads(apk.with_suffix(".apk.json").read_text())
    assert validate_manifest(report, SHA) == report
    assert report["sha256"] == hashlib.sha256(apk.read_bytes()).hexdigest()
    assert report["release_origin"] == env["STAGING_RELEASE_ORIGIN"]
    assert report["storage_layout"] == "sha256-v1"


@pytest.mark.parametrize(
    "origin", ["", "http://reviewed.ecs.us-east-1.on.aws", "https://foreign.invalid"]
)
def test_unreviewed_origin_cannot_produce_a_staging_manifest(tmp_path: Path, origin: str) -> None:
    apk = tmp_path / f"mobile-staging-{SHA}.apk"
    apk.write_bytes(b"synthetic binary")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/artifact_manifest.py"),
            str(apk),
            "--kind",
            "staging-apk",
            "--sha",
            SHA,
        ],
        env={**os.environ, "STAGING_RELEASE_ORIGIN": origin},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2 and not apk.with_suffix(".apk.json").exists()


def test_backend_attestation_keeps_its_existing_schema(tmp_path: Path) -> None:
    artifact = tmp_path / "backend.oci.tar"
    artifact.write_bytes(b"synthetic oci")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/artifact_manifest.py"),
            str(artifact),
            "--kind",
            "backend-oci",
            "--sha",
            SHA,
            "--digest",
            "sha256:" + "b" * 64,
        ],
        cwd=tmp_path,
        check=True,
    )
    report = json.loads(artifact.with_suffix(".tar.json").read_text())
    assert report["schema_version"] == 1 and report["oci_digest"] == "sha256:" + "b" * 64
    assert "storage_layout" not in report and "release_origin" not in report
