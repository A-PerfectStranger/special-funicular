"""Recovery must stop before mutation if MFA is absent; unrelated errors prove no lockout."""

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from scripts.e1_cognito_controls import exercise, locked


def test_recovery_does_not_change_a_password_without_a_fresh_totp_challenge() -> None:
    provider, vault = MagicMock(), MagicMock()
    subject = str(uuid.uuid4())
    provider.get_user_pool_mfa_config.return_value = {
        "MfaConfiguration": "ON",
        "SoftwareTokenMfaConfiguration": {"Enabled": True},
    }
    provider.create_user_pool_client.return_value = {"UserPoolClient": {"ClientId": "private-test"}}
    provider.admin_get_user.return_value = {"UserAttributes": [{"Name": "sub", "Value": subject}]}
    provider.admin_initiate_auth.return_value = {"AuthenticationResult": {"IdToken": "synthetic"}}
    with pytest.raises(RuntimeError, match="TOTP challenge was not required"):
        exercise(
            provider,
            vault,
            {"PoolId": "synthetic"},
            {"users": {"e1-a-p1": {"sub": subject, "mfa_ready": True, "password": "synthetic"}}},
        )
    provider.admin_set_user_password.assert_not_called()
    vault.put_secret_value.assert_not_called()
    provider.delete_user_pool_client.assert_called_once()


@pytest.mark.parametrize(
    "code,message,expected",
    [
        ("NotAuthorizedException", "Password attempts exceeded", True),
        ("NotAuthorizedException", "Incorrect username or password", False),
        ("ThrottlingException", "Password attempts exceeded", False),
    ],
)
def test_only_explicit_native_lockout_counts(code: str, message: str, expected: bool) -> None:
    assert (
        locked(ClientError({"Error": {"Code": code, "Message": message}}, "AdminInitiateAuth"))
        is expected
    )


def test_interrupted_recovery_finishes_vault_checkpoint_without_replacing_active_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, vault = MagicMock(), MagicMock()
    subject = str(uuid.uuid4())
    provider.get_user_pool_mfa_config.return_value = {
        "MfaConfiguration": "ON",
        "SoftwareTokenMfaConfiguration": {"Enabled": True},
    }
    provider.create_user_pool_client.return_value = {"UserPoolClient": {"ClientId": "private-test"}}

    def get_user(**values: str) -> dict[str, object]:
        if values["Username"] == "e1-b-s2":
            raise RuntimeError("stop before native probe")
        return {"UserAttributes": [{"Name": "sub", "Value": subject}]}

    def authenticate(**values: Any) -> dict[str, str]:
        if values["AuthParameters"]["PASSWORD"] == "old-synthetic":
            raise ClientError({"Error": {"Code": "NotAuthorizedException"}}, "AdminInitiateAuth")
        return {"ChallengeName": "SOFTWARE_TOKEN_MFA", "Session": "synthetic"}

    provider.admin_get_user.side_effect = get_user
    provider.admin_initiate_auth.side_effect = authenticate
    provider.admin_respond_to_auth_challenge.return_value = {
        "AuthenticationResult": {"IdToken": "synthetic"}
    }
    monkeypatch.setattr("scripts.e1_cognito_controls.time.sleep", lambda _: None)
    state = {
        "users": {
            "e1-a-p1": {
                "sub": subject,
                "mfa_ready": True,
                "password": "old-synthetic",
                "recovery_pending_password": "pending-synthetic",
                "totp_seed": "JBSWY3DPEHPK3PXP",
            },
            "e1-b-s2": {"sub": str(uuid.uuid4()), "mfa_ready": True},
        }
    }
    with pytest.raises(RuntimeError, match="stop before native probe"):
        exercise(
            provider, vault, {"PoolId": "synthetic", "AcceptanceFixtureSecret": "synthetic"}, state
        )
    provider.admin_set_user_password.assert_not_called()
    assert state["users"]["e1-a-p1"]["password"] == "pending-synthetic"
    assert "recovery_pending_password" not in state["users"]["e1-a-p1"]
    vault.put_secret_value.assert_called_once()
    provider.delete_user_pool_client.assert_called_once()
