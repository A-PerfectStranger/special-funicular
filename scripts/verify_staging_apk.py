"""Fail a staging APK build if its actual bundle/native manifest has stale public config."""

import argparse
import json
import os
import zipfile
from pathlib import Path


def verify(path: Path) -> None:
    origin = json.loads(Path("infra/environments/staging.json").read_text())["base_url"]
    if os.environ.get("EXPO_PUBLIC_API_URL") != origin:
        raise RuntimeError("Reviewed staging origin required")
    with zipfile.ZipFile(path) as apk:
        bundle = apk.read("assets/index.android.bundle")
        manifest = apk.read("AndroidManifest.xml")
    if any(
        value.encode() not in bundle
        for value in [
            origin,
            "retiro-seguro-staging://auth/callback",
        ]
    ):
        raise RuntimeError("Staging bundle is missing the reviewed API/callback")
    for value in ["org.retiroseguro.staging", "retiro-seguro-staging"]:
        if value.encode() not in manifest and value.encode("utf-16-le") not in manifest:
            raise RuntimeError("Staging native package/scheme missing")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    args = parser.parse_args()
    verify(args.apk)
    print("Actual staging APK bundle, package and callback: PASS; no device-test claim")
