"""Read-only production billing gate. Reports booleans, never balances or credentials."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from scripts.aws_cli import aws
from scripts.production import ACCOUNT, failure, operation, report

COST_PLAN_PARAMETER = "/retiro-production/cost-plan"


def cost_plan_checks(plan: dict[str, Any], now: datetime) -> dict[str, bool]:
    try:
        reviewed = datetime.fromisoformat(plan["pricing_checked_at"])
        until = datetime.fromisoformat(plan["custody_until"])
        new = Decimal(str(plan["new_resources_and_custody_reserve_usd"]))
        retained = Decimal(str(plan["existing_retained_reserve_usd"]))
        contingency = Decimal(str(plan["contingency_reserve_usd"]))
        valid = all(value.is_finite() for value in [new, retained, contingency])
        return {
            "reviewed_cost_plan": plan.get("schema_version") == 1
            and plan.get("operator_verified_official_prices") is True
            and plan.get("window_hours") == 3
            and reviewed.tzinfo is not None
            and now - timedelta(days=1) <= reviewed <= now,
            "custody_financed": until.tzinfo is not None and until >= now + timedelta(days=97),
            "reserves_within_allocations": valid
            and 0 < new <= 40
            and retained >= 50
            and contingency >= 30
            and new + retained + contingency <= 150,
        }
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return {
            "reviewed_cost_plan": False,
            "custody_financed": False,
            "reserves_within_allocations": False,
        }


def free_plan_custody_valid(
    account_plan: dict[str, Any], cost_plan: dict[str, Any], now: datetime
) -> bool:
    """FREE ends within six months; its credits last twelve months from account creation.

    Require the shorter FREE account lifetime to cover the whole custody period.
    Plan expiry is not reported as the actual credit expiration date, and PAID
    plans cannot use this conservative bound.
    """
    try:
        expires = datetime.fromisoformat(account_plan["accountPlanExpirationDate"])
        until = datetime.fromisoformat(cost_plan["custody_until"])
        return (
            account_plan.get("accountPlanType") == "FREE"
            and account_plan.get("accountPlanStatus") == "ACTIVE"
            and expires.tzinfo is not None
            and until.tzinfo is not None
            and expires >= until > now
        )
    except (KeyError, TypeError, ValueError):
        return False


def evaluate(
    budget: dict[str, Any],
    credit_plan: dict[str, Any],
    cost: dict[str, Any],
    cost_plan: dict[str, Any],
    now: datetime,
) -> dict[str, bool]:
    checks = cost_plan_checks(cost_plan, now)
    # Owner requires FREE; never upgrade billing or accept a paid/unknown plan.
    checks["free_account_plan_active"] = (
        credit_plan.get("accountPlanType") == "FREE"
        and credit_plan.get("accountPlanStatus") == "ACTIVE"
    )
    if not all(checks.values()):
        return checks
    reserve = sum(
        Decimal(str(cost_plan[key]))
        for key in [
            "new_resources_and_custody_reserve_usd",
            "existing_retained_reserve_usd",
            "contingency_reserve_usd",
        ]
    )
    totals = [item["Total"]["UnblendedCost"] for item in cost.get("ResultsByTime", [])]
    credit = credit_plan.get("accountPlanRemainingCredits", {})
    try:
        amounts = [Decimal(item["Amount"]) for item in totals]
        credit_amount = Decimal(str(credit.get("amount", 0)))
        valid_amounts = all(amount.is_finite() and amount >= 0 for amount in amounts)
        valid_credit = credit_amount.is_finite() and credit_amount >= 0
    except (KeyError, TypeError, ArithmeticError):
        checks["financial_amounts_valid"] = False
        return checks
    checks.update(
        {
            "gross_budget_150_usd": budget.get("TimeUnit") == "CUSTOM"
            and budget.get("BudgetType") == "COST"
            and budget.get("BudgetLimit", {}).get("Unit") == "USD"
            and Decimal(str(budget["BudgetLimit"]["Amount"])) == 150
            and budget.get("CostTypes", {}).get("IncludeCredit") is False
            and budget.get("CostTypes", {}).get("IncludeRefund") is False,
            "gross_usage_complete": bool(totals)
            and valid_amounts
            and not cost.get("NextPageToken")
            and all(item["Unit"] == "USD" for item in totals),
            "usage_and_reserves_within_ceiling": bool(totals)
            and valid_amounts
            and sum(amounts) + reserve <= 150,
            "credit_covers_reserves": credit.get("unit") == "USD"
            and valid_credit
            and credit_amount >= reserve,
            "free_plan_valid_through_custody": free_plan_custody_valid(credit_plan, cost_plan, now),
            "budget_active": datetime.fromisoformat(budget["TimePeriod"]["Start"])
            <= now
            < datetime.fromisoformat(budget["TimePeriod"]["End"]),
        }
    )
    return checks


def preflight(plan: dict[str, Any] | None = None) -> dict[str, bool]:
    if aws("sts", "get-caller-identity").get("Account") != ACCOUNT:
        raise RuntimeError("BLOCKED: wrong production account")
    if plan is None:
        plan = json.loads(
            aws(
                "ssm",
                "get-parameter",
                "--name",
                COST_PLAN_PARAMETER,
            )["Parameter"]["Value"]
        )
    now = datetime.now(UTC)
    budget = aws(
        "budgets",
        "describe-budget",
        "--account-id",
        ACCOUNT,
        "--budget-name",
        "retiro-seguro-total-150-usd",
    )["Budget"]
    start = datetime.fromisoformat(budget["TimePeriod"]["Start"]).date()
    cost = aws(
        "ce",
        "get-cost-and-usage",
        "--time-period",
        f"Start={start},End={now.date() + timedelta(days=1)}",
        "--granularity",
        "MONTHLY",
        "--metrics",
        "UnblendedCost",
        "--filter",
        json.dumps({"Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund"]}}}),
    )
    checks = evaluate(budget, aws("freetier", "get-account-plan-state"), cost, plan, now)
    report(
        "production-preflight",
        {"checks": checks, "passed": all(checks.values()), "checked_at": now.isoformat()},
    )
    if not all(checks.values()):
        raise RuntimeError("BLOCKED: production billing/custody preflight")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cost-plan", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.cost_plan.read_text()) if args.cost_plan else None
    with operation("BILLING_PREFLIGHT"):
        print(json.dumps({"checks": preflight(plan), "passed": True}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        raise SystemExit(failure(error)) from None
