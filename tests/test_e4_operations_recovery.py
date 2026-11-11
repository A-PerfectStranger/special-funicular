"""Recovery preserves the actual retained key and refuses any remaining bucket/data."""

import copy
import json
from typing import Any

import pytest
from cfnlint.decode import decode

from scripts import e4_operations_recovery as recovery

KEY_ID = "11111111-1111-1111-1111-111111111111"
KEY_ARN = f"arn:aws:kms:us-east-1:{recovery.ACCOUNT}:key/{KEY_ID}"
STACK_ID = f"arn:aws:cloudformation:us-east-1:{recovery.ACCOUNT}:stack/{recovery.STACK}/synthetic"


def resolved(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"Ref"}:
            assert value["Ref"] == "AWS::AccountId"
            return recovery.ACCOUNT
        if set(value) == {"Fn::Sub"}:
            return value["Fn::Sub"].replace("${AWS::AccountId}", recovery.ACCOUNT)
        return {key: resolved(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolved(item) for item in value]
    return value


class Cloud:
    def __init__(self) -> None:
        template, errors = decode("infra/aws/e4-operations.yaml")
        assert not errors and template is not None
        self.policy = resolved(template["Resources"]["OperationsKey"]["Properties"]["KeyPolicy"])
        self.meta = {
            "AWSAccountId": recovery.ACCOUNT,
            "KeyId": KEY_ID,
            "Arn": KEY_ARN,
            "Description": recovery.KEY_DESCRIPTION,
            "KeyManager": "CUSTOMER",
            "KeyState": "Enabled",
            "Enabled": True,
            "KeyUsage": "ENCRYPT_DECRYPT",
            "KeySpec": "SYMMETRIC_DEFAULT",
            "Origin": "AWS_KMS",
        }
        self.tags = [
            {"TagKey": "Project", "TagValue": "retiro-seguro"},
            {"TagKey": "Environment", "TagValue": "staging"},
        ]
        self.rotation = True
        self.current: dict[str, Any] | None = {
            "StackStatus": "ROLLBACK_COMPLETE",
            "StackId": STACK_ID,
        }
        self.resources = [
            {
                "LogicalResourceId": "OperationsKey",
                "ResourceType": "AWS::KMS::Key",
                "ResourceStatus": "DELETE_SKIPPED",
                "PhysicalResourceId": KEY_ID,
            },
            {
                "LogicalResourceId": "MobileBucket",
                "ResourceType": "AWS::S3::Bucket",
                "ResourceStatus": "DELETE_SKIPPED",
                "PhysicalResourceId": None,
            },
            {
                "LogicalResourceId": "AlertTopic",
                "ResourceType": "AWS::SNS::Topic",
                "ResourceStatus": "DELETE_COMPLETE",
                "PhysicalResourceId": "synthetic-topic",
            },
        ]
        self.next_token: str | None = None
        self.bucket_exists = False
        self.bucket_denied = False
        self.calls: list[tuple[str, ...]] = []

    def aws(self, *args: str) -> dict[str, Any]:
        self.calls.append(args)
        if args[:2] == ("kms", "describe-key"):
            assert args[-1] == KEY_ID
            return {"KeyMetadata": self.meta}
        if args[:2] == ("kms", "list-resource-tags"):
            return {"Tags": self.tags}
        if args[:2] == ("kms", "get-key-rotation-status"):
            return {"KeyRotationEnabled": self.rotation}
        if args[:2] == ("kms", "get-key-policy"):
            return {"Policy": json.dumps(self.policy)}
        if args[:2] == ("cloudformation", "describe-stacks"):
            if self.current is None:
                raise RuntimeError("cloudformation.describe-stacks: ValidationError")
            return {"Stacks": [self.current]}
        if args[:2] == ("cloudformation", "list-stack-resources"):
            return {"StackResourceSummaries": self.resources, "NextToken": self.next_token}
        if args[:2] == ("s3api", "head-bucket"):
            assert args[-1] == recovery.ACCOUNT
            if self.bucket_denied:
                raise RuntimeError("s3api.head-bucket: 403")
            if not self.bucket_exists:
                raise RuntimeError("s3api.head-bucket: 404")
            return {}
        if args[:2] == ("cloudformation", "delete-stack"):
            assert args[-1] == STACK_ID  # exact failed incarnation, not only its name
            self.current = None
            return {}
        if args[:3] == ("cloudformation", "wait", "stack-delete-complete"):
            return {}
        pytest.fail(f"Unexpected AWS operation: {args[:2]}")

    @property
    def writes(self) -> list[tuple[str, ...]]:
        read = {
            "describe-key",
            "list-resource-tags",
            "get-key-rotation-status",
            "get-key-policy",
            "describe-stacks",
            "list-stack-resources",
            "head-bucket",
            "wait",
        }
        return [call for call in self.calls if call[1] not in read]


def test_recovery_only_removes_failed_stack_registration_and_preserves_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud = Cloud()
    original = copy.deepcopy(cloud.meta)
    monkeypatch.setattr(recovery, "aws", cloud.aws)
    assert recovery.prepare(KEY_ID) == KEY_ARN
    assert cloud.writes == [("cloudformation", "delete-stack", "--stack-name", STACK_ID)]
    assert cloud.meta == original and cloud.meta["Enabled"] is True
    assert sum(call[:2] == ("kms", "describe-key") for call in cloud.calls) == 2


@pytest.mark.parametrize(
    "state", [None, "DELETE_IN_PROGRESS", "CREATE_COMPLETE", "UPDATE_COMPLETE"]
)
def test_interrupted_recovery_or_successful_rerun_reuses_same_key(
    monkeypatch: pytest.MonkeyPatch, state: str | None
) -> None:
    cloud = Cloud()
    cloud.current = (
        None
        if state is None
        else {
            "StackStatus": state,
            "StackId": STACK_ID,
            "Parameters": [{"ParameterKey": "ExistingOperationsKeyArn", "ParameterValue": KEY_ARN}],
        }
    )
    cloud.bucket_exists = state in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}
    monkeypatch.setattr(recovery, "aws", cloud.aws)
    assert recovery.prepare(KEY_ID) == KEY_ARN and not cloud.writes


