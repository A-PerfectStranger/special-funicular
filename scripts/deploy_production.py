"""Promote the approved digest into isolated, dark production; never enables school use."""

import argparse
import json
import time
from typing import Any

from scripts.aws_cli import aws
from scripts.commission_staging import register, runtime_digests
from scripts.deploy_staging import candidate_running
from scripts.isolated_task import run_isolated_task
from scripts.production import (
    IMAGE_REPOSITORY,
    SERVICE,
    arm_window,
    base_outputs,
    candidate,
    configuration,
    definition,
    failure,
    identity,
    network,
    report,
)
from scripts.production_preflight import preflight
from scripts.sync_staging_origin import gateway_origin
from scripts.verify_staging import verify
from scripts.verify_staging_network import verify_ingress


def gateway() -> dict[str, Any]:
    state: dict[str, Any] = aws(
        "ecs", "describe-express-gateway-service", "--service-arn", SERVICE
    )["service"]
    if state.get("status", {}).get("statusCode") != "ACTIVE":
        raise RuntimeError("BLOCKED: active commissioned production gateway required")
    return state


def wait_database(base: dict[str, str]) -> None:
    for _ in range(120):
        db = aws("rds", "describe-db-instances", "--db-instance-identifier", "retiro-production")[
            "DBInstances"
        ][0]
        if (
            db.get("PubliclyAccessible") is not False
            or db.get("StorageEncrypted") is not True
            or db.get("KmsKeyId") != base["DatabaseKeyArn"]
            or db.get("BackupRetentionPeriod", 0) < 7
            or db.get("DeletionProtection") is not True
            or db.get("Endpoint", {}).get("Address") != base["DbHost"]
        ):
            raise RuntimeError("BLOCKED: production database privacy/backup/key drift")
        if db["DBInstanceStatus"] == "available":
            return
        if db["DBInstanceStatus"] == "stopped":
            aws("rds", "start-db-instance", "--db-instance-identifier", "retiro-production")
        elif db["DBInstanceStatus"] not in {"starting", "stopping", "backing-up", "modifying"}:
            raise RuntimeError("BLOCKED: unexpected production database state")
        time.sleep(10)
    raise RuntimeError("BLOCKED: production database start timeout")


def migrate(base: dict[str, str], sha: str, digest: str) -> None:
    task = register(definition(base, IMAGE_REPOSITORY + "@" + digest, sha, "migrate"))
    result = run_isolated_task(aws, base["Cluster"], task, network(base))
    if not result.get("containers") or any(c.get("exitCode") != 0 for c in result["containers"]):
        raise RuntimeError("BLOCKED: production migration failed; no deploy permitted")
    report(
        "production-migration",
        {"sha": sha, "digest": digest, "passed": True, "task": result["taskArn"]},
    )


def verify_running(
    base: dict[str, str], task: str, expected: set[str]
) -> tuple[str, dict[str, Any]]:
    for _ in range(100):
        state = aws("ecs", "describe-express-gateway-service", "--service-arn", SERVICE)["service"]
        status = state.get("status", {}).get("statusCode", "")
        if status == "ACTIVE" and candidate_running(base["Cluster"], task, expected):
            origin = gateway_origin(state)
            net = verify_ingress(base["Cluster"], SERVICE, base["AppSecurityGroup"])
            probes = verify(origin)
            if probes["passed"]:
                return origin, {"network": net, "probes": probes}
        if "FAILED" in status:
            break
        time.sleep(10)
    raise RuntimeError("BLOCKED: production digest/TLS/readiness verification failed")


