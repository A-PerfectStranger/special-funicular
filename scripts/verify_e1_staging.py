"""Independent real E1 cloud checks. No SQL credentials, Sign or write permissions."""

import argparse
import hashlib
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
from archive_worker.storage import IntegrityFailure
from archive_worker.verifier import ExternalVerifier, VerificationDeadlineExceeded
from botocore.config import Config
from botocore.exceptions import ClientError

from scripts.commission_e1 import outputs


def demand(condition: bool) -> None:
    if not condition:
        raise RuntimeError("Cloud configuration or isolation check failed")


def denied(operation: Any, **arguments: Any) -> None:
    try:
        operation(**arguments)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in {"AccessDenied", "AccessDeniedException"}:
            return
        raise RuntimeError("Expected access denial was not established") from None
    raise RuntimeError("Unexpected cloud permission; acceptance failed")


def verify(minimum_sequence: int = 1, workers: int = 4, max_seconds: int = 480) -> dict[str, Any]:
    if not 1 <= workers <= 8 or not 1 <= max_seconds <= 480:
        raise ValueError("Bounded verification configuration required")
    started = time.monotonic()
    deadline = started + max_seconds

    def remaining() -> None:
        if time.monotonic() >= deadline:
            raise VerificationDeadlineExceeded()

    def progress(done: int, total: int) -> None:
        if done == 0 or done == total or done % 100 == 0:
            print(
                json.dumps(
                    {
                        "phase": "external_chain",
                        "verified_events": done,
                        "listed_checkpoints": total,
                        "workers": workers,
                        "elapsed_seconds": int(time.monotonic() - started),
                    }
                ),
                flush=True,
            )

    session = boto3.Session(region_name="us-east-1")
    options = Config(
        connect_timeout=3,
        read_timeout=10,
        retries={"mode": "standard", "total_max_attempts": 2},
        max_pool_connections=8,
    )
    identity = session.client("sts", config=options).get_caller_identity()
    demand(
        identity["Account"] == "028364485203"
        and identity["Arn"].startswith(
            "arn:aws:sts::028364485203:assumed-role/retiro-staging-E1Verifier/"
        )
    )
    config = outputs("retiro-staging-e1")
    s3, kms, cognito = (
        session.client("s3", config=options),
        session.client("kms", config=options),
        session.client("cognito-idp", config=options),
    )
    bucket = config["Bucket"]
    demand(s3.get_bucket_versioning(Bucket=bucket).get("Status") == "Enabled")
    lock = s3.get_object_lock_configuration(Bucket=bucket)["ObjectLockConfiguration"]
    demand(
        lock.get("ObjectLockEnabled") == "Enabled"
        and lock.get("Rule", {}).get("DefaultRetention") == {"Mode": "COMPLIANCE", "Days": 7}
    )
    demand(
        all(s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"].values())
    )
    encryption = s3.get_bucket_encryption(Bucket=bucket)["ServerSideEncryptionConfiguration"][
        "Rules"
    ]
    demand(
        len(encryption) == 1
        and encryption[0]["ApplyServerSideEncryptionByDefault"]
        == {
            "SSEAlgorithm": "aws:kms",
            "KMSMasterKeyID": config["EncryptionKeyArn"],
        }
    )
    for name, usage, key_spec in [
        ("EncryptionKeyArn", "ENCRYPT_DECRYPT", "SYMMETRIC_DEFAULT"),
        ("SigningKeyArn", "SIGN_VERIFY", "RSA_3072"),
    ]:
        key = kms.describe_key(KeyId=config[name])["KeyMetadata"]
        demand(
            key.get("KeyState") == "Enabled"
            and key.get("KeyUsage") == usage
            and key.get("KeySpec") == key_spec
            and key.get("Arn") == config[name]
        )
    pool = cognito.describe_user_pool(UserPoolId=config["PoolId"])["UserPool"]
    demand(pool.get("MfaConfiguration") == "ON" and pool.get("UserPoolTier") == "ESSENTIALS")
    demand(pool.get("AdminCreateUserConfig", {}).get("AllowAdminCreateUserOnly") is True)
    demand(
        pool.get("AccountRecoverySetting", {}).get("RecoveryMechanisms")
        == [{"Name": "admin_only", "Priority": 1}]
    )
    domain = cognito.describe_user_pool_domain(Domain="retiro-e1-028364485203")["DomainDescription"]
    demand(domain.get("UserPoolId") == config["PoolId"] and domain.get("ManagedLoginVersion") == 2)
    verifier = ExternalVerifier(
        s3,
        kms,
        bucket,
        config["SigningKeyArn"],
        config["EncryptionKeyArn"],
        workers=workers,
        deadline=deadline,
        progress=progress,
    )
    report = None
    # An in-flight checkpoint is not accepted as a hole; wait a bounded interval for completion.
    for attempt in range(15):
        remaining()
        try:
            report = verifier.verify(minimum_sequence=minimum_sequence)
            break
        except IntegrityFailure:
            print(json.dumps({"phase": "external_chain_retry", "attempt": attempt + 1}), flush=True)
            remaining()
            time.sleep(2)
    demand(report is not None)
    assert report is not None
    remaining()
    denied(
        kms.sign,
        KeyId=config["SigningKeyArn"],
        MessageType="DIGEST",
        SigningAlgorithm="RSASSA_PSS_SHA_256",
        Message=hashlib.sha256(b"E1 denied probe").digest(),
    )
    # A random, separate prefix cannot overwrite an archive/checkpoint even if IAM drifts.
    remaining()
    denied(
        s3.put_object,
        Bucket=bucket,
        Key="acceptance-denied-probes/" + uuid.uuid4().hex,
        Body=b"synthetic permission probe",
        IfNoneMatch="*",
        ServerSideEncryption="aws:kms",
        SSEKMSKeyId=config["EncryptionKeyArn"],
    )
    checkpoint = f"checkpoints/{report['last_sequence']:020d}.json"
    remaining()
    head = s3.head_object(Bucket=bucket, Key=checkpoint)
    demand(
        head.get("ObjectLockMode") == "COMPLIANCE"
        and head.get("ObjectLockRetainUntilDate") is not None
        and head["ObjectLockRetainUntilDate"] > datetime.now(UTC) + timedelta(days=1)
    )
    # Exact retained COMPLIANCE version is immutable even for account administration.
    remaining()
    denied(s3.delete_object, Bucket=bucket, Key=checkpoint, VersionId=head["VersionId"])
    remaining()
    denied(
        s3.put_object_retention,
        Bucket=bucket,
        Key=checkpoint,
        VersionId=head["VersionId"],
        Retention={
            "Mode": "COMPLIANCE",
            "RetainUntilDate": datetime.now(UTC) + timedelta(minutes=1),
        },
    )
    remaining()
    return {
        "passed": True,
        "e1_accepted": False,
        "scope": (
            "Real Cognito configuration and independent S3/KMS archive; "
            "SQL-copy recovery and browser flows are separate"
        ),
        "checked_at": datetime.now(UTC).isoformat(),
        "checks": {
            "cognito_managed_login_mfa": True,
            "seven_day_compliance": True,
            "versioning_private_kms": True,
            "keys_enabled_distinct": True,
            "independent_sign_put_delete_retention_denied": True,
        },
        "external_high_water": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum-sequence", type=int, default=1)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--max-seconds", type=int, default=480)
    options = parser.parse_args()
    if options.minimum_sequence < 1:
        parser.error("A positive external high-water mark is required")
    if not 1 <= options.max_seconds <= 480:
        parser.error("Verification duration must be between one and 480 seconds")
    Path("work").mkdir(exist_ok=True)
    try:
        report = verify(options.minimum_sequence, options.workers, options.max_seconds)
    except VerificationDeadlineExceeded:
        report = {"passed": False, "e1_accepted": False, "error": "verification_deadline_exceeded"}
    except ClientError as exc:
        report = {
            "passed": False,
            "e1_accepted": False,
            "error": "aws_operation_failed",
            "operation": exc.operation_name,
            "code": exc.response["Error"]["Code"],
        }
    except Exception:
        report = {"passed": False, "e1_accepted": False, "error": "cloud_verification_failed"}
    Path("work/e1-cloud-acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    print("E1 independent cloud checks: " + ("PASS" if report["passed"] else "FAIL"))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
