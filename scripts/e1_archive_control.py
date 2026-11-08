"""Bounded synthetic archive drill control; no API, evidence, retention or key mutation."""

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from scripts.aws_cli import aws
from scripts.commission_e1 import outputs
from scripts.commission_staging import runtime_digests
from scripts.e1_release import start_archive

STATE = Path("work/e1-archive-drill-control.json")


def validate_definition(
    definition: dict[str, Any], config: dict[str, str], sha: str, digest: str
) -> None:
    containers = definition.get("containerDefinitions", [])
    if len(containers) != 1:
        raise RuntimeError("One isolated archive container required")
    container = containers[0]
    environment = {item["name"]: item["value"] for item in container.get("environment", [])}
    if (
        definition.get("family") != "retiro-staging-archive"
        or definition.get("taskRoleArn") != config["ArchiveTaskArn"]
        or definition.get("executionRoleArn") != config["ArchiveExecutionArn"]
        or container.get("image")
        != ("028364485203.dkr.ecr.us-east-1.amazonaws.com/retiro-staging/backend@" + digest)
        or environment.get("GIT_SHA") != sha
        or environment.get("PGUSER") != "retiro_archiver"
        or environment.get("APP_ENV") != "staging"
        or container.get("command")
        != ["python", "-m", "archive_worker.runner", "--max-runtime-seconds", "10800"]
        or container.get("secrets")
        != [{"name": "PGPASSWORD", "valueFrom": config["ArchivePassword"]}]
    ):
        raise RuntimeError("Approved isolated archive definition required")


def control(action: str, sha: str, digest: str) -> None:
    if not re.fullmatch("[0-9a-f]{40}", sha) or not re.fullmatch("sha256:[0-9a-f]{64}", digest):
        raise RuntimeError("Immutable candidate required")
    identity = aws("sts", "get-caller-identity")
    if identity["Account"] != "028364485203" or not identity["Arn"].startswith(
        "arn:aws:sts::028364485203:assumed-role/retiro-staging-Deploy/"
    ):
        raise RuntimeError("Isolated Deploy identity required")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    latest = subprocess.check_output(
        ["git", "ls-remote", "origin", "refs/heads/main"], text=True
    ).split()[0]
    # Recovery of this exact saved worker remains allowed if main advanced during the drill.
    if head != sha or (action == "pause" and latest != sha):
        raise RuntimeError("Current reviewed main candidate required")
    base, config = outputs("retiro-staging-base"), outputs("retiro-staging-e1")
    cluster = base["Cluster"]
    if action == "resume":
        state = json.loads(STATE.read_text())
        if (
            state.get("sha") != sha
            or state.get("digest") != digest
            or state.get("cluster") != cluster
        ):
            raise RuntimeError("Matching private drill state required")
        arn = state["definition"]
        definition = aws("ecs", "describe-task-definition", "--task-definition", arn)[
            "taskDefinition"
        ]
        validate_definition(definition, config, sha, digest)
        start_archive(base, arn, runtime_digests(digest))
        return
    arns = aws("ecs", "list-tasks", "--cluster", cluster, "--family", "retiro-staging-archive")[
        "taskArns"
    ]
    if not arns:
        raise RuntimeError("A healthy archive worker is required before the drill")
    tasks = aws("ecs", "describe-tasks", "--cluster", cluster, "--tasks", *arns)["tasks"]
    definitions = {task["taskDefinitionArn"] for task in tasks}
    if len(tasks) != len(arns) or len(definitions) != 1:
        raise RuntimeError("A single verified archive definition required")
    definition_arn = definitions.pop()
    definition = aws("ecs", "describe-task-definition", "--task-definition", definition_arn)[
        "taskDefinition"
    ]
    validate_definition(definition, config, sha, digest)
    expected = runtime_digests(digest)
    if any(
        task.get("lastStatus") != "RUNNING"
        or not task.get("containers")
        or any(container.get("imageDigest") not in expected for container in task["containers"])
        for task in tasks
    ):
        raise RuntimeError("A healthy approved archive worker is required")
    STATE.parent.mkdir(exist_ok=True)
    # Record recovery information before the first stop, including partial-stop failures.
    STATE.write_text(
        json.dumps({"sha": sha, "digest": digest, "cluster": cluster, "definition": definition_arn})
    )
    for arn in arns:
        aws(
            "ecs",
            "stop-task",
            "--cluster",
            cluster,
            "--task",
            arn,
            "--reason",
            "Synthetic E1 archive-absence acceptance drill",
        )
    aws("ecs", "wait", "tasks-stopped", "--cluster", cluster, "--tasks", *arns)
    remaining = aws(
        "ecs", "list-tasks", "--cluster", cluster, "--family", "retiro-staging-archive"
    )["taskArns"]
    if remaining:
        raise RuntimeError("Archive absence was not established")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["pause", "resume"])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--digest", required=True)
    options = parser.parse_args()
    try:
        control(options.action, options.sha, options.digest)
        print("Synthetic archive control: " + options.action + " PASS")
    except Exception:
        print("BLOCKED: synthetic archive control failed; inspect AWS privately")
        raise SystemExit(2) from None
