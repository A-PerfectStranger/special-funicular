"""E1Acceptance can invoke only fixed E2 synthetic cohort commands, never accept arbitrary SQL."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import boto3

from scripts.aws_cli import aws
from scripts.commission_e1 import outputs
from scripts.commission_staging import register


def load() -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    session = boto3.Session(region_name="us-east-1")
    caller = session.client("sts").get_caller_identity()
    if caller["Account"] != "028364485203" or not caller["Arn"].startswith(
        "arn:aws:sts::028364485203:assumed-role/retiro-staging-E1Acceptance/"
    ):
        raise RuntimeError("Isolated acceptance required")
    config = outputs("retiro-staging-e1")
    state = json.loads(
        session.client("secretsmanager").get_secret_value(
            SecretId=config["AcceptanceFixtureSecret"]
        )["SecretString"]
    )
    e2 = state.get("e2", {})
    if (
        e2.get("release_sha") != os.environ.get("GITHUB_SHA")
        or len(e2.get("users", {})) != 2
        or not all(r.get("mfa_ready") for r in e2["users"].values())
    ):
        raise RuntimeError("Fresh prepared E2 cohort for this release required")
    environment = json.loads(Path("infra/environments/staging.json").read_text())
    if (
        environment.get("synthetic_only") is not True
        or environment.get("pickup_enabled") is not False
    ):
        raise RuntimeError("Synthetic only")
    return e2, config, environment


def execute(action: str) -> None:
    e2, config, environment = load()
    previous = aws("ecs", "describe-task-definition", "--task-definition", "retiro-staging-api")[
        "taskDefinition"
    ]
    values = {i["name"]: i["value"] for i in previous["containerDefinitions"][0]["environment"]}
    image = previous["containerDefinitions"][0]["image"]
    if (
        values.get("GIT_SHA") != e2["release_sha"]
        or values.get("E2_FAMILY_ENABLED") != "true"
        or previous.get("taskRoleArn") != config["ApiTaskArn"]
        or "@sha256:" not in image
    ):
        raise RuntimeError("Approved current E2 API required")
    batch = e2["batch"]
    users = list(e2["users"].values())
    secondary = next(u for u in users if not u["principal"])
    command: dict[str, Any] = {"action": action}
    if action == "seed":
        command.update(
            batch=batch,
            parents=[
                {"id": u["parent_id"], "hash": hashlib.sha256(u["invitation"].encode()).hexdigest()}
                for u in users
            ],
        )
    else:
        command.update(school_id=batch["school_id"], target=batch["students"][0]["id"])
        if action == "principal":
            command.update(operation="CHANGE_PRINCIPAL", data={"parent_id": secondary["parent_id"]})
        elif action == "block":
            command.update(
                operation="SET_POLICY",
                data={"windows": batch["students"][0]["windows"], "blocked": True},
            )
        else:
            raise ValueError()
    definition = {
        k: copy.deepcopy(previous[k])
        for k in [
            "networkMode",
            "requiresCompatibilities",
            "cpu",
            "memory",
            "runtimePlatform",
            "containerDefinitions",
        ]
    }
    definition.update(
        family="retiro-staging-fixture", executionRoleArn=config["FixtureExecutionArn"]
    )
    container = definition["containerDefinitions"][0]
    container.pop("portMappings", None)
    container["environment"] = [
        {"name": k, "value": v}
        for k, v in values.items()
        if k in {"APP_ENV", "GIT_SHA", "PGHOST", "PGDATABASE", "PGSSLMODE", "PGSSLROOTCERT"}
    ]
    container["environment"] += [
        {"name": "PGUSER", "value": "retiro_importer"},
        {"name": "E2_FIXTURE_COMMAND", "value": json.dumps(command)},
    ]
    container["secrets"] = [{"name": "PGPASSWORD", "valueFrom": config["ImporterPassword"]}]
    container["command"] = ["python", "-c", Path("scripts/seed_e2_roster.py").read_text()]
    container["logConfiguration"]["options"]["awslogs-stream-prefix"] = "e2-fixture"
    task = register(definition)
    network = {
        "awsvpcConfiguration": {
            "subnets": environment["subnets"],
            "securityGroups": environment["security_groups"],
            "assignPublicIp": "ENABLED",
        }
    }
    run = aws(
        "ecs",
        "run-task",
        "--cluster",
        environment["cluster"],
        "--task-definition",
        task,
        "--launch-type",
        "FARGATE",
        "--network-configuration",
        json.dumps(network),
    )
    if run.get("failures") or len(run.get("tasks", [])) != 1:
        raise RuntimeError("Private task absent")
    arn = run["tasks"][0]["taskArn"]
    aws("ecs", "wait", "tasks-stopped", "--cluster", environment["cluster"], "--tasks", arn)
    ended = aws("ecs", "describe-tasks", "--cluster", environment["cluster"], "--tasks", arn)[
        "tasks"
    ][0]
    if not ended.get("containers") or any(c.get("exitCode") != 0 for c in ended["containers"]):
        raise RuntimeError("Private task rejected")
    print("E2 fixed synthetic control committed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed", "principal", "block"])
    args = parser.parse_args()
    try:
        execute(args.action)
    except Exception:
        print("BLOCKED: E2 synthetic control failed; inspect privately.")
        raise SystemExit(2) from None
