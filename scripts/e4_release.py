"""E4 reuses the approved digest with a notifier-only SQL and execution identity."""

import copy
from typing import Any

from scripts.commission_staging import task_definition


def notification_definition(
    base: dict[str, str], config: dict[str, str], image: str, sha: str
) -> dict[str, Any]:
    required = [
        "NotifierTaskArn",
        "NotifierExecutionArn",
        "NotifierPassword",
        "ExpoAccessTokenSecret",
        "AllowedDevicesSecret",
    ]
    if any(not config.get(key) for key in required):
        raise RuntimeError("BLOCKED: E4 notifier credentials and team allowlist required")
    definition = copy.deepcopy(task_definition(base, image, sha, False))
    definition["family"] = "retiro-staging-notifications"
    definition["taskRoleArn"] = config["NotifierTaskArn"]
    definition["executionRoleArn"] = config["NotifierExecutionArn"]
    container = definition["containerDefinitions"][0]
    container.pop("portMappings", None)
    container["command"] = [
        "python",
        "-m",
        "notification_worker.runner",
        "--max-runtime-seconds",
        "10800",
    ]
    # No Django secret, runtime, reader, archiver, importer or migration credential.
    environment = {item["name"]: item["value"] for item in container["environment"]}
    environment.update({"PGUSER": "retiro_notifier"})
    container["environment"] = [{"name": k, "value": v} for k, v in environment.items()]
    container["secrets"] = [
        {"name": "PGPASSWORD", "valueFrom": config["NotifierPassword"]},
        {"name": "EXPO_PUSH_ACCESS_TOKEN", "valueFrom": config["ExpoAccessTokenSecret"]},
        {"name": "EXPO_PUSH_ALLOWED_TOKEN_HASHES", "valueFrom": config["AllowedDevicesSecret"]},
    ]
    container["logConfiguration"]["options"]["awslogs-stream-prefix"] = "notifications"
    return definition
