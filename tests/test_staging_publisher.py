"""Unapproved/fork CI runs must never reach AWS image publication."""

import json
from typing import Any

import pytest

from scripts import publish_staging


@pytest.mark.parametrize(
    "override",
    [
        {"conclusion": "failure"},
        {"head_branch": "feat/untrusted"},
        {"event": "pull_request"},
        {"name": "Other CI"},
        {"head_repository": {"full_name": "other/repository"}},
    ],
)
def test_unapproved_ci_cannot_publish(
    override: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    run = dict(
        conclusion="success",
        head_branch="main",
        event="push",
        name="E0 CI",
        head_repository={"full_name": "A-PerfectStranger/special-funicular"},
    )
    run.update(override)
    commands: list[list[str]] = []

    def output(command: list[str]) -> bytes:
        commands.append(command)
        return json.dumps(run).encode()

    monkeypatch.setattr(publish_staging.subprocess, "check_output", output)
    monkeypatch.setattr("sys.argv", ["publish_staging.py", "--run-id", "123"])
    with pytest.raises(SystemExit, match="BLOCKED"):
        publish_staging.main()
    assert len(commands) == 1 and commands[0][:2] == ["gh", "api"]
