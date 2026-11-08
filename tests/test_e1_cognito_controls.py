"""Recovery must stop before mutation if MFA is absent; unrelated errors prove no lockout."""

import uuid
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
