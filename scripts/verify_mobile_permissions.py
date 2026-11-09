"""Inspect the merged, compiled APK permissions; source configuration alone is insufficient."""

import argparse
import os
import re
import subprocess
from pathlib import Path


def verify(path: Path) -> None:
    sdk = Path(os.environ["ANDROID_HOME"])
    aapt = sdk / "build-tools" / "36.0.0" / "aapt2"
    output = subprocess.check_output([str(aapt), "dump", "permissions", str(path)], text=True)
    permissions = set(re.findall(r"uses-permission(?:-sdk-\d+)?: name='([^']+)'", output))
    if (
        "android.permission.CAMERA" not in permissions
        or "android.permission.RECORD_AUDIO" in permissions
    ):
        raise RuntimeError("BLOCKED: actual APK must allow QR camera and exclude microphone")
    print("Actual APK camera/microphone permissions: PASS; no device-test claim")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    verify(parser.parse_args().apk)
