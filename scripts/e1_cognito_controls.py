"""Operator-only proof on two fixed synthetic users. No enrollment, rebinding or messages."""

import json
import secrets
import time
import uuid
from typing import Any

import pyotp
from botocore.exceptions import ClientError


def failure_label(error: Exception) -> str:
    """Emit only fixed labels; provider messages can contain private input."""
    barriers = {
        "Mandatory TOTP required": "mandatory_totp_missing",
        "TOTP challenge was not required": "totp_challenge_missing",
        "Synthetic MFA not completed": "totp_not_completed",
        "Original synthetic binding required": "original_binding_changed",
        "Recent MFA required for synthetic recovery": "recent_mfa_expired",
        "Replaced password remained valid": "previous_password_still_valid",
        "Recovery changed the original subject; no rebinding allowed": "recovery_subject_changed",
        "Original lockout fixture required": "original_lockout_fixture_changed",
        "Incorrect password unexpectedly accepted": "incorrect_password_accepted",
        "First native lockout was not observed": "native_first_lockout_not_observed",
        "Sixth password failure was not established": "native_sixth_failure_not_established",
        "Second native lockout was not observed": "native_second_lockout_not_observed",
        "The second native lockout did not exceed the first": "native_second_window_too_short",
    }
    if type(error) is RuntimeError and len(error.args) == 1 and isinstance(error.args[0], str):
        return barriers.get(error.args[0], "unclassified_private_failure")
    if isinstance(error, ClientError):
        provider_error = error.response.get("Error", {})
        code = provider_error.get("Code") if isinstance(provider_error, dict) else None
        if not isinstance(code, str):
            return "unclassified_private_failure"
        return {
            "NotAuthorizedException": "provider_not_authorized",
            "TooManyRequestsException": "provider_rate_limit",
            "TooManyFailedAttemptsException": "provider_attempt_limit",
            "ThrottlingException": "provider_rate_limit",
            "CodeMismatchException": "provider_totp_mismatch",
            "ExpiredCodeException": "provider_totp_expired",
            "InvalidParameterException": "provider_invalid_parameter",
            "PasswordHistoryPolicyViolationException": "provider_password_history",
            "AccessDeniedException": "provider_access_denied",
        }.get(code, "unclassified_private_failure")
    return "unclassified_private_failure"


def locked(error: ClientError) -> bool:
    return (
        error.response["Error"]["Code"] == "NotAuthorizedException"
        and "password attempts exceeded" in error.response["Error"].get("Message", "").lower()
    )


def exercise(
    cognito: Any, vault: Any, config: dict[str, str], state: dict[str, Any]
) -> dict[str, bool]:
    print("E1 private step: Cognito configuration", flush=True)
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
    native_trace = False

    def auth(username: str, password: str) -> dict[str, Any]:
        started = time.monotonic()
        outcome = "transport_failure"
        try:
            response = dict(
                cognito.admin_initiate_auth(
                    UserPoolId=pool,
                    ClientId=client,
                    AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                    AuthParameters={"USERNAME": username, "PASSWORD": password},
                )
            )
            outcome = (
                "mfa_challenge"
                if response.get("ChallengeName") == "SOFTWARE_TOKEN_MFA"
                else "unexpected_success"
            )
            return response
        except ClientError as error:
            outcome = (
                "lockout"
                if locked(error)
                else "password_rejected"
                if error.response["Error"]["Code"] == "NotAuthorizedException"
                else failure_label(error)
            )
            raise
        finally:
            if native_trace:
                print(
                    json.dumps(
                        {
                            "native_outcome": outcome,
                            "elapsed_ms": round((time.monotonic() - started) * 1000),
                        }
                    ),
                    flush=True,
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
        vault.put_secret_value(
            SecretId=config["AcceptanceFixtureSecret"], SecretString=json.dumps(state)
        )

    try:
        print("E1 private step: recent MFA and synthetic password recovery", flush=True)
        username = "e1-a-p1"
        record = state["users"][username]
        if not record.get("mfa_ready") or subject(username) != record["sub"]:
            raise RuntimeError("Original synthetic binding required")
        pending_is_active = False
        try:
            verified_at = mfa(username, record["password"])
        except ClientError as error:
            # A checkpointed password can already be active after interruption.
            if error.response["Error"]["Code"] != "NotAuthorizedException" or not record.get(
                "recovery_pending_password"
            ):
                raise
            verified_at = mfa(username, record["recovery_pending_password"])
            pending_is_active = True
        if not record.get("recovery_pending_password"):
            record["recovery_pending_password"] = secrets.token_urlsafe(36) + "aA1!"
            save()  # Never lose the new credential if interrupted after the provider update.
        if time.monotonic() - verified_at >= 300:
            raise RuntimeError("Recent MFA required for synthetic recovery")
        previous_password = record["password"]
        replacement = record["recovery_pending_password"]
        if not pending_is_active:
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
        print("E1 private step: native exponential lockout", flush=True)
        native_trace = True
        username = "e1-b-s2"
        record = state["users"][username]
        if not record.get("mfa_ready") or subject(username) != record["sub"]:
            raise RuntimeError("Original lockout fixture required")
        print("E1 native step: baseline MFA", flush=True)
        mfa(username, record["password"])
        print("E1 native step: five failed passwords", flush=True)
        for _ in range(5):
            try:
                auth(username, secrets.token_urlsafe(32) + "wrongA1!")
            except ClientError as error:
                if error.response["Error"]["Code"] != "NotAuthorizedException":
                    raise
            else:
                raise RuntimeError("Incorrect password unexpectedly accepted")
        print("E1 native step: first lockout observation", flush=True)
        try:
            auth(username, record["password"])
        except ClientError as error:
            if not locked(error):
                raise
        else:
            raise RuntimeError("First native lockout was not observed")
        time.sleep(1.2)
        print("E1 native step: sixth failed password", flush=True)
        try:
            auth(username, secrets.token_urlsafe(32) + "wrongA1!")
        except ClientError as error:
            if error.response["Error"]["Code"] != "NotAuthorizedException" or locked(error):
                raise RuntimeError("Sixth password failure was not established") from None
        else:
            raise RuntimeError("Incorrect password unexpectedly accepted")
        print("E1 native step: second lockout observation", flush=True)
        try:
            auth(username, record["password"])
        except ClientError as error:
            if not locked(error):
                raise
        else:
            raise RuntimeError("Second native lockout was not observed")
        time.sleep(1.2)
        print("E1 native step: longer second window", flush=True)
        try:
            auth(username, record["password"])
        except ClientError as error:
            if not locked(error):
                raise
        else:
            raise RuntimeError("The second native lockout did not exceed the first")
        time.sleep(1.2)
        print("E1 native step: expiry and MFA", flush=True)
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
