"""Prepare the exact pinned Gradle archive through its official release API."""

import argparse
import hashlib
import os
import re
import subprocess
from pathlib import Path

PIN_SOURCE = Path("apps/mobile/plugins/withPinnedGradle.cjs")
WRAPPER = Path("apps/mobile/android/gradle/wrapper/gradle-wrapper.properties")
CACHE = Path("work/native-tools")


def pin() -> tuple[str, str]:
    source = PIN_SOURCE.read_text()
    versions = re.findall(r"gradle-([0-9]+\.[0-9]+\.[0-9]+)-bin\.zip", source)
    hashes = re.findall(r"distributionSha256Sum=([0-9a-f]{64})", source)
    if len(versions) != 1 or len(hashes) != 1:
        raise ValueError("BLOCKED: unambiguous source Gradle version/checksum required")
    return versions[0], hashes[0]


def verify(archive: Path, expected: str) -> None:
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError("BLOCKED: pinned Gradle checksum mismatch")


def download() -> Path:
    version, expected = pin()
    CACHE.mkdir(parents=True, exist_ok=True)
    archive = CACHE / f"gradle-{version}-bin.zip"
    if not archive.exists():
        subprocess.run(
            [
                "gh",
                "release",
                "download",
                f"v{version}",
                "--repo",
                "gradle/gradle-distributions",
                "--pattern",
                archive.name,
                "--dir",
                str(CACHE),
            ],
            check=True,
        )
    verify(archive, expected)
    return archive.resolve()


def use(archive: Path, wrapper: Path = WRAPPER) -> None:
    version, expected = pin()
    source = wrapper.read_text()
    checksum = re.search(r"^distributionSha256Sum=([0-9a-f]{64})$", source, re.M)
    if not checksum or checksum[1] != expected or f"gradle-{version}-bin.zip" not in source:
        raise ValueError("BLOCKED: generated wrapper must match the source pin")
    verify(archive, expected)
    uri = archive.resolve().as_uri().replace(":", "\\:")
    updated, count = re.subn(
        r"^distributionUrl=.*$", lambda _: "distributionUrl=" + uri, source, flags=re.M
    )
    if count != 1:
        raise ValueError("BLOCKED: one generated distribution URL required")
    wrapper.write_text(updated)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["download", "use"])
    parser.add_argument("archive", nargs="?", type=Path)
    args = parser.parse_args()
    if args.mode == "download":
        archive = download()
        if os.environ.get("GITHUB_OUTPUT"):
            with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
                stream.write("archive=" + str(archive) + "\n")
    else:
        if args.archive is None:
            parser.error("use requires a verified local archive")
        use(args.archive)
    print("Pinned Gradle version and SHA-256 verified; no tool version change")


if __name__ == "__main__":
    main()
