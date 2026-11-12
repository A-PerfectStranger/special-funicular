"""Shared boundaries for the isolated, technical-only first production window."""

import json
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

from scripts.aws_cli import aws
from scripts.commission_e1 import outputs
from scripts.commission_staging import task_definition
from scripts.validate_deploy import validate

ACCOUNT = "028364485203"
SERVICE = f"arn:aws:ecs:us-east-1:{ACCOUNT}:service/retiro-production/retiro-api"
SOURCE_REPOSITORY = "retiro-staging/backend"
IMAGE_REPOSITORY = f"{ACCOUNT}.dkr.ecr.us-east-1.amazonaws.com/{SOURCE_REPOSITORY}"
CONFIG = Path("infra/environments/production.json")
FLAGS = ["e1_enabled", "e2_enabled", "e3_enabled", "e4_enabled", "pickup_enabled"]
STAGES = {
    "PRODUCTION",
    "SOURCE_APPROVAL",
    "FOUNDATION",
    "BILLING_PREFLIGHT",
    "ECS_SERVICE_ROLE",
    "RDS_ENGINE_SELECTION",
    "RETAINED_SECRET_METADATA",
    "CLOUDFORMATION_BASE",
    "CLOUDFORMATION_LIFECYCLE",
    "COST_PLAN_STORAGE",
    "SERVICE_COMMISSION",
    "PRODUCTION_PREPARE",
    "PRODUCTION_MIGRATE",
    "PRODUCTION_DEPLOY",
    "RECOVERY_INSPECTION",
    "RECOVERY_REMOVE_FAILED_RECORD",
}
AWS_ERROR_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "ExpiredToken",
    "ExpiredTokenException",
    "ValidationError",
    "ValidationException",
    "ResourceNotFoundException",
    "ImageNotFoundException",
    "InsufficientCapabilitiesException",
    "AlreadyExistsException",
    "ThrottlingException",
    "RequestLimitExceeded",
    "LimitExceededException",
    "CliRequestFailed",
}


@contextmanager
def operation(stage: str) -> Iterator[None]:
    if stage not in STAGES:
        raise ValueError("Unknown production stage")
    print(json.dumps({"stage": stage, "status": "STARTED"}), flush=True)
    try:
        yield
    except Exception as error:
        # Preserve the original exception for callers; only fixed diagnostics
        # are serialized by failure(). Nested operations retain the deepest stage.
        current = getattr(error, "production_stage", None)
        if not isinstance(current, str) or current not in STAGES:
            error.production_stage = stage  # type: ignore[attr-defined]
        raise


def technical_only(config: dict[str, Any]) -> None:
    if (
        config.get("environment") != "production"
        or config.get("commissioning_mode") != "technical_only"
        or config.get("synthetic_only") is not True
        or any(config.get(flag) is not False for flag in FLAGS)
    ):
        raise RuntimeError("BLOCKED: technical production cannot enable business operations")


def configuration() -> dict[str, Any]:
    config: dict[str, Any] = json.loads(CONFIG.read_text())
    technical_only(config)
    if validate(config):
        raise RuntimeError("BLOCKED: production configuration has not been commissioned")
    if (
        config["account_id"] != ACCOUNT
        or config["cluster"] != "retiro-production"
        or config["service"] != SERVICE
        or config["image_repository"] != IMAGE_REPOSITORY
        or config["deploy_role_arn"] != f"arn:aws:iam::{ACCOUNT}:role/retiro-production-Deploy"
        or config["migration_role_arn"] != f"arn:aws:iam::{ACCOUNT}:role/retiro-production-Migrate"
    ):
        raise RuntimeError("BLOCKED: unexpected production target")
    return config


