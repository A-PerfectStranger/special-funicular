"""Static/command regressions only; do not imply real AWS commissioning."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from cfnlint.decode import decode

from scripts.commission_e1 import billing_preflight, bootstrap_definition, operator_principal


def test_e1_stack_has_mandatory_mfa_worm_and_distinct_keys() -> None:
    template, errors = decode("infra/aws/e1-staging.yaml")
    assert not errors and template
    resources = template["Resources"]
    pool = resources["Pool"]["Properties"]
    assert pool["MfaConfiguration"] == "ON"
    assert pool["EnabledMfas"] == ["SOFTWARE_TOKEN_MFA"]
    assert pool["AdminCreateUserConfig"]["AllowAdminCreateUserOnly"]
    for name in ["WebClient", "MobileClient"]:
        client = resources[name]["Properties"]
        assert client["AllowedOAuthFlows"] == ["code"]
        assert client["IdTokenValidity"] == client["AccessTokenValidity"] == 5
        assert client["ExplicitAuthFlows"] == ["ALLOW_REFRESH_TOKEN_AUTH"]
    bucket = resources["EvidenceBucket"]["Properties"]
    assert bucket["ObjectLockConfiguration"]["Rule"]["DefaultRetention"] == {
        "Mode": "COMPLIANCE",
        "Days": 7,
    }
    assert bucket["VersioningConfiguration"]["Status"] == "Enabled"
    assert all(bucket["PublicAccessBlockConfiguration"].values())
    assert resources["SigningKey"]["Properties"]["KeySpec"] == "RSA_3072"
    assert resources["SigningKey"]["Properties"]["KeyUsage"] == "SIGN_VERIFY"
    for name in ["EvidenceBucket", "EncryptionKey", "SigningKey"]:
        assert resources[name]["DeletionPolicy"] == "Retain"
    verifier = str(resources["Verifier"]["Properties"]["Policies"])
    assert "kms:Sign'" not in verifier and "s3:PutObject'" not in verifier
    assert "kms:Verify" in verifier


def test_ci_or_runtime_identity_cannot_commission() -> None:
    with patch(
        "scripts.commission_e1.aws",
        return_value={"Role": {"Arn": "arn:aws:iam::028364485203:role/retiro-staging-Deploy"}},
    ):
        with pytest.raises(RuntimeError, match="not provisioning operators"):
            operator_principal(
                {"Arn": "arn:aws:sts::028364485203:assumed-role/retiro-staging-Deploy/session"}
            )


def test_billing_checks_whole_custom_budget_not_just_current_month() -> None:
    start = (datetime.now(UTC) - timedelta(days=40)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    calls: list[tuple[str, ...]] = []

    def fake(*args: str) -> dict:
        calls.append(args)
        if args[:2] == ("freetier", "get-account-plan-state"):
            return {
                "accountPlanRemainingCredits": {"unit": "USD", "amount": "100"},
                "accountPlanExpirationDate": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
            }
        if args[:2] == ("budgets", "describe-budget"):
            return {
                "Budget": {
                    "BudgetLimit": {"Amount": "150", "Unit": "USD"},
                    "TimeUnit": "CUSTOM",
                    "TimePeriod": {"Start": start.isoformat()},
                }
            }
        return {"ResultsByTime": [{"Total": {"UnblendedCost": {"Unit": "USD", "Amount": "1"}}}]}

    with patch("scripts.commission_e1.aws", side_effect=fake):
        assert all(billing_preflight().values())
    ce = next(call for call in calls if call[0] == "ce")
    assert f"Start={start.date()}" in ce[ce.index("--time-period") + 1]


def test_bootstrap_never_injects_reader_secrets_into_application_task() -> None:
    base = {
        key: key
        for key in [
            "DbHost",
            "DjangoSecret",
            "MasterSecret",
            "MigrationPassword",
            "RuntimePassword",
            "Logs",
            "BootstrapExecution",
            "ApiExecution",
        ]
    }
    e1 = {
        key: key
        for key in [
            "SchoolReadPassword",
            "SystemReadPassword",
            "ImporterPassword",
            "ArchivePassword",
            "NotifierPassword",
        ]
    }
    definition = bootstrap_definition(base, e1, "synthetic-image@sha256:" + "a" * 64, "a" * 40)
    assert definition["family"] == "retiro-staging-e1-bootstrap"
    secrets = {s["name"] for s in definition["containerDefinitions"][0]["secrets"]}
    assert secrets == {
        "PGPASSWORD",
        "E1_SCHOOL_READ_PASSWORD",
        "E1_SYSTEM_READ_PASSWORD",
        "E1_IMPORTER_PASSWORD",
        "E1_ARCHIVER_PASSWORD",
        "E1_NOTIFIER_PASSWORD",
    }
    assert "taskRoleArn" not in definition
