"""Verify SHA/config of the OCI artifact against the loaded image, without rebuilding."""

import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path


def main() -> None:
    sha = sys.argv[1]
    archive_path = Path("artifacts") / f"backend-{sha}.oci.tar"
    with tarfile.open(archive_path) as archive:

        def read_blob(digest: str) -> bytes:
            algorithm, value = digest.split(":", 1)
            if algorithm != "sha256" or len(value) != 64:
                raise ValueError("Digest OCI invalido")
            stream = archive.extractfile(f"blobs/sha256/{value}")
            if stream is None:
                raise ValueError("Blob OCI ausente")
            data = stream.read()
            if hashlib.sha256(data).hexdigest() != value:
                raise ValueError("Digest OCI no coincide")
            return data

        index_file = archive.extractfile("index.json")
        if index_file is None:
            raise ValueError("Indice OCI ausente")
        index = json.load(index_file)
        if len(index["manifests"]) != 1:
            raise ValueError("Se esperaba una imagen de plataforma unica sin attestations")
        descriptor = index["manifests"][0]
        manifest = json.loads(read_blob(descriptor["digest"]))
        config = json.loads(read_blob(manifest["config"]["digest"]))
        if config["config"]["Labels"]["org.opencontainers.image.revision"] != sha:
            raise ValueError("SHA OCI no coincide")
        loaded_id = subprocess.check_output(  # noqa: S603
            ["docker", "image", "inspect", f"retiro-backend:{sha}", "--format", "{{.Id}}"],  # noqa: S607
            text=True,
        ).strip()
        if loaded_id != manifest["config"]["digest"]:
            raise ValueError("Imagen cargada difiere de la configuracion OCI")
        Path("artifacts/image.json").write_text(
            json.dumps(
                {
                    "sha": sha,
                    "digest": descriptor["digest"],
                    "config_digest": loaded_id,
                    "processes": ["api", "worker-check-only"],
                },
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
