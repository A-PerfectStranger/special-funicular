"""Read-only credit checks through GitHub OIDC; never publish financial amounts.

E0 preflight only. Does not provision or certify a deployment (RFS22 / CA-S22).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROLE = re.compile(r"arn:aws:iam::([0-9]{12}):role/retiro-seguro-github-preflight")


def aws_read(env: dict[str, str], *args: str) -> dict[str, Any] | None:
    result = subprocess.run(
        ["aws", *args, "--region", "us-east-1", "--output", "json", "--no-cli-pager"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        return None  # Never print CLI stderr, balances, credentials, or remote bodies.
    value = json.loads(result.stdout)
    return value if isinstance(value, dict) else None


def unrelated_iam_access_denied(env: dict[str, str]) -> bool:
    result = subprocess.run(
        ["aws", "iam", "list-users", "--max-items", "1", "--no-cli-pager"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return result.returncode != 0 and "AccessDenied" in result.stderr


def assess(plan: dict[str, Any] | None, cost: dict[str, Any] | None) -> dict[str, bool]:
    checks = {
        "credits_cover_150_usd": False,
        "credits_valid_through_2027_05_06": False,
        "gross_usage_read": False,
        "monthly_gross_under_150_usd": False,
    }
    if plan:
        credit = plan.get("accountPlanRemainingCredits", {})
        checks["credits_cover_150_usd"] = (
            credit.get("unit") == "USD" and Decimal(str(credit.get("amount", "0"))) >= 150
        )
        expiry = datetime.fromisoformat(str(plan.get("accountPlanExpirationDate", "")))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        checks["credits_valid_through_2027_05_06"] = (
            expiry.date().isoformat() >= "2027-05-06" and expiry > datetime.now(UTC)
        )
    if cost and cost.get("ResultsByTime") and not cost.get("NextPageToken"):
        totals = [period["Total"]["UnblendedCost"] for period in cost["ResultsByTime"]]
        checks["gross_usage_read"] = all(total["Unit"] == "USD" for total in totals)
        checks["monthly_gross_under_150_usd"] = (
            checks["gross_usage_read"] and sum(Decimal(total["Amount"]) for total in totals) < 150
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-arn", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    match = ROLE.fullmatch(args.role_arn)
    if (
        not match
        or os.environ.get("GITHUB_REPOSITORY") != "A-PerfectStranger/special-funicular"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
    ):
        print("BLOCKED: preflight is restricted to manual runs of the repository's main branch")
        return 2
    report: dict[str, Any] = {
        "scope": "Read-only E0 credit preflight; not deployment or project cost acceptance",
        "checked_at": datetime.now(UTC).isoformat(),
        "passed": False,
    }
    try:
        request_url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
        request_url += ("&" if "?" in request_url else "?") + urlencode(
            {"audience": "sts.amazonaws.com"}
        )
        request = Request(
            request_url,
            headers={
                "Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"],
            },
        )
        with urlopen(request, timeout=15) as response:
            token = json.load(response)["value"]
        with tempfile.TemporaryDirectory(prefix="retiro-oidc-") as directory:
            token_path = Path(directory) / "token"
            token_path.touch(mode=0o600)
            token_path.write_text(token)
            env = os.environ.copy()
            for name in [
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN",
                "AWS_PROFILE",
            ]:
                env.pop(name, None)
            env.update(
                AWS_WEB_IDENTITY_TOKEN_FILE=str(token_path),
                AWS_ROLE_ARN=args.role_arn,
                AWS_ROLE_SESSION_NAME="retiro-preflight-" + os.environ["GITHUB_RUN_ID"],
                AWS_CONFIG_FILE="/dev/null",
                AWS_SHARED_CREDENTIALS_FILE="/dev/null",
                AWS_EC2_METADATA_DISABLED="true",
                AWS_STS_REGIONAL_ENDPOINTS="regional",
            )
            identity = aws_read(env, "sts", "get-caller-identity")
            report["account_matches_role"] = bool(identity and identity.get("Account") == match[1])
            if report["account_matches_role"]:
                report["unrelated_iam_access_denied"] = unrelated_iam_access_denied(env)
                today = datetime.now(UTC).date()
                plan = aws_read(env, "freetier", "get-account-plan-state")
                cost = aws_read(
                    env,
                    "ce",
                    "get-cost-and-usage",
                    "--time-period",
                    f"Start={today.replace(day=1)},End={today + timedelta(days=1)}",
                    "--granularity",
                    "MONTHLY",
                    "--metrics",
                    "UnblendedCost",
                    "--filter",
                    json.dumps(
                        {
                            "Not": {
                                "Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund"]}
                            }
                        }
                    ),
                )
                report["checks"] = assess(plan, cost)
                report["passed"] = report["unrelated_iam_access_denied"] and all(
                    report["checks"].values()
                )
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation, subprocess.SubprocessError):
        report["error"] = "identity_or_billing_verification_failed"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print("AWS read-only preflight: " + ("PASS" if report["passed"] else "BLOCKED"))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
