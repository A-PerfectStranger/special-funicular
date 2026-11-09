"""Only a proven pre-execution failure may retry a private synthetic command."""

from typing import Any

import pytest

from scripts.fixture_task import run_fixture_task


def invocation(outcomes: list[dict[str, Any]]) -> tuple[Any, list[tuple[str, ...]]]:
    calls: list[tuple[str, ...]] = []
    states = iter(outcomes)

    def call(*args: str) -> dict[str, Any]:
        calls.append(args)
        if args[1] == "run-task":
            return {"tasks": [{"taskArn": "synthetic-task"}]}
        if args[1] == "describe-tasks":
            return {"tasks": [next(states)]}
        return {}

    return call, calls


def not_started() -> dict[str, Any]:
    return {"stopCode": "TaskFailedToStart", "containers": [{"exitCode": None}]}


def test_known_nonexecution_retries_the_same_fixed_command_once() -> None:
    passed = {"containers": [{"exitCode": 0}]}
    call, calls = invocation([not_started(), passed])
    assert run_fixture_task(call, "synthetic-cluster", "fixed-definition", {}) is passed
    starts = [c for c in calls if c[1] == "run-task"]
    assert len(starts) == 2 and starts[0] == starts[1]


@pytest.mark.parametrize(
    "state",
    [
        {"stopCode": "EssentialContainerExited", "containers": [{"exitCode": 2}]},
        {"stopCode": "EssentialContainerExited", "containers": [{"exitCode": 42}]},
        {**not_started(), "startedAt": "2026-11-08T23:00:00Z"},
        {"stopCode": "TaskFailedToStart", "containers": [{"exitCode": 2}]},
        {"stopCode": "TaskFailedToStart", "containers": [{"lastStatus": "RUNNING"}]},
        {"containers": []},
    ],
)
def test_sql_rejection_consumed_cohort_or_uncertain_execution_never_retries(
    state: dict[str, Any],
) -> None:
    call, calls = invocation([state])
    assert run_fixture_task(call, "synthetic", "fixed", {}) is state
    assert len([c for c in calls if c[1] == "run-task"]) == 1


def test_repeated_startup_failure_is_bounded_to_two_attempts() -> None:
    call, calls = invocation([not_started(), not_started()])
    assert run_fixture_task(call, "synthetic", "fixed", {})["stopCode"] == "TaskFailedToStart"
    assert len([c for c in calls if c[1] == "run-task"]) == 2


def test_unknown_creation_failure_is_not_retried() -> None:
    calls = []

    def failed(*args: str) -> dict[str, Any]:
        calls.append(args)
        return {"failures": [{"reason": "synthetic-failure"}], "tasks": []}

    with pytest.raises(RuntimeError, match="not created"):
        run_fixture_task(failed, "synthetic", "fixed", {})
    assert len(calls) == 1
