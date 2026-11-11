"""Execute a trusted main job with short-lived AWS credentials, never logging tokens."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--role",
        choices=["Deploy", "Migrate", "E1Verifier", "E1Acceptance", "MobilePublisher"],
        required=True,
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if (
        os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_REPOSITORY") != "A-PerfectStranger/special-funicular"
    ):
        raise SystemExit("BLOCKED: repository main only")
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise SystemExit("BLOCKED: command required")
    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    url += ("&" if "?" in url else "?") + urlencode({"audience": "sts.amazonaws.com"})
    with urlopen(
        Request(
            url, headers={"Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]}
        ),
        timeout=15,
    ) as response:
        token = json.load(response)["value"]
    env = os.environ.copy()
    for name in [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "AWS_CREDENTIAL_EXPIRATION",
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_ROLE_ARN",
        "AWS_ROLE_SESSION_NAME",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
    ]:
        env.pop(name, None)
    env.update(
        AWS_REGION="us-east-1",
        AWS_DEFAULT_REGION="us-east-1",
        AWS_CONFIG_FILE="/dev/null",
        AWS_SHARED_CREDENTIALS_FILE="/dev/null",
        AWS_EC2_METADATA_DISABLED="true",
    )
    with tempfile.TemporaryDirectory(prefix="retiro-oidc-") as directory:
        path = Path(directory) / "token"
        path.touch(mode=0o600)
        path.write_text(token)
        # Exchange the short-lived GitHub JWT once. Fresh SDK processes later in
        # a long trial must reuse this STS session, not exchange an expired JWT.
        result = subprocess.run(
            [
                "aws",
                "sts",
                "assume-role-with-web-identity",
                "--role-arn",
                f"arn:aws:iam::028364485203:role/retiro-staging-{args.role}",
                "--role-session-name",
                "retiro-github-" + args.role.lower(),
                "--web-identity-token",
                "file://" + str(path),
                "--duration-seconds",
                "3600",
                "--region",
                "us-east-1",
                "--output",
                "json",
                "--no-sign-request",
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            credentials = json.loads(result.stdout)["Credentials"]
            values = {
                "AWS_ACCESS_KEY_ID": credentials["AccessKeyId"],
                "AWS_SECRET_ACCESS_KEY": credentials["SecretAccessKey"],
                "AWS_SESSION_TOKEN": credentials["SessionToken"],
            }
            if result.returncode or not all(isinstance(v, str) and v for v in values.values()):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise SystemExit(
                "BLOCKED: temporary AWS federation failed; command not started"
            ) from None
        env.update(values)
    # The JWT file is gone before any child runs; STS secrets remain in memory.
    return subprocess.call(command, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
