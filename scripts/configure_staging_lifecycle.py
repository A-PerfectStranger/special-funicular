"""Recover only the failed lifecycle stack; never touch retained database resources."""

import argparse
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.aws_cli import aws

STACK = "retiro-staging-lifecycle"
RESOURCE_TYPES = {
    "Expiry": "AWS::IAM::Role",
    "DatabaseIdleGuard": "AWS::Scheduler::Schedule",
    "LifecyclePermissions": "AWS::IAM::Policy",
}


def recover() -> None:
    try:
        stack = aws("cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0]
    except RuntimeError as exc:
        if str(exc) == "cloudformation.describe-stacks: ValidationError":
            return  # deploy will still reject any state other than a missing/updatable stack
        raise
    if stack["StackStatus"] != "ROLLBACK_COMPLETE":
        return
    tags = {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}
    if tags.get("Project") != "retiro-seguro":
        raise RuntimeError("Lifecycle ownership mismatch; nothing deleted")
    resources = aws("cloudformation", "describe-stack-resources", "--stack-name", STACK)[
        "StackResources"
    ]
    if any(RESOURCE_TYPES.get(r["LogicalResourceId"]) != r["ResourceType"] for r in resources):
        raise RuntimeError("Unexpected lifecycle resource; nothing deleted")
    aws("cloudformation", "delete-stack", "--stack-name", STACK)
    subprocess.run(
        [
            "aws",
            "cloudformation",
            "wait",
            "stack-delete-complete",
            "--region",
            "us-east-1",
            "--stack-name",
            STACK,
        ],
        check=True,
    )


def start_date(now: datetime) -> str:
    return (
        (now + timedelta(hours=3))
        .astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def configure(template: Path) -> None:
    if aws("sts", "get-caller-identity")["Account"] != "028364485203":
        raise RuntimeError("Wrong account; no lifecycle mutation performed")
    recover()
    result = subprocess.run(
        [
            "aws",
            "cloudformation",
            "deploy",
            "--region",
            "us-east-1",
            "--stack-name",
            STACK,
            "--template-file",
            str(template),
            "--capabilities",
            "CAPABILITY_NAMED_IAM",
            "--parameter-overrides",
            "StopNotBefore=" + start_date(datetime.now(UTC)),
            "--tags",
            "Project=retiro-seguro",
            "Environment=staging",
            "--no-fail-on-empty-changeset",
        ],
        check=False,
    )
    if result.returncode:
        subprocess.run(
            [
                "aws",
                "cloudformation",
                "describe-stack-events",
                "--region",
                "us-east-1",
                "--stack-name",
                STACK,
                "--query",
                "StackEvents[?ResourceStatus=='CREATE_FAILED'].[LogicalResourceId,ResourceStatusReason]",
                "--output",
                "table",
            ],
            check=False,
        )
        raise RuntimeError("Lifecycle configuration failed; base database unchanged")
    print("Lifecycle configured: three-hour active window and hourly database idle guard")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    configure(parser.parse_args().template)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit("BLOCKED: " + str(exc)) from None
