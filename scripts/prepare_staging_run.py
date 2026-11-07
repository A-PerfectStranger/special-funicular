"""Open a bounded staging window and start only the dedicated private RDS instance."""

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime, timedelta

from scripts.aws_cli import aws


def defer_idle_stop(expiry: datetime) -> None:
    schedule = aws("scheduler", "get-schedule", "--name", "retiro-staging-db-idle-guard")
    aws(
        "scheduler",
        "update-schedule",
        "--name",
        schedule["Name"],
        "--schedule-expression",
        schedule["ScheduleExpression"],
        "--schedule-expression-timezone",
        schedule.get("ScheduleExpressionTimezone", "UTC"),
        "--flexible-time-window",
        json.dumps(schedule["FlexibleTimeWindow"]),
        "--target",
        json.dumps(schedule["Target"]),
        "--state",
        "ENABLED",
        "--start-date",
        expiry.isoformat(),
    )


def open_window() -> None:
    defer_idle_stop(datetime.now(UTC) + timedelta(hours=3))
    for _ in range(120):
        instance = aws(
            "rds", "describe-db-instances", "--db-instance-identifier", "retiro-staging"
        )["DBInstances"][0]
        if (
            instance["PubliclyAccessible"]
            or not instance["StorageEncrypted"]
            or not instance.get("KmsKeyId")
        ):
            raise RuntimeError("Database privacy/encryption drift; no migration permitted")
        status = instance["DBInstanceStatus"]
        if status == "available":
            print("Private RDS available; idle-stop guard resumes after the active window")
            return
        if status == "stopped":
            aws("rds", "start-db-instance", "--db-instance-identifier", "retiro-staging")
        time.sleep(10)
    raise RuntimeError("RDS start timeout; migration/deployment prohibited")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    latest = subprocess.check_output(
        ["git", "ls-remote", "origin", "refs/heads/main"], text=True
    ).split()[0]
    if latest != args.sha:
        raise SystemExit("OBSOLETE: no staging window opened")
    identity = aws("sts", "get-caller-identity")
    if not identity["Arn"].startswith(
        "arn:aws:sts::028364485203:assumed-role/retiro-staging-Deploy/"
    ):
        raise SystemExit("BLOCKED: isolated deployment identity required")
    open_window()


if __name__ == "__main__":
    main()
