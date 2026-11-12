"""Authenticated, versioned staging APK custody. Never creates public or presigned links."""

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from scripts.aws_cli import aws
from scripts.commission_e1 import outputs, validate_operator
from scripts.sync_staging_origin import gateway_origin, release_origin

ACCOUNT = "028364485203"
BUCKET = f"retiro-internal-mobile-{ACCOUNT}-us-east-1"


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_manifest(data: Any, sha: str) -> dict[str, Any]:
    if (
        not re.fullmatch(r"[0-9a-f]{40}", sha)
        or not isinstance(data, dict)
        or data.get("schema_version") != 1
        or data.get("git_sha") != sha
        or data.get("kind") != "staging-apk"
        or data.get("filename") != f"mobile-staging-{sha}.apk"
        or data.get("pickup_enabled") is not False
        or data.get("distribution") != "private-development-only"
        or data.get("storage_layout") != "sha256-v1"
        or not re.fullmatch(
            r"https://[a-z0-9-]+\.ecs\.us-east-1\.on\.aws", str(data.get("release_origin", ""))
        )
        or not re.fullmatch(r"[0-9a-f]{64}", str(data.get("sha256", "")))
        or not re.fullmatch(r"[0-9a-f]{64}", str(data.get("firebase_config_sha256", "")))
    ):
        raise RuntimeError("BLOCKED: exact Firebase-configured staging APK manifest required")
    return data


def object_prefix(sha: str, digest: str) -> str:
    # A recreated gateway or repeated native build can change the APK's bytes
    # without changing the source commit. Keep every binary immutable by digest.
    return f"staging/{sha}/{digest}/"


def require_live_release(sha: str, origin: str) -> None:
    """Operator-only read: reject an APK whose pinned endpoint was retired or replaced."""
    service = aws(
        "ecs",
        "describe-express-gateway-service",
        "--service-arn",
        "arn:aws:ecs:us-east-1:028364485203:service/retiro-staging/retiro-api",
    )["service"]
    if gateway_origin(service) != origin:
        raise RuntimeError("BLOCKED: APK does not match the live staging release")
    task = aws(
        "ecs",
        "describe-task-definition",
        "--task-definition",
        service["activeConfigurations"][0]["taskDefinitionArn"],
    )["taskDefinition"]
    containers = task.get("containerDefinitions", [])
    if len(containers) != 1:
        raise RuntimeError("BLOCKED: APK does not match the live staging release")
    env = {value["name"]: value["value"] for value in containers[0].get("environment", [])}
    image = containers[0].get("image", "")
    images = aws(
        "ecr",
        "describe-images",
        "--repository-name",
        "retiro-staging/backend",
        "--image-ids",
        "imageTag=" + sha,
    ).get("imageDetails", [])
    if (
        env.get("GIT_SHA") != sha
        or env.get("E1_IDENTITY_ENABLED") != "true"
        or env.get("E2_FAMILY_ENABLED") != "true"
        or len(images) != 1
        or image
        != "028364485203.dkr.ecr.us-east-1.amazonaws.com/retiro-staging/backend@"
        + images[0].get("imageDigest", "")
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", images[0].get("imageDigest", ""))
    ):
        raise RuntimeError("BLOCKED: APK does not match the live staging release")


