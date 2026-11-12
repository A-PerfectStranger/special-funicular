"""Narrow recovery of a failed production foundation with no database.

Only the failed CloudFormation record may be removed. Database, keys, secrets
and evidence are never deleted. Unknown resources or state block recovery.
"""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from scripts.aws_cli import aws
from scripts.commission_e1 import validate_operator
from scripts.production import ACCOUNT, failure, operation

STACK = "retiro-production-base"
SECRETS = {"RuntimePassword", "MigrationPassword", "DjangoSecret"}


def require_database_absent() -> None:
    try:
        aws("rds", "describe-db-instances", "--db-instance-identifier", "retiro-production")
    except RuntimeError as error:
        if str(error) in {
            "rds.describe-db-instances: DBInstanceNotFound",
            "rds.describe-db-instances: DBInstanceNotFoundFault",
        }:
            return
        raise
    raise RuntimeError("BLOCKED: production database exists; automatic stack recovery prohibited")


def validate_key(arn_or_id: str) -> str:
    metadata = aws("kms", "describe-key", "--key-id", arn_or_id)["KeyMetadata"]
    arn: str = metadata["Arn"]
    tags = {
        tag["TagKey"]: tag["TagValue"]
        for tag in aws(
            "kms",
            "list-resource-tags",
            "--key-id",
            arn,
        )["Tags"]
    }
    if (
        not re.fullmatch(rf"arn:aws:kms:us-east-1:{ACCOUNT}:key/[0-9a-f-]{{36}}", arn)
        or metadata.get("AWSAccountId") != ACCOUNT
        or metadata.get("KeyManager") != "CUSTOMER"
        or metadata.get("KeyState") != "Enabled"
        or metadata.get("KeyUsage") != "ENCRYPT_DECRYPT"
        or metadata.get("KeySpec") != "SYMMETRIC_DEFAULT"
        or metadata.get("Origin") != "AWS_KMS"
        or any(
            tags.get(k) != v
            for k, v in {
                "Project": "retiro-seguro",
                "Environment": "production",
                "Function": "database-backups",
            }.items()
        )
        or aws("kms", "get-key-rotation-status", "--key-id", arn).get("KeyRotationEnabled")
        is not True
    ):
        raise RuntimeError("BLOCKED: retained production key metadata mismatch")
    policy = json.loads(
        aws("kms", "get-key-policy", "--key-id", arn, "--policy-name", "default")["Policy"]
    )
    statements = policy.get("Statement", [])
    expected = {
        "Effect": "Allow",
        "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT}:root"},
        "Action": "kms:*",
        "Resource": "*",
    }
    if (
        policy.get("Version") != "2012-10-17"
        or not isinstance(statements, list)
        or len(statements) != 1
        or not isinstance(statements[0], dict)
        or {k: v for k, v in statements[0].items() if k != "Sid"} != expected
    ):
        raise RuntimeError("BLOCKED: retained production key policy mismatch")
    return arn


def validate_secret(logical: str, arn: str) -> None:
    if logical not in SECRETS or not arn.startswith(
        f"arn:aws:secretsmanager:us-east-1:{ACCOUNT}:secret:retiro-production/{logical}-"
    ):
        raise RuntimeError("BLOCKED: retained secret reference mismatch")
    secret = aws("secretsmanager", "describe-secret", "--secret-id", arn)
    tags = {tag["Key"]: tag["Value"] for tag in secret.get("Tags", [])}
    if (
        secret.get("ARN") != arn
        or secret.get("Name") != "retiro-production/" + logical
        or secret.get("DeletedDate")
        or tags.get("Project") != "retiro-seguro"
        or tags.get("Environment") != "production"
    ):
        raise RuntimeError("BLOCKED: retained secret metadata mismatch")


