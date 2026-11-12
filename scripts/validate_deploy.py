"""Offline fail-closed gate. Success validates input, never claims a deployment."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def validate(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "environment",
        "provider",
        "region",
        "account_id",
        "deploy_role_arn",
        "migration_role_arn",
        "image_repository",
        "cluster",
        "service",
        "task_definition",
        "migration_task_definition",
        "subnets",
        "security_groups",
        "base_url",
    ]
    for field in required:
        if not config.get(field):
            errors.append(f"missing {field}")
    if config.get("environment") not in {"staging", "production"}:
        errors.append("environment must be staging or production")
    if config.get("provider") != "aws" or config.get("region") != "us-east-1":
        errors.append("provider/region must match selected aws/us-east-1")
    account = config.get("account_id")
    if not isinstance(account, str) or not re.fullmatch(r"\d{12}", account):
        errors.append("invalid account_id")
    for field in ["deploy_role_arn", "migration_role_arn"]:
        value = config.get(field)
        if not isinstance(value, str) or not re.fullmatch(
            rf"arn:aws:iam::{re.escape(str(account))}:role/[\w+=,.@/-]+", value
        ):
            errors.append(f"invalid {field}")
    if config.get("deploy_role_arn") == config.get("migration_role_arn"):
        errors.append("deployment and migration roles must be distinct")
    url = urlparse(str(config.get("base_url") or ""))
    if url.scheme != "https" or not url.hostname or url.username or url.query or url.fragment:
        errors.append("base_url must be HTTPS without credentials/query/fragment")
    if config.get("budget_verified") is not True or config.get("credit_ceiling_usd") != 150:
        errors.append("verify actual spend/remaining credits and the 150 USD ceiling")
    if config.get("pickup_enabled") is not False or config.get("synthetic_only") is not True:
        errors.append("E0 permits synthetic data only, with pickups disabled")
    if config.get("e3_enabled") is True and (
        config.get("environment") != "staging"
        or config.get("e1_enabled") is not True
        or config.get("e2_enabled") is not True
    ):
        errors.append("E3 requires synthetic staging and E1/E2 gates")
    if config.get("e4_enabled") is True and config.get("e3_enabled") is not True:
        errors.append("E4 requires the E3 protected physical-report gate")
    if config.get("environment") == "production" and (
        config.get("commissioning_mode") != "technical_only"
        or any(
            config.get(flag) is not False
            for flag in ["e1_enabled", "e2_enabled", "e3_enabled", "e4_enabled", "pickup_enabled"]
        )
    ):
        errors.append(
            "production currently supports technical commissioning with business disabled"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        if not isinstance(config, dict):
            raise ValueError("expected object")
    except (OSError, ValueError):
        print("BLOCKED/NOT_CONFIGURED: invalid configuration file", file=sys.stderr)
        return 2
    errors = validate(config)
    if errors:
        print("BLOCKED/NOT_CONFIGURED:\n" + "\n".join(errors), file=sys.stderr)
        return 2
    print("Configuration structurally valid; live IAM, budget and staging require verification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
