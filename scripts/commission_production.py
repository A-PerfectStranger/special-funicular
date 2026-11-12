"""Operator-only foundation/SQL/gateway commissioning; synthetic technical production."""

import argparse
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from scripts.aws_cli import aws
from scripts.commission_e1 import outputs, validate_operator
from scripts.commission_staging import register, runtime_digests
from scripts.deploy_production import deploy, migrate, verify_running, wait_database
from scripts.isolated_task import run_isolated_task
from scripts.prepare_staging_account import read
from scripts.production import (
    CONFIG,
    IMAGE_REPOSITORY,
    SERVICE,
    arm_window,
    candidate,
    definition,
    failure,
    network,
    operation,
    report,
    technical_only,
)
from scripts.production_preflight import COST_PLAN_PARAMETER, preflight


def require_source(sha: str, digest: str) -> None:
    if (
        subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != sha
        or subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    ):
        raise RuntimeError("BLOCKED: clean reviewed main source required")
    candidate(sha, digest)
    caller = aws("sts", "get-caller-identity")
    validate_operator(caller)
    if (
        ":role/retiro-production-" in caller["Arn"]
        or ":assumed-role/retiro-production-" in caller["Arn"]
    ):
        raise RuntimeError("BLOCKED: production CI/runtime identities are not operators")
    # Bootstrap is a privileged operation. Require the full image AND source to
    # have passed main CI; never use a branch/fork build to provision production.
    url = (
        "https://api.github.com/repos/A-PerfectStranger/special-funicular/"
        f"actions/workflows/ci.yml/runs?branch=main&head_sha={sha}&event=push&per_page=10"
    )
    with urlopen(
        Request(url, headers={"Accept": "application/vnd.github+json"}), timeout=15
    ) as response:
        ci = json.load(response)["workflow_runs"]
    if not any(
        r["head_sha"] == sha
        and r["head_branch"] == "main"
        and r["event"] == "push"
        and r["head_repository"]["full_name"] == "A-PerfectStranger/special-funicular"
        and r["status"] == "completed"
        and r["conclusion"] == "success"
        for r in ci
    ):
        raise RuntimeError("BLOCKED: approved main CI required before commissioning")


