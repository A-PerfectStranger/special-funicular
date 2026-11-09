"""Bounded retry for a synthetic fixture container proven never to have started."""

import json
from collections.abc import Callable
from typing import Any


def run_fixture_task(
    call: Callable[..., dict[str, Any]],
    cluster: str,
    definition: str,
    network: dict[str, Any],
) -> dict[str, Any]:
    for attempt in range(2):
        result = call(
            "ecs",
            "run-task",
            "--cluster",
            cluster,
            "--task-definition",
            definition,
            "--launch-type",
            "FARGATE",
            "--network-configuration",
            json.dumps(network),
        )
        if result.get("failures") or len(result.get("tasks", [])) != 1:
            raise RuntimeError("Private fixture task not created")
        arn = result["tasks"][0]["taskArn"]
        call("ecs", "wait", "tasks-stopped", "--cluster", cluster, "--tasks", arn)
        ended: list[dict[str, Any]] = call(
            "ecs", "describe-tasks", "--cluster", cluster, "--tasks", arn
        )["tasks"]
        if len(ended) != 1:
            raise RuntimeError("Private fixture task status missing")
        task = ended[0]
        never_started = (
            task.get("stopCode") == "TaskFailedToStart"
            and not task.get("startedAt")
            and all(
                c.get("exitCode") is None and c.get("lastStatus") != "RUNNING"
                for c in task.get("containers", [])
            )
        )
        if attempt == 0 and never_started:
            print("Synthetic fixture startup failed before execution; one bounded retry.")
            continue
        return task
    raise RuntimeError("Private fixture startup exhausted")
