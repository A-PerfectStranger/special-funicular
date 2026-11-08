"""Private synthetic Cognito/MFA fixtures. Secrets never enter logs, task metadata or Git."""

import argparse
import json
import re
import secrets
import uuid
from pathlib import Path

import boto3
import pyotp
from botocore.exceptions import ClientError

from scripts.aws_cli import aws
from scripts.commission_e1 import outputs, validate_operator
from scripts.commission_staging import register, task_definition
from scripts.e1_fixture_data import catalogue, roster_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-only", action="store_true", required=True)
    parser.parse_args()
    session = boto3.Session(region_name="us-east-1")
    validate_operator(session.client("sts").get_caller_identity())
    config, base = outputs("retiro-staging-e1"), outputs("retiro-staging-base")
    if not config.get("AcceptanceFixtureSecret") or not config.get("FixtureExecutionArn"):
        raise RuntimeError("Update the reviewed E1 stack before creating fixtures")
    cognito = session.client("cognito-idp")
    vault = session.client("secretsmanager")
    secret_arn = config["AcceptanceFixtureSecret"]
    state = json.loads(vault.get_secret_value(SecretId=secret_arn)["SecretString"])
    if state.get("schema_version") != 1 or not isinstance(state.get("users"), dict):
        raise RuntimeError("Invalid synthetic fixture store")
    users = state["users"]

    def save() -> None:
        vault.put_secret_value(SecretId=secret_arn, SecretString=json.dumps(state))

    pool = config["PoolId"]
    if cognito.describe_user_pool(UserPoolId=pool)["UserPool"].get("MfaConfiguration") != "ON":
        raise RuntimeError("Mandatory MFA required before synthetic provisioning")
    # Temporary, IAM-only enrollment client. Its audience is never accepted by the BFF.
    client = cognito.create_user_pool_client(
        UserPoolId=pool,
        ClientName="e1-private-enrollment-" + uuid.uuid4().hex[:12],
        GenerateSecret=False,
        ExplicitAuthFlows=["ALLOW_ADMIN_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        AccessTokenValidity=5,
        IdTokenValidity=5,
        RefreshTokenValidity=1,
        TokenValidityUnits={"AccessToken": "minutes", "IdToken": "minutes", "RefreshToken": "days"},
    )["UserPoolClient"]["ClientId"]
    try:
        for username, specification in catalogue().items():
            record = users.get(username)
            if record is None:
                record = {
                    "password": secrets.token_urlsafe(36) + "aA1!",
                    "sub": None,
                    "totp_seed": None,
                    "password_set": False,
                    "mfa_ready": False,
                }
                users[username] = record
                save()
            try:
                existing = cognito.admin_get_user(UserPoolId=pool, Username=username)
            except cognito.exceptions.UserNotFoundException:
                if record["sub"] is not None:
                    raise RuntimeError(
                        "Fixture identity disappeared; do not rebind students"
                    ) from None
                cognito.admin_create_user(
                    UserPoolId=pool, Username=username, MessageAction="SUPPRESS"
                )
                existing = cognito.admin_get_user(UserPoolId=pool, Username=username)
            sub = next(
                item["Value"] for item in existing["UserAttributes"] if item["Name"] == "sub"
            )
            if record["sub"] is not None and record["sub"] != sub:
                raise RuntimeError("Fixture subject changed; no automatic rebinding")
            record["sub"] = sub
            if not record["password_set"]:
                cognito.admin_set_user_password(
                    UserPoolId=pool, Username=username, Password=record["password"], Permanent=True
                )
                record["password_set"] = True
                save()
            auth = cognito.admin_initiate_auth(
                UserPoolId=pool,
                ClientId=client,
                AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": record["password"]},
            )
            challenge = auth.get("ChallengeName")
            challenge_session = auth.get("Session")
            if not challenge_session:
                raise RuntimeError("MFA challenge was not required")
            if challenge == "MFA_SETUP":
                associated = cognito.associate_software_token(Session=challenge_session)
                record["totp_seed"] = associated["SecretCode"]
                save()  # Recover even if the process stops after verification.
                verified = cognito.verify_software_token(
                    Session=associated["Session"],
                    UserCode=pyotp.TOTP(record["totp_seed"]).now(),
                    FriendlyDeviceName="E1 synthetic test",
                )
                if verified.get("Status") != "SUCCESS":
                    raise RuntimeError("Synthetic TOTP enrollment not verified")
                completed = cognito.admin_respond_to_auth_challenge(
                    UserPoolId=pool,
                    ClientId=client,
                    ChallengeName="MFA_SETUP",
                    Session=verified["Session"],
                    ChallengeResponses={"USERNAME": username},
                )
            elif challenge == "SOFTWARE_TOKEN_MFA" and record["totp_seed"]:
                completed = cognito.admin_respond_to_auth_challenge(
                    UserPoolId=pool,
                    ClientId=client,
                    ChallengeName="SOFTWARE_TOKEN_MFA",
                    Session=challenge_session,
                    ChallengeResponses={
                        "USERNAME": username,
                        "SOFTWARE_TOKEN_MFA_CODE": pyotp.TOTP(record["totp_seed"]).now(),
                    },
                )
            else:
                raise RuntimeError("Unexpected synthetic identity challenge")
            if not completed.get("AuthenticationResult"):
                raise RuntimeError("Synthetic MFA not completed")
            cognito.admin_set_user_mfa_preference(
                UserPoolId=pool,
                Username=username,
                SoftwareTokenMfaSettings={"Enabled": True, "PreferredMfa": True},
            )
            if not record["mfa_ready"]:
                record["mfa_ready"] = True
                save()
            print("synthetic_identity_mfa_ready=" + specification["role"], flush=True)
    finally:
        cognito.delete_user_pool_client(UserPoolId=pool, ClientId=client)
    payload = roster_payload(config["Issuer"], users)
    previous = aws("ecs", "describe-task-definition", "--task-definition", "retiro-staging-api")[
        "taskDefinition"
    ]
    image = previous["containerDefinitions"][0]["image"]
    if not re.fullmatch(
        r"028364485203\.dkr\.ecr\.us-east-1\.amazonaws\.com/retiro-staging/backend@sha256:[0-9a-f]{64}",
        image,
    ):
        raise RuntimeError("Digest-pinned project image required for private roster seed")
    source_sha = next(
        (
            item["value"]
            for item in previous["containerDefinitions"][0]["environment"]
            if item["name"] == "GIT_SHA"
        ),
        "",
    )
    if not re.fullmatch("[0-9a-f]{40}", source_sha):
        raise RuntimeError("Immutable source identity required for private roster seed")
    definition = task_definition(base, image, source_sha, False)
    definition["family"] = "retiro-staging-fixture"
    definition["executionRoleArn"] = config["FixtureExecutionArn"]
    container = definition["containerDefinitions"][0]
    container.pop("portMappings", None)
    container["command"] = ["python", "-c", Path("scripts/seed_e1_roster.py").read_text()]
    for item in container["environment"]:
        if item["name"] == "PGUSER":
            item["value"] = "retiro_importer"
    container["environment"].append({"name": "E1_FIXTURE_DATA", "value": json.dumps(payload)})
    container["secrets"] = [{"name": "PGPASSWORD", "valueFrom": config["ImporterPassword"]}]
    registered = register(definition)
    network = {
        "awsvpcConfiguration": {
            "subnets": [base["Public0"], base["Public1"]],
            "securityGroups": [base["AppSecurityGroup"]],
            "assignPublicIp": "ENABLED",
        }
    }
    run = aws(
        "ecs",
        "run-task",
        "--cluster",
        base["Cluster"],
        "--task-definition",
        registered,
        "--launch-type",
        "FARGATE",
        "--network-configuration",
        json.dumps(network),
    )
    if run.get("failures") or len(run.get("tasks", [])) != 1:
        raise RuntimeError("Synthetic SQL seed did not start")
    task = run["tasks"][0]["taskArn"]
    aws("ecs", "wait", "tasks-stopped", "--cluster", base["Cluster"], "--tasks", task)
    finished = aws("ecs", "describe-tasks", "--cluster", base["Cluster"], "--tasks", task)["tasks"][
        0
    ]
    if not finished.get("containers") or any(
        c.get("exitCode") != 0 for c in finished["containers"]
    ):
        raise RuntimeError("Synthetic SQL seed failed; no partial roster transaction")
    state["roster_ready"] = True
    save()
    print("Synthetic identities, TOTP and roster prepared. E1 integrated acceptance still pending.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClientError as exc:
        print("BLOCKED: synthetic fixture AWS operation: " + exc.response["Error"]["Code"])
        raise SystemExit(2) from None
    except RuntimeError as exc:
        print("BLOCKED: " + str(exc))
        raise SystemExit(2) from None
    except Exception:
        print("BLOCKED: synthetic fixture setup failed; no credentials printed")
        raise SystemExit(2) from None