def destination(s3: Any) -> tuple[str, str]:
    configured = outputs("retiro-staging-operations")
    bucket, key = configured["MobileBucket"], configured["MobileEncryptionKeyArn"]
    if bucket != BUCKET or not re.fullmatch(
        rf"arn:aws:kms:us-east-1:{ACCOUNT}:key/[0-9a-f-]{{36}}", key
    ):
        raise RuntimeError("BLOCKED: unexpected private mobile destination")
    args = {"Bucket": bucket, "ExpectedBucketOwner": ACCOUNT}
    protection = s3.get_public_access_block(**args)["PublicAccessBlockConfiguration"]
    if (
        any(
            protection.get(name) is not True
            for name in [
                "BlockPublicAcls",
                "BlockPublicPolicy",
                "IgnorePublicAcls",
                "RestrictPublicBuckets",
            ]
        )
        or s3.get_bucket_policy_status(**args)["PolicyStatus"]["IsPublic"] is not False
    ):
        raise RuntimeError("BLOCKED: bucket public access protection required")
    rules = s3.get_bucket_encryption(**args)["ServerSideEncryptionConfiguration"]["Rules"]
    if (
        len(rules) != 1
        or rules[0].get("ApplyServerSideEncryptionByDefault")
        != {"SSEAlgorithm": "aws:kms", "KMSMasterKeyID": key}
        or s3.get_bucket_versioning(**args).get("Status") != "Enabled"
    ):
        raise RuntimeError("BLOCKED: exact encryption and versioning required")
    tags = {item["Key"]: item["Value"] for item in s3.get_bucket_tagging(**args)["TagSet"]}
    if any(
        tags.get(k) != v
        for k, v in {
            "Project": "retiro-seguro",
            "Environment": "staging",
            "Data": "internal-apk",
        }.items()
    ):
        raise RuntimeError("BLOCKED: internal staging bucket tags required")
    policy = json.loads(s3.get_bucket_policy(**args)["Policy"])
    required = {
        "NoBearerDownloadLinks": (
            ["s3:GetObject", "s3:GetObjectVersion"],
            f"arn:aws:s3:::{bucket}/*",
            {"StringEquals": {"s3:authType": "REST-QUERY-STRING"}},
        ),
        "WriteOnceArtifactNames": (
            "s3:PutObject",
            f"arn:aws:s3:::{bucket}/staging/*",
            {"StringNotEquals": {"s3:if-none-match": "*"}},
        ),
    }
    for sid, (actions, resource, condition) in required.items():
        if not any(
            statement.get("Sid") == sid
            and statement.get("Effect") == "Deny"
            and statement.get("Principal") == "*"
            and statement.get("Condition") == condition
            and statement.get("Action") == actions
            and statement.get("Resource") == resource
            for statement in policy.get("Statement", [])
        ):
            raise RuntimeError("BLOCKED: authenticated immutable artifact policy required")
    return bucket, key


def read_object(s3: Any, bucket: str, key: str, encryption: str) -> tuple[Any, str]:
    value = s3.get_object(Bucket=bucket, Key=key, ExpectedBucketOwner=ACCOUNT)
    version = value.get("VersionId")
    if (
        not isinstance(version, str)
        or version == "null"
        or not version
        or value.get("ServerSideEncryption") != "aws:kms"
        or value.get("SSEKMSKeyId") != encryption
    ):
        value["Body"].close()
        raise RuntimeError("BLOCKED: object version/encryption not proven")
    return value["Body"], version


def publish_object(s3: Any, bucket: str, encryption: str, key: str, path: Path) -> str:
    expected = checksum(path)
    with path.open("rb") as stream:
        try:
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=stream,
                ExpectedBucketOwner=ACCOUNT,
                IfNoneMatch="*",
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=encryption,
                ChecksumSHA256=base64.b64encode(bytes.fromhex(expected)).decode("ascii"),
                ContentType="application/json"
                if path.suffix == ".json"
                else "application/vnd.android.package-archive",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "PreconditionFailed":
                raise
            # Safe retry: an existing name must have exactly the same bytes.
    body, version = read_object(s3, bucket, key, encryption)
    try:
        actual = hashlib.file_digest(body, "sha256").hexdigest()
    finally:
        body.close()
    if actual != expected:
        raise RuntimeError("BLOCKED: artifact name conflict or readback checksum mismatch")
    return version


