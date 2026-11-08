"""Real E2 trial: private fixture setup then shared mobile code, secrets only in stdin/memory."""

import json
import os
import subprocess

from scripts.e2_fixture_control import (
    SELECTION,
    CohortUsed,
    available_cohorts,
    execute,
    load,
    read_context,
    release_sha,
)


class CohortPoolExhausted(RuntimeError):
    pass


def main() -> int:
    state, _, _ = read_context()
    sha = release_sha()
    cohorts = available_cohorts(state, sha)
    SELECTION.parent.mkdir(exist_ok=True)
    for cohort in cohorts:
        # Only public correlation metadata is persisted, never credentials or invitation bytes.
        SELECTION.write_text(json.dumps({"sha": sha, "trial_id": cohort["trial_id"]}))
        try:
            execute("seed")
            break
        except CohortUsed:
            continue
    else:
        raise CohortPoolExhausted("Synthetic cohort pool exhausted; operator refill required")
    execute("bulk-drill")
    e2, config, environment = load()
    payload = {**e2, "origin": environment["base_url"], "mobile_redirect": config["MobileRedirect"]}
    child_env = os.environ.copy()
    child_env["NODE_USE_ENV_PROXY"] = "1"
    for name in ["DEBUG", "PWDEBUG", "NODE_DEBUG"]:
        child_env.pop(name, None)
    return subprocess.run(
        ["node", "--experimental-strip-types", "tests/staging/e2-browser.mjs"],
        input=json.dumps(payload).encode(),
        env=child_env,
        check=False,
    ).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CohortPoolExhausted:
        print("BLOCKED: E2_COHORT_POOL_EXHAUSTED; operator refill required.")
        raise SystemExit(2) from None
    except Exception:
        print("BLOCKED: E2 trial setup failed; inspect private fixture and approved candidate.")
        raise SystemExit(2) from None
