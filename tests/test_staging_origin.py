"""Callback maintenance must never expand into resource, identity or SQL provisioning."""

import copy
import json
from typing import Any

import pytest

from scripts import sync_staging_origin as module

ORIGIN = "https://reviewed.ecs.us-east-1.on.aws"
CONFIG = {
    "base_url": ORIGIN,
    "service": "reviewed-service",
    "synthetic_only": True,
    "pickup_enabled": False,
    "account_id": "028364485203",
}
OUTPUTS = {
    "WebRedirect": "https://old.ecs.us-east-1.on.aws/auth/callback",
    "PoolId": "unchanged-pool",
    "WebClientId": "unchanged-client",
    "MobileClientId": "unchanged-mobile",
    "Bucket": "unchanged-evidence",
    "EncryptionKeyArn": "unchanged-key",
    "AcceptanceFixtureSecret": "unchanged-vault",
}
CHANGE = {
    "ResourceChange": {
        "LogicalResourceId": "WebClient",
        "ResourceType": "AWS::Cognito::UserPoolClient",
        "Action": "Modify",
        "Replacement": "False",
        "Scope": ["Properties"],
        "Details": [{"Target": {"Attribute": "Properties", "Name": "CallbackURLs"}}],
    }
}


@pytest.mark.parametrize("damage", ["extra_resource", "iam", "replace", "scope", "other_property"])
def test_unexpected_changes_cannot_execute(damage: str) -> None:
    change = copy.deepcopy(CHANGE)
    changes = [change]
    if damage == "extra_resource":
        changes.append(copy.deepcopy(change))
    elif damage == "iam":
        change["ResourceChange"]["ResourceType"] = "AWS::IAM::Role"
    elif damage == "replace":
        change["ResourceChange"]["Replacement"] = "True"
    elif damage == "scope":
        change["ResourceChange"]["Scope"] = ["Tags"]
    else:
        change["ResourceChange"]["Details"][0]["Target"]["Name"] = "AllowedOAuthScopes"
    with pytest.raises(RuntimeError):
        module.validate_change_set(changes)


@pytest.mark.parametrize("already_synced", [False, True])
def test_only_existing_callback_changes_and_other_parameters_outputs_are_preserved(
    monkeypatch: pytest.MonkeyPatch, already_synced: bool
) -> None:
    executed = already_synced
    calls: list[tuple[str, ...]] = []

    def read(*args: str) -> dict[str, Any]:
        nonlocal executed
        calls.append(args)
        command = args[:2]
        if command == ("sts", "get-caller-identity"):
            return {"Account": "028364485203", "Arn": "arn:aws:iam::028364485203:user/operator"}
        if command == ("ecs", "describe-express-gateway-service"):
            return {
                "service": {
                    "status": {"statusCode": "ACTIVE"},
                    "activeConfigurations": [{"ingressPaths": [{"endpoint": ORIGIN[8:]}]}],
                }
            }
        if command == ("cloudformation", "describe-stacks"):
            outputs = {
                **OUTPUTS,
                **({"WebRedirect": ORIGIN + "/auth/callback"} if executed else {}),
            }
            return {
                "Stacks": [
                    {
                        "Outputs": [{"OutputKey": k, "OutputValue": v} for k, v in outputs.items()],
                        "Parameters": [
                            {"ParameterKey": k, "ParameterValue": v}
                            for k, v in {
                                "WebOrigin": ORIGIN
                                if executed
                                else "https://old.ecs.us-east-1.on.aws",
                                "MobileRedirect": "unchanged-native",
                                "ExistingLogsArn": "unchanged-logs",
                            }.items()
                        ],
                    }
                ]
            }
        if command == ("cloudformation", "create-change-set"):
            assert "--use-previous-template" in args
            assert json.loads(args[args.index("--parameters") + 1]) == [
                {"ParameterKey": "WebOrigin", "ParameterValue": ORIGIN},
                {"ParameterKey": "MobileRedirect", "UsePreviousValue": True},
                {"ParameterKey": "ExistingLogsArn", "UsePreviousValue": True},
            ]
            return {}
        if command == ("cloudformation", "describe-change-set"):
            return {"Status": "CREATE_COMPLETE", "Changes": [copy.deepcopy(CHANGE)]}
        if command == ("cloudformation", "execute-change-set"):
            executed = True
            return {}
        if command == ("cloudformation", "wait"):
            return {}
        if command == ("cognito-idp", "describe-user-pool-client"):
            return {"UserPoolClient": {"CallbackURLs": [ORIGIN + "/auth/callback"]}}
        raise AssertionError("Unexpected AWS operation")

    monkeypatch.setattr(module, "aws", read)
    module.sync(CONFIG)
    assert sum(c[:2] == ("cloudformation", "execute-change-set") for c in calls) == (
        0 if already_synced else 1
    )


def test_callback_drift_and_ci_operator_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RuntimeError, match="STAGING_ORIGIN_DRIFT"):
        module.require_web_origin(ORIGIN, "https://stale.ecs.us-east-1.on.aws/auth/callback")
    monkeypatch.setattr(
        module,
        "aws",
        lambda *a: {
            "Account": "028364485203",
            "Arn": "arn:aws:sts::028364485203:assumed-role/retiro-staging-Deploy/ci",
        },
    )
    with pytest.raises(RuntimeError, match="not provisioning operators"):
        module.sync(CONFIG)


def test_unreviewed_observed_hostname_stops_before_any_stack_or_client_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def read(*args: str) -> dict[str, Any]:
        if args[:2] == ("sts", "get-caller-identity"):
            return {"Account": "028364485203", "Arn": "arn:aws:iam::028364485203:user/operator"}
        assert args[:2] == ("ecs", "describe-express-gateway-service")
        return {
            "service": {
                "status": {"statusCode": "ACTIVE"},
                "activeConfigurations": [
                    {"ingressPaths": [{"endpoint": "unreviewed.ecs.us-east-1.on.aws"}]}
                ],
            }
        }

    monkeypatch.setattr(module, "aws", read)
    with pytest.raises(RuntimeError, match="differs from reviewed"):
        module.sync(CONFIG)
