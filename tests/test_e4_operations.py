"""Operator bootstrap cannot send mail/provision before source, identity and cost checks."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from cfnlint.decode import decode

from scripts import commission_e4_operations as operations

SHA = "a" * 40
PRIVATE_ADDRESS = "operator@example.invalid"


@pytest.mark.parametrize(
    "subscribers,extra",
    [
        ([], {}),
        (
            [
                {"SubscriptionType": "EMAIL", "Address": "one@example.invalid"},
                {"SubscriptionType": "EMAIL", "Address": "two@example.invalid"},
            ],
            {},
        ),
        ([{"SubscriptionType": "EMAIL", "Address": PRIVATE_ADDRESS}], {"NextToken": "more"}),
        ([{"SubscriptionType": "EMAIL", "Address": "bad address"}], {}),
    ],
)
def test_ambiguous_recipient_does_not_send_any_email(
    monkeypatch: pytest.MonkeyPatch, subscribers: list[dict[str, str]], extra: dict[str, str]
) -> None:
    monkeypatch.setattr(operations, "aws", lambda *a: {"Subscribers": subscribers, **extra})
    with pytest.raises(RuntimeError, match="BLOCKED"):
        operations.budget_recipient()


def configure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[list[str]]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "commission",
            "--expected-sha",
            SHA,
            "--use-budget-alert-email",
        ],
    )
    monkeypatch.setattr(
        operations.subprocess, "check_output", lambda args, **kw: SHA if "rev-parse" in args else ""
    )
    calls: list[list[str]] = []

    def aws(*args: str) -> dict[str, Any]:
        if args[:2] == ("sts", "get-caller-identity"):
            return {"Account": "028364485203", "Arn": "arn:aws:iam::028364485203:user/operator"}
        if args[:2] == ("budgets", "describe-subscribers-for-notification"):
            return {"Subscribers": [{"SubscriptionType": "EMAIL", "Address": PRIVATE_ADDRESS}]}
        if args[:2] == ("sns", "list-subscriptions-by-topic"):
            return {
                "Subscriptions": [
                    {
                        "Protocol": "email",
                        "Endpoint": PRIVATE_ADDRESS,
                        "SubscriptionArn": "PendingConfirmation",
                    }
                ]
            }
        pytest.fail("Unexpected AWS call")

    def deploy(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        assert kwargs["capture_output"] is True
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(operations, "aws", aws)
    monkeypatch.setattr(operations, "billing_preflight", lambda: {"all_budget_checks": True})
    monkeypatch.setattr(
        operations,
        "outputs",
        lambda _: {
            "OperatorAlertTopicArn": (
                "arn:aws:sns:us-east-1:028364485203:retiro-staging-operations-alerts"
            )
        },
    )
    monkeypatch.setattr(operations.subprocess, "run", deploy)
    return calls


def test_authorized_bootstrap_redacts_email_and_does_not_claim_acceptance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = configure(monkeypatch, tmp_path)
    assert operations.main() == 0 and len(calls) == 1
    report = json.loads(Path("work/e4-operations.json").read_text())
    assert report["alert_subscription_confirmed"] is False
    assert report["apk_published"] is False and report["e4_accepted"] is False
    assert PRIVATE_ADDRESS not in json.dumps(report) + capsys.readouterr().out


@pytest.mark.parametrize("failure", ["budget", "dirty_source", "wrong_sha", "wrong_account"])
def test_no_provisioning_or_confirmation_email_before_preflight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    calls = configure(monkeypatch, tmp_path)
    if failure == "budget":

        def fail() -> dict[str, bool]:
            raise RuntimeError("Budget blocked")

        monkeypatch.setattr(operations, "billing_preflight", fail)
    elif failure in {"dirty_source", "wrong_sha"}:
        monkeypatch.setattr(
            operations.subprocess,
            "check_output",
            lambda args, **kw: (
                ("b" * 40 if failure == "wrong_sha" else SHA) if "rev-parse" in args else "dirty"
            ),
        )
    else:
        monkeypatch.setattr(operations, "aws", lambda *a: {"Account": "123456789012"})
    monkeypatch.setattr(
        operations, "budget_recipient", lambda: pytest.fail("must not resolve email")
    )
    with pytest.raises(RuntimeError):
        operations.main()
    assert not calls


def test_operations_role_has_no_student_database_or_evidence_permissions() -> None:
    template, errors = decode("infra/aws/e4-operations.yaml")
    assert not errors and template is not None
    resources = template["Resources"]
    role = resources["MobilePublisher"]["Properties"]
    trust = role["AssumeRolePolicyDocument"]["Statement"][0]["Condition"]["StringEquals"]
    assert trust["token.actions.githubusercontent.com:sub"] == (
        "repo:A-PerfectStranger@144553443/special-funicular@1449067177:ref:refs/heads/main"
    )
    actions = {
        action
        for statement in role["Policies"][0]["PolicyDocument"]["Statement"]
        for action in (
            statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
        )
    }
    assert "s3:PutObject" in actions
    assert not any(
        action.startswith(("secretsmanager:", "ecs:", "rds:", "iam:"))
        or action in {"s3:DeleteObject", "s3:PutBucketPolicy", "kms:Sign", "kms:*"}
        for action in actions
    )
    assert template["Parameters"]["AlertEmail"]["NoEcho"] is True
    assert resources["MobileBucket"]["DeletionPolicy"] == "Retain"
