"""E0 acceptance must fail on unsafe responses or invalid real TLS (CA-S09/13/14)."""

import json
import ssl
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from scripts.verify_staging import PROBES, validate_origin, verify


@pytest.fixture(scope="module")
def certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    directory = tmp_path_factory.mktemp("tls")
    cert, key = directory / "cert.pem", directory / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    return cert, key


@contextmanager
def endpoint(certificate: tuple[Path, Path], mode: str = "safe") -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            match = next(p for p in PROBES if p[0] == self.command and p[1] == self.path)
            status, body = match[2][0], match[3]
            headers: dict[str, str] = {}
            if mode == "redirect":
                status, headers = 302, {"Location": "https://must-not-be-followed.invalid/"}
            elif self.path == "/health/ready" and mode == "db_down":
                status, body = 503, {"status": "unavailable"}
            elif self.path == "/v1/capabilities" and mode in {"enabled", "wrong_type"}:
                body = {"api_version": "v1", "pickup_enabled": True if mode == "enabled" else 0}
            if mode == "cookie":
                headers["Set-Cookie"] = "credential=DO-NOT-RECORD"
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if mode != "missing_headers":
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header(
                    "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
                )
                self.send_header("Strict-Transport-Security", "max-age=31536000")
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        do_POST = do_GET

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    if mode == "tls12":
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(*certificate)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_safe_endpoint_with_real_tls(certificate: tuple[Path, Path]) -> None:
    with endpoint(certificate) as origin:
        report = verify(origin, ca_file=str(certificate[0]))
    assert report["passed"] is True
    assert len(report["checks"]) == len(PROBES)
    assert "release provenance not verified" in report["scope"]


@pytest.mark.parametrize(
    "mode", ["db_down", "enabled", "wrong_type", "redirect", "missing_headers", "cookie", "tls12"]
)
def test_unsafe_staging_never_passes(certificate: tuple[Path, Path], mode: str) -> None:
    with endpoint(certificate, mode) as origin:
        report = verify(origin, ca_file=str(certificate[0]))
    assert report["passed"] is False
    assert "DO-NOT-RECORD" not in json.dumps(report)
    assert "must-not-be-followed" not in json.dumps(report)


def test_untrusted_certificate_is_rejected(certificate: tuple[Path, Path]) -> None:
    with endpoint(certificate) as origin:
        report = verify(origin)
    assert report["passed"] is False
    assert all(not check["passed"] for check in report["checks"])


@pytest.mark.parametrize(
    "origin",
    [
        "http://example.com",
        "https://user:password@example.com",
        "https://example.com/path",
        "https://example.com?secret=x",
        "https://example.com#token",
        "https://example.com:invalid",
        "https://example.com/\n",
    ],
)
def test_invalid_origins_are_rejected_before_network_access(origin: str) -> None:
    with pytest.raises(ValueError):
        validate_origin(origin)
