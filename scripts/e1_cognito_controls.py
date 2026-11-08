"""Operator-only proof on two fixed synthetic users. No enrollment, rebinding or messages."""

import secrets
import time
import uuid
from typing import Any

import pyotp
from botocore.exceptions import ClientError


def locked(error: ClientError) -> bool:
    return (
        error.response["Error"]["Code"] == "NotAuthorizedException"
        and "password attempts exceeded" in error.response["Error"].get("Message", "").lower()
    )


def exercise(
    cognito: Any, vault: Any, config: dict[str, str], state: dict[str, Any]
) -> dict[str, bool]:
    pool = config["PoolId"]
    policy = cognito.get_user_pool_mfa_config(UserPoolId=pool)
    if policy.get("MfaConfiguration") != "ON" or not policy.get(
        "SoftwareTokenMfaConfiguration", {}
    ).get("Enabled"):
        raise RuntimeError("Mandatory TOTP required")
    client = cognito.create_user_pool_client(
        UserPoolId=pool,
        ClientName="e1-private-controls-" + uuid.uuid4().hex[:12],
        GenerateSecret=False,
        PreventUserExistenceErrors="ENABLED",
        ExplicitAuthFlows=["ALLOW_ADMIN_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        AccessTokenValidity=5,
        IdTokenValidity=5,
        RefreshTokenValidity=1,
        TokenValidityUnits={"AccessToken": "minutes", "IdToken": "minutes", "RefreshToken": "days"},
    )["UserPoolClient"]["ClientId"]
    used: dict[str, str] = {}

    def auth(username: str, password: str) -> dict[str, Any]:
        return dict(
            cognito.admin_initiate_auth(
                UserPoolId=pool,
                ClientId=client,
                AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": password},
            )
        )

    def mfa(username: str, password: str) -> float:
        response = auth(username, password)
        if response.get("ChallengeName") != "SOFTWARE_TOKEN_MFA" or not response.get("Session"):
            raise RuntimeError("TOTP challenge was not required")
        totp = pyotp.TOTP(state["users"][username]["totp_seed"])
        code = totp.now()
        if used.get(username) == code:
            time.sleep(31 - time.time() % 30)
            code = totp.now()
        used[username] = code
        completed = cognito.admin_respond_to_auth_challenge(
            UserPoolId=pool,
            ClientId=client,
            ChallengeName="SOFTWARE_TOKEN_MFA",
            Session=response["Session"],
            ChallengeResponses={"USERNAME": username, "SOFTWARE_TOKEN_MFA_CODE": code},
        )
        if not completed.get("AuthenticationResult"):
            raise RuntimeError("Synthetic MFA not completed")
        return time.monotonic()

    def subject(username: str) -> str:
        user = cognito.admin_get_user(UserPoolId=pool, Username=username)
        return str(next(item["Value"] for item in user["UserAttributes"] if item["Name"] == "sub"))

    def save() -> None:
        import json

        vault.put_secret_value(
            SecretId=config["AcceptanceFixtureSecret"], SecretString=json.dumps(state)
        )

    try:
        username = "e1-a-p1"
        record = state["users"][username]
        if not record.get("mfa_ready") or subject(username) != record["sub"]:
            raise RuntimeError("Original synthetic binding required")
        try:
            verified_at = mfa(username, record["password"])
        except ClientError as error:
            # A checkpointed password can already be active after interruption.
            if error.response["Error"]["Code"] != "NotAuthorizedException" or not record.get(
                "recovery_pending_password"
            ):
                raise
            verified_at = mfa(username, record["recovery_pending_password"])
        if not record.get("recovery_pending_password"):
            record["recovery_pending_password"] = secrets.token_urlsafe(36) + "aA1!"
            save()  # Never lose the new credential if interrupted after the provider update.
        if time.monotonic() - verified_at >= 300:
            raise RuntimeError("Recent MFA required for synthetic recovery")
        previous_password = record["password"]
        replacement = record["recovery_pending_password"]
        cognito.admin_set_user_password(
            UserPoolId=pool, Username=username, Password=replacement, Permanent=True
        )
        record["password"] = replacement
        record.pop("recovery_pending_password")
        save()
        if previous_password != replacement:
            try:
                auth(username, previous_password)
            except ClientError as error:
                if error.response["Error"]["Code"] != "NotAuthorizedException" or locked(error):
                    raise
            else:
                raise RuntimeError("Replaced password remained valid")
        mfa(username, replacement)
        if subject(username) != record["sub"]:
            raise RuntimeError("Recovery changed the original subject; no rebinding allowed")
        username = "e1-b-s2"
        record = state["users"][username]
        if not record.get("mfa_ready") or subject(username) != record["sub"]:
            raise RuntimeError("Original lockout fixture required")
        mfa(username, record["password"])
        for _ in range(5):
            try:
                auth(username, secrets.token_urlsafe(32) + "wrongA1!")
            except ClientError as error:
                if error.response["Error"]["Code"] != "NotAuthorizedException":
                    raise
            else:
                raise RuntimeError("Incorrect password unexpectedly accepted")
        try:
            auth(username, record["password"])
        except ClientError as error:
            if not locked(error):
                raise
        else:
            raise RuntimeError("First native lockout was not observed")
        time.sleep(1.2)
        try:
            auth(username, secrets.token_urlsafe(32) + "wrongA1!")
        except ClientError as error:
            if error.response["Error"]["Code"] != "NotAuthorizedException" or locked(error):
                raise RuntimeError("Sixth password failure was not established") from None
        else:
            raise RuntimeError("Incorrect password unexpectedly accepted")
        try:
            auth(username, record["password"])
        except ClientError as error:
            if not locked(error):
                raise
        else:
            raise RuntimeError("Second native lockout was not observed")
        time.sleep(1.2)
        try:
            auth(username, record["password"])
        except ClientError as error:
            if not locked(error):
                raise
        else:
            raise RuntimeError("The second native lockout did not exceed the first")
        time.sleep(1.2)
        mfa(username, record["password"])
        return {
            "password_recovery_required_recent_mfa": True,
            "recovery_preserved_original_subject": True,
            "recovered_password_mfa_verified": True,
            "native_first_lockout_observed": True,
            "native_second_lockout_longer_than_first": True,
            "native_expiry_mfa_verified": True,
        }
    finally:
        cognito.delete_user_pool_client(UserPoolId=pool, ClientId=client)
