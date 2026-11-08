"""Operator-only synthetic export and rewritten SQL copy, retained privately in S3."""

import argparse
import base64
import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

import boto3

from scripts.aws_cli import aws
from scripts.commission_e1 import outputs, validate_operator
from scripts.commission_staging import register, task_definition
from scripts.e1_cognito_controls import exercise
from scripts.e1_fixture_data import roster_payload
from scripts.e1_policy_inspection import only_pool_reads, protects_application_keys
from scripts.e1_snapshot_data import rewrite_copy, validate_local_chain


def read_private_rows(
    logs: Any, group: str, stream: str
) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    rows: dict[int, dict[str, Any]] = {}
    expected = None
    checks: dict[str, bool] = {}
    token = None
    for _ in range(100):
        result = logs.get_log_events(
            logGroupName=group,
            logStreamName=stream,
            startFromHead=True,
            **({"nextToken": token} if token else {}),
        )
        for event in result["events"]:
            message = event["message"]
            if message.startswith("E1_PRIVATE_DB_BOUNDARIES="):
                checks = json.loads(message.removeprefix("E1_PRIVATE_DB_BOUNDARIES="))
            elif message.startswith("E1_PRIVATE_SNAPSHOT_ROW="):
                row = json.loads(message.removeprefix("E1_PRIVATE_SNAPSHOT_ROW="))
                sequence = row["sequence"]
                if type(sequence) is not int or (sequence in rows and rows[sequence] != row):
                    raise RuntimeError("Invalid private snapshot stream")
                rows[sequence] = row
            elif message.startswith("E1_PRIVATE_SNAPSHOT_END="):
                expected = int(message.removeprefix("E1_PRIVATE_SNAPSHOT_END="))
        if result["nextForwardToken"] == token:
            if expected is not None and len(rows) == expected:
                break
            time.sleep(1)
        token = result["nextForwardToken"]
    if expected is None or len(rows) != expected:
        raise RuntimeError("Incomplete private snapshot stream")
    ordered = [rows[key] for key in sorted(rows)]
    validate_local_chain(ordered)
    if not checks or any(value is not True for value in checks.values()):
        raise RuntimeError("Missing database boundary evidence")
    return ordered, checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-only", action="store_true", required=True)
    parser.add_argument("--exercise-cognito-controls", action="store_true")
    options = parser.parse_args()
    print("E1 private step: operator and configuration", flush=True)
    session = boto3.Session(region_name="us-east-1")
    validate_operator(session.client("sts").get_caller_identity())
    config, base = outputs("retiro-staging-e1"), outputs("retiro-staging-base")
    previous = aws("ecs", "describe-task-definition", "--task-definition", "retiro-staging-api")[
        "taskDefinition"
    ]
    image = previous["containerDefinitions"][0]["image"]
    if not re.fullmatch(
        r"028364485203\.dkr\.ecr\.us-east-1\.amazonaws\.com/retiro-staging/backend@sha256:[0-9a-f]{64}",
        image,
    ):
        raise RuntimeError("Project digest-pinned image required")
    sha = next(
        item["value"]
        for item in previous["containerDefinitions"][0]["environment"]
        if item["name"] == "GIT_SHA"
    )
    if not re.fullmatch("[0-9a-f]{40}", sha):
        raise RuntimeError("Immutable source required")
    definition = task_definition(base, image, sha, False)
    definition["family"] = "retiro-staging-fixture"
    definition["executionRoleArn"] = config["FixtureExecutionArn"]
    container = definition["containerDefinitions"][0]
    container.pop("portMappings", None)
    container["command"] = ["python", "-c", Path("scripts/export_e1_snapshot.py").read_text()]
    fixture = json.loads(
        session.client("secretsmanager").get_secret_value(
            SecretId=config["AcceptanceFixtureSecret"]
        )["SecretString"]
    )
    if fixture.get("roster_ready") is not True:
        raise RuntimeError("Prepared original synthetic fixture required")
    cognito_controls = None
    if options.exercise_cognito_controls:
        cognito_controls = exercise(
            session.client("cognito-idp"), session.client("secretsmanager"), config, fixture
        )
    print("E1 private step: original roster and private SQL snapshot", flush=True)
    container["environment"].append(
        {
            "name": "E1_EXPECTED_ROSTER",
            "value": json.dumps(roster_payload(config["Issuer"], fixture["users"])),
        }
    )
    container["secrets"] = [{"name": "PGPASSWORD", "valueFrom": config["ImporterPassword"]}]
    for item in container["environment"]:
        if item["name"] == "PGUSER":
            item["value"] = "retiro_importer"
    container["logConfiguration"]["options"]["awslogs-stream-prefix"] = "snapshot-private"
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
        raise RuntimeError("Private export did not start")
    arn = run["tasks"][0]["taskArn"]
    aws("ecs", "wait", "tasks-stopped", "--cluster", base["Cluster"], "--tasks", arn)
    task = aws("ecs", "describe-tasks", "--cluster", base["Cluster"], "--tasks", arn)["tasks"][0]
    if not task.get("containers") or any(c.get("exitCode") != 0 for c in task["containers"]):
        raise RuntimeError("Private export failed; no snapshot accepted")
    stream = "snapshot-private/" + container["name"] + "/" + arn.rsplit("/", 1)[1]
    rows, boundaries = read_private_rows(session.client("logs"), base["Logs"], stream)
    print("E1 private step: effective AWS boundary policies", flush=True)
    kms, iam = session.client("kms"), session.client("iam")
    for key in ["EncryptionKeyArn", "SigningKeyArn"]:
        policy = json.loads(kms.get_key_policy(KeyId=config[key], PolicyName="default")["Policy"])
        boundaries[key + "_application_admin_denied"] = protects_application_keys(policy)
    role = "retiro-staging-E1ApiTask"
    names = iam.list_role_policies(RoleName=role)
    attached = iam.list_attached_role_policies(RoleName=role)
    policies = [
        iam.get_role_policy(RoleName=role, PolicyName=name)["PolicyDocument"]
        for name in names["PolicyNames"]
    ]
    boundaries["api_task_has_only_pool_policy_reads"] = (
        not names.get("IsTruncated")
        and not attached.get("IsTruncated")
        and not attached["AttachedPolicies"]
        and only_pool_reads(policies)
    )
    if not all(boundaries.values()):
        raise RuntimeError("AWS boundary inspection failed")
    print("E1 private step: retained original and rewritten copies", flush=True)
    mutated = rewrite_copy(rows)
    s3 = session.client("s3")
    nonce = uuid.uuid4().hex
    report: dict[str, Any] = {
        "schema_version": 1,
        "synthetic_only": True,
        "source_sha": sha,
        "boundary_checks": boundaries,
        "cognito_controls": cognito_controls,
    }

    def put(key: str, value: Any) -> dict[str, str]:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        if len(payload) > 16 * 1024 * 1024:
            raise RuntimeError("Private snapshot size limit")
        result = s3.put_object(
            Bucket=config["Bucket"],
            Key=key,
            Body=payload,
            IfNoneMatch="*",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config["EncryptionKeyArn"],
            BucketKeyEnabled=True,
            ContentType="application/json",
            ChecksumSHA256=base64.b64encode(hashlib.sha256(payload).digest()).decode(),
        )
        if not result.get("VersionId") or result["VersionId"] == "null":
            raise RuntimeError("Versioned private snapshot required")
        return {
            "key": key,
            "version": result["VersionId"],
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    report["original"] = put(f"acceptance-snapshots/original/{nonce}.json", rows)
    report["rewritten"] = put(f"acceptance-snapshots/rewritten/{nonce}.json", mutated)
    reference = put(f"acceptance-snapshots/reports/{nonce}.json", report)
    # Only immutable metadata is printed, never rows, credentials or provider logs.
    print(
        json.dumps(
            {
                "report_key": reference["key"],
                "report_version": reference["version"],
                "report_sha256": reference["sha256"],
                "e1_accepted": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("BLOCKED: private synthetic snapshot preparation failed; inspect AWS privately")
        raise SystemExit(2) from None
