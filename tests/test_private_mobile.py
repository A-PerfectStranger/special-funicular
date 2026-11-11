"""Private APK custody fails closed on public storage, wrong source and conflicting retries."""

import hashlib
import io
import json
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from scripts import private_mobile as mobile

SHA = "a" * 40
KEY = "arn:aws:kms:us-east-1:028364485203:key/11111111-1111-1111-1111-111111111111"


def manifest(payload: bytes = b"synthetic apk") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "git_sha": SHA,
        "kind": "staging-apk",
        "filename": f"mobile-staging-{SHA}.apk",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "pickup_enabled": False,
        "distribution": "private-development-only",
        "firebase_config_sha256": "b" * 64,
    }


class Store:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.public = False
        self.versioning = "Enabled"
        self.encryption = KEY
        self.object_version = "version-1"
        self.policy: dict[str, Any] = {
            "Statement": [
                {
                    "Sid": "NoBearerDownloadLinks",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                    "Resource": f"arn:aws:s3:::{mobile.BUCKET}/*",
                    "Condition": {"StringEquals": {"s3:authType": "REST-QUERY-STRING"}},
                },
                {
                    "Sid": "WriteOnceArtifactNames",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:PutObject",
                    "Resource": f"arn:aws:s3:::{mobile.BUCKET}/staging/*",
                    "Condition": {"StringNotEquals": {"s3:if-none-match": "*"}},
                },
            ]
        }
        self.writes = 0

    def get_public_access_block(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": not self.public,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        }

    def get_bucket_policy_status(self, **kwargs: Any) -> dict[str, Any]:
        return {"PolicyStatus": {"IsPublic": self.public}}

    def get_bucket_encryption(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "ServerSideEncryptionConfiguration": {
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                            "KMSMasterKeyID": self.encryption,
                        }
                    }
                ]
            }
        }

    def get_bucket_versioning(self, **kwargs: Any) -> dict[str, Any]:
        return {"Status": self.versioning}

    def get_bucket_tagging(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "TagSet": [
                {"Key": k, "Value": v}
                for k, v in {
                    "Project": "retiro-seguro",
                    "Environment": "staging",
                    "Data": "internal-apk",
                }.items()
            ]
        }

    def get_bucket_policy(self, **kwargs: Any) -> dict[str, Any]:
        return {"Policy": json.dumps(self.policy)}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["ExpectedBucketOwner"] == mobile.ACCOUNT
        assert kwargs["IfNoneMatch"] == "*"
        assert kwargs["SSEKMSKeyId"] == KEY
        assert "ACL" not in kwargs
        key = kwargs["Key"]
        if key in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.writes += 1
        self.objects[key] = kwargs["Body"].read()
        return {"VersionId": self.object_version}

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["ExpectedBucketOwner"] == mobile.ACCOUNT
        return {
            "Body": io.BytesIO(self.objects[kwargs["Key"]]),
            "VersionId": self.object_version,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": self.encryption,
        }


def configure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Store:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        mobile,
        "outputs",
        lambda _: {
            "MobileBucket": mobile.BUCKET,
            "MobileEncryptionKeyArn": KEY,
        },
    )
    monkeypatch.setattr(
        mobile,
        "aws",
        lambda *a: {
            "Account": mobile.ACCOUNT,
            "Arn": f"arn:aws:iam::{mobile.ACCOUNT}:user/operator",
        },
    )
    return Store()


@pytest.mark.parametrize(
    "change",
    [
        {"git_sha": "c" * 40},
        {"filename": "../other.apk"},
        {"kind": "development-apk"},
        {"pickup_enabled": True},
        {"firebase_config_sha256": None},
        {"sha256": "invalid"},
    ],
)
def test_manifest_rejects_wrong_source_or_unconfigured_apk(change: dict[str, Any]) -> None:
    with pytest.raises(RuntimeError, match="manifest required"):
        mobile.validate_manifest({**manifest(), **change}, SHA)


@pytest.mark.parametrize(
    "field,value",
    [
        ("public", True),
        ("versioning", "Suspended"),
        ("encryption", "different-key"),
        ("policy", {"Statement": []}),
    ],
)
def test_destination_blocks_storage_drift_before_any_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, value: Any
) -> None:
    store = configure(monkeypatch, tmp_path)
    setattr(store, field, value)
    with pytest.raises(RuntimeError, match="BLOCKED"):
        mobile.destination(store)
    assert store.writes == 0


