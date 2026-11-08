"""Serialized migration/deployment of the latest approved main digest, synthetic only."""

import argparse
import copy
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from scripts.aws_cli import aws
from scripts.commission_staging import arm_expiry, register, runtime_digests, task_definition
from scripts.e1_release import api_definition, archive_definition, start_archive
from scripts.verify_staging import verify
from scripts.verify_staging_network import verify_ingress


def migration_definition(outputs: dict[str, str], image: str, sha: str) -> dict[str, Any]:
    task = copy.deepcopy(task_definition(outputs, image, sha, False))
    task["family"] = "retiro-staging-migrate"
    task["executionRoleArn"] = outputs["MigrationExecution"]
    container = task["containerDefinitions"][0]
    container.pop("portMappings", None)
    container["command"] = ["python", "manage.py", "migrate_locked", "--noinput"]
    for item in container["environment"]:
        if item["name"] == "PGUSER":
            item["value"] = "retiro_migrator"
    container["secrets"] = [
        {"name": "DJANGO_SECRET_KEY", "valueFrom": outputs["DjangoSecret"]},
        {"name": "PGPASSWORD", "valueFrom": outputs["MigrationPassword"]},
    ]
    return task


def candidate_running(cluster: str, definition: str, expected: set[str]) -> bool:
    arns = aws("ecs", "list-tasks", "--cluster", cluster, "--service-name", "retiro-api")[
        "taskArns"
    ]
    if not arns:
        return False
    tasks = aws("ecs", "describe-tasks", "--cluster", cluster, "--tasks", *arns)["tasks"]
    return bool(tasks) and all(
        task["taskDefinitionArn"] == definition
        and task["lastStatus"] == "RUNNING"
        and all(container.get("imageDigest") in expected for container in task["containers"])
        for task in tasks
    )