def rollback_definition(base: dict[str, str], state: dict[str, Any]) -> str:
    arn: str = state["activeConfigurations"][0]["taskDefinitionArn"]
    task = aws("ecs", "describe-task-definition", "--task-definition", arn)["taskDefinition"]
    previous = task.get("containerDefinitions", [])
    if len(previous) != 1:
        raise RuntimeError("BLOCKED: incompatible production rollback target")
    container = previous[0]
    env = {item["name"]: item["value"] for item in container.get("environment", [])}
    secrets = {item["name"]: item["valueFrom"] for item in container.get("secrets", [])}
    if (
        env.get("APP_ENV") != "production"
        or env.get("PGUSER") != "retiro_runtime"
        or env.get("PGHOST") != base["DbHost"]
        or env.get("PGSSLMODE") != "verify-full"
        or any(
            env.get(flag) != "false"
            for flag in [
                "E1_IDENTITY_ENABLED",
                "E2_FAMILY_ENABLED",
                "E3_PICKUP_ENABLED",
                "E4_OPERATIONS_ENABLED",
            ]
        )
        or secrets
        != {"DJANGO_SECRET_KEY": base["DjangoSecret"], "PGPASSWORD": base["RuntimePassword"]}
        or not container.get("image", "").startswith(IMAGE_REPOSITORY + "@sha256:")
    ):
        raise RuntimeError("BLOCKED: incompatible production rollback target")
    return arn


def deploy(base: dict[str, str], sha: str, digest: str, expires: str) -> None:
    state = gateway()
    previous = rollback_definition(base, state)
    expected = runtime_digests(digest)
    task = register(definition(base, IMAGE_REPOSITORY + "@" + digest, sha, "api"))
    candidate(sha, digest)  # Latest main checked again under the serialized deployment job.
    aws(
        "ecs",
        "update-express-gateway-service",
        "--service-arn",
        SERVICE,
        "--task-definition-arn",
        task,
    )
    try:
        origin, evidence = verify_running(base, task, expected)
    except Exception:
        # Code only. Never downgrade schema, restore a backup or modify domain evidence.
        aws(
            "ecs",
            "update-express-gateway-service",
            "--service-arn",
            SERVICE,
            "--task-definition-arn",
            previous,
        )
        old_task = aws("ecs", "describe-task-definition", "--task-definition", previous)[
            "taskDefinition"
        ]
        old_digest = old_task["containerDefinitions"][0]["image"].split("@", 1)[1]
        restored_origin, restored = verify_running(base, previous, runtime_digests(old_digest))
        report(
            "production-deployment",
            {
                "sha": sha,
                "digest": digest,
                "passed": False,
                "rollback_verified": True,
                "origin": restored_origin,
                **restored,
            },
        )
        raise RuntimeError("BLOCKED: candidate failed; compatible code rollback verified") from None
    report(
        "production-deployment",
        {
            "sha": sha,
            "digest": digest,
            "origin": origin,
            "service": SERVICE,
            "task_definition": task,
            "expires_at": expires,
            "passed": True,
            "business_enabled": False,
            "e4_accepted": False,
            "e5_accepted": False,
            "scope": "Isolated technical production; no school activation",
            **evidence,
        },
    )
    print(
        json.dumps(
            {
                "passed": True,
                "sha": sha,
                "digest": digest,
                "origin": origin,
                "business_enabled": False,
            }
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=["prepare", "migrate", "deploy"])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--digest", required=True)
    args = parser.parse_args()
    config = configuration()
    identity("Migrate" if args.mode == "migrate" else "Deploy")
    candidate(args.sha, args.digest)
    base = base_outputs(config)
    if args.mode == "prepare":
        preflight()
        expires = arm_window()
        wait_database(base)
        # Scheduled retirement changes the origin. A future window requires a fresh
        # observed gateway, never a success from a null/retired destination.
        if gateway_origin(gateway()) != config["base_url"]:
            raise RuntimeError("BLOCKED: production origin drift; recommission observed target")
        print(json.dumps({"production_window_ready": True, "expires_at": expires}))
    elif args.mode == "migrate":
        migrate(base, args.sha, args.digest)
    else:
        # Keep the preparation deadline; a slow migration must not silently
        # extend the billed window or postpone an already armed retirement.
        schedule = aws("scheduler", "get-schedule", "--name", "retiro-production-expiry-api")
        from datetime import UTC, datetime

        expires = schedule["ScheduleExpression"].removeprefix("at(").removesuffix(")")
        if schedule.get("State") != "ENABLED" or datetime.fromisoformat(expires).replace(
            tzinfo=UTC
        ) <= datetime.now(UTC):
            raise RuntimeError("BLOCKED: production window expired before deployment")
        deploy(base, args.sha, args.digest, expires)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        raise SystemExit(failure(error)) from None
