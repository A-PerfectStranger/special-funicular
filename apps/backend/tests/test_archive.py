"""AT05/06 adapter regression with real RSA-PSS, simulated AWS storage (not acceptance)."""

import io
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from archive_worker.storage import ArchiveConfiguration, IntegrityFailure, WormArchive
from archive_worker.verifier import ExternalVerifier
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


@pytest.fixture
def archive() -> tuple[WormArchive, MemoryS3, ExternalVerifier]:
    s3, kms = MemoryS3(), MemoryKMS()
    config = ArchiveConfiguration(
        "synthetic-bucket", "encryption-key", "signing-key", "us-east-1", 7
    )
    adapter = WormArchive(config, s3, kms)  # type: ignore[arg-type]
    verifier = ExternalVerifier(s3, kms, config.bucket, config.signing_key, config.encryption_key)  # type: ignore[arg-type]
    return adapter, s3, verifier


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
