"""Independent comparison with immutable private original and rewritten SQL copies."""

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
from archive_worker.storage import IntegrityFailure
from archive_worker.verifier import ExternalVerifier, SnapshotDivergence

from scripts.commission_e1 import outputs
from scripts.e1_snapshot_data import validate_local_chain


def retained_json(s3: Any, config: dict[str, str], reference: dict[str, str], maximum: int) -> Any:
    response = s3.get_object(
        Bucket=config["Bucket"], Key=reference["key"], VersionId=reference["version"]
    )
    stream = response["Body"]
    try:
        payload = stream.read(maximum + 1)
    finally:
        stream.close()
    if (
        len(payload) > maximum
        or response.get("VersionId") != reference["version"]
        or reference["version"] == "null"
        or response.get("ObjectLockMode") != "COMPLIANCE"
        or response.get("ServerSideEncryption") != "aws:kms"
        or response.get("SSEKMSKeyId") != config["EncryptionKeyArn"]
        or not response.get("LastModified")
        or not response.get("ObjectLockRetainUntilDate")
        or response["ObjectLockRetainUntilDate"]
        < response["LastModified"] + timedelta(days=7, seconds=-1)
        or response["ObjectLockRetainUntilDate"] <= datetime.now(UTC)
        or hashlib.sha256(payload).hexdigest() != reference["sha256"]
    ):
        raise IntegrityFailure()
    return json.loads(payload)


def compare_copies(
    verifier: ExternalVerifier,
    original: list[dict[str, Any]],
    rewritten: list[dict[str, Any]],
    minimum_sequence: int,
) -> dict[str, Any]:
    anchored = verifier.verify(minimum_sequence, original)
    try:
        verifier.verify(minimum_sequence, rewritten)
    except SnapshotDivergence:
        return anchored
    raise IntegrityFailure()


def verify(
    report_key: str, report_version: str, report_hash: str, minimum_sequence: int
) -> dict[str, Any]:
    match = re.fullmatch(r"acceptance-snapshots/reports/([0-9a-f]{32})\.json", report_key)
    if not match or not re.fullmatch("[0-9a-f]{64}", report_hash) or minimum_sequence < 1:
        raise IntegrityFailure()
    session = boto3.Session(region_name="us-east-1")
    caller = session.client("sts").get_caller_identity()
    if caller["Account"] != "028364485203" or not caller["Arn"].startswith(
        "arn:aws:sts::028364485203:assumed-role/retiro-staging-E1Verifier/"
    ):
        raise IntegrityFailure()
    config = outputs("retiro-staging-e1")
    s3, kms = session.client("s3"), session.client("kms")
    report = retained_json(
        s3, config, {"key": report_key, "version": report_version, "sha256": report_hash}, 4096
    )
    if report.get("synthetic_only") is not True or report.get("schema_version") != 1:
        raise IntegrityFailure()
    boundaries = report.get("boundary_checks")
    if (
        not isinstance(boundaries, dict)
        or not boundaries
        or any(value is not True for value in boundaries.values())
    ):
        raise IntegrityFailure()
    snapshots = []
    for name in ["original", "rewritten"]:
        reference = report[name]
        if reference["key"] != f"acceptance-snapshots/{name}/{match[1]}.json":
            raise IntegrityFailure()
        rows = retained_json(s3, config, reference, 16 * 1024 * 1024)
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise IntegrityFailure()
        validate_local_chain(rows)
        snapshots.append(rows)
    original, rewritten = snapshots
    if original == rewritten or len(original) != len(rewritten):
        raise IntegrityFailure()
    verifier = ExternalVerifier(
        s3, kms, config["Bucket"], config["SigningKeyArn"], config["EncryptionKeyArn"]
    )
    anchored = compare_copies(verifier, original, rewritten, minimum_sequence)
    return {
        "passed": True,
        "e1_accepted": False,
        "sql_credentials_used": False,
        "operator_inspected_boundaries": boundaries,
        "original_matches_external_archive": True,
        "rewritten_local_chain_valid": True,
        "external_rejected_rewritten_copy": True,
        "external_high_water": anchored,
        "checked_at": datetime.now(UTC).isoformat(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-key", required=True)
    parser.add_argument("--report-version", required=True)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--minimum-sequence", required=True, type=int)
    arguments = parser.parse_args()
    Path("work").mkdir(exist_ok=True)
    try:
        result = verify(
            arguments.report_key,
            arguments.report_version,
            arguments.report_sha256,
            arguments.minimum_sequence,
        )
    except Exception:
        result = {"passed": False, "e1_accepted": False, "error": "recovery_verification_failed"}
    Path("work/e1-recovery-acceptance.json").write_text(json.dumps(result, indent=2) + "\n")
    print("E1 independent SQL-copy recovery: " + ("PASS" if result["passed"] else "FAIL"))
    raise SystemExit(0 if result["passed"] else 2)
