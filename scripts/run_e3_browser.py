"""Real E3 protocol acceptance; reuse this job's E2 cohort without resetting history."""

import json
import os
import subprocess

from scripts.e2_fixture_control import execute, load, read_context
from scripts.e3_fixture_data import fixture_batch


def main() -> int:
    execute("e3-seed")
    cohort, config, environment = load()
    state, _, _ = read_context()
    primary = {name: value for name, value in cohort["users"].items() if value["principal"]}
    payload = {
        "trial_id": cohort["trial_id"],
        "users": {
            **primary,
            **{name: state["users"][name] for name in ["e1-a-guard", "e1-b-guard"]},
        },
        "origin": environment["base_url"],
        "mobile_redirect": config["MobileRedirect"],
        "batch": fixture_batch(cohort),
    }
    child_env = os.environ.copy()
    child_env["NODE_USE_ENV_PROXY"] = "1"
    for name in ["DEBUG", "PWDEBUG", "NODE_DEBUG"]:
        child_env.pop(name, None)
    return subprocess.run(
        ["node", "--experimental-strip-types", "tests/staging/e3-browser.mjs"],
        input=json.dumps(payload).encode(),
        env=child_env,
        check=False,
    ).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("BLOCKED: E3 synthetic setup failed; no reset or partial acceptance.")
        raise SystemExit(2) from None
