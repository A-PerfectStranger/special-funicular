"""Recovery permits only the exact failed CFN record, preserving retained resources."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import commission_production as commission
from scripts import production_recovery as recovery

KEY = f"arn:aws:kms:us-east-1:{recovery.ACCOUNT}:key/11111111-1111-1111-1111-111111111111"
STACK_ID = f"arn:aws:cloudformation:us-east-1:{recovery.ACCOUNT}:stack/{recovery.STACK}/1111-2222"
TAGS = [{"Key": "Project", "Value": "retiro-seguro"}, {"Key": "Environment", "Value": "production"}]


@pytest.fixture
def cloud(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    template = json.loads(Path("infra/aws/production-base.json").read_text())
    secrets = {
        name: (
            f"arn:aws:secretsmanager:us-east-1:{recovery.ACCOUNT}:secret:"
            f"retiro-production/{name}-abcdef"
        )
        for name in recovery.SECRETS
    }
    state: dict[str, Any] = {
        "calls": [],
        "database": "absent",
        "template": template,
        "stack": {"StackId": STACK_ID, "StackStatus": "ROLLBACK_COMPLETE", "Tags": TAGS},
        "resources": [
            {
                "LogicalResourceId": "Database",
                "ResourceType": "AWS::RDS::DBInstance",
                "ResourceStatus": "CREATE_FAILED",
                "PhysicalResourceId": "retiro-production",
            },
            {
                "LogicalResourceId": "DatabaseKey",
                "ResourceType": "AWS::KMS::Key",
                "ResourceStatus": "DELETE_SKIPPED",
                "PhysicalResourceId": KEY,
            },
            *[
                {
                    "LogicalResourceId": name,
                    "ResourceType": "AWS::SecretsManager::Secret",
                    "ResourceStatus": "DELETE_SKIPPED",
                    "PhysicalResourceId": arn,
                }
                for name, arn in secrets.items()
            ],
        ],
        "metadata": {
            "Arn": KEY,
            "AWSAccountId": recovery.ACCOUNT,
            "KeyManager": "CUSTOMER",
            "KeyState": "Enabled",
            "KeyUsage": "ENCRYPT_DECRYPT",
            "KeySpec": "SYMMETRIC_DEFAULT",
            "Origin": "AWS_KMS",
        },
        "rotation": True,
        "policy": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{recovery.ACCOUNT}:root"},
                    "Action": "kms:*",
                    "Resource": "*",
                }
            ],
        },
        "secret_metadata": {
            arn: {"ARN": arn, "Name": "retiro-production/" + name, "Tags": TAGS}
            for name, arn in secrets.items()
        },
    }

    def aws(*args: str) -> dict[str, Any]:
        state["calls"].append(args)
        op = args[:2]
        if op == ("sts", "get-caller-identity"):
            return {
                "Account": recovery.ACCOUNT,
                "Arn": f"arn:aws:iam::{recovery.ACCOUNT}:user/operator",
            }
        if op == ("rds", "describe-db-instances"):
            if state["database"] == "absent":
                raise RuntimeError("rds.describe-db-instances: DBInstanceNotFound")
            if state["database"] == "denied":
                raise RuntimeError("rds.describe-db-instances: AccessDenied")
            return {"DBInstances": [{}]}
        if op == ("cloudformation", "describe-stacks"):
            return {"Stacks": [state["stack"]]}
        if op == ("cloudformation", "list-stack-resources"):
            return {"StackResourceSummaries": state["resources"]}
        if op == ("cloudformation", "get-template"):
            return {"TemplateBody": state["template"]}
        if op == ("kms", "describe-key"):
            return {"KeyMetadata": state["metadata"]}
        if op == ("kms", "list-resource-tags"):
            return {
                "Tags": [{"TagKey": t["Key"], "TagValue": t["Value"]} for t in TAGS]
                + [{"TagKey": "Function", "TagValue": "database-backups"}]
            }
        if op == ("kms", "get-key-rotation-status"):
            return {"KeyRotationEnabled": state["rotation"]}
        if op == ("kms", "get-key-policy"):
            return {"Policy": json.dumps(state["policy"])}
        if op == ("secretsmanager", "describe-secret"):
            return state["secret_metadata"][args[3]]
        if op in {("cloudformation", "delete-stack"), ("cloudformation", "wait")}:
            return {}
        pytest.fail(f"Unexpected AWS operation {op}")

    monkeypatch.setattr(recovery, "aws", aws)
    return state


def test_inspection_and_recovery_preserve_all_protected_resources(cloud: dict[str, Any]) -> None:
    plan = recovery.inspect()
    assert plan["retained_database_key_arn"] == KEY
    assert len(plan["retained_secrets"]) == 3
    assert not any(c[1] == "delete-stack" for c in cloud["calls"])
    recovery.remove_failed_record(plan)
    mutations = [c for c in cloud["calls"] if c[1] in {"delete-stack", "wait"}]
    assert mutations == [
        ("cloudformation", "delete-stack", "--stack-name", STACK_ID),
        ("cloudformation", "wait", "stack-delete-complete", "--stack-name", STACK_ID),
    ]
    assert "ExistingDatabaseKeyArn=" + KEY in recovery.retained_parameters(plan)
    assert all(c[:2] != ("secretsmanager", "get-secret-value") for c in cloud["calls"])


@pytest.mark.parametrize("database", ["exists", "denied"])
def test_failed_creation_does_not_prove_database_absence(
    cloud: dict[str, Any], database: str
) -> None:
    cloud["database"] = database
    with pytest.raises(RuntimeError):
        recovery.inspect()
    assert not any(c[1] == "delete-stack" for c in cloud["calls"])


@pytest.mark.parametrize(
    "change",
    [
        "healthy",
        "foreign",
        "survivor",
        "retention",
        "disabled",
        "rotation",
        "policy",
        "secret",
        "drift",
    ],
)
def test_unknown_state_or_drift_never_removes_stack(cloud: dict[str, Any], change: str) -> None:
    plan = recovery.inspect()
    if change == "healthy":
        cloud["stack"]["StackStatus"] = "CREATE_COMPLETE"
    elif change == "foreign":
        cloud["stack"]["StackId"] = STACK_ID.replace(recovery.ACCOUNT, "999999999999")
    elif change == "survivor":
        cloud["resources"].append(
            {
                "LogicalResourceId": "Vpc",
                "ResourceType": "AWS::EC2::VPC",
                "ResourceStatus": "DELETE_FAILED",
                "PhysicalResourceId": "vpc-123",
            }
        )
    elif change == "retention":
        cloud["template"]["Resources"]["DatabaseKey"]["DeletionPolicy"] = "Delete"
    elif change == "disabled":
        cloud["metadata"]["KeyState"] = "Disabled"
    elif change == "rotation":
        cloud["rotation"] = False
    elif change == "policy":
        cloud["policy"]["Statement"][0]["Principal"] = {"AWS": "*"}
    elif change == "secret":
        next(iter(cloud["secret_metadata"].values()))["DeletedDate"] = "pending"
    else:
        plan = {**plan, "resource_fingerprint": "changed"}
    with pytest.raises(RuntimeError):
        recovery.remove_failed_record(plan)
    assert not any(c[1] == "delete-stack" for c in cloud["calls"])


def test_recovery_of_previously_external_retained_resources(cloud: dict[str, Any]) -> None:
    plan = recovery.inspect()
    cloud["stack"]["Parameters"] = [
        {"ParameterKey": "ExistingDatabaseKeyArn", "ParameterValue": KEY},
        *[
            {"ParameterKey": "Existing" + name, "ParameterValue": arn}
            for name, arn in plan["retained_secrets"].items()
        ],
    ]
    cloud["resources"] = cloud["resources"][:1]
    observed = recovery.inspect()
    assert observed["retained_database_key_arn"] == KEY
    assert observed["retained_secrets"] == plan["retained_secrets"]


def test_plan_drift_of_reference_cannot_remove_stack(cloud: dict[str, Any]) -> None:
    plan = copy.deepcopy(recovery.inspect())
    plan["retained_database_key_arn"] = ""
    with pytest.raises(RuntimeError, match="plan drift"):
        recovery.remove_failed_record(plan)
    assert not any(c[1] == "delete-stack" for c in cloud["calls"])


def test_inspector_writes_only_private_plan(
    cloud: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "private" / "plan.json"
    monkeypatch.setattr("sys.argv", ["inspect", "--plan", str(destination)])
    assert recovery.main() == 0
    assert destination.stat().st_mode & 0o777 == 0o600
    assert destination.parent.stat().st_mode & 0o777 == 0o700
    assert json.loads(destination.read_text())["database_absent"] is True


def test_free_plan_and_financial_gate_precedes_failed_record_removal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    monkeypatch.setattr(
        "sys.argv",
        [
            "commission",
            "--step",
            "recover-foundation",
            "--sha",
            "a" * 40,
            "--digest",
            "sha256:" + "b" * 64,
            "--cost-plan",
            str(plan),
            "--recovery-plan",
            str(plan),
        ],
    )
    monkeypatch.setattr(commission, "require_source", lambda *a: None)

    def blocked(*args: Any) -> Any:
        raise RuntimeError("billing blocked")

    monkeypatch.setattr(commission, "preflight", blocked)
    monkeypatch.setattr(
        commission, "remove_failed_record", lambda *a: pytest.fail("must not delete")
    )
    with pytest.raises(RuntimeError, match="billing blocked"):
        commission.main()


def test_foundation_reuses_verified_key_without_creating_replacement(
    cloud: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = recovery.inspect()
    deployments: dict[str, list[str]] = {}
    monkeypatch.setattr(commission, "preflight", lambda *a: {})
    monkeypatch.setattr(commission, "retained_parameters", recovery.retained_parameters)

    def metadata(*args: str, **kwargs: Any) -> dict[str, Any]:
        if args[0] == "iam":
            return {"Role": {}}
        logical = args[3].split("/")[-1]
        return cloud["secret_metadata"][plan["retained_secrets"][logical]]

    def aws(*args: str) -> dict[str, Any]:
        if args[1] == "describe-db-engine-versions":
            return {"DBEngineVersions": [{"EngineVersion": "17.11"}]}
        if args[1] == "describe-orderable-db-instance-options":
            return {"OrderableDBInstanceOptions": [{}]}
        assert args[:2] == ("ssm", "put-parameter")
        return {}

    monkeypatch.setattr(commission, "aws", aws)
    monkeypatch.setattr(commission, "read", metadata)
    monkeypatch.setattr(
        commission,
        "deploy_stack",
        lambda name, template, params: deployments.update({name: params}),
    )
    monkeypatch.setattr(commission, "report", lambda *a: None)
    commission.foundation({}, plan)
    parameters = deployments[recovery.STACK]
    assert "ExistingDatabaseKeyArn=" + KEY in parameters
    for name, arn in plan["retained_secrets"].items():
        assert "Existing" + name + "=" + arn in parameters
    template = json.loads(Path("infra/aws/production-base.json").read_text())
    assert template["Resources"]["DatabaseKey"]["Condition"] == "CreateDatabaseKey"
    assert template["Conditions"]["CreateDatabaseKey"] == {
        "Fn::Equals": [{"Ref": "ExistingDatabaseKeyArn"}, ""]
    }
