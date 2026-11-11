"""Materialize Android's public Firebase configuration from private CI settings.

FCM service-account private keys belong to Expo credentials, never this file.
"""

import json
import os
from pathlib import Path
from typing import Any


def validate(data: dict[str, Any], package: str) -> None:
    project = data.get("project_info", {})
    if (
        project.get("project_id") != "retiro-seguro-2ab03"
        or not str(project.get("project_number", "")).isdecimal()
        or "private_key" in data
        or data.get("type") == "service_account"
        or package not in {"org.retiroseguro.staging", "org.retiroseguro.app"}
    ):
        raise ValueError("Invalid Firebase project configuration")
    clients = data.get("client", [])
    if not isinstance(clients, list):
        raise ValueError("Firebase clients missing")
    selected = next(
        (
            value
            for value in clients
            if isinstance(value, dict)
            and value.get("client_info", {}).get("android_client_info", {}).get("package_name")
            == package
        ),
        None,
    )
    if not selected:
        raise ValueError("Firebase Android package mismatch")
    app_id = selected.get("client_info", {}).get("mobilesdk_app_id", "")
    if not isinstance(app_id, str) or not app_id.startswith(
        f"1:{project['project_number']}:android:"
    ):
        raise ValueError("Firebase Android app identifier mismatch")
    if not any(
        isinstance(value, dict)
        and isinstance(value.get("current_key"), str)
        and value["current_key"]
        for value in selected.get("api_key", [])
    ):
        raise ValueError("Firebase Android registration configuration missing")


def main() -> None:
    raw = os.environ.get("ANDROID_GOOGLE_SERVICES_JSON", "")
    package = os.environ.get("ANDROID_PACKAGE_ID", "")
    if not 1 <= len(raw) <= 65536:
        raise ValueError("Missing Firebase Android configuration")
    data = json.loads(raw)
    validate(data, package)
    output = Path("work/mobile-push/google-services.json").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(data, stream)
    if os.environ.get("GITHUB_ENV"):
        with Path(os.environ["GITHUB_ENV"]).open("a") as stream:
            stream.write(f"ANDROID_GOOGLE_SERVICES_FILE={output}\n")
    print("Firebase Android configuration verified; no credentials printed")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "BLOCKED: missing or incompatible Android Firebase configuration"
        ) from None
