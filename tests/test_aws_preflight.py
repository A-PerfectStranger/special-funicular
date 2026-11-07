"""Federation must stay read-only, branch-scoped, and redact financial data (CA-S22)."""

import io
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts import aws_preflight


def synthetic_plan(amount: float = 180.25) -> dict[str, Any]:
    return {
        "accountPlanRemainingCredits": {"amount": amount, "unit": "USD"},
        "accountPlanExpirationDate": "2027-05-06T23:59:59Z",
    }


def synthetic_cost(amount: str = "7.31") -> dict[str, Any]:
    return {"ResultsByTime": [{"Total": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}}}]}


def test_federation_is_exactly_main_and_read_only() -> None:
    template = yaml.load(
        Path("infra/aws/github-preflight.yaml").read_text(), Loader=yaml.BaseLoader
    )
    role = template["Resources"]["PreflightRole"]["Properties"]
    trust = role["AssumeRolePolicyDocument"]["Statement"][0]
    expected_subject = "repo:A-PerfectStranger/special-funicular:ref:refs/heads/main"
    assert trust["Condition"] == {
        "StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            "token.actions.githubusercontent.com:sub": expected_subject,
        }
    }
    assert trust["Action"] == "sts:AssumeRoleWithWebIdentity"
    permissions = role["Policies"][0]["PolicyDocument"]["Statement"]
    assert len(permissions) == 1
    assert set(permissions[0]["Action"]) == {"freetier:GetAccountPlanState", "ce:GetCostAndUsage"}
    assert "ManagedPolicyArns" not in role


def test_missing_or_insufficient_billing_evidence_blocks() -> None:
    assert not any(aws_preflight.assess(None, None).values())
    assert not aws_preflight.assess(synthetic_plan(149), synthetic_cost())["credits_cover_150_usd"]
    assert not aws_preflight.assess(synthetic_plan(), synthetic_cost("150"))[
        "monthly_gross_under_150_usd"
    ]
    assert not aws_preflight.assess(
        synthetic_plan(), {**synthetic_cost(), "NextPageToken": "more"}
    )["gross_usage_read"]
    assert all(aws_preflight.assess(synthetic_plan(), synthetic_cost()).values())


def test_preflight_report_never_publishes_amounts_credentials_or_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    role = "arn:aws:iam::123456789012:role/retiro-seguro-github-preflight"
    for name, value in {
        "GITHUB_REPOSITORY": "A-PerfectStranger/special-funicular",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ID": "123",
        "ACTIONS_ID_TOKEN_REQUEST_URL": "https://example.invalid/token",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "synthetic-request-secret",
        "AWS_ACCESS_KEY_ID": "synthetic-static-key-must-not-propagate",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        aws_preflight, "urlopen", lambda *a, **kw: io.BytesIO(b'{"value":"synthetic-jwt"}')
    )

    def read(env: dict[str, str], *args: str) -> dict[str, Any]:
        assert "AWS_ACCESS_KEY_ID" not in env
        assert Path(env["AWS_WEB_IDENTITY_TOKEN_FILE"]).stat().st_mode & 0o777 == 0o600
        if args[0] == "sts":
            return {"Account": "123456789012", "Arn": "not-for-publication"}
        return synthetic_plan() if args[0] == "freetier" else synthetic_cost()

    monkeypatch.setattr(aws_preflight, "aws_read", read)
    monkeypatch.setattr(aws_preflight, "unrelated_iam_access_denied", lambda env: True)
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv", ["aws_preflight.py", "--role-arn", role, "--report", str(output)]
    )
    assert aws_preflight.main() == 0
    report = output.read_text()
    assert json.loads(report)["passed"] is True
    published = report + capsys.readouterr().out
    for private in [
        "180.25",
        "7.31",
        "123456789012",
        "synthetic-jwt",
        "synthetic-request-secret",
        "not-for-publication",
    ]:
        assert private not in published


@pytest.mark.parametrize("ref", ["refs/heads/feat/untrusted", "refs/pull/2/merge"])
def test_non_main_cannot_even_request_an_oidc_token(
    ref: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_REF", ref)
    monkeypatch.setenv("GITHUB_REPOSITORY", "A-PerfectStranger/special-funicular")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setattr(
        "sys.argv",
        [
            "aws_preflight.py",
            "--role-arn",
            "arn:aws:iam::123456789012:role/retiro-seguro-github-preflight",
            "--report",
            str(tmp_path / "report.json"),
        ],
    )
    assert aws_preflight.main() == 2
    assert not (tmp_path / "report.json").exists()
