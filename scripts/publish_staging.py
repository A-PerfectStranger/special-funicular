"""Publish the approved CI OCI archive, preserving and verifying its exact digest."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def finish(report: dict[str, Any]) -> int:
    Path("work/published-image.json").write_text(json.dumps(report, indent=2) + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
            for field in ["git_sha", "oci_digest", "image"]:
                stream.write(field + "=" + str(report[field]) + "\n")
    print(json.dumps(report))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, type=int)
    args = parser.parse_args()
    repo = "A-PerfectStranger/special-funicular"
    run = json.loads(
        subprocess.check_output(["gh", "api", f"repos/{repo}/actions/runs/{args.run_id}"])
    )
    if (
        run["conclusion"] != "success"
        or run["name"] != "E0 CI"
        or run["head_branch"] != "main"
        or run["event"] != "push"
        or run["head_repository"]["full_name"] != repo
    ):
        raise SystemExit("BLOCKED: a successful main push E0 CI run is required")
    sha = run["head_sha"]
    if not re.fullmatch("[0-9a-f]{40}", sha):
        raise SystemExit("BLOCKED: SHA")
    directory = Path("work/release")
    directory.mkdir(parents=True, exist_ok=False)
    subprocess.run(
        [
            "gh",
            "run",
            "download",
            str(args.run_id),
            "--repo",
            repo,
            "--name",
            "backend-" + sha,
            "--dir",
            str(directory),
        ],
        check=True,
    )
    archive = directory / "backend.oci.tar"
    manifest = json.loads((directory / "backend.oci.tar.json").read_text())
    with archive.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    digest = manifest["oci_digest"]
    if (
        manifest["git_sha"] != sha
        or manifest["kind"] != "backend-oci"
        or manifest["sha256"] != checksum
        or manifest.get("pickup_enabled") is not False
        or not re.fullmatch("sha256:[0-9a-f]{64}", digest)
    ):
        raise SystemExit("BLOCKED: artifact provenance/checksum")
    registry = "028364485203.dkr.ecr.us-east-1.amazonaws.com"
    repository = registry + "/retiro-staging/backend"
    report = {
        "git_sha": sha,
        "oci_digest": digest,
        "image": repository + "@" + digest,
        "ci_run_id": args.run_id,
    }
    existing = subprocess.run(
        [
            "aws",
            "ecr",
            "describe-images",
            "--repository-name",
            "retiro-staging/backend",
            "--image-ids",
            "imageTag=" + sha,
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if existing.returncode == 0:
        if json.loads(existing.stdout)["imageDetails"][0]["imageDigest"] != digest:
            raise SystemExit("BLOCKED: immutable tag already names a different digest")
        return finish(report)
    if "ImageNotFoundException" not in existing.stderr:
        raise SystemExit("BLOCKED: registry lookup failed; absence not established")
    with tempfile.TemporaryDirectory(prefix="retiro-registry-") as temporary:
        auth = str(Path(temporary) / "auth.json")
        password = subprocess.check_output(
            ["aws", "ecr", "get-login-password", "--region", "us-east-1"]
        )
        subprocess.run(
            [
                "skopeo",
                "login",
                "--authfile",
                auth,
                "--username",
                "AWS",
                "--password-stdin",
                registry,
            ],
            input=password,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "skopeo",
                "copy",
                "--all",
                "--preserve-digests",
                "--authfile",
                auth,
                "oci-archive:" + str(archive),
                "docker://" + repository + ":" + sha,
            ],
            check=True,
        )
    result = json.loads(
        subprocess.check_output(
            [
                "aws",
                "ecr",
                "describe-images",
                "--repository-name",
                "retiro-staging/backend",
                "--image-ids",
                "imageTag=" + sha,
                "--output",
                "json",
            ]
        )
    )
    if result["imageDetails"][0]["imageDigest"] != digest:
        raise SystemExit("BLOCKED: registry digest changed")
    return finish(report)


if __name__ == "__main__":
    raise SystemExit(main())
