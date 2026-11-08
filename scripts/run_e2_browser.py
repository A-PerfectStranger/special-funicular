"""Real E2 trial: private fixture setup then shared mobile code, secrets only in stdin/memory."""

import json
import os
import subprocess

from scripts.e2_fixture_control import execute, load


def main() -> int:
    e2, config, environment = load()
    execute("seed")
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
    except Exception:
        print("BLOCKED: E2 trial setup failed; inspect private fixture and approved candidate.")
        raise SystemExit(2) from None
