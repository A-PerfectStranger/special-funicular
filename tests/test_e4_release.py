"""E4 boundaries: separate credentials, incompatible native config and gated deployment."""

import pytest

from scripts.e1_release import api_definition
from scripts.e4_release import notification_definition
from scripts.mobile_push_config import validate
from tests.test_e1_release import configuration


def test_e4_notifier_and_web_receive_only_their_own_credentials() -> None:
    base, config = configuration()
    config.update(
        {
            key: key
            for key in [
                "SchoolReadPassword",
                "NotifierPassword",
                "NotifierTaskArn",
                "NotifierExecutionArn",
                "ExpoAccessTokenSecret",
                "AllowedDevicesSecret",
            ]
        }
    )
    api = api_definition(
        base,
        config,
        "image@sha256:approved",
        "a" * 40,
        enable_family=True,
        enable_pickup=True,
        enable_operations=True,
    )
    notifier = notification_definition(base, config, "image@sha256:approved", "a" * 40)
    web, worker = api["containerDefinitions"][0], notifier["containerDefinitions"][0]
    assert {value["valueFrom"] for value in web["secrets"]} == {
        "DjangoSecret",
        "RuntimePassword",
        "SystemReadPassword",
        "SchoolReadPassword",
    }
    assert {value["valueFrom"] for value in worker["secrets"]} == {
        "NotifierPassword",
        "ExpoAccessTokenSecret",
        "AllowedDevicesSecret",
    }
    assert "portMappings" not in worker
    assert (
        notifier["taskRoleArn"] != api["taskRoleArn"]
        and notifier["executionRoleArn"] != api["executionRoleArn"]
    )
    assert worker["command"][-1] == "10800"
    with pytest.raises(RuntimeError, match="E4"):
        api_definition(base, config, "image", "a" * 40, enable_operations=True)
    del config["AllowedDevicesSecret"]
    with pytest.raises(RuntimeError, match="BLOCKED"):
        notification_definition(base, config, "image", "a" * 40)


def test_firebase_client_config_rejects_wrong_package_project_and_private_key() -> None:
    data = {
        "project_info": {"project_id": "retiro-seguro-2ab03", "project_number": "123456789"},
        "client": [
            {
                "client_info": {
                    "android_client_info": {"package_name": "org.retiroseguro.staging"},
                    "mobilesdk_app_id": "1:123456789:android:synthetic",
                },
                "api_key": [{"current_key": "synthetic-public-client-configuration"}],
            }
        ],
    }
    validate(data, "org.retiroseguro.staging")
    with pytest.raises(ValueError):
        validate(data, "org.retiroseguro.app")
    with pytest.raises(ValueError):
        validate({**data, "private_key": "SYNTHETIC"}, "org.retiroseguro.staging")
    with pytest.raises(ValueError):
        validate(
            {**data, "project_info": {"project_id": "another", "project_number": "123"}},
            "org.retiroseguro.staging",
        )
