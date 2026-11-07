import argparse
import hashlib
import json
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--kind", required=True, choices=["development-apk", "backend-oci"])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--digest")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("a full commit SHA is required")
    if args.kind == "backend-oci" and not re.fullmatch(r"sha256:[0-9a-f]{64}", args.digest or ""):
        parser.error("backend OCI manifest digest is required (not the archive checksum)")
    with args.artifact.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    data = {
        "schema_version": 1,
        "git_sha": args.sha,
        "kind": args.kind,
        "filename": args.artifact.name,
        "sha256": checksum,
        "oci_digest": args.digest,
        "pickup_enabled": False,
        "distribution": "private-development-only",
    }
    args.artifact.with_suffix(args.artifact.suffix + ".json").write_text(
        json.dumps(data, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