def test_policy_sid_alone_does_not_prove_protection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store = configure(monkeypatch, tmp_path)
    store.policy["Statement"][0]["Resource"] = "arn:aws:s3:::other/*"
    with pytest.raises(RuntimeError, match="policy required"):
        mobile.destination(store)


@pytest.mark.parametrize("blocked_sse_c", [False, True])
def test_destination_accepts_the_real_s3_sdk_schema_including_additional_protection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blocked_sse_c: bool
) -> None:
    store = configure(monkeypatch, tmp_path)
    client = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="synthetic",
        aws_secret_access_key="synthetic",
    )
    args = {"Bucket": mobile.BUCKET, "ExpectedBucketOwner": mobile.ACCOUNT}
    rule: dict[str, Any] = {
        # API field from GetBucketEncryption, not CloudFormation's property name.
        "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms", "KMSMasterKeyID": KEY},
        "BucketKeyEnabled": True,
    }
    if blocked_sse_c:
        rule["BlockedEncryptionTypes"] = {"EncryptionType": ["SSE-C"]}
    with Stubber(client) as stub:
        # Stubber validates all responses against the pinned botocore service
        # model. A hand-written fake using the CFN field would be rejected here.
        stub.add_response("get_public_access_block", store.get_public_access_block(), args)
        stub.add_response("get_bucket_policy_status", store.get_bucket_policy_status(), args)
        stub.add_response(
            "get_bucket_encryption", {"ServerSideEncryptionConfiguration": {"Rules": [rule]}}, args
        )
        stub.add_response("get_bucket_versioning", {"Status": "Enabled"}, args)
        stub.add_response("get_bucket_tagging", store.get_bucket_tagging(), args)
        stub.add_response("get_bucket_policy", store.get_bucket_policy(), args)
        assert mobile.destination(client) == (mobile.BUCKET, KEY)
        stub.assert_no_pending_responses()


@pytest.mark.parametrize(
    "error,expected",
    [
        (
            RuntimeError("BLOCKED: exact encryption and versioning required"),
            {"stage": "encryption", "code": "ENCRYPTION_OR_VERSIONING_MISMATCH"},
        ),
        (
            ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "private-token@example.invalid"}},
                "PutObject",
            ),
            {"stage": "aws", "code": "AccessDenied", "operation": "PutObject"},
        ),
        (
            ClientError(
                {"Error": {"Code": "private-token", "Message": "private@example.invalid"}},
                "private-operation",
            ),
            {"stage": "aws", "code": "AWS_REQUEST_FAILED", "operation": "AwsRequest"},
        ),
        (
            RuntimeError("cloudformation.describe-stacks: AccessDeniedException"),
            {
                "stage": "aws",
                "code": "AccessDeniedException",
                "operation": "cloudformation.describe-stacks",
            },
        ),
        (
            ValueError("private-token@example.invalid"),
            {"stage": "private_transfer", "code": "LOCAL_OR_RESPONSE_ERROR"},
        ),
    ],
)
def test_cli_failures_report_only_fixed_categories_and_safe_aws_codes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    expected: dict[str, str],
) -> None:
    def fail() -> int:
        raise error

    monkeypatch.setattr(mobile, "main", fail)
    assert mobile.cli() == 2
    raw = capsys.readouterr().out
    assert json.loads(raw) == {"status": "BLOCKED", **expected}
    assert "private-token" not in raw and "example.invalid" not in raw


def test_private_write_retains_safe_aws_error_details_without_printing_remote_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store = Store()
    path = tmp_path / "candidate.apk"
    path.write_bytes(b"synthetic apk")

    def denied(**kwargs: Any) -> dict[str, Any]:
        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "private-token"}}, "PutObject"
        )

    monkeypatch.setattr(store, "put_object", denied)

    def publish() -> int:
        mobile.publish_object(store, mobile.BUCKET, KEY, "staging/candidate.apk", path)
        return 0

    monkeypatch.setattr(mobile, "main", publish)
    assert mobile.cli() == 2
    raw = capsys.readouterr().out
    assert json.loads(raw)["operation"] == "PutObject"
    assert json.loads(raw)["code"] == "AccessDenied" and "private-token" not in raw
    assert not store.objects


