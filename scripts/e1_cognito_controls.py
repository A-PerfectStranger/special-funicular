"""Operator-only proof on two fixed synthetic users. No enrollment, rebinding or messages."""

import json
import secrets
import time
import uuid
from collections.abc import Callable
from math import ceil, floor
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
        "Five initial password failures were not established": "native_initial_failures_missing",
        "Native first expiry was not observed": "native_first_expiry_timeout",
        "Native second expiry was not observed": "native_second_expiry_timeout",
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


def measure_native_lockout(
    auth: Callable[[str, str], dict[str, Any]], username: str, password: str
) -> dict[str, float]:
    """Prove growth using conservative RPC bounds, never a presumed server expiry."""
    print("E1 native step: five failed passwords", flush=True)
    fifth_started = fifth_finished = 0.0
    for _ in range(5):
        fifth_started = time.monotonic()
        try:
            auth(username, secrets.token_urlsafe(32) + "wrongA1!")
        except ClientError as error:
            if error.response["Error"]["Code"] != "NotAuthorizedException":
                raise
            if locked(error):
                raise RuntimeError("Five initial password failures were not established") from None
        else:
            raise RuntimeError("Incorrect password unexpectedly accepted")
        fifth_finished = time.monotonic()

    def prove_locked(message: str) -> None:
        try:
            auth(username, password)
        except ClientError as error:
            if not locked(error):
                raise
        else:
            raise RuntimeError(message)

    print("E1 native step: first lockout observation", flush=True)
    prove_locked("First native lockout was not observed")
    print("E1 native step: wait for first expiry and establish sixth failure", flush=True)
    # Locked probes do not count as password failures. The first ordinary wrong-
    # password rejection proves expiry AND establishes exactly one additional failure.
    second_start: tuple[float, float] | None = None
    deadline = fifth_finished + 20
    while time.monotonic() < deadline:
        time.sleep(0.2)
        started = time.monotonic()
        try:
            auth(username, secrets.token_urlsafe(32) + "wrongA1!")
        except ClientError as error:
            if locked(error):
                continue
            if error.response["Error"]["Code"] != "NotAuthorizedException":
                raise
            second_start = started, time.monotonic()
            break
        else:
            raise RuntimeError("Incorrect password unexpectedly accepted")
    if second_start is None:
        raise RuntimeError("Native first expiry was not observed")
    sixth_started, sixth_finished = second_start
    # The first server lock starts no earlier than the fifth request starts and
    # expires no later than the ordinary sixth failure's response. This is an upper bound.
    first_upper = ceil((sixth_finished - fifth_started) * 1000) / 1000
    print(json.dumps({"native_first_lockout_upper_seconds": first_upper}), flush=True)
    print("E1 native step: second lockout observation", flush=True)
    prove_locked("Second native lockout was not observed")
    delay = sixth_finished + first_upper + 0.1 - time.monotonic()
    if delay > 0:
        time.sleep(delay)
    print("E1 native step: prove second window exceeds first upper bound", flush=True)
    second_probe_started = time.monotonic()
    # The second lock started before the sixth response ended and was still
    # active after this probe began. Its lower bound must exceed the first upper bound.
    second_lower = floor((second_probe_started - sixth_finished) * 1000) / 1000
    print(json.dumps({"native_second_probe_lower_seconds": second_lower}), flush=True)
    prove_locked("The second native lockout did not exceed the first")
    if second_lower <= first_upper:
        raise RuntimeError("The second native lockout did not exceed the first")
    print("E1 native step: observe second expiry", flush=True)
    deadline = sixth_finished + max(20, first_upper * 3)
    while time.monotonic() < deadline:
        time.sleep(0.2)
        try:
            result = auth(username, password)
        except ClientError as error:
            if locked(error):
                continue
            raise
        if result.get("ChallengeName") != "SOFTWARE_TOKEN_MFA" or not result.get("Session"):
            raise RuntimeError("TOTP challenge was not required")
        return {
            "first_lockout_upper_seconds": first_upper,
            "second_lockout_lower_seconds": second_lower,
            "second_expiry_upper_seconds": ceil((time.monotonic() - sixth_started) * 1000) / 1000,
        }
    raise RuntimeError("Native second expiry was not observed")


def exercise(
    cognito: Any, vault: Any, config: dict[str, str], state: dict[str, Any]
) -> dict[str, Any]:
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
        measurement = measure_native_lockout(auth, username, record["password"])
        print("E1 native step: expiry and MFA", flush=True)
        mfa(username, record["password"])
        return {
            "password_recovery_required_recent_mfa": True,
            "recovery_preserved_original_subject": True,
            "recovered_password_mfa_verified": True,
            "native_first_lockout_observed": True,
            "native_second_lockout_longer_than_first": True,
            "native_expiry_mfa_verified": True,
            "native_lockout_measurement": measurement,
        }
    finally:
        cognito.delete_user_pool_client(UserPoolId=pool, ClientId=client)
