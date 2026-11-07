import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.image_manifest import main


def write_oci(tmp_path: Path, *, corrupt: bool = False) -> tuple[str, str]:
    sha = "a" * 40
    config = json.dumps({"config": {"Labels": {"org.opencontainers.image.revision": sha}}}).encode()
    config_digest = "sha256:" + hashlib.sha256(config).hexdigest()
    manifest = json.dumps({"config": {"digest": config_digest}}).encode()
    manifest_digest = "sha256:" + hashlib.sha256(manifest).hexdigest()
    files = {
        "index.json": json.dumps({"manifests": [{"digest": manifest_digest}]}).encode(),
        "blobs/sha256/" + manifest_digest[7:]: manifest,
        "blobs/sha256/" + config_digest[7:]: b"tampered" if corrupt else config,
    }
    (tmp_path / "artifacts").mkdir()
    with tarfile.open(tmp_path / f"artifacts/backend-{sha}.oci.tar", "w") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return config_digest, manifest_digest


def test_manifest_links_exact_config_and_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_digest, manifest_digest = write_oci(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["image_manifest.py", "a" * 40])
    with patch("scripts.image_manifest.subprocess.check_output", return_value=config_digest):
        main()
    release = json.loads(Path("artifacts/image.json").read_text())
    assert release["digest"] == manifest_digest
    assert release["config_digest"] == config_digest
    with patch("scripts.image_manifest.subprocess.check_output", return_value="sha256:wrong"):
        with pytest.raises(ValueError, match="difiere"):
            main()


def test_corrupt_blob_rejected_before_running_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_oci(tmp_path, corrupt=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["image_manifest.py", "a" * 40])
    with patch("scripts.image_manifest.subprocess.check_output") as inspect:
        with pytest.raises(ValueError, match="Digest OCI no coincide"):
            main()
        inspect.assert_not_called()