def test_publish_retry_is_read_back_and_never_overwrites_a_conflict(tmp_path: Path) -> None:
    store = Store()
    path = tmp_path / "app.apk"
    path.write_bytes(b"first candidate")
    assert (
        mobile.publish_object(store, mobile.BUCKET, KEY, "staging/artifact.apk", path)
        == "version-1"
    )
    assert (
        mobile.publish_object(store, mobile.BUCKET, KEY, "staging/artifact.apk", path)
        == "version-1"
    )
    path.write_bytes(b"conflicting candidate")
    with pytest.raises(RuntimeError, match="conflict"):
        mobile.publish_object(store, mobile.BUCKET, KEY, "staging/artifact.apk", path)
    assert store.objects["staging/artifact.apk"] == b"first candidate" and store.writes == 1


@pytest.mark.parametrize("field,value", [("object_version", "null"), ("encryption", "other-key")])
def test_readback_rejects_unproven_custody(tmp_path: Path, field: str, value: str) -> None:
    store = Store()
    path = tmp_path / "app.apk"
    path.write_bytes(b"candidate")
    setattr(store, field, value)
    with pytest.raises(RuntimeError, match="version/encryption"):
        mobile.publish_object(store, mobile.BUCKET, KEY, "staging/artifact.apk", path)


@pytest.mark.parametrize("corrupt", [False, True])
def test_authenticated_download_verifies_bytes_before_exposing_apk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, corrupt: bool
) -> None:
    store = configure(monkeypatch, tmp_path)
    data = manifest()
    key = f"staging/{SHA}/{data['filename']}"
    store.objects[key] = b"corrupt" if corrupt else b"synthetic apk"
    store.objects[key + ".json"] = json.dumps(data).encode()
    if corrupt:
        with pytest.raises(RuntimeError, match="checksum mismatch"):
            mobile.download(store, SHA, data["sha256"])
        assert not list(tmp_path.rglob("*.apk")) and not list(tmp_path.rglob("*.part"))
    else:
        report = mobile.download(store, SHA, data["sha256"])
        path = Path(report["apk"])
        assert path.read_bytes() == b"synthetic apk"
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
        assert report["installed_on_android"] is False


def test_a_replaced_apk_and_matching_manifest_do_not_override_trusted_actions_checksum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store = configure(monkeypatch, tmp_path)
    trusted_checksum = manifest()["sha256"]
    forged = manifest(b"different signed build")
    key = f"staging/{SHA}/{forged['filename']}"
    store.objects[key] = b"different signed build"
    store.objects[key + ".json"] = json.dumps(forged).encode()
    with pytest.raises(RuntimeError, match="trusted Actions checksum"):
        mobile.download(store, SHA, trusted_checksum)
    assert not list(tmp_path.rglob("*.apk"))


def test_publisher_federation_and_manifest_are_required_before_upload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store = configure(monkeypatch, tmp_path)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "A-PerfectStranger/special-funicular")
    monkeypatch.setattr(
        mobile.subprocess, "check_output", lambda args, **kw: SHA if "rev-parse" in args else ""
    )
    with pytest.raises(RuntimeError, match="MobilePublisher identity"):
        mobile.publish(store, SHA)
    monkeypatch.setattr(
        mobile,
        "aws",
        lambda *a: {
            "Account": mobile.ACCOUNT,
            "Arn": f"arn:aws:sts::{mobile.ACCOUNT}:assumed-role/retiro-staging-MobilePublisher/job",
        },
    )
    directory = tmp_path / "work/artifacts"
    directory.mkdir(parents=True)
    data = manifest()
    path = directory / data["filename"]
    path.write_bytes(b"synthetic apk")
    path.with_suffix(".apk.json").write_text(json.dumps(data))
    report = mobile.publish(store, SHA)
    assert report["private_published"] is True and report["installed_on_android"] is False
    assert len(store.objects) == 2
    monkeypatch.setenv("GITHUB_REF", "refs/pull/32/merge")
    with pytest.raises(RuntimeError, match="trusted main"):
        mobile.publish(store, SHA)
    assert store.writes == 2
