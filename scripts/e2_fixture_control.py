"""E1Acceptance can invoke only fixed E2 synthetic cohort commands, never accept arbitrary SQL."""

import argparse
import copy
import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import boto3

from scripts.aws_cli import aws
from scripts.commission_e1 import outputs
from scripts.commission_staging import register
from scripts.e1_fixture_data import identifier

SELECTION = Path("work/e2-selected-trial.json")


class CohortUsed(Exception):
    """A synthetic cohort already has durable rows; never reset it."""


def read_context() -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
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
    environment = json.loads(Path("infra/environments/staging.json").read_text())
    if (
        environment.get("synthetic_only") is not True
        or environment.get("pickup_enabled") is not False
    ):
        raise RuntimeError("Synthetic only")
    if state.get("schema_version") != 1 or state.get("roster_ready") is not True:
        raise RuntimeError("Prepared synthetic fixture catalogue required")
    return state, config, environment


def release_sha() -> str:
    return os.environ.get("E2_RELEASE_SHA", os.environ.get("GITHUB_SHA", ""))


def available_cohorts(state: dict[str, Any], sha: str) -> list[dict[str, Any]]:
    if not re.fullmatch("[0-9a-f]{40}", sha):
        raise RuntimeError("Immutable release required")
    pooled = state.get("e2_pool")
    if pooled is not None:
        if not isinstance(pooled, list) or not 1 <= len(pooled) <= 8:
            raise RuntimeError("Bounded cohort pool required")
        cohorts = pooled
    else:
        single = state.get("e2", {})
        if single.get("release_sha") != sha:
            raise RuntimeError("Prepared cohort for this exact release required")
        cohorts = [single]
    seen: set[str] = set()
    for value in cohorts:
        trial = str(uuid.UUID(value["trial_id"]))
        users = value.get("users", {})
        if (
            trial in seen
            or len(users) != 2
            or not all(
                u.get("mfa_ready") is True
                and u.get("password")
                and u.get("totp_seed")
                and u.get("sub")
                and u.get("invitation")
                and u.get("contact", "").endswith("@synthetic.invalid")
                for u in users.values()
            )
            or {u.get("principal") for u in users.values()} != {True, False}
        ):
            raise RuntimeError("Complete independent synthetic cohort required")
        seen.add(trial)
    return [
        {**value, "prepared_sha": value["release_sha"], "release_sha": sha} for value in cohorts
    ]


def load() -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    state, config, environment = read_context()
    sha = release_sha()
    cohorts = available_cohorts(state, sha)
    if SELECTION.exists():
        selected = json.loads(SELECTION.read_text())
        if selected.get("sha") != sha:
            raise RuntimeError("Selection belongs to another release")
        cohort = next((c for c in cohorts if c["trial_id"] == selected.get("trial_id")), None)
        if cohort is None:
            raise RuntimeError("Unknown prepared cohort")
    elif state.get("e2_pool") is not None:
        raise RuntimeError("Explicit job-local cohort selection required")
    else:
        cohort = cohorts[0]
    return cohort, config, environment


def execute(action: str) -> None:
    e2, config, environment = load()
    previous = aws("ecs", "describe-task-definition", "--task-definition", "retiro-staging-api")[
        "taskDefinition"
    ]
    values = {i["name"]: i["value"] for i in previous["containerDefinitions"][0]["environment"]}
    image = previous["containerDefinitions"][0]["image"]
    expected_digest = os.environ.get("E2_RELEASE_DIGEST", "")
    if not re.fullmatch("sha256:[0-9a-f]{64}", expected_digest):
        raise RuntimeError("Approved immutable image digest required")
    if (
        image
        != "028364485203.dkr.ecr.us-east-1.amazonaws.com/retiro-staging/backend@" + expected_digest
        or values.get("GIT_SHA") != e2["release_sha"]
        or values.get("E2_FAMILY_ENABLED") != "true"
        or previous.get("taskRoleArn") != config["ApiTaskArn"]
        or not re.fullmatch(
            r"028364485203\.dkr\.ecr\.us-east-1\.amazonaws\.com/retiro-staging/backend@sha256:[0-9a-f]{64}",
            image,
        )
    ):
        raise RuntimeError("Approved current E2 API required")
    batch = e2["batch"]
    users = list(e2["users"].values())
    secondary = next(u for u in users if not u["principal"])
    primary = next(u for u in users if u["principal"])
    command: dict[str, Any] = {"action": action}
    if action == "seed":
        command.update(
            batch=batch,
            parents=[
                {"id": u["parent_id"], "hash": hashlib.sha256(u["invitation"].encode()).hexdigest()}
                for u in users
            ],
        )
    elif action == "bulk-drill":
        command.update(
            batch=batch, other_school_id=identifier("school-b"), other_site_id=identifier("site-b")
        )
    else:
        command.update(school_id=batch["school_id"], target=batch["students"][0]["id"])
        command.update(
            issuer=config["Issuer"],
            expected_accounts=[{"parent_id": u["parent_id"], "subject": u["sub"]} for u in users],
        )
        if action == "principal":
            command.update(operation="CHANGE_PRINCIPAL", data={"parent_id": secondary["parent_id"]})
        elif action == "original-principal":
            command.update(operation="CHANGE_PRINCIPAL", data={"parent_id": primary["parent_id"]})
        elif action == "deactivate":
            command.update(
                operation="DEACTIVATE", data={}, account_parent_id=secondary["parent_id"]
            )
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
    codes = [c.get("exitCode") for c in ended.get("containers", [])]
    if action == "seed" and codes == [42]:
        raise CohortUsed()
    if codes != [0]:
        raise RuntimeError("Private task rejected")
    print("E2 fixed synthetic control committed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["seed", "principal", "original-principal", "block", "deactivate", "bulk-drill"],
    )
    args = parser.parse_args()
    try:
        execute(args.action)
    except Exception:
        print("BLOCKED: E2 synthetic control failed; inspect privately.")
        raise SystemExit(2) from None
