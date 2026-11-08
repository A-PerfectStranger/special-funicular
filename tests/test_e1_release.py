"""Credential and immutable-source boundaries for the E1 deployment adapter."""

import pytest

from scripts.e1_release import api_definition, archive_definition


def configuration() -> tuple[dict[str, str], dict[str, str]]:
    base = {
        key: key
        for key in [
            "DbHost",
            "DjangoSecret",
            "MasterSecret",
            "MigrationPassword",
            "RuntimePassword",
            "Logs",
            "BootstrapExecution",
            "ApiExecution",
        ]
    }
    config = {
        key: key
        for key in [
            "PoolId",
            "WebClientId",
            "MobileClientId",
            "ApiTaskArn",
            "ArchiveTaskArn",
            "ArchiveExecutionArn",
            "SystemReadPassword",
            "ArchivePassword",
            "Bucket",
            "EncryptionKeyArn",
            "SigningKeyArn",
        ]
    }
    config.update(
        {
            "Issuer": "https://cognito-idp.us-east-1.amazonaws.com/PoolId",
            "WebRedirect": "https://stage.ecs.us-east-1.on.aws/auth/callback",
            "MobileRedirect": "retiro-seguro-staging://auth/callback",
        }
    )
    return base, config


def test_api_worker_share_digest_but_not_credentials_or_identity() -> None:
    base, config = configuration()
    image = "synthetic@sha256:" + "a" * 64
    api = api_definition(base, config, image, "b" * 40)
    worker = archive_definition(base, config, image, "b" * 40)
    api_container, worker_container = (
        api["containerDefinitions"][0],
        worker["containerDefinitions"][0],
    )
    assert api_container["image"] == worker_container["image"] == image
    assert api["taskRoleArn"] != worker["taskRoleArn"]
    assert api["executionRoleArn"] != worker["executionRoleArn"]
    assert {item["valueFrom"] for item in api_container["secrets"]} == {
        "DjangoSecret",
        "RuntimePassword",
        "SystemReadPassword",
    }
    assert worker_container["secrets"] == [{"name": "PGPASSWORD", "valueFrom": "ArchivePassword"}]
    assert "portMappings" not in worker_container
    assert worker_container["command"][-1] == "10800"
    for definition in [api, worker]:
        container = definition["containerDefinitions"][0]
        assert container["readonlyRootFilesystem"] and container["user"] == "10001:10001"
        assert all("PASSWORD" not in item["name"] for item in container["environment"])


def test_missing_or_shared_keys_prevent_e1_definition() -> None:
    base, config = configuration()
    config["SigningKeyArn"] = config["EncryptionKeyArn"]
    with pytest.raises(RuntimeError, match="separate"):
        api_definition(base, config, "image", "sha")
    del config["Bucket"]
    with pytest.raises(RuntimeError, match="complete"):
        archive_definition(base, config, "image", "sha")


def test_failed_archive_replacement_never_stops_previous_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import e1_release

    calls: list[tuple[str, ...]] = []

    def api(*args: str) -> dict[str, object]:
        calls.append(args)
        if args[1] == "list-tasks":
            return {"taskArns": ["old-worker"]}
        if args[1] == "run-task":
            return {"tasks": [{"taskArn": "new-worker"}]}
        if args[1] == "describe-tasks":
            return {"tasks": [{"lastStatus": "STOPPED"}]}
        return {}

    monkeypatch.setattr(e1_release, "aws", api)
    base = {key: key for key in ["Cluster", "Public0", "Public1", "AppSecurityGroup"]}
    with pytest.raises(RuntimeError, match="previous worker untouched"):
        e1_release.start_archive(base, "new-definition", {"approved-digest"})
    stops = [call for call in calls if call[1] == "stop-task"]
    assert len(stops) == 1 and stops[0][stops[0].index("--task") + 1] == "new-worker"


def test_archive_digest_is_verified_before_old_worker_is_stopped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import e1_release

    calls: list[tuple[str, ...]] = []

    def api(*args: str) -> dict[str, object]:
        calls.append(args)
        if args[1] == "list-tasks":
            return {"taskArns": ["old-worker"]}
        if args[1] == "run-task":
            return {"tasks": [{"taskArn": "new-worker"}]}
        if args[1] == "describe-tasks":
            return {
                "tasks": [
                    {
                        "lastStatus": "RUNNING",
                        "taskDefinitionArn": "new-definition",
                        "containers": [{"imageDigest": "approved-digest", "lastStatus": "RUNNING"}],
                    }
                ]
            }
        return {}

    monkeypatch.setattr(e1_release, "aws", api)
    base = {key: key for key in ["Cluster", "Public0", "Public1", "AppSecurityGroup"]}
    assert e1_release.start_archive(base, "new-definition", {"approved-digest"}) == "new-worker"
    assert [call[1] for call in calls] == ["list-tasks", "run-task", "describe-tasks", "stop-task"]
    assert calls[-1][calls[-1].index("--task") + 1] == "old-worker"
