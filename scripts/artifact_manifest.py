import argparse
import hashlib
import json
import os
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument(
        "--kind", required=True, choices=["development-apk", "staging-apk", "backend-oci"]
    )
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
        "firebase_config_sha256": hashlib.sha256(
            Path(os.environ["ANDROID_GOOGLE_SERVICES_FILE"]).read_bytes()
        ).hexdigest()
        if os.environ.get("ANDROID_GOOGLE_SERVICES_FILE")
        else None,
    }
    if args.kind == "staging-apk":
        origin = os.environ.get("STAGING_RELEASE_ORIGIN", "")
        if not re.fullmatch(r"https://[a-z0-9-]+\.ecs\.us-east-1\.on\.aws", origin):
            parser.error("verified staging release origin required")
        data.update(storage_layout="sha256-v1", release_origin=origin)
    args.artifact.with_suffix(args.artifact.suffix + ".json").write_text(
        json.dumps(data, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
