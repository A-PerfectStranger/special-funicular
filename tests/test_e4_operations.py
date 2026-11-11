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
    monkeypatch.setattr(operations, "stack", lambda: None)
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


def test_rolled_back_stack_requires_explicit_recovery_without_retrying_deploy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = configure(monkeypatch, tmp_path)
    monkeypatch.setattr(operations, "stack", lambda: {"StackStatus": "ROLLBACK_COMPLETE"})
    assert operations.cli() == 2
    assert json.loads(capsys.readouterr().out)["code"] == "RETAINED_KEY_RECOVERY_REQUIRED"
    assert not calls


@pytest.mark.parametrize("recover", [True, False])
def test_recovery_and_subsequent_updates_preserve_the_retained_key_parameter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, recover: bool
) -> None:
    calls = configure(monkeypatch, tmp_path)
    key = "11111111-1111-1111-1111-111111111111"
    arn = f"arn:aws:kms:us-east-1:028364485203:key/{key}"
    if recover:
        monkeypatch.setattr(
            "sys.argv",
            [
                "commission",
                "--expected-sha",
                SHA,
                "--use-budget-alert-email",
                "--recover-retained-key-id",
                key,
            ],
        )
        monkeypatch.setattr(operations, "prepare", lambda value: arn if value == key else "wrong")
    else:
        monkeypatch.setattr(
            operations,
            "stack",
            lambda: {
                "StackStatus": "CREATE_COMPLETE",
                "Parameters": [{"ParameterKey": "ExistingOperationsKeyArn", "ParameterValue": arn}],
            },
        )
        monkeypatch.setattr(
            operations, "retained_key", lambda value: arn if value == key else "wrong"
        )
        monkeypatch.setattr(
            operations, "prepare", lambda _: pytest.fail("must not recover healthy stack")
        )
    monkeypatch.setattr(
        operations,
        "outputs",
        lambda _: {
            "OperatorAlertTopicArn": "arn:aws:sns:us-east-1:028364485203:synthetic",
            "MobileEncryptionKeyArn": arn,
        },
    )
    assert operations.main() == 0
    assert f"ExistingOperationsKeyArn={arn}" in calls[0]
    assert json.loads(Path("work/e4-operations.json").read_text())["retained_key_reused"] is True


def test_success_is_rejected_if_the_deployed_key_is_not_the_one_recovered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "commission",
            "--expected-sha",
            SHA,
            "--use-budget-alert-email",
            "--recover-retained-key-id",
            "synthetic",
        ],
    )
    monkeypatch.setattr(operations, "prepare", lambda _: "retained-key-arn")
    assert operations.cli() == 2
    assert json.loads(capsys.readouterr().out)["code"] == "RETAINED_KEY_NOT_REUSED"
    assert not Path("work/e4-operations.json").exists()


def test_deploy_failure_does_not_print_captured_private_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        operations.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(
            [], 1, "private response", PRIVATE_ADDRESS + " secret-token"
        ),
    )
    assert operations.cli() == 2
    raw = capsys.readouterr().out
    assert json.loads(raw)["stage"] == "cloudformation_deploy"
    assert (
        PRIVATE_ADDRESS not in raw and "secret-token" not in raw and "private response" not in raw
    )


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


def test_sns_topic_policy_uses_only_service_supported_topic_actions() -> None:
    template, errors = decode("infra/aws/e4-operations.yaml")
    assert not errors and template is not None
    statements = template["Resources"]["AlertTopicPolicy"]["Properties"]["PolicyDocument"][
        "Statement"
    ]
    supported = {
        "sns:GetTopicAttributes",
        "sns:SetTopicAttributes",
        "sns:AddPermission",
        "sns:RemovePermission",
        "sns:DeleteTopic",
        "sns:Subscribe",
        "sns:ListSubscriptionsByTopic",
        "sns:Publish",
    }
    for statement in statements:
        actions = statement["Action"]
        assert set(actions if isinstance(actions, list) else [actions]) <= supported
    cloudwatch = next(
        s for s in statements if s["Principal"] == {"Service": "cloudwatch.amazonaws.com"}
    )
    assert cloudwatch["Action"] == "sns:Publish"
    assert "aws:SourceAccount" in cloudwatch["Condition"]["StringEquals"]
    assert "aws:SourceArn" in cloudwatch["Condition"]["ArnLike"]


@pytest.mark.parametrize(
    "error,stage,code",
    [
        (
            RuntimeError("budgets.describe-subscribers-for-notification: AccessDeniedException"),
            "alert_recipient",
            "AccessDeniedException",
        ),
        (
            RuntimeError("BLOCKED: one unambiguous authorized budget email required"),
            "alert_recipient",
            "ALERT_RECIPIENT_AMBIGUOUS",
        ),
        (
            RuntimeError("BLOCKED: operations stack failed; inspect private stack events"),
            "cloudformation_deploy",
            "STACK_DEPLOY_FAILED",
        ),
        (
            ValueError("private remote response operator@example.invalid and secret-token"),
            "subscription",
            "LOCAL_OR_RESPONSE_ERROR",
        ),
    ],
)
def test_cli_reports_failure_stage_without_exception_payload(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    stage: str,
    code: str,
) -> None:
    def fail() -> int:
        with operations.stage(stage):
            raise error

    monkeypatch.setattr(operations, "main", fail)
    assert operations.cli() == 2
    raw = capsys.readouterr().out
    assert json.loads(raw) == {"status": "BLOCKED", "stage": stage, "code": code}
    assert PRIVATE_ADDRESS not in raw and "secret-token" not in raw