def deploy_stack(name: str, template: Path, parameters: list[str]) -> None:
    existing = read(
        "cloudformation", "describe-stacks", "--stack-name", name, absent="does not exist"
    )
    if existing:
        stack = existing["Stacks"][0]
        tags = {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}
        if (
            tags.get("Project") != "retiro-seguro"
            or tags.get("Environment") != "production"
            or stack["StackStatus"] not in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}
        ):
            raise RuntimeError(
                "BLOCKED: production stack requires operator inspection; nothing deleted"
            )
    result = subprocess.run(
        [
            "aws",
            "cloudformation",
            "deploy",
            "--region",
            "us-east-1",
            "--stack-name",
            name,
            "--template-file",
            str(template),
            "--capabilities",
            "CAPABILITY_NAMED_IAM",
            "--parameter-overrides",
            *parameters,
            "--tags",
            "Project=retiro-seguro",
            "Environment=production",
            "Data=synthetic",
            "--no-fail-on-empty-changeset",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "BLOCKED: production CloudFormation failed; inspect private stack events"
        )


def foundation(plan: dict[str, Any]) -> None:
    with operation("BILLING_PREFLIGHT"):
        preflight(plan)  # Before ANY provisioning mutation, including cost-plan storage.
    with operation("ECS_SERVICE_ROLE"):
        if (
            read("iam", "get-role", "--role-name", "AWSServiceRoleForECS", absent="NoSuchEntity")
            is None
        ):
            raise RuntimeError("BLOCKED: existing ECS service-linked role required")
    with operation("RDS_ENGINE_SELECTION"):
        versions = aws("rds", "describe-db-engine-versions", "--engine", "postgres")[
            "DBEngineVersions"
        ]
        version = max(
            (v["EngineVersion"] for v in versions if v["EngineVersion"].startswith("17.")),
            key=lambda v: tuple(int(n) for n in v.split(".")),
        )
        if not aws(
            "rds",
            "describe-orderable-db-instance-options",
            "--engine",
            "postgres",
            "--engine-version",
            version,
            "--db-instance-class",
            "db.t4g.micro",
        ).get("OrderableDBInstanceOptions"):
            raise RuntimeError("BLOCKED: selected private PostgreSQL instance unavailable")
    params = ["EngineVersion=" + version]
    with operation("RETAINED_SECRET_METADATA"):
        for name in ["RuntimePassword", "MigrationPassword", "DjangoSecret"]:
            secret = read(
                "secretsmanager",
                "describe-secret",
                "--secret-id",
                "retiro-production/" + name,
                absent="ResourceNotFoundException",
            )
            if secret:
                tags = {tag["Key"]: tag["Value"] for tag in secret.get("Tags", [])}
                if (
                    tags.get("Project") != "retiro-seguro"
                    or tags.get("Environment") != "production"
                    or secret.get("DeletedDate")
                ):
                    raise RuntimeError(
                        "BLOCKED: retained production secret ownership/state mismatch"
                    )
                params.append("Existing" + name + "=" + secret["ARN"])
    with operation("CLOUDFORMATION_BASE"):
        deploy_stack("retiro-production-base", Path("infra/aws/production-base.json"), params)
    end = datetime.now(UTC) + timedelta(hours=3)
    with operation("CLOUDFORMATION_LIFECYCLE"):
        deploy_stack(
            "retiro-production-lifecycle",
            Path("infra/aws/production-lifecycle.yaml"),
            [
                "StopNotBefore=" + end.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "WindowExpiryAt=" + end.strftime("%Y-%m-%dT%H:%M:%S"),
            ],
        )
    # Private parameters contain price review/reserves, never IdP or domain secrets.
    with operation("COST_PLAN_STORAGE"):
        aws(
            "ssm",
            "put-parameter",
            "--name",
            COST_PLAN_PARAMETER,
            "--type",
            "String",
            "--value",
            json.dumps(plan),
            "--overwrite",
        )
    report("production-foundation", {"passed": True, "business_enabled": False})


def commission(sha: str, digest: str) -> None:
    preflight()
    config: dict[str, Any] = json.loads(CONFIG.read_text())
    technical_only(config)
    base = outputs("retiro-production-base")
    expires = arm_window()
    wait_database(base)
    bootstrap = register(definition(base, IMAGE_REPOSITORY + "@" + digest, sha, "bootstrap"))
    result = run_isolated_task(aws, base["Cluster"], bootstrap, network(base))
    if not result.get("containers") or any(c.get("exitCode") != 0 for c in result["containers"]):
        raise RuntimeError("BLOCKED: production SQL bootstrap failed")
    migrate(base, sha, digest)
    task = register(definition(base, IMAGE_REPOSITORY + "@" + digest, sha, "api"))
    state = read(
        "ecs",
        "describe-express-gateway-service",
        "--service-arn",
        SERVICE,
        absent="Service not found",
    )
    if state and state["service"].get("status", {}).get("statusCode") == "INACTIVE":
        state = None
    candidate(sha, digest)
    if state is None:
        aws(
            "ecs",
            "create-express-gateway-service",
            "--cluster",
            base["Cluster"],
            "--service-name",
            "retiro-api",
            "--infrastructure-role-arn",
            base["ExpressInfrastructure"],
            "--task-definition-arn",
            task,
            "--health-check-path",
            "/health/live",
            "--network-configuration",
            json.dumps(
                {
                    "subnets": [base["Public0"], base["Public1"]],
                    "securityGroups": [base["AppSecurityGroup"]],
                }
            ),
            "--scaling-target",
            '{"minTaskCount":1,"maxTaskCount":1}',
            "--tags",
            "key=Project,value=retiro-seguro",
            "key=Environment,value=production",
        )
    else:
        if state["service"].get("status", {}).get("statusCode") != "ACTIVE":
            raise RuntimeError("BLOCKED: production gateway is transitioning; no update")
        deploy(base, sha, digest, expires)
    if state is None:
        origin, evidence = verify_running(base, task, runtime_digests(digest))
    else:
        deployed = json.loads(Path("work/production-deployment.json").read_text())
        origin, task = deployed["origin"], deployed["task_definition"]
        evidence = {key: deployed[key] for key in ["network", "probes"]}
    config.update(
        {
            "deploy_role_arn": base["Deploy"],
            "migration_role_arn": base["Migrate"],
            "image_repository": base["ImageRepository"],
            "cluster": base["Cluster"],
            "service": SERVICE,
            "task_definition": task,
            "migration_task_definition": "retiro-production-migrate",
            "subnets": [base["Public0"], base["Public1"]],
            "security_groups": [base["AppSecurityGroup"]],
            "base_url": origin,
            "budget_verified": True,
        }
    )
    # This is a proposed public configuration from observed AWS values. The operator
    # reviews/commits it; a failed command never changes the versioned destination.
    report("production-configuration", config)
    report(
        "production-commission",
        {
            "sha": sha,
            "digest": digest,
            "origin": origin,
            "expires_at": expires,
            "passed": True,
            "business_enabled": False,
            "e4_accepted": False,
            "e5_accepted": False,
            **evidence,
        },
    )
    print(
        json.dumps(
            {
                "production_technical_commissioned": True,
                "origin": origin,
                "configuration": "work/production-configuration.json",
                "business_enabled": False,
            }
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", required=True, choices=["foundation", "commission"])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--cost-plan", type=Path)
    args = parser.parse_args()
    with operation("SOURCE_APPROVAL"):
        require_source(args.sha, args.digest)
    if args.step == "foundation":
        if not args.cost_plan:
            raise RuntimeError("BLOCKED: reviewed private cost plan required")
        with operation("FOUNDATION"):
            foundation(json.loads(args.cost_plan.read_text()))
    else:
        with operation("SERVICE_COMMISSION"):
            commission(args.sha, args.digest)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        raise SystemExit(failure(error)) from None
