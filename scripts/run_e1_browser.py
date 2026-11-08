"""Run real synthetic browser/protocol checks; fixture credentials stay in memory/stdin."""

import argparse
import json
import os
import subprocess
from pathlib import Path

import boto3

from scripts.commission_e1 import outputs
from scripts.e1_fixture_data import identifier


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=["basic", "archive-drill"], default="basic")
    arguments = parser.parse_args()
    session = boto3.Session(region_name="us-east-1")
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != "028364485203" or not identity["Arn"].startswith(
        "arn:aws:sts::028364485203:assumed-role/retiro-staging-E1Acceptance/"
    ):
        raise RuntimeError("Isolated synthetic acceptance identity required")
    config = outputs("retiro-staging-e1")
    fixture = json.loads(
        session.client("secretsmanager").get_secret_value(
            SecretId=config["AcceptanceFixtureSecret"]
        )["SecretString"]
    )
    if fixture.get("schema_version") != 1 or fixture.get("roster_ready") is not True:
        raise RuntimeError("Private synthetic fixtures have not been provisioned")
    required = ["e1-system", "e1-a-admin", "e1-a-p1", "e1-b-guard"]
    for name in required:
        user = fixture.get("users", {}).get(name, {})
        if not user.get("mfa_ready") or not user.get("password") or not user.get("totp_seed"):
            raise RuntimeError("Complete MFA synthetic fixture required")
    expected = json.loads(Path("infra/environments/staging.json").read_text())["base_url"]
    if config["WebRedirect"] != expected + "/auth/callback":
        raise RuntimeError("Observed staging callback differs from reviewed environment")
    payload = {
        "scenario": arguments.scenario,
        "expected_scopes": {
            "e1-a-p1": {"role": "PADRE", "school_id": None, "site_id": None},
            "e1-b-guard": {
                "role": "GUARDIA",
                "school_id": identifier("school-b"),
                "site_id": identifier("site-b"),
            },
        },
        "origin": expected,
        "mobile_redirect": config["MobileRedirect"],
        "users": {name: fixture["users"][name] for name in required},
    }
    Path("work").mkdir(exist_ok=True)
    environment = os.environ.copy()
    environment["NODE_USE_ENV_PROXY"] = "1"
    # No fixture file, command-line secrets, Playwright debug, traces or screenshots.
    environment.pop("DEBUG", None)
    environment.pop("PWDEBUG", None)
    environment.pop("NODE_DEBUG", None)
    return subprocess.run(
        ["node", "--experimental-strip-types", "tests/staging/e1-browser.mjs"],
        input=json.dumps(payload).encode(),
        env=environment,
        check=False,
    ).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("BLOCKED: private synthetic browser setup failed; inspect AWS privately")
        raise SystemExit(2) from None
