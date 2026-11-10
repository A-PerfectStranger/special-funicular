"""An expired gateway can be recreated without enabling identity or accepting a release."""

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import deploy_staging as module

SHA, DIGEST = "f" * 40, "sha256:" + "a" * 64
ORIGIN = "https://new.ecs.us-east-1.on.aws"


@pytest.mark.parametrize("mode", ["missing", "wrong_callback", "ready"])
def test_bootstrap_remains_stateless_until_owned_origin_and_callback_match(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("infra/environments").mkdir(parents=True)
    Path("infra/environments/staging.json").write_text(
        json.dumps(
            {
                "synthetic_only": True,
                "pickup_enabled": False,
                "e1_enabled": True,
                "e2_enabled": True,
                "e3_enabled": True,
                "base_url": "https://retired.ecs.us-east-1.on.aws",
            }
        )
    )
    output = tmp_path / "job-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(
        "sys.argv", ["deploy", "--mode", "deploy", "--sha", SHA, "--digest", DIGEST]
    )
    monkeypatch.setattr(module.subprocess, "check_output", lambda *a, **kw: SHA)
    active = {
        "status": {"statusCode": "ACTIVE"},
        "activeConfigurations": [{"ingressPaths": [{"endpoint": ORIGIN[8:]}]}],
    }
    monkeypatch.setattr(module, "describe_gateway", lambda: None if mode == "missing" else active)
    archives: list[str] = []
    monkeypatch.setattr(module, "start_archive", lambda *a: archives.append("started") or "archive")
    monkeypatch.setattr(module, "runtime_digests", lambda *a: {DIGEST})
    monkeypatch.setattr(module, "register", lambda *a: "definition")
    monkeypatch.setattr(module, "task_definition", lambda *a: {"stateless": True})
    monkeypatch.setattr(module, "api_definition", lambda *a, **kw: {"identity": True})
    monkeypatch.setattr(module, "archive_definition", lambda *a: {})
    monkeypatch.setattr(module, "deploy_express", lambda *a: ("service", "previous", "expiry"))
    monkeypatch.setattr(module, "candidate_running", lambda *a: True)
    monkeypatch.setattr(module, "verify_ingress", lambda *a: {})

    def verify(origin: str, *, e3_enabled: bool) -> dict[str, Any]:
        assert origin == ORIGIN
        assert e3_enabled is (mode == "ready")
        return {"passed": True}

    monkeypatch.setattr(module, "verify", verify)

    def aws(*args: str) -> dict[str, Any]:
        if args[:2] == ("sts", "get-caller-identity"):
            return {
                "Account": "028364485203",
                "Arn": "arn:aws:sts::028364485203:assumed-role/retiro-staging-Deploy/ci",
            }
        if args[:2] == ("cloudformation", "describe-stacks"):
            values = {
                "Cluster": "cluster",
                "ImageRepository": "repository",
                "AppSecurityGroup": "group",
            }
            if args[-1] == "retiro-staging-e1":
                values = {
                    "WebRedirect": (
                        ORIGIN if mode == "ready" else "https://retired.ecs.us-east-1.on.aws"
                    )
                    + "/auth/callback"
                }
            return {
                "Stacks": [
                    {"Outputs": [{"OutputKey": k, "OutputValue": v} for k, v in values.items()]}
                ]
            }
        if args[:2] == ("ecs", "describe-express-gateway-service"):
            return {"service": active}
        if args[:2] == ("ecs", "list-tasks"):
            return {"taskArns": ["task"]}
        if args[:2] == ("ecs", "describe-tasks"):
            return {
                "tasks": [
                    {"taskDefinitionArn": "definition", "containers": [{"imageDigest": DIGEST}]}
                ]
            }
        raise AssertionError("Unexpected AWS mutation or rollback")

    monkeypatch.setattr(module, "aws", aws)
    assert module.main() == (0 if mode == "ready" else 2)
    report = json.loads(Path("work/staging-deployment.json").read_text())
    assert report["origin"] == ORIGIN and report["runtime_digest_verified"] is True
    assert report["passed"] is (mode == "ready")
    assert report["e1_identity_enabled"] is report["e3_pickup_enabled"] is (mode == "ready")
    assert report["origin_sync_required"] is (mode != "ready")
    assert len(archives) == (1 if mode == "ready" else 0)
    if mode == "ready":
        assert output.read_text() == "origin=" + ORIGIN + "\n"
    else:
        assert not output.exists()
