"""AT05/06 adapter regression with real RSA-PSS, simulated AWS storage (not acceptance)."""

import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from archive_worker.storage import ArchiveConfiguration, IntegrityFailure, WormArchive
from archive_worker.verifier import ExternalVerifier, VerificationDeadlineExceeded
from botocore.exceptions import ClientError
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils


class MemoryS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}
        self.read_versions: list[str | None] = []

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        key = kwargs["Key"]
        if key in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        assert kwargs["IfNoneMatch"] == "*"
        self.objects[key] = {
            **kwargs,
            "VersionId": f"version-{len(self.objects) + 1}",
            "LastModified": datetime.now(UTC),
            "ObjectLockMode": "COMPLIANCE",
            "ObjectLockRetainUntilDate": datetime.now(UTC) + timedelta(days=7),
        }
        return {"VersionId": self.objects[key]["VersionId"]}

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self.read_versions.append(kwargs.get("VersionId"))
        if kwargs["Key"] not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        data = self.objects[kwargs["Key"]]
        if "VersionId" in kwargs and kwargs["VersionId"] != data["VersionId"]:
            raise ClientError({"Error": {"Code": "NoSuchVersion"}}, "GetObject")
        return {**data, "Body": io.BytesIO(data["Body"])}

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        return dict(self.objects[kwargs["Key"]])

    def get_paginator(self, _: str) -> "MemoryS3":
        return self

    def paginate(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [
            {
                "Contents": [
                    {"Key": key} for key in sorted(self.objects) if key.startswith(kwargs["Prefix"])
                ]
            }
        ]


class MemoryKMS:
    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def sign(self, **kwargs: Any) -> dict[str, bytes]:
        assert kwargs["SigningAlgorithm"] == "RSASSA_PSS_SHA_256"
        return {
            "Signature": self.key.sign(
                kwargs["Message"],
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
                utils.Prehashed(hashes.SHA256()),
            )
        }

    def verify(self, **kwargs: Any) -> dict[str, bool]:
        try:
            self.key.public_key().verify(
                kwargs["Signature"],
                kwargs["Message"],
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
                utils.Prehashed(hashes.SHA256()),
            )
            return {"SignatureValid": True}
        except InvalidSignature:
            return {"SignatureValid": False}


def make_archive(workers: int) -> tuple[WormArchive, MemoryS3, ExternalVerifier]:
    s3, kms = MemoryS3(), MemoryKMS()
    config = ArchiveConfiguration(
        "synthetic-bucket", "encryption-key", "signing-key", "us-east-1", 7
    )
    adapter = WormArchive(config, s3, kms)  # type: ignore[arg-type]
    verifier = ExternalVerifier(
        cast(Any, s3),
        cast(Any, kms),
        config.bucket,
        config.signing_key,
        config.encryption_key,
        workers=workers,
    )
    return adapter, s3, verifier


@pytest.fixture(params=[1, 4])
def archive(request: pytest.FixtureRequest) -> tuple[WormArchive, MemoryS3, ExternalVerifier]:
    return make_archive(request.param)


def event(sequence: int, previous: str = "0" * 64) -> tuple[bytes, str]:
    import hashlib

    payload = json.dumps(
        {
            "id": f"synthetic-event-{sequence}",
            "sequence": sequence,
            "canonical_format": "pg-jsonb-utf8-v1",
            "previous_digest": previous,
        }
    ).encode()
    return payload, hashlib.sha256(payload).hexdigest()


def test_retry_recovers_same_exact_versions_without_duplicate_objects(archive: Any) -> None:
    adapter, s3, verifier = archive
    payload, digest = event(1)
    first = adapter.archive(payload, digest, 1)
    second = adapter.archive(payload, digest, 1)
    assert first == second and len(s3.objects) == 3
    assert verifier.verify(1)["last_digest"] == digest
    assert verifier.verify(1)["database_used"] is False


def test_independent_verifier_detects_gap_and_modified_bytes(archive: Any) -> None:
    adapter, s3, verifier = archive
    payload, first_hash = event(1)
    adapter.archive(payload, first_hash, 1)
    payload2, second_hash = event(2, first_hash)
    adapter.archive(payload2, second_hash, 2)
    assert verifier.verify(2)["verified_events"] == 2
    key = next(key for key in s3.objects if key.startswith("events/00000000000000000001"))
    s3.objects[key]["Body"] = b"{}"
    with pytest.raises(IntegrityFailure):
        verifier.verify(2)
    s3.objects[key]["Body"] = payload
    del s3.objects["manifests/00000000000000000001.json"]
    with pytest.raises(IntegrityFailure):
        verifier.verify(2)


def test_missing_tail_requires_external_high_water_and_wrong_key_rejected(archive: Any) -> None:
    adapter, s3, verifier = archive
    payload, digest = event(1)
    adapter.archive(payload, digest, 1)
    with pytest.raises(IntegrityFailure):
        verifier.verify(2)
    verifier.trusted_key = "different-key"
    with pytest.raises(IntegrityFailure):
        verifier.verify(1)


def test_database_copy_rewritten_with_consistent_local_hash_is_detected(archive: Any) -> None:
    import base64
    import hashlib

    adapter, _, verifier = archive
    payload, digest = event(1)
    adapter.archive(payload, digest, 1)
    snapshot = [
        {
            "sequence": 1,
            "event_id": "synthetic-event-1",
            "digest": digest,
            "canonical_base64": base64.b64encode(payload).decode(),
        }
    ]
    assert verifier.verify(1, snapshot)["database_snapshot_compared"] is True
    forged = payload.replace(b"synthetic-event-1", b"forged-event-0001")
    snapshot[0]["digest"] = hashlib.sha256(forged).hexdigest()
    snapshot[0]["canonical_base64"] = base64.b64encode(forged).decode()
    with pytest.raises(IntegrityFailure):
        verifier.verify(1, snapshot)
    with pytest.raises(IntegrityFailure):
        verifier.verify(1, [])


@pytest.mark.parametrize("mutation", ["retention", "encryption", "bytes", "version"])
def test_adapter_never_accepts_unprotected_or_substituted_object(
    archive: Any, mutation: str
) -> None:
    adapter, s3, _ = archive
    payload, digest = event(1)
    protected, _ = adapter.archive(payload, digest, 1)
    obj = s3.objects[protected.key]
    if mutation == "retention":
        obj["ObjectLockRetainUntilDate"] = datetime.now(UTC) + timedelta(seconds=1)
    elif mutation == "encryption":
        obj["SSEKMSKeyId"] = "wrong-key"
    elif mutation == "bytes":
        obj["Body"] = b"{}"
    else:
        obj["VersionId"] = "different-version"
    with pytest.raises(IntegrityFailure):
        adapter.inspect(protected.key, protected.version, payload)


def test_rewritten_copy_with_a_valid_recomputed_chain_is_rejected(archive: Any) -> None:
    import base64
    import hashlib

    from scripts.e1_snapshot_data import rewrite_copy, validate_local_chain

    adapter, _, verifier = archive
    rows = []
    previous = "0" * 64
    for sequence in [1, 2]:
        payload = json.dumps(
            {
                "id": f"synthetic-{sequence}",
                "sequence": sequence,
                "canonical_format": "pg-jsonb-utf8-v1",
                "previous_digest": previous,
                "snapshot": {"result": "VERIFIED"},
            }
        ).encode()
        previous = hashlib.sha256(payload).hexdigest()
        adapter.archive(payload, previous, sequence)
        rows.append(
            {
                "sequence": sequence,
                "event_id": f"synthetic-{sequence}",
                "canonical_base64": base64.b64encode(payload).decode(),
                "digest": previous,
            }
        )
    rewritten = rewrite_copy(rows)
    validate_local_chain(rewritten)
    assert verifier.verify(2, rows)["database_snapshot_compared"] is True
    with pytest.raises(IntegrityFailure):
        verifier.verify(2, rewritten)


def test_parallel_volume_verifies_every_event_and_reports_ordered_progress() -> None:
    adapter, s3, verifier = make_archive(4)
    previous = "0" * 64
    for sequence in range(1, 1428):
        payload, previous = event(sequence, previous)
        adapter.archive(payload, previous, sequence)
    s3.read_versions.clear()
    progress: list[tuple[int, int]] = []
    verifier.progress = lambda done, total: progress.append((done, total))
    parallel = verifier.verify(1427)
    assert parallel["last_digest"] == previous and parallel["verified_events"] == 1427
    assert len(s3.read_versions) == 1427 * 3
    assert progress == [(done, 1427) for done in range(1428)]
    verifier.workers = 1
    assert verifier.verify(1427) == parallel


def test_verification_concurrency_and_submitted_work_are_bounded(monkeypatch: Any) -> None:
    from archive_worker import verifier as module

    adapter, _, verifier = make_archive(4)
    previous = "0" * 64
    for sequence in range(1, 17):
        payload, previous = event(sequence, previous)
        adapter.archive(payload, previous, sequence)
    lock = threading.Lock()
    entered, release = threading.Event(), threading.Event()
    active = maximum = submitted = peak_outstanding = 0
    futures: list[Any] = []
    original = verifier.record

    def record(sequence: int, key: str) -> Any:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
            if active == 4:
                entered.set()
        try:
            assert release.wait(5)
            return original(sequence, key)
        finally:
            with lock:
                active -= 1

    class TrackedPool(ThreadPoolExecutor):
        def submit(self, *args: Any, **kwargs: Any) -> Any:
            nonlocal submitted, peak_outstanding
            with lock:
                submitted += 1
                future = super().submit(*args, **kwargs)
                futures.append(future)
                peak_outstanding = max(peak_outstanding, sum(not f.done() for f in futures))
            return future

    monkeypatch.setattr(verifier, "record", record)
    monkeypatch.setattr(module, "ThreadPoolExecutor", TrackedPool)
    with ThreadPoolExecutor(max_workers=1) as coordinator:
        result = coordinator.submit(verifier.verify, 16)
        try:
            assert entered.wait(3)
            with lock:
                assert active == 4 and submitted <= 8
        finally:
            release.set()
        assert result.result(timeout=5)["verified_events"] == 16
    assert maximum == 4 and peak_outstanding <= 8 and active == 0
    assert all(f.done() for f in futures)


def test_expired_deadline_never_accepts_a_partial_chain(archive: Any) -> None:
    adapter, s3, verifier = archive
    payload, digest = event(1)
    adapter.archive(payload, digest, 1)
    s3.read_versions.clear()
    verifier.deadline = time.monotonic() - 1
    with pytest.raises(VerificationDeadlineExceeded):
        verifier.verify(1)
    assert not s3.read_versions


def test_deadline_mid_chain_stops_without_a_success_result(archive: Any) -> None:
    adapter, _, verifier = archive
    previous = "0" * 64
    for sequence in range(1, 5):
        payload, previous = event(sequence, previous)
        adapter.archive(payload, previous, sequence)

    def progress(done: int, _: int) -> None:
        if done == 1:
            verifier.deadline = time.monotonic() - 1

    verifier.progress = progress
    with pytest.raises(VerificationDeadlineExceeded):
        verifier.verify(4)


def test_gap_and_external_high_water_fail_before_reading_prefix_again(archive: Any) -> None:
    adapter, s3, verifier = archive
    payload, digest = event(1)
    adapter.archive(payload, digest, 1)
    s3.read_versions.clear()
    with pytest.raises(IntegrityFailure):
        verifier.verify(2)
    assert not s3.read_versions
    s3.objects["checkpoints/00000000000000000002.json"] = s3.objects.pop(
        "checkpoints/00000000000000000001.json"
    )
    with pytest.raises(IntegrityFailure):
        verifier.verify(1)
    assert not s3.read_versions


def test_an_incomplete_worker_stream_never_becomes_a_success_report(
    archive: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter, _, verifier = archive
    previous = "0" * 64
    for sequence in [1, 2]:
        payload, previous = event(sequence, previous)
        adapter.archive(payload, previous, sequence)

    def incomplete(keys: list[str]) -> Any:
        yield verifier.record(1, keys[0])

    monkeypatch.setattr(verifier, "records", incomplete)
    with pytest.raises(IntegrityFailure):
        verifier.verify(2)


@pytest.mark.parametrize("damage", ["duplicate_id", "broken_link", "signature"])
def test_parallel_checks_still_reject_signed_duplicates_links_and_bad_signatures(
    archive: Any, damage: str
) -> None:
    import hashlib

    adapter, s3, verifier = archive
    first, first_hash = event(1)
    adapter.archive(first, first_hash, 1)
    second, _ = event(2, first_hash if damage != "broken_link" else "f" * 64)
    if damage == "duplicate_id":
        second = second.replace(b"synthetic-event-2", b"synthetic-event-1")
    adapter.archive(second, hashlib.sha256(second).hexdigest(), 2)
    if damage == "signature":
        key = "checkpoints/00000000000000000002.json"
        envelope = json.loads(s3.objects[key]["Body"])
        envelope["signature"] = "AA=="
        s3.objects[key]["Body"] = json.dumps(envelope).encode()
    with pytest.raises(IntegrityFailure):
        verifier.verify(2)
