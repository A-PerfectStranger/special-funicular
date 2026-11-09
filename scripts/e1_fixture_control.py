"""Main acceptance caller: change only two fixed synthetic accounts using a private task."""

import argparse
import copy
import json
import os
import re
from pathlib import Path

import boto3

from scripts.aws_cli import aws
from scripts.commission_e1 import outputs
from scripts.commission_staging import register
from scripts.e1_fixture_data import identifier
from scripts.isolated_task import run_isolated_task

USERS = ["e1-a-p1", "e1-b-guard"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["revoke", "restore", "restore-all"])
    parser.add_argument("username", nargs="?", choices=USERS)
    options = parser.parse_args()
    if options.action != "restore-all" and options.username is None:
        parser.error("One fixed synthetic account is required")
    session = boto3.Session(region_name="us-east-1")
    caller = session.client("sts").get_caller_identity()
    if caller["Account"] != "028364485203" or not caller["Arn"].startswith(
        "arn:aws:sts::028364485203:assumed-role/retiro-staging-E1Acceptance/"
    ):
        raise RuntimeError("Isolated acceptance identity required")
    config = outputs("retiro-staging-e1")
    state = json.loads(
        session.client("secretsmanager").get_secret_value(
            SecretId=config["AcceptanceFixtureSecret"]
        )["SecretString"]
    )
    environment = json.loads(Path("infra/environments/staging.json").read_text())
    if environment.get("synthetic_only") is not True or not state.get("roster_ready"):
        raise RuntimeError("Prepared synthetic staging required")
    previous = aws("ecs", "describe-task-definition", "--task-definition", "retiro-staging-api")[
        "taskDefinition"
    ]
    container = previous["containerDefinitions"][0]
    values = {item["name"]: item["value"] for item in container["environment"]}
    if (
        not re.fullmatch(
            r"028364485203\.dkr\.ecr\.us-east-1\.amazonaws\.com/retiro-staging/backend@sha256:[0-9a-f]{64}",
            container["image"],
        )
        or values.get("GIT_SHA") != os.environ.get("GITHUB_SHA")
        or values.get("APP_ENV") != "staging"
        or values.get("E1_IDENTITY_ENABLED") != "true"
        or previous.get("taskRoleArn") != config["ApiTaskArn"]
    ):
        raise RuntimeError("Current approved E1 trial required")
    definition = {
        key: copy.deepcopy(previous[key])
        for key in [
            "networkMode",
            "requiresCompatibilities",
            "cpu",
            "memory",
            "runtimePlatform",
            "containerDefinitions",
        ]
    }
    definition["family"] = "retiro-staging-fixture"
    definition["executionRoleArn"] = config["FixtureExecutionArn"]
    container = definition["containerDefinitions"][0]
    container.pop("portMappings", None)
    selected = USERS if options.action == "restore-all" else [options.username]
    targets = [
        {"id": identifier(name), "subject": state["users"][name]["sub"]} for name in selected
    ]
    data = {
        "synthetic_only": True,
        "issuer": config["Issuer"],
        "targets": targets,
        "active": options.action != "revoke",
    }
    allowed = {"APP_ENV", "GIT_SHA", "PGHOST", "PGDATABASE", "PGSSLMODE", "PGSSLROOTCERT"}
    container["environment"] = [
        {"name": key, "value": value} for key, value in values.items() if key in allowed
    ]
    container["environment"] += [
        {"name": "PGUSER", "value": "retiro_importer"},
        {"name": "E1_FIXTURE_CONTROL", "value": json.dumps(data)},
    ]
    container["secrets"] = [{"name": "PGPASSWORD", "valueFrom": config["ImporterPassword"]}]
    container["command"] = ["python", "-c", Path("scripts/change_e1_fixture.py").read_text()]
    container["logConfiguration"]["options"]["awslogs-stream-prefix"] = "fixture-control"
    task_definition = register(definition)
    network = {
        "awsvpcConfiguration": {
            "subnets": environment["subnets"],
            "securityGroups": environment["security_groups"],
            "assignPublicIp": "ENABLED",
        }
    }
    ended = run_isolated_task(aws, environment["cluster"], task_definition, network)
    if not ended.get("containers") or any(
        item.get("exitCode") != 0 for item in ended["containers"]
    ):
        raise RuntimeError("Private status command failed")
    print("Synthetic fixture control: " + options.action + " PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("BLOCKED: private synthetic status control failed; inspect AWS privately")
        raise SystemExit(2) from None
