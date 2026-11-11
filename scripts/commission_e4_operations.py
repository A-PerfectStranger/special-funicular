"""Operator bootstrap for private staging APKs and the authorized budget-email alert channel."""

import argparse
import json
import re
import subprocess
from pathlib import Path

from scripts.aws_cli import aws
from scripts.commission_e1 import billing_preflight, outputs, validate_operator


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
    args = parser.parse_args()
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if (
        not re.fullmatch(r"[0-9a-f]{40}", args.expected_sha)
        or sha != args.expected_sha
        or subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    ):
        raise RuntimeError("BLOCKED: exact clean reviewed checkout required")
    validate_operator(aws("sts", "get-caller-identity"))
    billing = billing_preflight()
    # Explicit operator flag authorizes SNS's confirmation email to this recipient.
    # Never print the address or provider diagnostics, including on failure.
    address = budget_recipient()
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
            f"AlertEmail={address}",
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
    configured = outputs("retiro-staging-operations")
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
        "apk_published": False,
        "e4_accepted": False,
        "e5_accepted": False,
    }
    Path("work").mkdir(exist_ok=True)
    Path("work/e4-operations.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("BLOCKED: operations commissioning rejected; inspect configuration privately")
        raise SystemExit(2) from None
