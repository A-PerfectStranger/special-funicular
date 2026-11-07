"""Read-only E0 data-plane checks (RFS09/13/14, CA-S09/13/14).

This is one part of staging acceptance, not a deployment or an IAM/budget check.
Never records response bodies, credentials, cookies, or an unverified release SHA.
"""

import argparse
import json
import ssl
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener, getproxies

MAX_BODY = 16384
PROBES: tuple[tuple[str, str, tuple[int, ...], dict[str, Any] | None], ...] = (
    ("GET", "/health/live", (200,), {"status": "ok"}),
    ("GET", "/health/ready", (200,), {"status": "ready"}),
    ("GET", "/v1/capabilities", (200,), {"api_version": "v1", "pickup_enabled": False}),
    ("GET", "/admin/", (404,), None),
    ("GET", "/v1/guard/confirm-pickup", (404,), None),
    ("GET", "/v1/me/students", (404,), None),
    # CSRF rejects anonymous writes before the method decorator in a live Django server.
    ("POST", "/health/live", (403, 405), None),
    ("POST", "/v1/capabilities", (403, 405), None),
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def validate_origin(base_url: str) -> str:
    """Accept only an HTTPS origin; do not send probes to credentials or URL paths."""
    url = urlsplit(base_url)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
        or any(c.isspace() or ord(c) < 32 for c in base_url)
    ):
        raise ValueError("An HTTPS origin without credentials, path, query or fragment is required")
    # Accessing port validates malformed/out-of-range ports before making requests.
    _ = url.port
    return base_url.rstrip("/")


def verify(base_url: str, *, ca_file: str | None = None) -> dict[str, Any]:
    origin = validate_origin(base_url)
    context = ssl.create_default_context(cafile=ca_file)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    opener = build_opener(HTTPSHandler(context=context), NoRedirect())
    checks: list[dict[str, Any]] = []
    for method, path, expected_statuses, expected_json in PROBES:
        result: dict[str, Any] = {"method": method, "path": path, "passed": False}
        response = None
        try:
            request = Request(origin + path, method=method, headers={"Accept": "application/json"})
            try:
                response = opener.open(request, timeout=10)
            except HTTPError as exc:
                response = exc
            with response:
                body = response.read(MAX_BODY + 1)
                status = response.code
                safe_headers = (
                    response.headers.get("Cache-Control") == "no-store"
                    and response.headers.get("X-Content-Type-Options") == "nosniff"
                    and "frame-ancestors 'none'"
                    in response.headers.get("Content-Security-Policy", "")
                    and "max-age=" in response.headers.get("Strict-Transport-Security", "")
                    and not response.headers.get_all("Set-Cookie")
                )
                content_matches = len(body) <= MAX_BODY
                if expected_json is not None:
                    content_matches = (
                        content_matches
                        and response.headers.get_content_type() == "application/json"
                        and json.dumps(json.loads(body), sort_keys=True)
                        == json.dumps(expected_json, sort_keys=True)
                    )
                result.update(
                    status=status,
                    passed=status in expected_statuses and safe_headers and content_matches,
                )
        except (OSError, URLError, ValueError):
            # Neither exception text nor remote content belongs in the report.
            result["error"] = "connection_tls_or_response_failed"
        checks.append(result)
    return {
        "scope": "E0 public data-plane only; IAM, budget and release provenance not verified",
        "checked_at": datetime.now(UTC).isoformat(),
        "origin": origin,
        "tls": "TLSv1.3 with certificate and hostname validation",
        "https_proxy_configured": bool(getproxies().get("https")),
        "tls_scope": "client to TLS peer; an intercepting proxy prevents origin TLS attestation",
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify(args.base_url)
    except (OSError, ValueError):
        print("BLOCKED/NOT_CONFIGURED: valid HTTPS origin and CA trust required", file=sys.stderr)
        return 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print("E0 data-plane checks: " + ("PASS" if report["passed"] else "FAIL"))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
