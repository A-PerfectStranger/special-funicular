"""E2 commissioning is private; CD never enables E2 as a side effect of E1."""

import json
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml

from scripts.e1_release import api_definition
from scripts.provision_e2_fixtures import cohort, enroll, finish_enrollment
from tests.test_e1_release import configuration


def test_e2_gate_is_explicit_and_never_adds_private_import_credentials_to_api() -> None:
    base, config = configuration()
    for enabled in [False, True]:
        definition = api_definition(
            base, config, "image@sha256:" + "a" * 64, "b" * 40, enable_family=enabled
        )
        container = definition["containerDefinitions"][0]
        env = {entry["name"]: entry["value"] for entry in container["environment"]}
        assert env["E2_FAMILY_ENABLED"] == str(enabled).lower()
        assert not any("import" in item["valueFrom"].lower() for item in container["secrets"])
    standard = yaml.safe_load(Path(".github/workflows/cd.yml").read_text())
    assert "--e2-trial" not in json.dumps(standard)
    trial = yaml.safe_load(Path(".github/workflows/e2-trial.yml").read_text())
    assert trial["concurrency"] == standard["concurrency"]
    assert trial["jobs"]["family"]["needs"] == ["publish", "acceptance"]
    shared = yaml.safe_load(Path(".github/workflows/e2-checks.yml").read_text())
    assert "E1Verifier" in json.dumps(shared["jobs"]["family"])
    assert standard["jobs"]["e2-acceptance"]["uses"] == "./.github/workflows/e2-checks.yml"
    assert "e2-acceptance" in standard["jobs"]["production"]["needs"]
    assert "needs.e2-acceptance.result == 'success'" in standard["jobs"]["production"]["if"]


def test_synthetic_cohort_has_no_real_contacts_and_finite_policies() -> None:
    first = cohort("a" * 40, str(uuid.uuid4()))
    second = cohort("a" * 40, str(uuid.uuid4()))
    assert set(first["users"]).isdisjoint(second["users"])
    assert {u["principal"] for u in first["users"].values()} == {True, False}
    assert all(
        u["contact"].endswith("@synthetic.invalid") and len(u["invitation"]) == 43
        for u in first["users"].values()
    )
    assert len(first["batch"]["students"][0]["windows"]) == 7


def confirmed_user() -> dict[str, Any]:
    return {
        "UserStatus": "CONFIRMED",
        "UserAttributes": [
            {"Name": "sub", "Value": "synthetic-sub"},
            {"Name": "email", "Value": "synthetic@synthetic.invalid"},
            {"Name": "email_verified", "Value": "true"},
        ],
    }


def test_interrupted_password_checkpoint_does_not_reassign_a_confirmed_password() -> None:
    cognito = Mock()
    cognito.admin_get_user.return_value = confirmed_user()
    cognito.admin_initiate_auth.return_value = {
        "ChallengeName": "SOFTWARE_TOKEN_MFA",
        "Session": "synthetic-session",
    }
    record = {
        "password": "synthetic password only",
        "sub": "synthetic-sub",
        "contact": "synthetic@synthetic.invalid",
        "totp_seed": "JBSWY3DPEHPK3PXP",
    }
    enroll(cognito, "pool", "client", "synthetic", record)
    cognito.admin_set_user_password.assert_not_called()
    cognito.admin_respond_to_auth_challenge.return_value = {
        "AuthenticationResult": {"AccessToken": "synthetic-unused"}
    }
    finish_enrollment(cognito, "pool", "client", "synthetic", record)
    assert record["mfa_ready"]


def test_existing_provider_contact_must_match_and_cannot_be_silently_changed() -> None:
    cognito = Mock()
    cognito.admin_get_user.return_value = confirmed_user()
    with pytest.raises(RuntimeError, match="contact changed"):
        enroll(
            cognito,
            "pool",
            "client",
            "synthetic",
            {"sub": "synthetic-sub", "contact": "other@synthetic.invalid"},
        )
    cognito.admin_set_user_password.assert_not_called()
    cognito.admin_initiate_auth.assert_not_called()
