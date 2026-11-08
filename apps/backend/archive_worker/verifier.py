"""Independent verifier: S3 and KMS Verify credentials only, no database dependency."""

import base64
import hashlib
import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from archive_worker.storage import IntegrityFailure, canonical_manifest

if TYPE_CHECKING:
    from mypy_boto3_kms import KMSClient
    from mypy_boto3_s3 import S3Client


class SnapshotDivergence(IntegrityFailure):
    """The supplied SQL copy differs from the successfully read external evidence."""


class ExternalVerifier:
    def __init__(
        self,
        s3: "S3Client",
        kms: "KMSClient",
        bucket: str,
        trusted_signing_key: str,
        encryption_key: str,
    ):
        self.s3, self.kms, self.bucket = s3, kms, bucket
        self.trusted_key, self.encryption_key = trusted_signing_key, encryption_key

    def read(self, key: str, version: str | None = None) -> tuple[bytes, str]:
        from botocore.exceptions import ClientError

        try:
            response = (
                self.s3.get_object(Bucket=self.bucket, Key=key, VersionId=version)
                if version
                else self.s3.get_object(Bucket=self.bucket, Key=key)
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"NoSuchKey", "NoSuchVersion", "404"}:
                raise IntegrityFailure() from None
            raise
        stream = response["Body"]
        try:
            payload = stream.read(65537)
        finally:
            stream.close()
        actual_version = response.get("VersionId", "")
        retained = response.get("ObjectLockRetainUntilDate")
        modified = response.get("LastModified")
        if (
            len(payload) > 65536
            or not actual_version
            or actual_version == "null"
            or (version and actual_version != version)
            or response.get("ObjectLockMode") != "COMPLIANCE"
            or retained is None
            or modified is None
            or retained < modified + timedelta(days=7, seconds=-1)
            or (
                response.get("ServerSideEncryption") != "aws:kms"
                or response.get("SSEKMSKeyId") != self.encryption_key
            )
        ):
            raise IntegrityFailure()
        return payload, actual_version

    def signed(self, payload: bytes) -> dict[str, Any]:
        envelope = json.loads(payload)
        if (
            envelope.get("algorithm") != "RSASSA_PSS_SHA_256"
            or envelope.get("key_arn") != self.trusted_key
        ):
            raise IntegrityFailure()
        result = self.kms.verify(
            KeyId=self.trusted_key,
            MessageType="DIGEST",
            SigningAlgorithm="RSASSA_PSS_SHA_256",
            Message=hashlib.sha256(canonical_manifest(envelope["content"])).digest(),
            Signature=base64.b64decode(envelope["signature"], validate=True),
        )
        if not result.get("SignatureValid"):
            raise IntegrityFailure()
        return dict(envelope["content"])

    def verify(
        self, minimum_sequence: int = 1, database_snapshot: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        keys: set[str] = set()
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix="checkpoints/"):
            keys.update(item["Key"] for item in page.get("Contents", []) if "Key" in item)
        if not keys:
            raise IntegrityFailure()
        previous = "0" * 64
        event_ids: set[str] = set()
        snapshot: dict[int, dict[str, Any]] | None = None
        if database_snapshot is not None:
            snapshot = {}
            for record in database_snapshot:
                sequence = record.get("sequence")
                if type(sequence) is not int or sequence < 1 or sequence in snapshot:
                    raise SnapshotDivergence()
                snapshot[sequence] = record
            if len(snapshot) != len(keys):
                raise SnapshotDivergence()
        for sequence, key in enumerate(sorted(keys), 1):
            if key != f"checkpoints/{sequence:020d}.json":
                raise IntegrityFailure()
            checkpoint = self.signed(self.read(key)[0])
            if checkpoint.get("sequence") != sequence:
                raise IntegrityFailure()
            manifest_payload, _ = self.read(
                checkpoint["manifest_key"], checkpoint["manifest_version"]
            )
            if hashlib.sha256(manifest_payload).hexdigest() != checkpoint["manifest_digest"]:
                raise IntegrityFailure()
            manifest = self.signed(manifest_payload)
            event_payload, _ = self.read(manifest["event_key"], manifest["event_version"])
            digest = hashlib.sha256(event_payload).hexdigest()
            event = json.loads(event_payload)
            if (
                manifest.get("sequence") != sequence
                or event.get("sequence") != sequence
                or event.get("id") != manifest.get("event_id")
                or event["id"] in event_ids
                or manifest.get("digest") != digest
                or event.get("previous_digest") != previous
                or manifest.get("previous_digest") != previous
                or event.get("canonical_format") != "pg-jsonb-utf8-v1"
            ):
                raise IntegrityFailure()
            if snapshot is not None:
                copied = snapshot.get(sequence)
                if not copied or copied.get("event_id") != event["id"]:
                    raise SnapshotDivergence()
                # Treat every byte and hash from the database copy as untrusted.
                encoded = copied.get("canonical_base64")
                if not isinstance(encoded, str) or len(encoded) > 90000:
                    raise SnapshotDivergence()
                if (
                    base64.b64decode(encoded, validate=True) != event_payload
                    or copied.get("digest") != digest
                ):
                    raise SnapshotDivergence()
            previous = digest
            event_ids.add(event["id"])
        # Callers persist a previous external high-water mark, never a DB-derived default.
        if len(keys) < minimum_sequence:
            raise IntegrityFailure()
        return {
            "passed": True,
            "verified_events": len(keys),
            "last_sequence": len(keys),
            "last_digest": previous,
            "database_used": False,
            "database_snapshot_compared": snapshot is not None,
        }