@pytest.mark.parametrize(
    "failure,code",
    [
        ("key_state", "RETAINED_KEY_IDENTITY_OR_STATE_MISMATCH"),
        ("key_tags", "RETAINED_KEY_TAGS_MISMATCH"),
        ("key_policy", "RETAINED_KEY_POLICY_MISMATCH"),
        ("key_rotation", "RETAINED_KEY_ROTATION_DISABLED"),
        ("bucket_exists", "EXISTING_BUCKET_REQUIRES_RECONCILIATION"),
        ("bucket_denied", "s3api.head-bucket: 403"),
        ("wrong_key", "ROLLED_BACK_KEY_NOT_PROVEN"),
        ("retained_bucket", "RETAINED_OR_ACTIVE_RESOURCE_REQUIRES_RECONCILIATION"),
        ("unexpected_resource", "UNEXPECTED_STACK_RESOURCE"),
        ("active_resource", "RETAINED_OR_ACTIVE_RESOURCE_REQUIRES_RECONCILIATION"),
        ("paginated_resources", "ROLLED_BACK_KEY_NOT_PROVEN"),
        ("busy_stack", "STACK_BUSY_OR_RECONCILIATION_REQUIRED"),
        ("healthy_different_key", "HEALTHY_STACK_KEY_MODE_MISMATCH"),
    ],
)
def test_recovery_fails_before_any_mutation_when_custody_or_scope_is_uncertain(
    monkeypatch: pytest.MonkeyPatch, failure: str, code: str
) -> None:
    cloud = Cloud()
    if failure == "key_state":
        cloud.meta["KeyState"] = "PendingDeletion"
    elif failure == "key_tags":
        cloud.tags[0]["TagValue"] = "another-project"
    elif failure == "key_policy":
        cloud.policy["Statement"][1]["Action"].remove("kms:ScheduleKeyDeletion")
    elif failure == "key_rotation":
        cloud.rotation = False
    elif failure in {"bucket_exists", "bucket_denied"}:
        setattr(cloud, failure, True)
    elif failure == "wrong_key":
        cloud.resources[0]["PhysicalResourceId"] = "other-key"
    elif failure == "retained_bucket":
        cloud.resources[1]["PhysicalResourceId"] = recovery.BUCKET
    elif failure == "unexpected_resource":
        cloud.resources.append(
            {
                "LogicalResourceId": "Database",
                "ResourceType": "AWS::RDS::DBInstance",
                "ResourceStatus": "DELETE_COMPLETE",
            }
        )
    elif failure == "active_resource":
        cloud.resources[2]["ResourceStatus"] = "CREATE_COMPLETE"
    elif failure == "paginated_resources":
        cloud.next_token = "more"
    elif failure == "busy_stack":
        assert cloud.current is not None
        cloud.current["StackStatus"] = "CREATE_IN_PROGRESS"
    elif failure == "healthy_different_key":
        assert cloud.current is not None
        cloud.current["StackStatus"] = "CREATE_COMPLETE"
    monkeypatch.setattr(recovery, "aws", cloud.aws)
    with pytest.raises(RuntimeError, match=code):
        recovery.prepare(KEY_ID)
    assert not cloud.writes


def test_a_second_rolled_back_attempt_can_reuse_its_external_key_without_recreating_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud = Cloud()
    cloud.resources.pop(0)
    assert cloud.current is not None
    cloud.current["Parameters"] = [
        {"ParameterKey": "ExistingOperationsKeyArn", "ParameterValue": KEY_ARN}
    ]
    monkeypatch.setattr(recovery, "aws", cloud.aws)
    assert recovery.prepare(KEY_ID) == KEY_ARN
    assert len(cloud.writes) == 1
