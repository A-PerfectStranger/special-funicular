"""A failed request only proves isolation when AWS explicitly denies access."""

import json
from pathlib import Path
from typing import Any

import pytest
from archive_worker.verifier import VerificationDeadlineExceeded
from botocore.exceptions import ClientError

from scripts import verify_e1_staging as cloud
from scripts.verify_e1_staging import denied


@pytest.mark.parametrize(
    "code", ["AccessDenied", "AccessDeniedException", "NoSuchKey", "ThrottlingException"]
)
def test_only_explicit_access_denial_counts_as_isolation(code: str) -> None:
    def operation() -> None:
        raise ClientError({"Error": {"Code": code, "Message": "private provider detail"}}, "Probe")

    if code.startswith("AccessDenied"):
        denied(operation)
    else:
        with pytest.raises(RuntimeError, match="not established"):
            denied(operation)


def test_unexpected_permission_is_never_accepted() -> None:
    with pytest.raises(RuntimeError, match="Unexpected cloud permission"):
        denied(lambda: None)


def test_internal_deadline_writes_failure_report_before_runner_cancellation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["verify"])

    def expired(*args: Any) -> dict[str, Any]:
        raise VerificationDeadlineExceeded()

    monkeypatch.setattr(cloud, "verify", expired)
    assert cloud.main() == 2
    report = json.loads(Path("work/e1-cloud-acceptance.json").read_text())
    assert report == {
        "passed": False,
        "e1_accepted": False,
        "error": "verification_deadline_exceeded",
    }
    assert "FAIL" in capsys.readouterr().out
