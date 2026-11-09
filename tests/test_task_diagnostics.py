"""Public CI diagnostics disclose classifications, never raw private task content."""

import json

from scripts.task_diagnostics import task_outcome


def test_private_details_and_raw_errors_cannot_escape_to_public_metadata() -> None:
    private = "synthetic-private-content-that-must-not-appear"
    result = task_outcome(
        {
            "stopCode": "TaskFailedToStart",
            "stoppedReason": "ResourceInitializationError: " + private,
            "taskArn": private,
            "environment": [{"name": "PGPASSWORD", "value": private}],
            "containers": [{"reason": private, "exitCode": None}],
        }
    )
    assert private not in json.dumps(result)
    assert result == {
        "stop_code": "TaskFailedToStart",
        "started": False,
        "exit_codes": [None],
        "reason_type": "ResourceInitializationError",
    }


def test_executed_sql_failure_remains_distinguishable_from_startup_failure() -> None:
    assert task_outcome(
        {
            "stopCode": "EssentialContainerExited",
            "startedAt": "synthetic-time",
            "containers": [{"exitCode": 2}],
        }
    ) == {
        "stop_code": "EssentialContainerExited",
        "started": True,
        "exit_codes": [2],
        "reason_type": "OTHER",
    }
