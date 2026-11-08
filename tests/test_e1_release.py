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
