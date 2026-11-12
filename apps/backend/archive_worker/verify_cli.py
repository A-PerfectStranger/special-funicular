"""External verifier process: AWS read/Verify credentials only, no Django or SQL."""

import argparse
import json
import os
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config

from archive_worker.verifier import ExternalVerifier


def load_snapshot(path: Path | None) -> list[dict[str, Any]] | None:
    if path is None:
        return None
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Snapshot exceeds limit")
    snapshot = json.loads(path.read_text())
    if not isinstance(snapshot, list) or not all(isinstance(row, dict) for row in snapshot):
        raise ValueError("Invalid snapshot")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum-sequence", type=int, required=True)
    parser.add_argument("--database-snapshot", type=Path)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    args = parser.parse_args()
    if args.minimum_sequence < 1:
        raise ValueError("External high-water mark required")
    options = Config(
        connect_timeout=3,
        read_timeout=10,
        retries={"mode": "standard", "total_max_attempts": 2},
        max_pool_connections=8,
    )
    verifier = ExternalVerifier(
        boto3.client("s3", config=options),
        boto3.client("kms", config=options),
        os.environ["ARCHIVE_BUCKET"],
        os.environ["MANIFEST_KMS_KEY_ARN"],
        os.environ["ARCHIVE_KMS_KEY_ARN"],
        workers=args.workers,
    )
    print(json.dumps(verifier.verify(args.minimum_sequence, load_snapshot(args.database_snapshot))))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print('{"passed":false,"error":"INTEGRITY_FAILURE"}')
        raise SystemExit(2) from None
