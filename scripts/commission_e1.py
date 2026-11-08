"""CloudShell/operator commissioning of E1 resources and SQL roles, not E1 acceptance.

No credential values leave Secrets Manager/ECS. No users, invitations or student
data are created here. The existing E0 service and evidence are never deleted.
"""

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from scripts.aws_cli import aws
from scripts.commission_staging import register, task_definition
from scripts.prepare_staging_run import open_window


def outputs(stack: str) -> dict[str, str]:
    return {
        item["OutputKey"]: item["OutputValue"]
        for item in aws("cloudformation", "describe-stacks", "--stack-name", stack)["Stacks"][0][
            "Outputs"
        ]
    }


def validate_operator(identity: dict[str, Any]) -> None:
    if identity.get("Account") != "028364485203":
        raise RuntimeError("Wrong AWS account")
    arn = identity.get("Arn", "")
    if not isinstance(arn, str) or not arn.startswith(
        ("arn:aws:iam::028364485203:", "arn:aws:sts::028364485203:")
    ):
        raise RuntimeError("Verified AWS operator identity required")
    if ":role/retiro-staging-" in arn or ":assumed-role/retiro-staging-" in arn:
        raise RuntimeError("CI/runtime roles are not provisioning operators")


def billing_preflight() -> dict[str, bool]:
    today = datetime.now(UTC).date()
    plan = aws("freetier", "get-account-plan-state")
    budget = aws(
        "budgets",
        "describe-budget",
        "--account-id",
        "028364485203",
        "--budget-name",
        "retiro-seguro-total-150-usd",
    )["Budget"]
    budget_start = datetime.fromisoformat(budget["TimePeriod"]["Start"])
    cost = aws(
        "ce",
        "get-cost-and-usage",
        "--time-period",
        f"Start={budget_start.date()},End={today + timedelta(days=1)}",
        "--granularity",
        "MONTHLY",
        "--metrics",
        "UnblendedCost",
        "--filter",
        json.dumps({"Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund"]}}}),
    )
    credit = plan.get("accountPlanRemainingCredits", {})
    totals = [item["Total"]["UnblendedCost"] for item in cost["ResultsByTime"]]
    # Five USD incremental commissioning + existing 27 USD retained-base reserve.
    checks = {
        "budget_150_usd": (
            budget["BudgetLimit"]["Unit"] == "USD"
            and Decimal(budget["BudgetLimit"]["Amount"]) == 150
            and budget.get("TimeUnit") == "CUSTOM"
        ),
        "gross_usage_complete": bool(totals)
        and not cost.get("NextPageToken")
        and all(t["Unit"] == "USD" for t in totals),
        "usage_plus_commission_and_reserve_within_total": sum(Decimal(t["Amount"]) for t in totals)
        + 32
        <= 150,
        "credit_covers_commission_and_reserve": credit.get("unit") == "USD"
        and Decimal(str(credit.get("amount", "0"))) >= 32,
        "credit_valid_through_retention": datetime.fromisoformat(plan["accountPlanExpirationDate"])
        >= datetime.now(UTC) + timedelta(days=8),
    }
    if not all(checks.values()):
        raise RuntimeError("Billing/credit/budget preflight blocked; no provisioning performed")
    return checks


