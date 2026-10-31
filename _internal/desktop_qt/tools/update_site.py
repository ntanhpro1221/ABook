"""Trang phát hành giả trên 127.0.0.1 + khoá minisign THỬ cho các phép thử bộ cập nhật (smoke_update.py, test_installer.py).

Khoá sinh tại chỗ mỗi lượt, không bao giờ là khoá thật; định dạng như `tauri signer` (base64 của file minisign), để
webui/minisign_verify.py đọc như khoá và chữ ký thật.
"""
import base64
import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def _b64(*lines: str) -> str:
    return base64.b64encode(("\n".join(lines) + "\n").encode()).decode()


class TestKey:
    def __init__(self) -> None:
        self.secret = Ed25519PrivateKey.generate()
        self.key_id = os.urandom(8)

    def pubkey(self) -> str:
        """Như plugins.updater.pubkey của tauri.conf.json."""
        raw = self.secret.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        return _b64("untrusted comment: minisign public key of a test run", base64.b64encode(b"Ed" + self.key_id + raw).decode())

    def sign(self, data: bytes, version: str) -> str:
        """Nội dung .sig cho `data` của bản `version` (trusted comment mang version, như chữ ký của build_windows_qt.ps1)."""
        trusted = f"timestamp:1\tfile:ABook_{version}_x64-setup.exe\tversion:{version}"
        signature = self.secret.sign(hashlib.blake2b(data, digest_size=64).digest())
        return _b64("untrusted comment: signature from a test key", base64.b64encode(b"ED" + self.key_id + signature).decode(),
                    "trusted comment: " + trusted, base64.b64encode(self.secret.sign(signature + trusted.encode())).decode())


class Site:
    """latest.json + các gói, phục vụ trên 127.0.0.1 tới khi close(). `requests`: các đường đã hỏi."""

    def __init__(self) -> None:
        self.requests: list[str] = []
        self.manifest: dict = {}
        self.packages: dict[str, bytes | Path] = {}
        site = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_GET(self) -> None:
                site.requests.append(self.path)
                if self.path == "/latest.json":
                    body = json.dumps(site.manifest).encode()
                else:
                    package = site.packages.get(self.path.lstrip("/"))
                    body = package.read_bytes() if isinstance(package, Path) else package
                if body is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def publish(self, version: str, package: bytes | Path, signature: str) -> None:
        name = f"ABook_{version}_x64-setup.exe"
        self.packages = {name: package}
        self.manifest = {"version": version, "notes": "Bản thử",
                         "platforms": {"windows-x86_64": {"url": f"{self.base}/{name}", "signature": signature}}}

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