def publish(s3: Any, sha: str) -> dict[str, Any]:
    if (
        os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_REPOSITORY") != "A-PerfectStranger/special-funicular"
        or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != sha
        or subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    ):
        raise RuntimeError("BLOCKED: clean exact trusted main source required")
    identity = aws("sts", "get-caller-identity")
    if identity.get("Account") != ACCOUNT or not identity.get("Arn", "").startswith(
        f"arn:aws:sts::{ACCOUNT}:assumed-role/retiro-staging-MobilePublisher/"
    ):
        raise RuntimeError("BLOCKED: isolated MobilePublisher identity required")
    apk = Path(f"work/artifacts/mobile-staging-{sha}.apk")
    manifest = apk.with_suffix(".apk.json")
    data = validate_manifest(json.loads(manifest.read_text()), sha)
    if data["release_origin"] != release_origin():
        raise RuntimeError("BLOCKED: APK manifest differs from the verified build origin")
    if checksum(apk) != data["sha256"]:
        raise RuntimeError("BLOCKED: local APK does not match its manifest")
    bucket, encryption = destination(s3)
    prefix = object_prefix(sha, data["sha256"])
    versions = {
        path.name: publish_object(s3, bucket, encryption, prefix + path.name, path)
        for path in [apk, manifest]
    }
    return {
        "sha": sha,
        "bucket": bucket,
        "versions": versions,
        "object_prefix": prefix,
        "apk_sha256": data["sha256"],
        "release_origin": data["release_origin"],
        "private_published": True,
        "installed_on_android": False,
        "e4_accepted": False,
        "e5_accepted": False,
    }