def candidate(sha: str, digest: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise RuntimeError("BLOCKED: immutable candidate required")
    latest = subprocess.check_output(
        ["git", "ls-remote", "origin", "refs/heads/main"], text=True
    ).split()[0]
    if latest != sha:
        raise RuntimeError("OBSOLETE: candidate is not the latest main")
    images = aws(
        "ecr",
        "describe-images",
        "--repository-name",
        SOURCE_REPOSITORY,
        "--image-ids",
        "imageTag=" + sha,
    ).get("imageDetails", [])
    if len(images) != 1 or images[0].get("imageDigest") != digest:
        raise RuntimeError("BLOCKED: approved source tag/digest mismatch")


def identity(role: str) -> None:
    caller = aws("sts", "get-caller-identity")
    if caller.get("Account") != ACCOUNT or not caller.get("Arn", "").startswith(
        f"arn:aws:sts::{ACCOUNT}:assumed-role/retiro-production-{role}/"
    ):
        raise RuntimeError("BLOCKED: isolated production identity required")


def base_outputs(config: dict[str, Any]) -> dict[str, str]:
    base = outputs("retiro-production-base")
    if (
        base["Cluster"] != config["cluster"]
        or base["ImageRepository"] != config["image_repository"]
        or sorted([base["Public0"], base["Public1"]]) != sorted(config["subnets"])
        or [base["AppSecurityGroup"]] != config["security_groups"]
        or base["Deploy"] != config["deploy_role_arn"]
        or base["Migrate"] != config["migration_role_arn"]
    ):
        raise RuntimeError("BLOCKED: production configuration/stack drift")
    for key in ["DjangoSecret", "RuntimePassword", "MigrationPassword"]:
        if not base[key].startswith(
            f"arn:aws:secretsmanager:us-east-1:{ACCOUNT}:secret:retiro-production/"
        ):
            raise RuntimeError("BLOCKED: production requires isolated managed secrets")
    return base


def definition(base: dict[str, str], image: str, sha: str, mode: str) -> dict[str, Any]:
    if mode not in {"api", "migrate", "bootstrap"}:
        raise ValueError("Unknown production task mode")
    task = task_definition(base, image, sha, mode == "bootstrap")
    task["family"] = "retiro-production-" + mode
    container = task["containerDefinitions"][0]
    env = {item["name"]: item["value"] for item in container["environment"]}
    env.update(
        APP_ENV="production",
        E1_IDENTITY_ENABLED="false",
        E2_FAMILY_ENABLED="false",
        E3_PICKUP_ENABLED="false",
        E4_OPERATIONS_ENABLED="false",
    )
    if mode == "migrate":
        task["executionRoleArn"] = base["MigrationExecution"]
        env["PGUSER"] = "retiro_migrator"
        container["command"] = ["python", "manage.py", "migrate_locked", "--noinput"]
        container["secrets"] = [
            {"name": "DJANGO_SECRET_KEY", "valueFrom": base["DjangoSecret"]},
            {"name": "PGPASSWORD", "valueFrom": base["MigrationPassword"]},
        ]
    elif mode == "bootstrap":
        container["command"] = [
            "python",
            "-c",
            Path("scripts/bootstrap_production_database.py").read_text(),
        ]
    if mode != "api":
        container.pop("portMappings", None)
    container["environment"] = [{"name": k, "value": v} for k, v in env.items()]
    return task


def network(base: dict[str, str]) -> dict[str, Any]:
    return {
        "awsvpcConfiguration": {
            "subnets": [base["Public0"], base["Public1"]],
            "securityGroups": [base["AppSecurityGroup"]],
            "assignPublicIp": "ENABLED",
        }
    }


def arm_window() -> str:
    """Arm teardown BEFORE opening resources; retain DB, keys, backups and secrets."""
    expiry = datetime.now(UTC) + timedelta(hours=3)
    role = outputs("retiro-production-lifecycle")["ExpiryRoleArn"]
    # Commissioning creates both schedules; missing guards block, never imply absence.
    for name, deadline in [
        ("retiro-production-expiry-api", expiry),
        ("retiro-production-db-idle-guard", expiry + timedelta(minutes=15)),
    ]:
        schedule = aws("scheduler", "get-schedule", "--name", name)
        expected_action = (
            "deleteExpressGatewayService" if name.endswith("api") else "stopDBInstance"
        )
        if (
            schedule["Target"].get("RoleArn") != role
            or schedule["Target"].get("Arn")
            != "arn:aws:scheduler:::aws-sdk:"
            + ("ecs:" if name.endswith("api") else "rds:")
            + expected_action
            or json.loads(schedule["Target"]["Input"])
            != (
                {"ServiceArn": SERVICE}
                if name.endswith("api")
                else {"DbInstanceIdentifier": "retiro-production"}
            )
        ):
            raise RuntimeError("BLOCKED: production lifecycle target drift")
        args = [
            "scheduler",
            "update-schedule",
            "--name",
            name,
            "--schedule-expression",
            "at(" + deadline.strftime("%Y-%m-%dT%H:%M:%S") + ")"
            if name.endswith("api")
            else schedule["ScheduleExpression"],
            "--schedule-expression-timezone",
            "UTC",
            "--flexible-time-window",
            json.dumps(schedule["FlexibleTimeWindow"]),
            "--target",
            json.dumps(schedule["Target"]),
            "--state",
            "ENABLED",
        ]
        if not name.endswith("api"):
            args += ["--start-date", deadline.isoformat()]
        aws(*args)
    return expiry.isoformat()


def report(name: str, data: dict[str, Any]) -> None:
    Path("work").mkdir(exist_ok=True)
    Path("work/" + name + ".json").write_text(json.dumps(data, indent=2) + "\n")


def failure(error: Exception | None = None) -> int:
    stage = getattr(error, "production_stage", "PRODUCTION")
    result: dict[str, Any] = {
        "status": "BLOCKED",
        "stage": stage if isinstance(stage, str) and stage in STAGES else "PRODUCTION",
        "code": "PRODUCTION_OPERATION_FAILED",
        "business_enabled": False,
    }
    codes = {
        "BLOCKED: clean reviewed main source required": "SOURCE_NOT_CLEAN_OR_WRONG_SHA",
        "OBSOLETE: candidate is not the latest main": "OBSOLETE_CANDIDATE",
        "BLOCKED: approved source tag/digest mismatch": "SOURCE_DIGEST_MISMATCH",
        "BLOCKED: approved main CI required before commissioning": "MAIN_CI_NOT_APPROVED",
        "BLOCKED: production billing/custody preflight": "BILLING_PREFLIGHT_FAILED",
        "BLOCKED: existing ECS service-linked role required": "ECS_SERVICE_ROLE_MISSING",
        "BLOCKED: selected private PostgreSQL instance unavailable": "RDS_INSTANCE_UNAVAILABLE",
        "BLOCKED: retained production secret ownership/state mismatch": "SECRET_METADATA_DRIFT",
        "BLOCKED: production stack requires operator inspection; nothing deleted": (
            "STACK_NOT_UPDATABLE"
        ),
        "BLOCKED: production CloudFormation failed; inspect private stack events": (
            "CLOUDFORMATION_DEPLOY_FAILED"
        ),
        "BLOCKED: production database exists; automatic stack recovery prohibited": (
            "RECOVERY_REQUIRES_DATABASE_ABSENCE"
        ),
        "BLOCKED: production recovery plan drift; nothing removed": "RECOVERY_PLAN_DRIFT",
        "BLOCKED: retained production key metadata mismatch": "RETAINED_KEY_METADATA_DRIFT",
        "BLOCKED: retained production key policy mismatch": "RETAINED_KEY_POLICY_DRIFT",
        "Wrong AWS account": "WRONG_ACCOUNT",
        "Verified AWS operator identity required": "OPERATOR_IDENTITY_REQUIRED",
        "CI/runtime roles are not provisioning operators": "CI_IDENTITY_REJECTED",
        "BLOCKED: production CI/runtime identities are not operators": "CI_IDENTITY_REJECTED",
        "BLOCKED: unexpected failed production stack ownership/state": "STACK_OWNERSHIP_OR_STATE",
        "BLOCKED: unexpected resource in failed production stack": "RECOVERY_UNKNOWN_RESOURCE",
        "BLOCKED: unexpected surviving production resource": "RECOVERY_UNEXPECTED_SURVIVOR",
        "BLOCKED: protected resource retention policy mismatch": "RECOVERY_RETENTION_POLICY_DRIFT",
        "BLOCKED: ambiguous retained production key": "RECOVERY_AMBIGUOUS_KEY",
        "BLOCKED: ambiguous retained production secret": "RECOVERY_AMBIGUOUS_SECRET",
        "BLOCKED: retained secret reference mismatch": "RETAINED_SECRET_REFERENCE_DRIFT",
        "BLOCKED: retained secret metadata mismatch": "RETAINED_SECRET_METADATA_DRIFT",
    }
    if isinstance(error, RuntimeError):
        result["code"] = codes.get(str(error), result["code"])
        match = re.fullmatch(
            r"(sts\.get-caller-identity|ecr\.describe-images|ssm\.get-parameter|ssm\.put-parameter|"
            r"budgets\.describe-budget|ce\.get-cost-and-usage|freetier\.get-account-plan-state|"
            r"rds\.describe-db-engine-versions|rds\.describe-orderable-db-instance-options|"
            r"cloudformation\.describe-stacks|cloudformation\.list-stack-resources|"
            r"cloudformation\.get-template|rds\.describe-db-instances|"
            r"kms\.describe-key|kms\.list-resource-tags|kms\.get-key-rotation-status|"
            r"kms\.get-key-policy|secretsmanager\.describe-secret): ([A-Za-z0-9_]{1,64})",
            str(error),
        )
        if match:
            result.update(
                code="AWS_REQUEST_FAILED",
                operation=match[1],
                aws_code=match[2] if match[2] in AWS_ERROR_CODES else "AWS_ERROR",
            )
    if isinstance(error, HTTPError):
        result.update(code="HTTP_REQUEST_FAILED", http_status=error.code)
    error_type = type(error).__name__
    if error_type in {
        "ValueError",
        "KeyError",
        "TypeError",
        "FileNotFoundError",
        "PermissionError",
        "HTTPError",
        "URLError",
        "TimeoutError",
        "JSONDecodeError",
        "RuntimeError",
    }:
        result["error_type"] = error_type
    try:
        report("production-operation-failure", result)
    except OSError:
        pass
    print(json.dumps(result), flush=True)
    return 2
