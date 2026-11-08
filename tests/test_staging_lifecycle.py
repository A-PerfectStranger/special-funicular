"""Regression for the live Scheduler rejection and safe lifecycle-only recovery."""

import subprocess
from datetime import UTC, datetime

import pytest

from scripts import configure_staging_lifecycle as lifecycle


def test_scheduler_start_date_includes_required_utc_milliseconds() -> None:
    assert lifecycle.start_date(datetime(2026, 11, 8, 0, 0, tzinfo=UTC)) == (
        "2026-11-08T03:00:00.000Z"
    )


@pytest.mark.parametrize("unexpected", [False, True])
def test_failed_lifecycle_never_deletes_database_resources(
    unexpected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, ...]] = []

    def read(*args: str) -> dict:
        calls.append(args)
        if args[1] == "describe-stacks":
            return {
                "Stacks": [
                    {
                        "StackStatus": "ROLLBACK_COMPLETE",
                        "Tags": [{"Key": "Project", "Value": "retiro-seguro"}],
                    }
                ]
            }
        if args[1] == "describe-stack-resources":
            return {
                "StackResources": [
                    {
                        "LogicalResourceId": "Database" if unexpected else "DatabaseIdleGuard",
                        "ResourceType": "AWS::RDS::DBInstance"
                        if unexpected
                        else "AWS::Scheduler::Schedule",
                    }
                ]
            }
        return {}

    monkeypatch.setattr(lifecycle, "aws", read)
    monkeypatch.setattr(
        lifecycle.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess([], 0)
    )
    if unexpected:
        with pytest.raises(RuntimeError, match="Unexpected lifecycle resource"):
            lifecycle.recover()
        assert not any(c[1] == "delete-stack" for c in calls)
    else:
        lifecycle.recover()
        assert (
            "cloudformation",
            "delete-stack",
            "--stack-name",
            "retiro-staging-lifecycle",
        ) in calls
    assert all("retiro-staging-base" not in c for c in calls)
