"""CloudShell commissioning with a CI-published digest; never reads secret values."""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.aws_cli import aws
from scripts.prepare_staging_run import defer_idle_stop
from scripts.verify_staging import verify
from scripts.verify_staging_network import verify_ingress


def register(data: dict[str, Any]) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as stream:
        json.dump(data, stream)
        stream.flush()
        return str(
            aws("ecs", "register-task-definition", "--cli-input-json", "file://" + stream.name)[
                "taskDefinition"
            ]["taskDefinitionArn"]
        )


def runtime_digests(digest: str) -> set[str]:
    result = aws(
        "ecr",
        "batch-get-image",
        "--repository-name",
        "retiro-staging/backend",
        "--image-ids",
        "imageDigest=" + digest,
    )
    raw = result["images"][0]["imageManifest"]
    if "sha256:" + hashlib.sha256(raw.encode()).hexdigest() != digest:
        raise RuntimeError("Registry manifest bytes do not match approved OCI digest")
    manifest = json.loads(raw)
    accepted = {digest}
    for child in manifest.get("manifests", []):
        platform = child.get("platform", {})
        if platform.get("os") == "linux" and platform.get("architecture") == "amd64":
            accepted.add(child["digest"])
    if manifest.get("manifests") and len(accepted) == 1:
        raise RuntimeError("Approved index has no Linux amd64 image")
    return accepted


def task_definition(
    outputs: dict[str, str], image: str, sha: str, bootstrap: bool
) -> dict[str, Any]:
    env = {
        "APP_ENV": "staging",
        "DJANGO_DEBUG": "false",
        "DJANGO_ALLOWED_HOSTS": ".ecs.us-east-1.on.aws,localhost",
        "PGHOST": outputs["DbHost"],
        "PGDATABASE": "retiro",
        "PGSSLMODE": "verify-full",
        "PGSSLROOTCERT": "/app/rds-ca.pem",
        "GIT_SHA": sha,
        "PGUSER": "retiro_bootstrap" if bootstrap else "retiro_runtime",
        "TRUSTED_INGRESS": "ecs-express",
    }
    secrets = {
        "DJANGO_SECRET_KEY": outputs["DjangoSecret"],
        "PGPASSWORD": outputs["MasterSecret"] + ":password::"
        if bootstrap
        else outputs["RuntimePassword"],
    }
    if bootstrap:
        secrets.update(
            MIGRATOR_PASSWORD=outputs["MigrationPassword"],
            RUNTIME_PASSWORD=outputs["RuntimePassword"],
        )
    command = (
        ["python", "-c", Path(__file__).with_name("bootstrap_database.py").read_text()]
        if bootstrap
        else [
            "gunicorn",
            "config.wsgi:application",
            "--bind",
            "0.0.0.0:8000",
            "--workers",
            "2",
            "--worker-tmp-dir",
            "/dev/shm",
            "--error-logfile",
            "-",
            "--log-level",
            "warning",
        ]
    )
    container: dict[str, Any] = {
        "name": "Main",
        "image": image,
        "essential": True,
        "user": "10001:10001",
        "readonlyRootFilesystem": True,
        "linuxParameters": {"initProcessEnabled": True, "capabilities": {"drop": ["ALL"]}},
        "environment": [{"name": k, "value": v} for k, v in env.items()],
        "secrets": [{"name": k, "valueFrom": v} for k, v in secrets.items()],
        "command": command,
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": outputs["Logs"],
                "awslogs-region": "us-east-1",
                "awslogs-stream-prefix": "bootstrap" if bootstrap else "api",
            },
        },
    }
    if not bootstrap:
        container["portMappings"] = [{"containerPort": 8000, "protocol": "tcp", "name": "http"}]
    return {
        "family": "retiro-staging-bootstrap" if bootstrap else "retiro-staging-api",
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["FARGATE"],
        "cpu": "256",
        "memory": "512",
        "executionRoleArn": outputs["BootstrapExecution"] if bootstrap else outputs["ApiExecution"],
        "runtimePlatform": {"cpuArchitecture": "X86_64", "operatingSystemFamily": "LINUX"},
        "containerDefinitions": [container],
    }


