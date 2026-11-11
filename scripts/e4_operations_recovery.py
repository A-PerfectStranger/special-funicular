"""Recover only rolled-back, empty operations infrastructure; retain its exact KMS key."""

import json
import re
from typing import Any

from scripts.aws_cli import aws

ACCOUNT = "028364485203"
STACK = "retiro-staging-operations"
BUCKET = f"retiro-internal-mobile-{ACCOUNT}-us-east-1"
KEY_DESCRIPTION = (
    "Internal mobile artifacts and operational alerts; separate from student evidence keys."
)


class RecoveryBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"BLOCKED: {code}")


def stack() -> dict[str, Any] | None:
    try:
        value = aws("cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0]
        if not isinstance(value, dict):
            raise RecoveryBlocked("STACK_RESPONSE_INVALID")
        return value
    except RuntimeError as error:
        if str(error) == "cloudformation.describe-stacks: ValidationError":
            return None
        raise


def retained_key(key_id: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", key_id):
        raise RecoveryBlocked("RETAINED_KEY_INVALID")
    arn = f"arn:aws:kms:us-east-1:{ACCOUNT}:key/{key_id}"
    meta = aws("kms", "describe-key", "--key-id", key_id)["KeyMetadata"]
    expected = {
        "AWSAccountId": ACCOUNT,
        "KeyId": key_id,
        "Arn": arn,
        "Description": KEY_DESCRIPTION,
        "KeyManager": "CUSTOMER",
        "KeyState": "Enabled",
        "Enabled": True,
        "KeyUsage": "ENCRYPT_DECRYPT",
        "KeySpec": "SYMMETRIC_DEFAULT",
        "Origin": "AWS_KMS",
    }
    if any(meta.get(k) != v for k, v in expected.items()):
        raise RecoveryBlocked("RETAINED_KEY_IDENTITY_OR_STATE_MISMATCH")
    tagged = aws("kms", "list-resource-tags", "--key-id", key_id)
    tags = {tag["TagKey"]: tag["TagValue"] for tag in tagged.get("Tags", [])}
    if (
        tagged.get("Truncated")
        or tags.get("Project") != "retiro-seguro"
        or tags.get("Environment") != "staging"
    ):
        raise RecoveryBlocked("RETAINED_KEY_TAGS_MISMATCH")
    if (
        aws("kms", "get-key-rotation-status", "--key-id", key_id).get("KeyRotationEnabled")
        is not True
    ):
        raise RecoveryBlocked("RETAINED_KEY_ROTATION_DISABLED")
    policy = json.loads(
        aws("kms", "get-key-policy", "--key-id", key_id, "--policy-name", "default")["Policy"]
    )
    statements = {s.get("Sid"): s for s in policy.get("Statement", [])}
    expected_statements = {
        "AccountAdministration": {
            "Sid": "AccountAdministration",
            "Effect": "Allow",
            "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT}:root"},
            "Action": "kms:*",
            "Resource": "*",
        },
        "ProtectFromApplicationAdministration": {
            "Sid": "ProtectFromApplicationAdministration",
            "Effect": "Deny",
            "Principal": "*",
            "Action": [
                "kms:DisableKey",
                "kms:ScheduleKeyDeletion",
                "kms:PutKeyPolicy",
                "kms:CreateGrant",
            ],
            "Resource": "*",
            "Condition": {
                "ArnLike": {"aws:PrincipalArn": f"arn:aws:iam::{ACCOUNT}:role/retiro-staging-*"}
            },
        },
        "EncryptedCloudWatchAlerts": {
            "Sid": "EncryptedCloudWatchAlerts",
            "Effect": "Allow",
            "Principal": {"Service": "cloudwatch.amazonaws.com"},
            "Action": ["kms:GenerateDataKey*", "kms:Decrypt"],
            "Resource": "*",
            "Condition": {"StringEquals": {"aws:SourceAccount": ACCOUNT}},
        },
    }
    # KMS can reorder Action arrays. All other policy fields must match the
    # reviewed operations key, including the deny against application key admins.
    for statement in [*statements.values(), *expected_statements.values()]:
        actions = statement.get("Action", [])
        statement["Action"] = sorted(actions if isinstance(actions, list) else [actions])
    if (
        policy.get("Version") != "2012-10-17"
        or statements != expected_statements
        or len(statements) != len(policy.get("Statement", []))
    ):
        raise RecoveryBlocked("RETAINED_KEY_POLICY_MISMATCH")
    return arn


def require_bucket_absent() -> None:
    try:
        aws("s3api", "head-bucket", "--bucket", BUCKET, "--expected-bucket-owner", ACCOUNT)
    except RuntimeError as error:
        if str(error) in {
            "s3api.head-bucket: 404",
            "s3api.head-bucket: NoSuchBucket",
            "s3api.head-bucket: NotFound",
        }:
            return
        raise
    raise RecoveryBlocked("EXISTING_BUCKET_REQUIRES_RECONCILIATION")


def prepare(key_id: str) -> str:
    """No key/bucket writes. Remove only a fully rolled-back stack registration.

    The explicit key ID makes recovery resumable after deletion of that failed
    registration. A successful stack must already reference the same retained key.
    """
    arn = retained_key(key_id)
    current = stack()
    if current is not None and current["StackStatus"] in {
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
    }:
        parameters = {
            p["ParameterKey"]: p.get("ParameterValue") for p in current.get("Parameters", [])
        }
        if parameters.get("ExistingOperationsKeyArn") != arn:
            raise RecoveryBlocked("HEALTHY_STACK_KEY_MODE_MISMATCH")
        return arn
    # A present bucket is never removed, reset, adopted or silently reconfigured.
    require_bucket_absent()
    if current is not None:
        status = current["StackStatus"]
        if status == "DELETE_IN_PROGRESS":
            aws("cloudformation", "wait", "stack-delete-complete", "--stack-name", STACK)
        elif status == "ROLLBACK_COMPLETE":
            response = aws("cloudformation", "list-stack-resources", "--stack-name", STACK)
            resources = response.get("StackResourceSummaries", [])
            expected_types = {
                "OperationsKey": "AWS::KMS::Key",
                "MobileBucket": "AWS::S3::Bucket",
                "MobileBucketPolicy": "AWS::S3::BucketPolicy",
                "MobilePublisher": "AWS::IAM::Role",
                "AlertTopic": "AWS::SNS::Topic",
                "AlertTopicPolicy": "AWS::SNS::TopicPolicy",
                "AlertSubscription": "AWS::SNS::Subscription",
            }
            keys = [r for r in resources if r.get("LogicalResourceId") == "OperationsKey"]
            parameters = {
                p["ParameterKey"]: p.get("ParameterValue") for p in current.get("Parameters", [])
            }
            external = parameters.get("ExistingOperationsKeyArn")
            retained_matches = (
                len(keys) == 1
                and keys[0].get("PhysicalResourceId") == key_id
                and keys[0].get("ResourceStatus") == "DELETE_SKIPPED"
            )
            external_matches = not keys and external == arn
            if (
                response.get("NextToken")
                or external not in {None, "", arn}
                or not (retained_matches or external_matches)
            ):
                raise RecoveryBlocked("ROLLED_BACK_KEY_NOT_PROVEN")
            for resource in resources:
                logical = resource.get("LogicalResourceId")
                if expected_types.get(logical) != resource.get("ResourceType"):
                    raise RecoveryBlocked("UNEXPECTED_STACK_RESOURCE")
                if logical == "OperationsKey":
                    continue
                if (
                    logical == "MobileBucket"
                    and resource.get("ResourceStatus") == "DELETE_SKIPPED"
                    and not resource.get("PhysicalResourceId")
                ):
                    continue
                if resource.get("ResourceStatus") != "DELETE_COMPLETE":
                    raise RecoveryBlocked("RETAINED_OR_ACTIVE_RESOURCE_REQUIRES_RECONCILIATION")
            # DELETE_SKIPPED key remains retained. No Delete/Schedule/DeleteObject
            # operation is ever issued to KMS, S3, databases or evidence storage.
            aws("cloudformation", "delete-stack", "--stack-name", current["StackId"])
            aws(
                "cloudformation",
                "wait",
                "stack-delete-complete",
                "--stack-name",
                current["StackId"],
            )
        else:
            raise RecoveryBlocked("STACK_BUSY_OR_RECONCILIATION_REQUIRED")
    # Prove that the same enabled key survived and is explicitly reused by CFN.
    retained_key(key_id)
    return arn
