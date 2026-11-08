"""AWS CLI boundary: return structured metadata and only redactable error codes."""

import json
import re
import subprocess
from typing import Any


def aws(*args: str) -> dict[str, Any]:
    result = subprocess.run(
        ["aws", *args, "--region", "us-east-1", "--output", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        code = re.search(r"An error occurred \(([A-Za-z0-9_]+)\)", result.stderr)
        raise RuntimeError(".".join(args[:2]) + ": " + (code[1] if code else "CliRequestFailed"))
    return json.loads(result.stdout) if result.stdout.strip() else {}