def deploy_express(outputs: dict[str, str], definition: str) -> tuple[str, str | None, str]:
    service = "arn:aws:ecs:us-east-1:028364485203:service/retiro-staging/retiro-api"
    state_result = subprocess.run(
        [
            "aws",
            "ecs",
            "describe-express-gateway-service",
            "--service-arn",
            service,
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    previous_definition = None
    state = None
    if state_result.returncode:
        if (
            "ServiceNotFound" not in state_result.stderr
            and "ClusterNotFound" not in state_result.stderr
        ):
            raise RuntimeError("Service lookup failed; absence not established")
    else:
        state = json.loads(state_result.stdout)["service"]
        status = state.get("status", {}).get("statusCode")
        if status == "INACTIVE":
            # Express retains the description after scheduled deletion. An HTTP
            # success from Describe does not mean that the service can be updated.
            state = None
        elif status != "ACTIVE" or not state.get("activeConfigurations"):
            raise RuntimeError("Express service not ready; no creation or update performed")
    if state is None:
        service = aws(
            "ecs",
            "create-express-gateway-service",
            "--cluster",
            outputs["Cluster"],
            "--service-name",
            "retiro-api",
            "--infrastructure-role-arn",
            outputs["ExpressInfrastructure"],
            "--task-definition-arn",
            definition,
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
        )["service"]["serviceArn"]
        try:
            expiry = arm_expiry(service)
        except Exception:
            aws("ecs", "delete-express-gateway-service", "--service-arn", service)
            raise RuntimeError("Expiry failed; service deletion requested") from None
    else:
        previous_definition = state["activeConfigurations"][0]["taskDefinitionArn"]
        aws(
            "ecs",
            "update-express-gateway-service",
            "--service-arn",
            service,
            "--task-definition-arn",
            definition,
        )
        expiry = arm_expiry(service)
    return service, previous_definition, expiry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["migrate", "deploy"], required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument(
        "--e1-trial", action="store_true", help="Synthetic E1 trial, not acceptance"
    )
    parser.add_argument(
        "--e2-trial", action="store_true", help="Bounded synthetic E2 trial; not acceptance"
    )
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{40}", args.sha) or not re.fullmatch(
        "sha256:[0-9a-f]{64}", args.digest
    ):
        raise SystemExit("BLOCKED: immutable release identity required")
    latest = subprocess.check_output(
        ["git", "ls-remote", "origin", "refs/heads/main"], text=True
    ).split()[0]
    if args.sha != latest:
        raise SystemExit("OBSOLETE: candidate is no longer the latest main; no mutation performed")
    identity = aws("sts", "get-caller-identity")
    role = "Migrate" if args.mode == "migrate" else "Deploy"
    if identity["Account"] != "028364485203" or not identity["Arn"].startswith(
        "arn:aws:sts::028364485203:assumed-role/retiro-staging-" + role + "/"
    ):
        raise SystemExit("BLOCKED: isolated deployment/migration identity required")
    environment = json.loads(Path("infra/environments/staging.json").read_text())
    if (
        environment.get("synthetic_only") is not True
        or environment.get("pickup_enabled") is not False
    ):
        raise SystemExit("BLOCKED: synthetic-only staging with pickups disabled required")
    e1_enabled = args.e1_trial or args.e2_trial or environment.get("e1_enabled") is True
    outputs = {
        v["OutputKey"]: v["OutputValue"]
        for v in aws("cloudformation", "describe-stacks", "--stack-name", "retiro-staging-base")[
            "Stacks"
        ][0]["Outputs"]
    }
    image = outputs["ImageRepository"] + "@" + args.digest
    if args.mode == "migrate":
        task = register(migration_definition(outputs, image, args.sha))
        network = {
            "awsvpcConfiguration": {
                "subnets": [outputs["Public0"], outputs["Public1"]],
                "securityGroups": [outputs["AppSecurityGroup"]],
                "assignPublicIp": "ENABLED",
            }
        }
        run = aws(
            "ecs",
            "run-task",
            "--cluster",
            outputs["Cluster"],
            "--task-definition",
            task,
            "--launch-type",
            "FARGATE",
            "--network-configuration",
            json.dumps(network),
        )
        if run.get("failures") or len(run.get("tasks", [])) != 1:
            raise RuntimeError("Migration did not start")
        arn = run["tasks"][0]["taskArn"]
        subprocess.run(
            [
                "aws",
                "ecs",
                "wait",
                "tasks-stopped",
                "--cluster",
                outputs["Cluster"],
                "--tasks",
                arn,
            ],
            check=True,
        )
        result = aws("ecs", "describe-tasks", "--cluster", outputs["Cluster"], "--tasks", arn)[
            "tasks"
        ][0]
        if not result.get("containers") or any(
            c.get("exitCode") != 0 for c in result["containers"]
        ):
            raise RuntimeError("Migration failed; deployment prohibited")
        print("Migration task completed with separate SQL identity")
        return 0
    expected = runtime_digests(args.digest)
    archive_task = None
    if e1_enabled:
        e1 = {
            v["OutputKey"]: v["OutputValue"]
            for v in aws("cloudformation", "describe-stacks", "--stack-name", "retiro-staging-e1")[
                "Stacks"
            ][0]["Outputs"]
        }
        # Validate both definitions before starting a process. Same image, isolated credentials.
        api = api_definition(outputs, e1, image, args.sha, enable_family=args.e2_trial)
        archive = register(archive_definition(outputs, e1, image, args.sha))
        archive_task = start_archive(outputs, archive, expected)
    else:
        api = task_definition(outputs, image, args.sha, False)
    definition = register(api)
    service, previous_definition, expiry = deploy_express(outputs, definition)
    origin = ""
    for _ in range(100):
        state = aws("ecs", "describe-express-gateway-service", "--service-arn", service)["service"]
        if state["status"]["statusCode"] == "ACTIVE" and candidate_running(
            outputs["Cluster"], definition, expected
        ):
            endpoint = state["activeConfigurations"][0]["ingressPaths"][0]["endpoint"]
            origin = endpoint if endpoint.startswith("https://") else "https://" + endpoint
            break
        if "FAILED" in state["status"]["statusCode"]:
            break
        time.sleep(15)
    network_evidence = verify_ingress(outputs["Cluster"], service, outputs["AppSecurityGroup"])
    report: dict[str, Any] = {}
    if origin:
        for _ in range(12):
            report = verify(origin)
            if report["passed"]:
                break
            time.sleep(10)
    tasks = aws(
        "ecs", "list-tasks", "--cluster", outputs["Cluster"], "--service-name", "retiro-api"
    )["taskArns"]
    running = (
        aws("ecs", "describe-tasks", "--cluster", outputs["Cluster"], "--tasks", *tasks)["tasks"]
        if tasks
        else []
    )
    correct = bool(running) and all(
        t["taskDefinitionArn"] == definition
        and all(c.get("imageDigest") in expected for c in t["containers"])
        for t in running
    )
    passed = bool(report.get("passed") and correct)
    evidence = {
        "sha": args.sha,
        "digest": args.digest,
        "origin": origin,
        "service": service,
        "task_definition": definition,
        "runtime_digest_verified": correct,
        "network": network_evidence,
        "expires_at": expiry,
        "probes": report,
        "passed": passed,
        "e1_identity_enabled": e1_enabled,
        "e2_family_enabled": args.e2_trial,
        "archive_task": archive_task,
        "e1_accepted": False,
        "scope": "Deployment and technical probes only; functional E1 acceptance is separate",
    }
    Path("work").mkdir(exist_ok=True)
    Path("work/staging-deployment.json").write_text(json.dumps(evidence, indent=2) + "\n")
    if not passed and previous_definition:
        # Compatible code only: no schema/evidence rollback.
        aws(
            "ecs",
            "update-express-gateway-service",
            "--service-arn",
            service,
            "--task-definition-arn",
            previous_definition,
        )
        print("Candidate failed; compatible previous task definition requested; schema untouched")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
