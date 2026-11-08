"""Reopen bounded staging after ECS retains an INACTIVE service description."""

import json
import subprocess
from typing import Any

import pytest

from scripts import deploy_staging


@pytest.mark.parametrize("status", ["INACTIVE", "ACTIVE", "DRAINING", "UNKNOWN"])
def test_retired_service_is_recreated_and_transitions_never_updated(
    status: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, ...]] = []
    description = {
        "service": {
            "status": {"statusCode": status},
            "activeConfigurations": [{"taskDefinitionArn": "previous-definition"}],
        }
    }
    monkeypatch.setattr(
        deploy_staging.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess([], 0, json.dumps(description), ""),
    )

    def aws(*args: str) -> dict[str, Any]:
        calls.append(args)
        if args[1] == "create-express-gateway-service":
            return {"service": {"serviceArn": "recreated-service"}}
        if args[1] == "update-express-gateway-service" and status != "ACTIVE":
            raise RuntimeError("ecs.update-express-gateway-service: InvalidParameterException")
        return {}

    monkeypatch.setattr(deploy_staging, "aws", aws)
    monkeypatch.setattr(deploy_staging, "arm_expiry", lambda service: "bounded-expiry")
    outputs = {
        key: key
        for key in ["Cluster", "ExpressInfrastructure", "Public0", "Public1", "AppSecurityGroup"]
    }
    if status in {"DRAINING", "UNKNOWN"}:
        with pytest.raises(RuntimeError, match="not ready"):
            deploy_staging.deploy_express(outputs, "approved-definition")
        assert not calls
    else:
        service, previous, expiry = deploy_staging.deploy_express(outputs, "approved-definition")
        assert expiry == "bounded-expiry"
        if status == "INACTIVE":
            assert service == "recreated-service" and previous is None
            assert [call[1] for call in calls] == ["create-express-gateway-service"]
        else:
            assert previous == "previous-definition"
            assert [call[1] for call in calls] == ["update-express-gateway-service"]


def test_lookup_denial_cannot_trigger_service_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        deploy_staging.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(
            [], 1, "", "An error occurred (AccessDeniedException)"
        ),
    )
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(deploy_staging, "aws", lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match="absence not established"):
        deploy_staging.deploy_express({}, "approved-definition")
    assert not calls
