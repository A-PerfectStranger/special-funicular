"""The failure drill cannot target business tasks and must recover after partial failure."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts.e1_archive_control import validate_definition
from scripts.e1_release import api_definition, archive_definition
from tests.test_e1_release import configuration


def test_drill_rejects_api_and_mismatched_archive_source() -> None:
    base, config = configuration()
    sha, digest = "a" * 40, "sha256:" + "b" * 64
    image = "028364485203.dkr.ecr.us-east-1.amazonaws.com/retiro-staging/backend@" + digest
    valid = archive_definition(base, config, image, sha)
    validate_definition(valid, config, sha, digest)
    with pytest.raises(RuntimeError, match="isolated archive"):
        validate_definition(api_definition(base, config, image, sha), config, sha, digest)
    with pytest.raises(RuntimeError, match="isolated archive"):
        validate_definition(valid, config, "c" * 40, digest)


@pytest.mark.parametrize("partial_pause", [False, True])
def test_recovery_runs_after_partial_stop_or_browser_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, partial_pause: bool
) -> None:
    from scripts import e1_archive_drill as module

    monkeypatch.chdir(tmp_path)
    controls: list[str] = []

    def run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        action = arguments[arguments.index("scripts.e1_archive_control") + 1]
        controls.append(action)
        if action == "pause":
            module.STATE.write_text("{}")
            if partial_pause:
                raise subprocess.CalledProcessError(2, arguments)
        return subprocess.CompletedProcess(arguments, 0)

    class FailedBrowser:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def poll(self) -> int:
            return 2

    monkeypatch.setattr(module.subprocess, "run", run)
    monkeypatch.setattr(module.subprocess, "Popen", FailedBrowser)
    assert module.drill("a" * 40, "sha256:" + "b" * 64) == 2
    assert controls == ["pause", "resume"]
    assert (
        json.loads(Path("work/e1-archive-recovery.json").read_text())["archive_recovered"] is True
    )
