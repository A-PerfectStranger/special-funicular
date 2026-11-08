"""Real AWS WORM adapter: immutable versions, exact-byte verification and external anchors."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_kms import KMSClient
    from mypy_boto3_s3 import S3Client


class ArchiveUnavailable(Exception):
    pass


class IntegrityFailure(ArchiveUnavailable):
    pass


def canonical_manifest(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


@dataclass(frozen=True)
class ProtectedObject:
    key: str
    version: str
    digest: str
    retained_until: datetime


@dataclass(frozen=True)
class ArchiveConfiguration:
    bucket: str
    encryption_key: str
    signing_key: str
    region: str
    retention_days: int

    @classmethod
    def configured(cls) -> ArchiveConfiguration:
        config = cls(
            os.environ.get("ARCHIVE_BUCKET", ""),
            os.environ.get("ARCHIVE_KMS_KEY_ARN", ""),
            os.environ.get("MANIFEST_KMS_KEY_ARN", ""),
            os.environ.get("AWS_REGION", ""),
            int(os.environ.get("ARCHIVE_RETENTION_DAYS", "0")),
        )
        if not all([config.bucket, config.encryption_key, config.signing_key, config.region]) or (
            config.retention_days != 7
            or config.encryption_key == config.signing_key
            or os.environ.get("APP_ENV") != "staging"
        ):
            # This configuration is only approved for synthetic staging, never production.
            raise ArchiveUnavailable()
        return config


class WormArchive:
    def __init__(self, config: ArchiveConfiguration, s3: S3Client, kms: KMSClient):
        self.config, self.s3, self.kms = config, s3, kms

    @classmethod
    def configured(cls) -> WormArchive:
        config = ArchiveConfiguration.configured()
        timeout = Config(connect_timeout=1, read_timeout=1, retries={"total_max_attempts": 1})
        return cls(
            config,
            boto3.client("s3", region_name=config.region, config=timeout),
            boto3.client("kms", region_name=config.region, config=timeout),
        )

    def inspect(self, key: str, version: str, expected: bytes) -> ProtectedObject:
        if not version or version == "null":
            raise IntegrityFailure()
        try:
            response = self.s3.get_object(Bucket=self.config.bucket, Key=key, VersionId=version)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"NoSuchKey", "NoSuchVersion", "404"}:
                raise IntegrityFailure() from None
            raise ArchiveUnavailable() from None
        body = response["Body"]
        try:
            actual = body.read(len(expected) + 1)
        finally:
            body.close()
        retained = response.get("ObjectLockRetainUntilDate")
        modified = response.get("LastModified")
        if (
            response.get("VersionId") != version
            or actual != expected
            or response.get("ObjectLockMode") != "COMPLIANCE"
            or retained is None
            or modified is None
            or retained <= datetime.now(UTC)
            or retained < modified + timedelta(days=self.config.retention_days, seconds=-1)
            or response.get("ServerSideEncryption") != "aws:kms"
            or response.get("SSEKMSKeyId") != self.config.encryption_key
        ):
            raise IntegrityFailure()
        return ProtectedObject(key, version, hashlib.sha256(actual).hexdigest(), retained)

    def put_once(self, key: str, payload: bytes) -> ProtectedObject:
        try:
            response = self.s3.put_object(
                Bucket=self.config.bucket,
                Key=key,
                Body=payload,
                IfNoneMatch="*",
                ContentType="application/json",
                ChecksumSHA256=base64.b64encode(hashlib.sha256(payload).digest()).decode(),
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=self.config.encryption_key,
                # The bucket enforces COMPLIANCE/7 days. This principal cannot
                # call PutObjectRetention, including through per-object headers.
            )
            version = response.get("VersionId", "")
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in {"PreconditionFailed", "412"}:
                raise ArchiveUnavailable() from None
            # Crash after PUT: recover the existing version, then verify its exact bytes.
            version = self.s3.head_object(Bucket=self.config.bucket, Key=key).get("VersionId", "")
        return self.inspect(key, version, payload)

    def signed_anchor(self, key: str, content: dict[str, Any]) -> ProtectedObject:
        encoded = canonical_manifest(content)
        # RSA PSS SHA-256 is randomized: recover an existing envelope before signing again.
        try:
            existing = self.s3.get_object(Bucket=self.config.bucket, Key=key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in {"NoSuchKey", "404"}:
                raise ArchiveUnavailable() from None
        else:
            stream = existing["Body"]
            try:
                payload = stream.read(65537)
            finally:
                stream.close()
            if len(payload) > 65536:
                raise IntegrityFailure()
            envelope = json.loads(payload)
            if envelope.get("content") != content:
                raise IntegrityFailure()
            self.verify_signature(envelope)
            return self.inspect(key, existing.get("VersionId", ""), payload)
        signature = self.kms.sign(
            KeyId=self.config.signing_key,
            Message=hashlib.sha256(encoded).digest(),
            MessageType="DIGEST",
            SigningAlgorithm="RSASSA_PSS_SHA_256",
        )["Signature"]
        envelope = {
            "content": content,
            "algorithm": "RSASSA_PSS_SHA_256",
            "key_arn": self.config.signing_key,
            "signature": base64.b64encode(signature).decode(),
        }
        payload = canonical_manifest(envelope)
        try:
            return self.put_once(key, payload)
        except IntegrityFailure:
            # Another valid worker may have won the conditional PUT with a different PSS salt.
            existing = self.s3.get_object(Bucket=self.config.bucket, Key=key)
            stream = existing["Body"]
            try:
                payload = stream.read(65537)
            finally:
                stream.close()
            other = json.loads(payload)
            if other.get("content") != content:
                raise IntegrityFailure() from None
            self.verify_signature(other)
            return self.inspect(key, existing.get("VersionId", ""), payload)

    def verify_signature(self, envelope: dict[str, Any]) -> None:
        if (
            envelope.get("key_arn") != self.config.signing_key
            or envelope.get("algorithm") != "RSASSA_PSS_SHA_256"
        ):
            raise IntegrityFailure()
        valid = self.kms.verify(
            KeyId=self.config.signing_key,
            Message=hashlib.sha256(canonical_manifest(envelope["content"])).digest(),
            MessageType="DIGEST",
            SigningAlgorithm="RSASSA_PSS_SHA_256",
            Signature=base64.b64decode(envelope["signature"], validate=True),
        )
        if not valid.get("SignatureValid"):
            raise IntegrityFailure()

    def archive(
        self, payload: bytes, digest: str, sequence: int
    ) -> tuple[ProtectedObject, ProtectedObject]:
        if hashlib.sha256(payload).hexdigest() != digest:
            raise IntegrityFailure()
        event = json.loads(payload)
        if event["sequence"] != sequence or event["canonical_format"] != "pg-jsonb-utf8-v1":
            raise IntegrityFailure()
        protected = self.put_once(f"events/{sequence:020d}/{event['id']}.json", payload)
        manifest = self.signed_anchor(
            f"manifests/{sequence:020d}.json",
            {
                "schema_version": 1,
                "sequence": sequence,
                "event_id": event["id"],
                "event_key": protected.key,
                "event_version": protected.version,
                "digest": digest,
                "previous_digest": event["previous_digest"],
                "retained_until": protected.retained_until.isoformat(),
            },
        )
        self.signed_anchor(
            f"checkpoints/{sequence:020d}.json",
            {
                "schema_version": 1,
                "sequence": sequence,
                "manifest_key": manifest.key,
                "manifest_version": manifest.version,
                "manifest_digest": manifest.digest,
            },
        )
        return protected, manifest