def bootstrap_definition(
    base: dict[str, str], e1: dict[str, str], image: str, sha: str
) -> dict[str, Any]:
    definition = task_definition(base, image, sha, True)
    definition["family"] = "retiro-staging-e1-bootstrap"
    container = definition["containerDefinitions"][0]
    container["command"] = ["python", "-c", Path("scripts/bootstrap_e1_database.py").read_text()]
    container["secrets"] = [
        {"name": "PGPASSWORD", "valueFrom": base["MasterSecret"] + ":password::"}
    ]
    for name, output in [
        ("SCHOOL_READ", "SchoolReadPassword"),
        ("SYSTEM_READ", "SystemReadPassword"),
        ("IMPORTER", "ImporterPassword"),
        ("ARCHIVER", "ArchivePassword"),
        ("NOTIFIER", "NotifierPassword"),
    ]:
        container["secrets"].append({"name": f"E1_{name}_PASSWORD", "valueFrom": e1[output]})
    return definition


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-origin", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"https://[a-z0-9-]+\.ecs\.us-east-1\.on\.aws", args.web_origin):
        raise RuntimeError("Observed staging origin required")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise RuntimeError("Clean reviewed checkout required")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    print("E1 step: identity", flush=True)
    identity = aws("sts", "get-caller-identity")
    validate_operator(identity)
    print("E1 step: billing preflight", flush=True)
    billing = billing_preflight()
    base = outputs("retiro-staging-base")
    log_arn = f"arn:aws:logs:us-east-1:028364485203:log-group:{base['Logs']}:*"
    print("E1 step: CloudFormation", flush=True)
    result = subprocess.run(
        [
            "aws",
            "cloudformation",
            "deploy",
            "--region",
            "us-east-1",
            "--stack-name",
            "retiro-staging-e1",
            "--template-file",
            "infra/aws/e1-staging.yaml",
            "--capabilities",
            "CAPABILITY_NAMED_IAM",
            "--no-fail-on-empty-changeset",
            "--parameter-overrides",
            f"WebOrigin={args.web_origin}",
            f"ExistingLogsArn={log_arn}",
            "--tags",
            "Project=retiro-seguro",
            "Environment=staging",
            "Data=synthetic",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("CloudFormation E1 commissioning failed; inspect stack events privately")
    e1 = outputs("retiro-staging-e1")
    print("E1 step: private database role bootstrap", flush=True)
    open_window()
    previous = aws("ecs", "describe-task-definition", "--task-definition", "retiro-staging-api")[
        "taskDefinition"
    ]
    image = previous["containerDefinitions"][0]["image"]
    if not re.fullmatch(
        r"028364485203\.dkr\.ecr\.us-east-1\.amazonaws\.com/retiro-staging/backend@sha256:[0-9a-f]{64}",
        image,
    ):
        raise RuntimeError("Existing digest-pinned image required for grant-only bootstrap")
    definition = register(bootstrap_definition(base, e1, image, sha))
    network = {
        "awsvpcConfiguration": {
            "subnets": [base["Public0"], base["Public1"]],
            "securityGroups": [base["AppSecurityGroup"]],
            "assignPublicIp": "ENABLED",
        }
    }
    run = aws(
        "ecs",
        "run-task",
        "--cluster",
        base["Cluster"],
        "--task-definition",
        definition,
        "--launch-type",
        "FARGATE",
        "--network-configuration",
        json.dumps(network),
    )
    if run.get("failures") or len(run.get("tasks", [])) != 1:
        raise RuntimeError("Private SQL role bootstrap did not start")
    task = run["tasks"][0]["taskArn"]
    aws("ecs", "wait", "tasks-stopped", "--cluster", base["Cluster"], "--tasks", task)
    finished = aws("ecs", "describe-tasks", "--cluster", base["Cluster"], "--tasks", task)["tasks"][
        0
    ]
    if not finished.get("containers") or any(
        item.get("exitCode") != 0 for item in finished["containers"]
    ):
        raise RuntimeError("Private SQL role bootstrap failed")
    report = {
        "sha": sha,
        "checked_at": datetime.now(UTC).isoformat(),
        "billing": billing,
        "resources_created": True,
        "sql_roles_bootstrapped": True,
        "e1_accepted": False,
        "remaining": [
            "candidate deployment",
            "synthetic identities/MFA",
            "real WORM/KMS/denials",
            "integrated web/mobile acceptance",
        ],
        "outputs": e1,
    }
    Path("work").mkdir(exist_ok=True)
    Path("work/e1-commission.json").write_text(json.dumps(report, indent=2) + "\n")
    print("E1 resources and SQL roles commissioned. E1 ACCEPTANCE PENDING.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        # All RuntimeErrors originate in explicit constant barriers or aws_cli,
        # which reports only service/operation and the AWS error identifier.
        print("BLOCKED: " + str(exc))
        raise SystemExit(2) from None
    except Exception:
        print(
            "BLOCKED: E1 commissioning failed; inspect private AWS events/logs. No E1 acceptance."
        )
        raise SystemExit(2) from None