def download(s3: Any, sha: str, expected_checksum: str) -> dict[str, Any]:
    validate_operator(aws("sts", "get-caller-identity"))
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_checksum
    ):
        raise RuntimeError("BLOCKED: exact release SHA and trusted Actions checksum required")
    bucket, encryption = destination(s3)
    name = f"mobile-staging-{sha}.apk"
    prefix = object_prefix(sha, expected_checksum)
    body, _ = read_object(s3, bucket, prefix + name + ".json", encryption)
    try:
        raw_manifest = body.read(16385)
    finally:
        body.close()
    if len(raw_manifest) > 16384:
        raise RuntimeError("BLOCKED: oversized artifact manifest")
    manifest = validate_manifest(json.loads(raw_manifest), sha)
    if manifest["sha256"] != expected_checksum:
        raise RuntimeError("BLOCKED: stored manifest differs from trusted Actions checksum")
    require_live_release(sha, manifest["release_origin"])
    directory = Path("work/mobile-download")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    path = directory / name
    body, version = read_object(s3, bucket, prefix + name, encryption)
    temporary = path.with_suffix(".part")
    try:
        with temporary.open("wb") as stream:
            temporary.chmod(0o600)
            while chunk := body.read(1024 * 1024):
                stream.write(chunk)
        if checksum(temporary) != manifest["sha256"]:
            raise RuntimeError("BLOCKED: downloaded APK checksum mismatch")
        temporary.replace(path)
    finally:
        body.close()
        temporary.unlink(missing_ok=True)
    with path.with_suffix(".apk.json").open("w") as stream:
        os.chmod(stream.name, 0o600)
        stream.write(json.dumps(manifest, indent=2) + "\n")
    return {
        "sha": sha,
        "apk": str(path.resolve()),
        "sha256": manifest["sha256"],
        "version": version,
        "release_origin": manifest["release_origin"],
        "installed_on_android": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["publish", "download"])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    if args.action == "download" and not args.expected_sha256:
        parser.error("download requires --expected-sha256 from this release's Actions manifest")
    s3 = boto3.Session(region_name="us-east-1").client("s3")
    report = (
        publish(s3, args.sha)
        if args.action == "publish"
        else download(s3, args.sha, args.expected_sha256)
    )
    if args.action == "publish":
        Path("work/artifacts/private-mobile.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


def failure_report(error: Exception) -> dict[str, str]:
    """Return fixed diagnostics; exception messages and remote payloads stay private."""
    known = {
        "BLOCKED: clean exact trusted main source required": ("source", "SOURCE_NOT_REVIEWED"),
        "BLOCKED: isolated MobilePublisher identity required": ("identity", "PUBLISHER_REQUIRED"),
        "BLOCKED: exact Firebase-configured staging APK manifest required": (
            "manifest",
            "CONFIGURED_MANIFEST_REQUIRED",
        ),
        "BLOCKED: local APK does not match its manifest": ("local_integrity", "CHECKSUM_MISMATCH"),
        "BLOCKED: APK manifest differs from the verified build origin": (
            "manifest",
            "BUILD_ORIGIN_MISMATCH",
        ),
        "BLOCKED: APK does not match the live staging release": (
            "release",
            "LIVE_RELEASE_MISMATCH",
        ),
        "BLOCKED: active observed Express service required": ("release", "LIVE_GATEWAY_REQUIRED"),
        "BLOCKED: single active gateway origin required": ("release", "LIVE_GATEWAY_REQUIRED"),
        "BLOCKED: unexpected private mobile destination": ("storage", "DESTINATION_MISMATCH"),
        "BLOCKED: bucket public access protection required": (
            "public_access",
            "PROTECTION_REQUIRED",
        ),
        "BLOCKED: exact encryption and versioning required": (
            "encryption",
            "ENCRYPTION_OR_VERSIONING_MISMATCH",
        ),
        "BLOCKED: internal staging bucket tags required": ("storage_tags", "TAGS_MISMATCH"),
        "BLOCKED: authenticated immutable artifact policy required": (
            "storage_policy",
            "POLICY_MISMATCH",
        ),
        "BLOCKED: object version/encryption not proven": ("object_metadata", "CUSTODY_NOT_PROVEN"),
        "BLOCKED: artifact name conflict or readback checksum mismatch": (
            "readback",
            "ARTIFACT_CONFLICT_OR_CHECKSUM_MISMATCH",
        ),
        "BLOCKED: exact release SHA and trusted Actions checksum required": (
            "download_source",
            "TRUSTED_SOURCE_REQUIRED",
        ),
        "BLOCKED: oversized artifact manifest": ("download_manifest", "MANIFEST_TOO_LARGE"),
        "BLOCKED: stored manifest differs from trusted Actions checksum": (
            "download_manifest",
            "TRUSTED_CHECKSUM_MISMATCH",
        ),
        "BLOCKED: downloaded APK checksum mismatch": ("download_integrity", "CHECKSUM_MISMATCH"),
    }
    stage, code = known.get(str(error), ("private_transfer", "LOCAL_OR_RESPONSE_ERROR"))
    report = {"status": "BLOCKED", "stage": stage, "code": code}
    aws_codes = {
        "AccessDenied",
        "AccessDeniedException",
        "ExpiredToken",
        "ExpiredTokenException",
        "InvalidAccessKeyId",
        "SignatureDoesNotMatch",
        "NoSuchBucket",
        "NoSuchKey",
        "NoSuchBucketPolicy",
        "NoSuchTagSet",
        "PreconditionFailed",
        "ConditionalRequestConflict",
        "InvalidArgument",
        "ValidationError",
        "ResourceNotFoundException",
        "ThrottlingException",
        "SlowDown",
        "InternalError",
        "ServiceUnavailable",
        "KMS.DisabledException",
        "KMS.NotFoundException",
        "KMS.AccessDeniedException",
        "CliRequestFailed",
    }
    if isinstance(error, ClientError):
        aws_code = error.response.get("Error", {}).get("Code", "")
        report.update(stage="aws", code=aws_code if aws_code in aws_codes else "AWS_REQUEST_FAILED")
        operations = {
            "GetPublicAccessBlock",
            "GetBucketPolicyStatus",
            "GetBucketEncryption",
            "GetBucketVersioning",
            "GetBucketTagging",
            "GetBucketPolicy",
            "PutObject",
            "GetObject",
        }
        report["operation"] = (
            error.operation_name if error.operation_name in operations else "AwsRequest"
        )
    elif isinstance(error, RuntimeError):
        match = re.fullmatch(
            r"(sts\.get-caller-identity|cloudformation\.describe-stacks|"
            r"ecs\.describe-express-gateway-service|ecs\.describe-task-definition|ecr\.describe-images)"
            r": ([A-Za-z0-9_]{1,64})",
            str(error),
        )
        if match:
            report.update(
                stage="aws",
                operation=match[1],
                code=match[2] if match[2] in aws_codes else "AWS_REQUEST_FAILED",
            )
    return report


def cli() -> int:
    try:
        return main()
    except Exception as error:
        print(json.dumps(failure_report(error)))
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
