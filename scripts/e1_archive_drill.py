"""Coordinate isolated Deploy/Acceptance children, always attempting archive recovery."""

import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from scripts.e1_archive_control import STATE

DENIAL = Path("work/e1-archive-denial-observed.json")
RESUMED = Path("work/e1-archive-resumed")


def command(role: str, module: str, *arguments: str) -> list[str]:
    return [
        "python3",
        "scripts/aws_oidc.py",
        "--role",
        role,
        "--",
        "python3",
        "-m",
        module,
        *arguments,
    ]


def drill(sha: str, digest: str) -> int:
    Path("work").mkdir(exist_ok=True)
    for path in [STATE, DENIAL, RESUMED]:
        path.unlink(missing_ok=True)  # Only coordination metadata, never evidence or credentials.
    browser: subprocess.Popen[bytes] | None = None
    recovered = False
    try:
        subprocess.run(
            command(
                "Deploy", "scripts.e1_archive_control", "pause", "--sha", sha, "--digest", digest
            ),
            check=True,
        )
        browser = subprocess.Popen(
            command("E1Acceptance", "scripts.run_e1_browser", "--scenario", "archive-drill"),
            start_new_session=True,
        )
        deadline = time.monotonic() + 180
        while not DENIAL.exists():
            if browser.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("Archive denial was not observed")
            time.sleep(0.5)
        subprocess.run(
            command(
                "Deploy", "scripts.e1_archive_control", "resume", "--sha", sha, "--digest", digest
            ),
            check=True,
        )
        recovered = True
        RESUMED.write_text("verified archive running\n")
        return browser.wait(timeout=180)
    except Exception:
        return 2
    finally:
        if STATE.exists() and not recovered:
            try:
                subprocess.run(
                    command(
                        "Deploy",
                        "scripts.e1_archive_control",
                        "resume",
                        "--sha",
                        sha,
                        "--digest",
                        digest,
                    ),
                    check=True,
                )
                recovered = True
            except Exception:
                print("BLOCKED: archive recovery failed; E1 acceptance prohibited")
        if browser is not None and browser.poll() is None:
            os.killpg(browser.pid, signal.SIGTERM)
            try:
                browser.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(browser.pid, signal.SIGKILL)
                browser.wait()
        Path("work/e1-archive-recovery.json").write_text(
            json.dumps({"archive_recovered": recovered, "e1_accepted": False}) + "\n"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--digest", required=True)
    options = parser.parse_args()
    raise SystemExit(drill(options.sha, options.digest))
