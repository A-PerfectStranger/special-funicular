"""Operator-only E2 synthetic identities; passwords/TOTP/invitations stay in the E1 vault."""

import argparse
import json
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
import pyotp

from scripts.commission_e1 import outputs, validate_operator
from scripts.e1_fixture_data import identifier


def enroll(cognito: Any, pool: str, client: str, name: str, record: dict[str, Any]) -> None:
    try:
        user = cognito.admin_get_user(UserPoolId=pool, Username=name)
    except cognito.exceptions.UserNotFoundException:
        if record.get("sub"):
            raise RuntimeError("No identity replacement allowed") from None
        cognito.admin_create_user(
            UserPoolId=pool,
            Username=name,
            MessageAction="SUPPRESS",
            UserAttributes=[
                {"Name": "email", "Value": record["contact"]},
                {"Name": "email_verified", "Value": "true"},
            ],
        )
        user = cognito.admin_get_user(UserPoolId=pool, Username=name)
    subject = next(a["Value"] for a in user["UserAttributes"] if a["Name"] == "sub")
    if record.get("sub") not in {None, subject}:
        raise RuntimeError("Subject changed")
    attributes = {item["Name"]: item["Value"] for item in user["UserAttributes"]}
    if attributes.get("email") != record["contact"] or attributes.get("email_verified") != "true":
        raise RuntimeError("Synthetic contact changed")
    record["sub"] = subject
    if not record.get("password_set") and user.get("UserStatus") != "CONFIRMED":
        cognito.admin_set_user_password(
            UserPoolId=pool, Username=name, Password=record["password"], Permanent=True
        )
        record["password_set"] = True
    auth = cognito.admin_initiate_auth(
        UserPoolId=pool,
        ClientId=client,
        AuthFlow="ADMIN_USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": name, "PASSWORD": record["password"]},
    )
    if auth.get("ChallengeName") == "MFA_SETUP":
        if record.get("totp_seed"):
            raise RuntimeError("Incomplete enrollment; inspect privately, do not replace seed")
        linked = cognito.associate_software_token(Session=auth["Session"])
        record["totp_seed"] = linked["SecretCode"]
        # Caller persists the seed before its first verification RPC.
        record["_setup_session"] = linked["Session"]
    elif auth.get("ChallengeName") == "SOFTWARE_TOKEN_MFA" and record.get("totp_seed"):
        record["_challenge_session"] = auth["Session"]
    else:
        raise RuntimeError("Mandatory synthetic MFA required")


def finish_enrollment(
    cognito: Any, pool: str, client: str, name: str, record: dict[str, Any]
) -> None:
    if record.get("_setup_session"):
        verified = cognito.verify_software_token(
            Session=record.pop("_setup_session"), UserCode=pyotp.TOTP(record["totp_seed"]).now()
        )
        if verified.get("Status") != "SUCCESS":
            raise RuntimeError("MFA verification failed")
        result = cognito.admin_respond_to_auth_challenge(
            UserPoolId=pool,
            ClientId=client,
            ChallengeName="MFA_SETUP",
            Session=verified["Session"],
            ChallengeResponses={"USERNAME": name},
        )
    else:
        result = cognito.admin_respond_to_auth_challenge(
            UserPoolId=pool,
            ClientId=client,
            ChallengeName="SOFTWARE_TOKEN_MFA",
            Session=record.pop("_challenge_session"),
            ChallengeResponses={
                "USERNAME": name,
                "SOFTWARE_TOKEN_MFA_CODE": pyotp.TOTP(record["totp_seed"]).now(),
            },
        )
    if not result.get("AuthenticationResult"):
        raise RuntimeError("MFA not completed")
    cognito.admin_set_user_mfa_preference(
        UserPoolId=pool,
        Username=name,
        SoftwareTokenMfaSettings={"Enabled": True, "PreferredMfa": True},
    )
    record["mfa_ready"] = True


