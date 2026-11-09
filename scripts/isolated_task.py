"""Bounded retry for an isolated staging container proven never to have started."""

import json
from collections.abc import Callable
from typing import Any

from scripts.task_diagnostics import task_outcome


def run_isolated_task(
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
            raise RuntimeError("Isolated task not created")
        arn = result["tasks"][0]["taskArn"]
        call("ecs", "wait", "tasks-stopped", "--cluster", cluster, "--tasks", arn)
        ended: list[dict[str, Any]] = call(
            "ecs", "describe-tasks", "--cluster", cluster, "--tasks", arn
        )["tasks"]
        if len(ended) != 1:
            raise RuntimeError("Isolated task status missing")
        task = ended[0]
        print(
            "Isolated task outcome: " + json.dumps({"attempt": attempt + 1, **task_outcome(task)})
        )
        never_started = (
            task.get("stopCode") == "TaskFailedToStart"
            and not task.get("startedAt")
            and all(
                c.get("exitCode") is None and c.get("lastStatus") != "RUNNING"
                for c in task.get("containers", [])
            )
        )
        if attempt == 0 and never_started:
            print("Isolated task startup failed before execution; one bounded retry.")
            continue
        return task
    raise RuntimeError("Isolated startup exhausted")
