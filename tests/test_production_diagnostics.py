"""Production failures expose fixed stages/codes without credentials or remote text."""

import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts import production


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("private credential Bearer synthetic-sensitive-opaque-value"),
        ValueError("private provider body with sensitive account data"),
        KeyError("private secret name"),
    ],
)
def test_unknown_error_text_is_never_published(
    error: Exception,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(type(error)) as raised, production.operation("SOURCE_APPROVAL"):
        raise error
    assert production.failure(raised.value) == 2
    output = capsys.readouterr().out
    assert "private" not in output and "Bearer" not in output and "sensitive" not in output
    result = json.loads(output.splitlines()[-1])
    assert result["stage"] == "SOURCE_APPROVAL" and result["business_enabled"] is False
    assert json.loads(Path("work/production-operation-failure.json").read_text()) == result


def test_nested_operations_report_the_deepest_failed_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    with (
        pytest.raises(RuntimeError) as raised,
        production.operation("FOUNDATION"),
        production.operation("BILLING_PREFLIGHT"),
    ):
        raise RuntimeError("BLOCKED: production billing/custody preflight")
    production.failure(raised.value)
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["stage"] == "BILLING_PREFLIGHT"
    assert result["code"] == "BILLING_PREFLIGHT_FAILED"


def test_public_ci_http_failure_does_not_serialize_url_headers_or_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    error = HTTPError(
        "https://private.invalid?credential=sensitive",
        403,
        "private body",
        {"Authorization": "private token"},
        io.BytesIO(b"private"),
    )
    with pytest.raises(HTTPError) as raised, production.operation("SOURCE_APPROVAL"):
        raise error
    production.failure(raised.value)
    output = capsys.readouterr().out
    assert "private" not in output and "Authorization" not in output and "credential" not in output
    result = json.loads(output.splitlines()[-1])
    assert result["http_status"] == 403 and result["code"] == "HTTP_REQUEST_FAILED"


@pytest.mark.parametrize(
    "aws_code,expected",
    [
        ("AccessDenied", "AccessDenied"),
        ("ExpiredToken", "ExpiredToken"),
        ("synthetic_private_value", "AWS_ERROR"),
    ],
)
def test_only_allowed_aws_error_codes_are_published(
    aws_code: str,
    expected: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    production.failure(RuntimeError("ecr.describe-images: " + aws_code))
    result = json.loads(capsys.readouterr().out)
    assert result["operation"] == "ecr.describe-images" and result["aws_code"] == expected


def test_failure_remains_reportable_when_artifact_directory_is_unwritable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def blocked(*args: object) -> None:
        raise PermissionError("private local path")

    monkeypatch.setattr(production, "report", blocked)
    assert production.failure(RuntimeError("private")) == 2
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "BLOCKED" and "private" not in output
