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


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Wrong AWS account", "WRONG_ACCOUNT"),
        ("Verified AWS operator identity required", "OPERATOR_IDENTITY_REQUIRED"),
        ("CI/runtime roles are not provisioning operators", "CI_IDENTITY_REJECTED"),
        ("BLOCKED: production CI/runtime identities are not operators", "CI_IDENTITY_REJECTED"),
        (
            "BLOCKED: unexpected failed production stack ownership/state",
            "STACK_OWNERSHIP_OR_STATE",
        ),
        ("BLOCKED: unexpected resource in failed production stack", "RECOVERY_UNKNOWN_RESOURCE"),
        ("BLOCKED: unexpected surviving production resource", "RECOVERY_UNEXPECTED_SURVIVOR"),
        (
            "BLOCKED: protected resource retention policy mismatch",
            "RECOVERY_RETENTION_POLICY_DRIFT",
        ),
        ("BLOCKED: ambiguous retained production key", "RECOVERY_AMBIGUOUS_KEY"),
        ("BLOCKED: ambiguous retained production secret", "RECOVERY_AMBIGUOUS_SECRET"),
        ("BLOCKED: retained secret reference mismatch", "RETAINED_SECRET_REFERENCE_DRIFT"),
        ("BLOCKED: retained secret metadata mismatch", "RETAINED_SECRET_METADATA_DRIFT"),
    ],
)
def test_recovery_failures_have_fixed_actionable_codes(
    message: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError) as raised, production.operation("RECOVERY_INSPECTION"):
        raise RuntimeError(message)
    assert production.failure(raised.value) == 2
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["code"] == expected and result["stage"] == "RECOVERY_INSPECTION"
    assert result["business_enabled"] is False


@pytest.mark.parametrize(
    "operation",
    [
        "cloudformation.list-stack-resources",
        "cloudformation.get-template",
        "rds.describe-db-instances",
        "kms.describe-key",
        "kms.list-resource-tags",
        "kms.get-key-rotation-status",
        "kms.get-key-policy",
        "secretsmanager.describe-secret",
    ],
)
def test_recovery_aws_failures_expose_only_allowed_operation_and_code(
    operation: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    production.failure(RuntimeError(operation + ": AccessDeniedException"))
    result = json.loads(capsys.readouterr().out)
    assert result["operation"] == operation
    assert result["aws_code"] == "AccessDeniedException"
    assert result["code"] == "AWS_REQUEST_FAILED"