def arm_expiry(service: str) -> str:
    outputs = aws("cloudformation", "describe-stacks", "--stack-name", "retiro-staging-lifecycle")[
        "Stacks"
    ][0]["Outputs"]
    role = next(item["OutputValue"] for item in outputs if item["OutputKey"] == "ExpiryRoleArn")
    expiry = datetime.now(UTC) + timedelta(hours=3)
    name = "retiro-staging-expiry-api"
    action = "update-schedule"
    try:
        aws("scheduler", "get-schedule", "--name", name)
    except RuntimeError as exc:
        if "ResourceNotFoundException" not in str(exc):
            raise
        action = "create-schedule"
    aws(
        "scheduler",
        action,
        "--name",
        name,
        "--schedule-expression",
        "at(" + expiry.strftime("%Y-%m-%dT%H:%M:%S") + ")",
        "--schedule-expression-timezone",
        "UTC",
        "--flexible-time-window",
        '{"Mode":"OFF"}',
        "--action-after-completion",
        "DELETE",
        "--target",
        json.dumps(
            {
                "Arn": "arn:aws:scheduler:::aws-sdk:ecs:deleteExpressGatewayService",
                "RoleArn": role,
                "Input": json.dumps({"ServiceArn": service}),
                "RetryPolicy": {"MaximumEventAgeInSeconds": 3600, "MaximumRetryAttempts": 2},
            }
        ),
    )
    defer_idle_stop(expiry + timedelta(minutes=15))
    return expiry.isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--digest", required=True)
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{40}", args.sha) or not re.fullmatch(
        "sha256:[0-9a-f]{64}", args.digest
    ):
        raise SystemExit("BLOCKED: full approved SHA and OCI digest required")
    identity = aws("sts", "get-caller-identity")
    if identity["Account"] != "028364485203":
        raise SystemExit("BLOCKED: wrong account")
    from scripts.prepare_staging_run import open_window

    open_window()
    outputs = {
        v["OutputKey"]: v["OutputValue"]
        for v in aws("cloudformation", "describe-stacks", "--stack-name", "retiro-staging-base")[
            "Stacks"
        ][0]["Outputs"]
    }
    registered = aws(
        "ecr",
        "describe-images",
        "--repository-name",
        "retiro-staging/backend",
        "--image-ids",
        "imageTag=" + args.sha,
    )["imageDetails"][0]["imageDigest"]
    if registered != args.digest:
        raise SystemExit("BLOCKED: ECR digest/tag mismatch")
    image = outputs["ImageRepository"] + "@" + args.digest
    network = {
        "awsvpcConfiguration": {
            "subnets": [outputs["Public0"], outputs["Public1"]],
            "securityGroups": [outputs["AppSecurityGroup"]],
            "assignPublicIp": "ENABLED",
        }
    }
    definition = register(task_definition(outputs, image, args.sha, True))
    run = aws(
        "ecs",
        "run-task",
        "--cluster",
        outputs["Cluster"],
        "--task-definition",
        definition,
        "--launch-type",
        "FARGATE",
        "--network-configuration",
        json.dumps(network),
    )
    if run.get("failures") or len(run.get("tasks", [])) != 1:
        raise RuntimeError("bootstrap task was not started")
    task = run["tasks"][0]["taskArn"]
    subprocess.run(
        [
            "aws",
            "ecs",
            "wait",
            "tasks-stopped",
            "--region",
            "us-east-1",
            "--cluster",
            outputs["Cluster"],
            "--tasks",
            task,
        ],
        check=True,
    )
    task_result = aws("ecs", "describe-tasks", "--cluster", outputs["Cluster"], "--tasks", task)[
        "tasks"
    ][0]
    if not task_result.get("containers") or any(
        c.get("exitCode") != 0 for c in task_result["containers"]
    ):
        raise RuntimeError("SQL bootstrap/TLS/RLS/migration failed; inspect private task logs")
    api_definition = register(task_definition(outputs, image, args.sha, False))
    created = aws(
        "ecs",
        "create-express-gateway-service",
        "--cluster",
        outputs["Cluster"],
        "--service-name",
        "retiro-api",
        "--infrastructure-role-arn",
        outputs["ExpressInfrastructure"],
        "--task-definition-arn",
        api_definition,
        "--health-check-path",
        "/health/live",
        "--network-configuration",
        json.dumps(
            {
                "subnets": [outputs["Public0"], outputs["Public1"]],
                "securityGroups": [outputs["AppSecurityGroup"]],
            }
        ),
        "--scaling-target",
        '{"minTaskCount":1,"maxTaskCount":1}',
        "--tags",
        "key=Project,value=retiro-seguro",
        "key=Environment,value=staging",
    )
    service = created["service"]["serviceArn"]
    try:
        expiry = arm_expiry(service)
    except Exception:
        aws("ecs", "delete-express-gateway-service", "--service-arn", service)
        raise RuntimeError("expiry scheduling failed; service deletion requested") from None
    endpoint = ""
    for _ in range(100):
        state = aws("ecs", "describe-express-gateway-service", "--service-arn", service)["service"]
        status = state["status"]["statusCode"]
        print("ECS commissioning: " + status, flush=True)
        if status == "ACTIVE":
            endpoint = state["activeConfigurations"][0]["ingressPaths"][0]["endpoint"]
            break
        if "FAILED" in status:
            raise RuntimeError("ECS commissioning failed; expiry remains armed")
        time.sleep(15)
    if not endpoint:
        raise RuntimeError("ECS commissioning timeout; expiry remains armed")
    origin = endpoint if endpoint.startswith("https://") else "https://" + endpoint
    network_evidence = verify_ingress(outputs["Cluster"], service, outputs["AppSecurityGroup"])
    report: dict[str, Any] = {}
    for _ in range(12):
        report = verify(origin)
        if report["passed"]:
            break
        time.sleep(10)
    tasks = aws(
        "ecs", "list-tasks", "--cluster", outputs["Cluster"], "--service-name", state["serviceName"]
    )["taskArns"]
    running = (
        aws("ecs", "describe-tasks", "--cluster", outputs["Cluster"], "--tasks", *tasks)["tasks"]
        if tasks
        else []
    )
    expected = runtime_digests(args.digest)
    same_digest = bool(running) and all(
        c.get("imageDigest") in expected for t in running for c in t["containers"]
    )
    evidence = {
        "sha": args.sha,
        "digest": args.digest,
        "service": service,
        "origin": origin,
        "bootstrap_task": task,
        "same_digest_running": same_digest,
        "network": network_evidence,
        "expires_at": expiry,
        "public_probes": report,
    }
    Path("staging-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        json.dumps(
            {
                "origin": origin,
                "service": service,
                "sha": args.sha,
                "digest": args.digest,
                "passed": bool(report.get("passed") and same_digest),
                "expires_at": expiry,
            },
            indent=2,
        )
    )
    return 0 if report.get("passed") and same_digest else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("BLOCKED: " + str(exc))
        raise SystemExit(2) from None
