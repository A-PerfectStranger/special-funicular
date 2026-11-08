"""Actual anonymous staging limit/recovery probe; no passwords, tokens or SQL access."""

import argparse
import hashlib
import json
import re
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


def start(client: httpx.Client, origin: str, expected: int) -> None:
    response = client.post(
        origin + "/v1/auth/mobile/start",
        json={
            "code_challenge": secrets.token_urlsafe(32),
            "purpose": "login",
        },
    )
    if response.status_code != expected:
        raise RuntimeError("Unexpected entry-point status")
    if expected == 200:
        result = response.json()
        if (
            not re.fullmatch("[A-Za-z0-9_-]{43}", result.get("state", ""))
            or not re.fullmatch("[A-Za-z0-9_-]{43}", result.get("exchange_key", ""))
            or not result.get("authorization_url", "").startswith(
                "https://retiro-e1-028364485203.auth.us-east-1.amazoncognito.com/"
            )
        ):
            raise RuntimeError("Invalid staging login contract")


def probe(sha: str, digest: str) -> dict[str, Any]:
    if not re.fullmatch("[0-9a-f]{40}", sha) or not re.fullmatch("sha256:[0-9a-f]{64}", digest):
        raise RuntimeError("Approved release identity required")
    config = json.loads(Path("infra/environments/staging.json").read_text())
    if config.get("synthetic_only") is not True or config.get("pickup_enabled") is not False:
        raise RuntimeError("Synthetic staging only")
    origin = config["base_url"]
    if not re.fullmatch(r"https://[a-z0-9-]+\.ecs\.us-east-1\.on\.aws", origin):
        raise RuntimeError("Reviewed staging origin required")
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=True) as client:
        start(client, origin, 200)
        for _ in range(5):
            response = client.post(
                origin + "/v1/auth/mobile/exchange",
                json={
                    "state": secrets.token_urlsafe(32),
                    "exchange_key": secrets.token_urlsafe(32),
                    "code": "synthetic-invalid-code",
                    "code_verifier": secrets.token_urlsafe(32),
                },
            )
            if response.status_code != 401:
                raise RuntimeError("Expected uniform rejection for invalid login")
        blocked_since = time.monotonic()
        start(client, origin, 401)  # A well-formed start would otherwise succeed.
        page = client.get(origin + "/auth/login")
        token = re.search(r'name="csrfmiddlewaretoken"\s+value="([A-Za-z0-9]+)"', page.text)
        if page.status_code != 200 or not token:
            raise RuntimeError("Independent web entry was not available")
        response = client.post(
            origin + "/auth/login",
            data={"csrfmiddlewaretoken": token[1]},
            headers={"Origin": origin, "Referer": origin + "/auth/login"},
        )
        if response.status_code != 302:
            raise RuntimeError("Failure limit incorrectly affected another entry point")
        print(
            "E1 backend limit: five failures blocked a valid start; web entry remains available",
            flush=True,
        )
        # Observe the real server expiry, never modify its clock/rows or offer a test bypass.
        last_denial = 0.0
        for seconds in [*range(60, 900, 60), 890, 905]:
            deadline = blocked_since + seconds
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(1, remaining))
            start(client, origin, 401 if seconds < 900 else 200)
            if seconds < 900:
                last_denial = time.monotonic() - blocked_since
                print("E1 backend limit: still blocked at the scheduled control", flush=True)
    return {
        "passed": True,
        "e1_accepted": False,
        "release_sha": sha,
        "image_digest": digest,
        "checked_at": datetime.now(UTC).isoformat(),
        "consecutive_failures": 5,
        "valid_start_denied_during_block": True,
        "other_entry_point_available": True,
        "valid_start_allowed_after_policy_expiry": True,
        "expected_policy_seconds": 900,
        "last_denial_after_seconds": round(last_denial, 3),
        "allowed_after_seconds": round(time.monotonic() - blocked_since, 3),
        "probe_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": (
            "Sampled actual anonymous staging HTTP limits; "
            "release/TLS origin evidence is supplied by the deployment report"
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--digest", required=True)
    args = parser.parse_args()
    Path("work").mkdir(exist_ok=True)
    try:
        result = probe(args.sha, args.digest)
    except (Exception, KeyboardInterrupt):
        result = {
            "passed": False,
            "e1_accepted": False,
            "error": "limit_probe_failed_or_interrupted",
        }
    Path("work/e1-backend-limit-acceptance.json").write_text(json.dumps(result, indent=2) + "\n")
    print("E1 real backend limits: " + ("PASS" if result["passed"] else "FAIL"))
    raise SystemExit(0 if result["passed"] else 2)
