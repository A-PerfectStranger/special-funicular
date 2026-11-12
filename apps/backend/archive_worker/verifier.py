"""Independent verifier: S3 and KMS Verify credentials only, no database dependency."""

import base64
import hashlib
import json
import time
from collections import deque
from collections.abc import Callable, Generator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from archive_worker.storage import IntegrityFailure, canonical_manifest

if TYPE_CHECKING:
    from mypy_boto3_kms import KMSClient
    from mypy_boto3_s3 import S3Client


class SnapshotDivergence(IntegrityFailure):
    """The supplied SQL copy differs from the successfully read external evidence."""


class VerificationDeadlineExceeded(RuntimeError):
    """Verification stopped without accepting a partial chain."""


@dataclass(frozen=True)
class _VerifiedRecord:
    event_id: str
    payload: bytes
    digest: str
    previous: str
    manifest_previous: str


class ExternalVerifier:
    def __init__(
        self,
        s3: "S3Client",
        kms: "KMSClient",
        bucket: str,
        trusted_signing_key: str,
        encryption_key: str,
        *,
        workers: int = 1,
        deadline: float | None = None,
        progress: Callable[[int, int], None] | None = None,
    ):
        if type(workers) is not int or not 1 <= workers <= 8:
            raise ValueError("Verification workers must be between one and eight")
        self.s3, self.kms, self.bucket = s3, kms, bucket
        self.trusted_key, self.encryption_key = trusted_signing_key, encryption_key
        self.workers, self.deadline, self.progress = workers, deadline, progress

    def remaining(self) -> None:
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise VerificationDeadlineExceeded()

    def read(self, key: str, version: str | None = None) -> tuple[bytes, str]:
        from botocore.exceptions import ClientError

        self.remaining()
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
        self.remaining()
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
        self.remaining()
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

    def record(self, sequence: int, key: str) -> _VerifiedRecord:
        checkpoint = self.signed(self.read(key)[0])
        if type(checkpoint.get("sequence")) is not int or checkpoint["sequence"] != sequence:
            raise IntegrityFailure()
        manifest_payload, _ = self.read(checkpoint["manifest_key"], checkpoint["manifest_version"])
        if hashlib.sha256(manifest_payload).hexdigest() != checkpoint["manifest_digest"]:
            raise IntegrityFailure()
        manifest = self.signed(manifest_payload)
        event_payload, _ = self.read(manifest["event_key"], manifest["event_version"])
        digest = hashlib.sha256(event_payload).hexdigest()
        event = json.loads(event_payload)
        event_previous, manifest_previous = (
            event.get("previous_digest"),
            manifest.get("previous_digest"),
        )
        if (
            type(manifest.get("sequence")) is not int
            or manifest["sequence"] != sequence
            or type(event.get("sequence")) is not int
            or event["sequence"] != sequence
            or not isinstance(event.get("id"), str)
            or not event["id"]
            or event["id"] != manifest.get("event_id")
            or manifest.get("digest") != digest
            or event.get("canonical_format") != "pg-jsonb-utf8-v1"
            or not isinstance(event_previous, str)
            or not isinstance(manifest_previous, str)
        ):
            raise IntegrityFailure()
        return _VerifiedRecord(
            event["id"],
            event_payload,
            digest,
            event_previous,
            manifest_previous,
        )

    def records(self, keys: list[str]) -> Generator[_VerifiedRecord, None, None]:
        if self.workers == 1:
            for sequence, key in enumerate(keys, 1):
                yield self.record(sequence, key)
            return
        items = iter(enumerate(keys, 1))
        # SDK clients are shared, read-only and thread-safe. Bound submitted
        # futures as well as running threads; never queue the entire archive.
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            pending: deque[Future[_VerifiedRecord]] = deque()
            try:
                for sequence, key in items:
                    pending.append(pool.submit(self.record, sequence, key))
                    if len(pending) == self.workers * 2:
                        break
                while pending:
                    self.remaining()
                    yield pending.popleft().result()
                    item = next(items, None)
                    if item is not None:
                        pending.append(pool.submit(self.record, *item))
            finally:
                for future in pending:
                    future.cancel()

    def verify(
        self, minimum_sequence: int = 1, database_snapshot: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        keys: set[str] = set()
        self.remaining()
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix="checkpoints/"):
            self.remaining()
            keys.update(item["Key"] for item in page.get("Contents", []) if "Key" in item)
        ordered = sorted(keys)
        if (
            not ordered
            or len(ordered) < minimum_sequence
            or any(
                key != f"checkpoints/{sequence:020d}.json"
                for sequence, key in enumerate(ordered, 1)
            )
        ):
            raise IntegrityFailure()
        if self.progress is not None:
            self.progress(0, len(ordered))
        previous = "0" * 64
        event_ids: set[str] = set()
        snapshot: dict[int, dict[str, Any]] | None = None
        if database_snapshot is not None:
            snapshot = {}
            for copied_record in database_snapshot:
                sequence = copied_record.get("sequence")
                if type(sequence) is not int or sequence < 1 or sequence in snapshot:
                    raise SnapshotDivergence()
                snapshot[sequence] = copied_record
            if len(snapshot) != len(keys):
                raise SnapshotDivergence()
        with closing(self.records(ordered)) as records:
            for sequence, record in enumerate(records, 1):
                self.remaining()
                if (
                    record.event_id in event_ids
                    or record.previous != previous
                    or record.manifest_previous != previous
                ):
                    raise IntegrityFailure()
                if snapshot is not None:
                    copied = snapshot.get(sequence)
                    if not copied or copied.get("event_id") != record.event_id:
                        raise SnapshotDivergence()
                    # Treat every byte and hash from the database copy as untrusted.
                    encoded = copied.get("canonical_base64")
                    if not isinstance(encoded, str) or len(encoded) > 90000:
                        raise SnapshotDivergence()
                    if (
                        base64.b64decode(encoded, validate=True) != record.payload
                        or copied.get("digest") != record.digest
                    ):
                        raise SnapshotDivergence()
                previous = record.digest
                event_ids.add(record.event_id)
                if self.progress is not None:
                    self.progress(sequence, len(ordered))
        # Callers persist a previous external high-water mark, never a DB-derived default.
        if len(event_ids) != len(keys) or len(keys) < minimum_sequence:
            raise IntegrityFailure()
        self.remaining()
        return {
            "passed": True,
            "verified_events": len(keys),
            "last_sequence": len(keys),
            "last_digest": previous,
            "database_used": False,
            "database_snapshot_compared": snapshot is not None,
        }
