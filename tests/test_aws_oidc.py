"""Long gates reuse temporary STS credentials without retaining an expiring GitHub JWT."""

import io
import json
import subprocess
from pathlib import Path
from typing import Any

import boto3
import pytest

from scripts import aws_oidc


def setup(
    monkeypatch: pytest.MonkeyPatch, role: str = "E1Acceptance", environment: str = "staging"
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["aws_oidc", "--environment", environment, "--role", role, "--", "synthetic-child"],
    )
    for name, value in {
        "GITHUB_REPOSITORY": "A-PerfectStranger/special-funicular",
        "GITHUB_REF": "refs/heads/main",
        "ACTIONS_ID_TOKEN_REQUEST_URL": "https://github.invalid/token",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "private-request-token",
        "AWS_ACCESS_KEY_ID": "old-static-key",
        "AWS_SECRET_ACCESS_KEY": "old-static-secret",
        "AWS_SESSION_TOKEN": "old-session",
        "AWS_SECURITY_TOKEN": "old-legacy-session",
        "AWS_CREDENTIAL_EXPIRATION": "2000-01-01T00:00:00Z",
        "AWS_ROLE_ARN": "arn:aws:iam::123456789012:role/unrelated",
        "AWS_WEB_IDENTITY_TOKEN_FILE": "/old/token",
        "AWS_ROLE_SESSION_NAME": "old-session-name",
        "AWS_PROFILE": "old-profile",
        "AWS_DEFAULT_PROFILE": "old-default-profile",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        aws_oidc, "urlopen", lambda *a, **kw: io.BytesIO(b'{"value":"private-github-jwt"}')
    )


@pytest.mark.parametrize(
    "role,environment",
    [
        (role, "staging")
        for role in ["Deploy", "Migrate", "E1Verifier", "E1Acceptance", "MobilePublisher"]
    ]
    + [("Deploy", "production"), ("Migrate", "production")],
)
def test_federates_once_and_fresh_sdk_children_work_without_the_jwt_file(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], role: str, environment: str
) -> None:
    setup(monkeypatch, role, environment)
    token_paths = []
    credentials = {
        "AccessKeyId": "temporary-key",
        "SecretAccessKey": "temporary-secret",
        "SessionToken": "temporary-session",
    }

    def exchange(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert args[:3] == ["aws", "sts", "assume-role-with-web-identity"]
        assert args[args.index("--role-arn") + 1] == (
            f"arn:aws:iam::028364485203:role/retiro-{environment}-" + role
        )
        assert args[args.index("--duration-seconds") + 1] == "3600"
        assert "--no-sign-request" in args
        assert kwargs["capture_output"] is True
        assert not any(
            k in kwargs["env"]
            for k in [
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN",
                "AWS_ROLE_ARN",
                "AWS_WEB_IDENTITY_TOKEN_FILE",
                "AWS_ROLE_SESSION_NAME",
                "AWS_PROFILE",
                "AWS_DEFAULT_PROFILE",
            ]
        )
        path = Path(args[args.index("--web-identity-token") + 1].removeprefix("file://"))
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.read_text() == "private-github-jwt"
        assert "private-github-jwt" not in " ".join(args)
        token_paths.append(path)
        return subprocess.CompletedProcess(args, 0, json.dumps({"Credentials": credentials}), "")

    def child(args: list[str], *, env: dict[str, str]) -> int:
        assert args == ["synthetic-child"]
        assert len(token_paths) == 1 and not token_paths[0].exists()
        assert env["AWS_ACCESS_KEY_ID"] == credentials["AccessKeyId"]
        assert env["AWS_SECRET_ACCESS_KEY"] == credentials["SecretAccessKey"]
        assert env["AWS_SESSION_TOKEN"] == credentials["SessionToken"]
        assert "AWS_WEB_IDENTITY_TOKEN_FILE" not in env and "AWS_ROLE_ARN" not in env
        assert "private-github-jwt" not in json.dumps(env)
        # Fresh boto3 sessions reproduce the private controls. They must use the
        # STS session even after the original JWT file is unavailable/expired.
        with monkeypatch.context() as context:
            for name in list(__import__("os").environ):
                if name.startswith("AWS_"):
                    context.delenv(name)
            for name, value in env.items():
                context.setenv(name, value)
            for _ in range(2):
                actual = boto3.Session().get_credentials()
                assert actual is not None and actual.method == "env"
                assert actual.get_frozen_credentials().token == credentials["SessionToken"]
        return 17

    monkeypatch.setattr(aws_oidc.subprocess, "run", exchange)
    monkeypatch.setattr(aws_oidc.subprocess, "call", child)
    assert aws_oidc.main() == 17
    assert len(token_paths) == 1
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("role", ["E1Verifier", "E1Acceptance", "MobilePublisher"])
def test_production_rejects_uncommissioned_federation_roles(
    role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup(monkeypatch, role, "production")
    monkeypatch.setattr(aws_oidc, "urlopen", lambda *a, **kw: pytest.fail("must not federate"))
    with pytest.raises(SystemExit, match="production accepts"):
        aws_oidc.main()


@pytest.mark.parametrize("ref", ["refs/heads/feature", "refs/pull/1/merge"])
def test_untrusted_ref_cannot_request_identity(monkeypatch: pytest.MonkeyPatch, ref: str) -> None:
    setup(monkeypatch)
    monkeypatch.setenv("GITHUB_REF", ref)
    monkeypatch.setattr(aws_oidc, "urlopen", lambda *a, **kw: pytest.fail("must not federate"))
    with pytest.raises(SystemExit, match="main only"):
        aws_oidc.main()


@pytest.mark.parametrize(
    "payload,code",
    [
        ("private-malformed-response", 0),
        ('{"Credentials":{}}', 0),
        ('{"Credentials":{"AccessKeyId":1,"SecretAccessKey":"x","SessionToken":"y"}}', 0),
        ('{"Credentials":{"AccessKeyId":"x","SecretAccessKey":"y","SessionToken":"z"}}', 1),
    ],
)
def test_failed_federation_blocks_child_and_redacts_remote_response(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], payload: str, code: int
) -> None:
    setup(monkeypatch)
    monkeypatch.setattr(
        aws_oidc.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess([], code, payload, "private-remote-error"),
    )
    monkeypatch.setattr(
        aws_oidc.subprocess, "call", lambda *a, **kw: pytest.fail("child must not run")
    )
    with pytest.raises(SystemExit) as error:
        aws_oidc.main()
    published = str(error.value) + str(capsys.readouterr())
    assert "federation failed" in published
    for secret in [payload, "private-remote-error", "private-github-jwt", "old-static-key"]:
        assert secret not in published
