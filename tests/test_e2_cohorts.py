"""Fresh invitation cohorts permit repeatable gates without widening Cognito IAM."""

import copy
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from scripts import e2_fixture_control, run_e2_browser
from scripts.e1_release import api_definition
from scripts.e2_fixture_control import CohortUsed, available_cohorts
from scripts.provision_e2_fixtures import cohort
from tests.test_e1_release import configuration


def prepared(sha: str = "a" * 40) -> dict[str, Any]:
    value = cohort(sha, str(uuid.uuid4()))
    for name, user in value["users"].items():
        user.update(sub=str(uuid.uuid4()), totp_seed="synthetic-seed-" + name, mfa_ready=True)
    return value


def test_preapproved_pool_is_independent_of_release_but_single_trial_is_pinned() -> None:
    first, second = prepared(), prepared()
    candidates = available_cohorts({"e2_pool": [first, second]}, "b" * 40)
    assert [c["trial_id"] for c in candidates] == [first["trial_id"], second["trial_id"]]
    assert all(c["release_sha"] == "b" * 40 and c["prepared_sha"] == "a" * 40 for c in candidates)
    assert first["release_sha"] == "a" * 40  # No vault mutation by CI.
    with pytest.raises(RuntimeError):
        available_cohorts({"e2": first}, "b" * 40)
    assert available_cohorts({"e2": first}, "a" * 40)[0]["trial_id"] == first["trial_id"]


@pytest.mark.parametrize(
    "damage", ["empty", "duplicate", "incomplete", "real_contact", "oversized"]
)
def test_invalid_pool_never_downgrades_to_another_fixture(damage: str) -> None:
    first = prepared()
    values = [first]
    if damage == "empty":
        values = []
    if damage == "duplicate":
        values = [first, copy.deepcopy(first)]
    if damage == "incomplete":
        next(iter(first["users"].values()))["mfa_ready"] = False
    if damage == "real_contact":
        next(iter(first["users"].values()))["contact"] = "someone@example.com"
    if damage == "oversized":
        values = [prepared() for _ in range(9)]
    with pytest.raises(RuntimeError):
        available_cohorts({"e2_pool": values}, "a" * 40)


def test_runner_skips_only_consumed_cohorts_and_persists_no_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = prepared(), prepared()
    monkeypatch.setenv("E2_RELEASE_SHA", "b" * 40)
    path = tmp_path / "selected.json"
    monkeypatch.setattr(run_e2_browser, "SELECTION", path)
    monkeypatch.setattr(
        run_e2_browser, "read_context", lambda: ({"e2_pool": [first, second]}, {}, {})
    )
    selected = []

    def execute(action: str) -> None:
        if action == "bulk-drill":
            return
        value = json.loads(path.read_text())
        selected.append(value)
        if len(selected) == 1:
            raise CohortUsed()

    monkeypatch.setattr(run_e2_browser, "execute", execute)
    monkeypatch.setattr(
        run_e2_browser,
        "load",
        lambda: (
            second,
            {"MobileRedirect": "synthetic://auth/callback"},
            {"base_url": "https://synthetic.invalid"},
        ),
    )
    captured = []

    def run(*args: Any, **kwargs: Any) -> Any:
        captured.append(kwargs["input"])

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(run_e2_browser.subprocess, "run", run)
    assert run_e2_browser.main() == 0
    assert [v["trial_id"] for v in selected] == [first["trial_id"], second["trial_id"]]
    assert set(json.loads(path.read_text())) == {"sha", "trial_id"}
    assert len(captured) == 1


def test_runner_never_skips_infrastructure_failure_or_reuses_exhausted_pool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = prepared()
    monkeypatch.setenv("E2_RELEASE_SHA", "a" * 40)
    monkeypatch.setattr(run_e2_browser, "SELECTION", tmp_path / "selected.json")
    monkeypatch.setattr(run_e2_browser, "read_context", lambda: ({"e2_pool": [first]}, {}, {}))

    def failure(action: str) -> None:
        raise RuntimeError("Infrastructure failure")

    monkeypatch.setattr(run_e2_browser, "execute", failure)
    with pytest.raises(RuntimeError, match="Infrastructure"):
        run_e2_browser.main()

    def consumed(action: str) -> None:
        raise CohortUsed()

    monkeypatch.setattr(run_e2_browser, "execute", consumed)
    with pytest.raises(RuntimeError, match="exhausted"):
        run_e2_browser.main()


