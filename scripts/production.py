"""Shared boundaries for the isolated, technical-only first production window."""

import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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


def failure() -> int:
    print(
        '{"status":"BLOCKED","code":"PRODUCTION_OPERATION_FAILED",'
        '"detail":"Inspect private operator logs; no business acceptance claimed"}'
    )
    return 2