def cohort(sha: str, trial: str) -> dict[str, Any]:
    stem = "e2-" + uuid.UUID(trial).hex[:16]
    school, site = identifier("school-a"), identifier("site-a")
    student = str(uuid.uuid5(uuid.UUID(trial), "student"))
    users = {}
    for suffix in ["p", "s"]:
        name = stem + "-" + suffix
        users[name] = {
            "password": secrets.token_urlsafe(36) + "aA1!",
            "sub": None,
            "totp_seed": None,
            "contact": name + "@synthetic.invalid",
            "invitation": secrets.token_urlsafe(32),
            "parent_id": str(uuid.uuid5(uuid.UUID(trial), suffix)),
            "principal": suffix == "p",
        }
    today = datetime.now(UTC).date()
    return {
        "release_sha": sha,
        "trial_id": trial,
        "users": users,
        "batch": {
            "schema_version": 1,
            "id": trial,
            "school_id": school,
            "parents": [{"id": r["parent_id"], "contact": r["contact"]} for r in users.values()],
            "students": [
                {
                    "id": student,
                    "site_id": site,
                    "name": "Estudiante sintético E2",
                    "blocked": False,
                    "windows": [
                        {
                            "weekday": day,
                            "from": "07:00",
                            "until": "18:00",
                            "start_date": str(today),
                            "end_date": str(today + timedelta(days=365)),
                        }
                        for day in range(1, 8)
                    ],
                }
            ],
            "links": [
                {"student_id": student, "parent_id": r["parent_id"], "principal": r["principal"]}
                for r in users.values()
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--trial-id", required=True)
    parser.add_argument(
        "--pool-size", type=int, default=0, help="Prepare 1..8 fresh cohorts for continuous gates"
    )
    parser.add_argument("--synthetic-only", action="store_true", required=True)
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{40}", args.sha):
        raise ValueError()
    trial = str(uuid.UUID(args.trial_id))
    session = boto3.Session(region_name="us-east-1")
    validate_operator(session.client("sts").get_caller_identity())
    config = outputs("retiro-staging-e1")
    cognito = session.client("cognito-idp")
    vault = session.client("secretsmanager")
    if not all(
        "email"
        in cognito.describe_user_pool_client(UserPoolId=config["PoolId"], ClientId=config[key])[
            "UserPoolClient"
        ].get("AllowedOAuthScopes", [])
        for key in ["WebClientId", "MobileClientId"]
    ):
        raise RuntimeError("Commission the email scope first")
    state = json.loads(
        vault.get_secret_value(SecretId=config["AcceptanceFixtureSecret"])["SecretString"]
    )
    if not state.get("roster_ready"):
        raise RuntimeError("Original E1 fixture required")
    if not 0 <= args.pool_size <= 8:
        raise ValueError("Pool limit")
    if args.pool_size:
        existing = {c["trial_id"]: c for c in state.get("e2_pool", [])}
        selected = []
        for index in range(args.pool_size):
            ident = str(uuid.uuid5(uuid.UUID(trial), str(index)))
            value = existing.get(ident) or cohort(args.sha, ident)
            if value["release_sha"] != args.sha:
                raise RuntimeError("Pool preparation belongs to another release")
            selected.append(value)
        # Secrets Manager retains prior versions; no SQL records, identities or tokens are reset.
        state["e2_pool"] = selected
    else:
        if state.get("e2", {}).get("trial_id") != trial:
            state["e2"] = cohort(args.sha, trial)
        if state["e2"]["release_sha"] != args.sha:
            raise RuntimeError("Trial belongs to another release")
        selected = [state["e2"]]

    def save() -> None:
        vault.put_secret_value(
            SecretId=config["AcceptanceFixtureSecret"], SecretString=json.dumps(state)
        )

    save()
    pool = config["PoolId"]
    client = cognito.create_user_pool_client(
        UserPoolId=pool,
        ClientName="e2-private-enrollment-" + uuid.uuid4().hex[:12],
        GenerateSecret=False,
        ExplicitAuthFlows=["ALLOW_ADMIN_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
    )["UserPoolClient"]["ClientId"]
    try:
        for value in selected:
            for name, record in value["users"].items():
                enroll(cognito, pool, client, name, record)
                save()
                finish_enrollment(cognito, pool, client, name, record)
                save()
    finally:
        cognito.delete_user_pool_client(UserPoolId=pool, ClientId=client)
    print("E2 synthetic MFA fixtures prepared. No acceptance or real messages claimed.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("BLOCKED: E2 fixture preparation failed; inspect privately, no identity reset.")
        raise SystemExit(2) from None