def test_private_task_contains_hashes_not_fixture_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = prepared()
    base, config = configuration()
    config.update(
        ImporterPassword="synthetic-import-arn", FixtureExecutionArn="synthetic-fixture-role"
    )
    digest = "sha256:" + "b" * 64
    image = "028364485203.dkr.ecr.us-east-1.amazonaws.com/retiro-staging/backend@" + digest
    previous = api_definition(base, config, image, "a" * 40, enable_family=True)
    environment = {
        "cluster": "synthetic",
        "subnets": ["synthetic"],
        "security_groups": ["synthetic"],
    }
    monkeypatch.setenv("E2_RELEASE_DIGEST", digest)
    monkeypatch.setattr(e2_fixture_control, "load", lambda: (value, config, environment))
    registered = []
    monkeypatch.setattr(
        e2_fixture_control,
        "register",
        lambda definition: registered.append(definition) or "synthetic-definition",
    )

    def aws(*args: str) -> dict[str, Any]:
        if args[1] == "describe-task-definition":
            return {"taskDefinition": previous}
        if args[1] == "run-task":
            return {"tasks": [{"taskArn": "synthetic-task"}]}
        if args[1] == "describe-tasks":
            return {"tasks": [{"containers": [{"exitCode": 42}]}]}
        return {}

    monkeypatch.setattr(e2_fixture_control, "aws", aws)
    with pytest.raises(CohortUsed):
        e2_fixture_control.execute("seed")
    raw = json.dumps(registered[0])
    for user in value["users"].values():
        assert (
            user["password"] not in raw
            and user["totp_seed"] not in raw
            and user["invitation"] not in raw
        )
    assert registered[0]["executionRoleArn"] == config["FixtureExecutionArn"]
    assert "taskRoleArn" not in registered[0]
    container = registered[0]["containerDefinitions"][0]
    assert container["secrets"] == [{"name": "PGPASSWORD", "valueFrom": config["ImporterPassword"]}]


def test_operator_prepares_a_bounded_pool_without_overwriting_e1_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    from unittest.mock import Mock

    from scripts import provision_e2_fixtures as tool

    base_id = str(uuid.uuid4())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "provision_e2",
            "--sha",
            "a" * 40,
            "--trial-id",
            base_id,
            "--pool-size",
            "3",
            "--synthetic-only",
        ],
    )
    clients = {name: Mock() for name in ["sts", "cognito-idp", "secretsmanager"]}
    clients["sts"].get_caller_identity.return_value = {
        "Account": "028364485203",
        "Arn": "arn:aws:iam::028364485203:user/synthetic-operator",
    }
    cognito = clients["cognito-idp"]
    vault = clients["secretsmanager"]
    cognito.describe_user_pool_client.return_value = {
        "UserPoolClient": {"AllowedOAuthScopes": ["openid", "email"]}
    }
    cognito.create_user_pool_client.return_value = {
        "UserPoolClient": {"ClientId": "temporary-enrollment"}
    }
    vault.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {"schema_version": 1, "roster_ready": True, "users": {"original-e1": "unchanged"}}
        )
    }
    session = Mock()
    session.client.side_effect = lambda name: clients[name]
    monkeypatch.setattr(tool.boto3, "Session", lambda **kwargs: session)
    monkeypatch.setattr(
        tool,
        "outputs",
        lambda name: {
            "PoolId": "synthetic-pool",
            "AcceptanceFixtureSecret": "synthetic-vault",
            "WebClientId": "web",
            "MobileClientId": "mobile",
        },
    )

    def enroll(*args: Any) -> None:
        record = args[-1]
        record.update(sub=str(uuid.uuid4()), totp_seed="synthetic-seed")

    monkeypatch.setattr(tool, "enroll", enroll)
    monkeypatch.setattr(tool, "finish_enrollment", lambda *args: args[-1].update(mfa_ready=True))
    tool.main()
    state = json.loads(vault.put_secret_value.call_args.kwargs["SecretString"])
    assert state["users"] == {"original-e1": "unchanged"}
    assert len(state["e2_pool"]) == 3
    assert all(all(u["mfa_ready"] for u in c["users"].values()) for c in state["e2_pool"])
    assert len({c["trial_id"] for c in state["e2_pool"]}) == 3
    cognito.delete_user_pool_client.assert_called_once_with(
        UserPoolId="synthetic-pool", ClientId="temporary-enrollment"
    )