def inspect() -> dict[str, Any]:
    """Read-only. The private plan binds the exact stack and retained references."""
    identity = aws("sts", "get-caller-identity")
    validate_operator(identity)
    if any(
        prefix in identity["Arn"]
        for prefix in [":role/retiro-production-", ":assumed-role/retiro-production-"]
    ):
        raise RuntimeError("BLOCKED: production CI/runtime identities are not operators")
    stack = aws("cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0]
    tags = {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}
    if (
        stack.get("StackStatus") != "ROLLBACK_COMPLETE"
        or tags.get("Project") != "retiro-seguro"
        or tags.get("Environment") != "production"
        or not re.fullmatch(
            rf"arn:aws:cloudformation:us-east-1:{ACCOUNT}:stack/{STACK}/[0-9a-f-]+",
            stack.get("StackId", ""),
        )
    ):
        raise RuntimeError("BLOCKED: unexpected failed production stack ownership/state")
    require_database_absent()
    resources = aws("cloudformation", "list-stack-resources", "--stack-name", stack["StackId"])[
        "StackResourceSummaries"
    ]
    original = aws("cloudformation", "get-template", "--stack-name", stack["StackId"])[
        "TemplateBody"
    ]
    template = json.loads(original) if isinstance(original, str) else original
    expected_resources = json.loads(Path("infra/aws/production-base.json").read_text())["Resources"]
    key = next(
        (
            p["ParameterValue"]
            for p in stack.get("Parameters", [])
            if p["ParameterKey"] == "ExistingDatabaseKeyArn"
        ),
        "",
    )
    secrets: dict[str, str] = {
        name: p["ParameterValue"]
        for name in SECRETS
        for p in stack.get("Parameters", [])
        if p["ParameterKey"] == "Existing" + name and p.get("ParameterValue")
    }
    for resource in resources:
        logical, kind, status = (
            resource[k] for k in ["LogicalResourceId", "ResourceType", "ResourceStatus"]
        )
        if logical not in expected_resources or expected_resources[logical]["Type"] != kind:
            raise RuntimeError("BLOCKED: unexpected resource in failed production stack")
        physical = resource.get("PhysicalResourceId")
        if status == "DELETE_COMPLETE" or not physical:
            continue
        if (
            logical == "Database"
            and status in {"CREATE_FAILED", "DELETE_SKIPPED"}
            and physical == "retiro-production"
        ):
            # Retain also applies to a resource whose creation failed. Neither
            # CFN status proves absence: the independent RDS read above must pass.
            if status == "DELETE_SKIPPED" and any(
                template["Resources"][logical].get(p) != "Retain"
                for p in ["DeletionPolicy", "UpdateReplacePolicy"]
            ):
                raise RuntimeError("BLOCKED: protected resource retention policy mismatch")
            continue
        if logical not in {"DatabaseKey", *SECRETS} or status != "DELETE_SKIPPED":
            raise RuntimeError("BLOCKED: unexpected surviving production resource")
        if any(
            template["Resources"][logical].get(p) != "Retain"
            for p in ["DeletionPolicy", "UpdateReplacePolicy"]
        ):
            raise RuntimeError("BLOCKED: protected resource retention policy mismatch")
        if logical == "DatabaseKey":
            if key:
                raise RuntimeError("BLOCKED: ambiguous retained production key")
            key = physical
        else:
            if logical in secrets:
                raise RuntimeError("BLOCKED: ambiguous retained production secret")
            validate_secret(logical, physical)
            secrets[logical] = physical
    if key:
        key = validate_key(key)
    for logical, arn in secrets.items():
        validate_secret(logical, arn)
    snapshot = [
        {
            k: r.get(k)
            for k in ["LogicalResourceId", "ResourceType", "ResourceStatus", "PhysicalResourceId"]
        }
        for r in resources
    ]
    snapshot.sort(key=lambda r: str(r["LogicalResourceId"]))
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    return {
        "schema_version": 1,
        "stack_name": STACK,
        "stack_id": stack["StackId"],
        "resource_fingerprint": fingerprint,
        "database_absent": True,
        "retained_database_key_arn": key,
        "retained_secrets": secrets,
    }


def retained_parameters(plan: dict[str, Any]) -> list[str]:
    if (
        plan.get("schema_version") != 1
        or plan.get("stack_name") != STACK
        or plan.get("database_absent") is not True
    ):
        raise RuntimeError("BLOCKED: exact private recovery plan required")
    require_database_absent()
    parameters = []
    if plan.get("retained_database_key_arn"):
        key = validate_key(plan["retained_database_key_arn"])
        parameters.append("ExistingDatabaseKeyArn=" + key)
    for logical, arn in plan.get("retained_secrets", {}).items():
        validate_secret(logical, arn)
        parameters.append("Existing" + logical + "=" + arn)
    return parameters


def remove_failed_record(expected: dict[str, Any]) -> None:
    """Caller must verify source, free plan and live budget before this mutation."""
    observed = inspect()
    if observed != expected:
        raise RuntimeError("BLOCKED: production recovery plan drift; nothing removed")
    aws("cloudformation", "delete-stack", "--stack-name", observed["stack_id"])
    aws("cloudformation", "wait", "stack-delete-complete", "--stack-name", observed["stack_id"])
    # Prove the protected references survived deletion before permitting a retry.
    retained_parameters(observed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=Path("work/production-recovery-plan.json"))
    args = parser.parse_args()
    with operation("RECOVERY_INSPECTION"):
        plan = inspect()
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        args.plan.parent.chmod(0o700)
        descriptor = os.open(
            args.plan, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(descriptor, "w") as stream:
            json.dump(plan, stream, indent=2)
        args.plan.chmod(0o600)
    print(
        json.dumps(
            {
                "inspection_passed": True,
                "database_absent": True,
                "retained_keys": int(bool(plan["retained_database_key_arn"])),
                "retained_secrets": len(plan["retained_secrets"]),
                "stack_removed": False,
                "business_enabled": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        raise SystemExit(failure(error)) from None
