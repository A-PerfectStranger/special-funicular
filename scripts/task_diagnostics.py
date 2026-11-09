"""Public-safe ECS outcome metadata: never include raw reasons, environment or logs."""

from typing import Any


def task_outcome(task: dict[str, Any]) -> dict[str, Any]:
    stop_codes = {
        "TaskFailedToStart",
        "EssentialContainerExited",
        "UserInitiated",
        "ServiceSchedulerInitiated",
        "SpotInterruption",
        "TerminationNotice",
    }
    kinds = [
        "ResourceInitializationError",
        "CannotPullContainerError",
        "CannotStartContainerError",
        "OutOfMemoryError",
        "ContainerRuntimeError",
    ]
    containers = task.get("containers", [])
    reasons = [task.get("stoppedReason", "")] + [c.get("reason", "") for c in containers]
    return {
        "stop_code": task.get("stopCode") if task.get("stopCode") in stop_codes else "OTHER",
        "started": bool(task.get("startedAt")),
        "exit_codes": [
            c.get("exitCode") if type(c.get("exitCode")) is int else None for c in containers
        ],
        "reason_type": next(
            (kind for kind in kinds if any(kind in str(r) for r in reasons)), "OTHER"
        ),
    }
