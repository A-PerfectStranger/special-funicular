"""Runtime must not carry bootstrap/DDL secrets; commissioning stays separate."""

import pytest

from scripts.commission_staging import task_definition


def test_api_task_has_only_runtime_secrets_and_readonly_root() -> None:
    outputs = {
        k: k
        for k in [
            "DbHost",
            "DjangoSecret",
            "RuntimePassword",
            "MasterSecret",
            "MigrationPassword",
            "Logs",
            "BootstrapExecution",
            "ApiExecution",
        ]
    }
    task = task_definition(outputs, "repository@sha256:digest", "a" * 40, False)
    container = task["containerDefinitions"][0]
    assert task["executionRoleArn"] == "ApiExecution"
    assert container["readonlyRootFilesystem"] is True
    assert container["user"] == "10001:10001"
    assert {s["valueFrom"] for s in container["secrets"]} == {"RuntimePassword", "DjangoSecret"}
    env = {p["name"]: p["value"] for p in container["environment"]}
    assert env["PGUSER"] == "retiro_runtime" and env["PGSSLMODE"] == "verify-full"
    assert env["PGSSLROOTCERT"] == "/app/rds-ca.pem"
    assert "MIGRATION_DATABASE_URL" not in env
    assert task["cpu"] == "256" and task["memory"] == "512"
    assert task["containerDefinitions"][0]["portMappings"][0]["name"] == "http"


def test_migration_task_cannot_carry_root_or_runtime_secrets() -> None:
    from scripts.deploy_staging import migration_definition

    outputs = {
        k: k
        for k in [
            "DbHost",
            "DjangoSecret",
            "RuntimePassword",
            "MasterSecret",
            "MigrationPassword",
            "Logs",
            "BootstrapExecution",
            "ApiExecution",
            "MigrationExecution",
        ]
    }
    task = migration_definition(outputs, "repository@sha256:digest", "a" * 40)
    container = task["containerDefinitions"][0]
    assert task["executionRoleArn"] == "MigrationExecution"
    assert task["family"] == "retiro-staging-migrate"
    assert "portMappings" not in container
    assert {s["valueFrom"] for s in container["secrets"]} == {"MigrationPassword", "DjangoSecret"}
    assert container["command"] == ["python", "manage.py", "migrate", "--noinput"]


def test_index_provenance_selects_only_linux_amd64(monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib
    import json

    from scripts import commission_staging

    body = json.dumps(
        {
            "manifests": [
                {
                    "digest": "sha256:" + "a" * 64,
                    "platform": {"os": "linux", "architecture": "amd64"},
                },
                {
                    "digest": "sha256:" + "b" * 64,
                    "platform": {"os": "unknown", "architecture": "unknown"},
                },
                {
                    "digest": "sha256:" + "c" * 64,
                    "platform": {"os": "linux", "architecture": "arm64"},
                },
            ]
        }
    )
    root = "sha256:" + hashlib.sha256(body.encode()).hexdigest()
    monkeypatch.setattr(commission_staging, "aws", lambda *a: {"images": [{"imageManifest": body}]})
    assert commission_staging.runtime_digests(root) == {root, "sha256:" + "a" * 64}


def test_changed_manifest_bytes_cannot_attest_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import commission_staging

    monkeypatch.setattr(commission_staging, "aws", lambda *a: {"images": [{"imageManifest": "{}"}]})
    with pytest.raises(RuntimeError, match="manifest bytes"):
        commission_staging.runtime_digests("sha256:" + "a" * 64)
