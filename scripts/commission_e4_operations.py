"""Operator bootstrap for private staging APKs and the authorized budget-email alert channel."""

import argparse
import json
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from scripts.aws_cli import aws
from scripts.commission_e1 import billing_preflight, outputs, validate_operator
from scripts.e4_operations_recovery import RecoveryBlocked, prepare, retained_key, stack


class CommissioningBlocked(RuntimeError):
    """A shareable failure location without remote payloads, email or credentials."""

    def __init__(self, stage: str, code: str) -> None:
        self.stage = stage
        self.code = code
        super().__init__(f"BLOCKED: {stage}: {code}")


@contextmanager
def stage(name: str) -> Iterator[None]:
    try:
        yield
    except CommissioningBlocked:
        raise
    except RecoveryBlocked as error:
        raise CommissioningBlocked(name, error.code) from None
    except Exception as error:
        # aws_cli already strips remote payloads. Accept only its exact error shape;
        # never print arbitrary exception text or subprocess stdout/stderr.
        match = re.fullmatch(r"[a-z0-9-]+\.[a-z0-9-]+: ([A-Za-z0-9_]{1,64})", str(error))
        known = {
            "BLOCKED: exact clean reviewed checkout required": "SOURCE_NOT_REVIEWED",
            "Wrong AWS account": "WRONG_ACCOUNT",
            "Verified AWS operator identity required": "OPERATOR_REQUIRED",
            "CI/runtime roles are not provisioning operators": "OPERATOR_REQUIRED",
            "Billing/credit/budget preflight blocked; no provisioning performed": "BUDGET_BLOCKED",
            "BLOCKED: one unambiguous authorized budget email required": (
                "ALERT_RECIPIENT_AMBIGUOUS"
            ),
            "BLOCKED: invalid budget email": "ALERT_RECIPIENT_INVALID",
            "BLOCKED: operations stack failed; inspect private stack events": "STACK_DEPLOY_FAILED",
        }
        code = match[1] if match else known.get(str(error), "LOCAL_OR_RESPONSE_ERROR")
        raise CommissioningBlocked(name, code) from None


def budget_recipient() -> str:
    response = aws(
        "budgets",
        "describe-subscribers-for-notification",
        "--account-id",
        "028364485203",
        "--budget-name",
        "retiro-seguro-total-150-usd",
        "--notification",
        json.dumps(
            {
                "NotificationType": "ACTUAL",
                "ComparisonOperator": "GREATER_THAN",
                "Threshold": 25,
                "ThresholdType": "PERCENTAGE",
            }
        ),
    )
    addresses = {
        value["Address"]
        for value in response.get("Subscribers", [])
        if value.get("SubscriptionType") == "EMAIL"
    }
    if response.get("NextToken") or len(addresses) != 1:
        raise RuntimeError("BLOCKED: one unambiguous authorized budget email required")
    address = addresses.pop()
    if not isinstance(address, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", address):
        raise RuntimeError("BLOCKED: invalid budget email")
    return address


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--use-budget-alert-email", action="store_true", required=True)
    parser.add_argument("--recover-retained-key-id")
    args = parser.parse_args()
    with stage("source"):
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        if (
            not re.fullmatch(r"[0-9a-f]{40}", args.expected_sha)
            or sha != args.expected_sha
            or subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        ):
            raise RuntimeError("BLOCKED: exact clean reviewed checkout required")
    with stage("identity"):
        validate_operator(aws("sts", "get-caller-identity"))
    with stage("budget"):
        billing = billing_preflight()
    # Explicit operator flag authorizes SNS's confirmation email to this recipient.
    # Never print the address or provider diagnostics, including on failure.
    with stage("alert_recipient"):
        address = budget_recipient()
    parameters = [f"AlertEmail={address}"]
    existing_key_arn = ""
    with stage("cloudformation_state"):
        current = stack()
        if args.recover_retained_key_id:
            existing_key_arn = prepare(args.recover_retained_key_id)
        elif current is not None and current["StackStatus"] == "ROLLBACK_COMPLETE":
            raise CommissioningBlocked("cloudformation_state", "RETAINED_KEY_RECOVERY_REQUIRED")
        elif current is not None:
            existing = {
                p["ParameterKey"]: p.get("ParameterValue", "")
                for p in current.get("Parameters", [])
            }
            # A normal update must never switch a recovered key back to a newly
            # created key just because the recovery flag was not repeated.
            if existing.get("ExistingOperationsKeyArn"):
                arn = existing["ExistingOperationsKeyArn"]
                if retained_key(arn.rsplit("/", 1)[-1]) != arn:
                    raise RecoveryBlocked("HEALTHY_STACK_KEY_MODE_MISMATCH")
                existing_key_arn = arn
        if existing_key_arn:
            parameters.append("ExistingOperationsKeyArn=" + existing_key_arn)
    with stage("cloudformation_deploy"):
        result = subprocess.run(
            [
                "aws",
                "cloudformation",
                "deploy",
                "--region",
                "us-east-1",
                "--stack-name",
                "retiro-staging-operations",
                "--template-file",
                "infra/aws/e4-operations.yaml",
                "--capabilities",
                "CAPABILITY_NAMED_IAM",
                "--no-fail-on-empty-changeset",
                "--parameter-overrides",
                *parameters,
                "--tags",
                "Project=retiro-seguro",
                "Environment=staging",
                "Data=internal-apk",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("BLOCKED: operations stack failed; inspect private stack events")
    with stage("stack_outputs"):
        configured = outputs("retiro-staging-operations")
        if existing_key_arn and configured.get("MobileEncryptionKeyArn") != existing_key_arn:
            raise CommissioningBlocked("stack_outputs", "RETAINED_KEY_NOT_REUSED")
    with stage("subscription"):
        subscribed = aws(
            "sns", "list-subscriptions-by-topic", "--topic-arn", configured["OperatorAlertTopicArn"]
        )
    confirmed = not subscribed.get("NextToken") and any(
        value.get("Endpoint") == address
        and value.get("Protocol") == "email"
        and value.get("SubscriptionArn", "").startswith("arn:aws:sns:")
        for value in subscribed.get("Subscriptions", [])
    )
    report = {
        "sha": sha,
        "billing": billing,
        "outputs": configured,
        "alert_subscription_confirmed": confirmed,
        "retained_key_reused": bool(existing_key_arn),
        "apk_published": False,
        "e4_accepted": False,
        "e5_accepted": False,
    }
    Path("work").mkdir(exist_ok=True)
    Path("work/e4-operations.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


def cli() -> int:
    try:
        return main()
    except CommissioningBlocked as error:
        print(json.dumps({"status": "BLOCKED", "stage": error.stage, "code": error.code}))
    except Exception:
        print(
            json.dumps({"status": "BLOCKED", "stage": "local", "code": "LOCAL_OR_RESPONSE_ERROR"})
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(cli())
