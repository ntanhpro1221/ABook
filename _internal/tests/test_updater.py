"""Bộ cập nhật của bản Qt (webui/updater.py) trước một trang phát hành giả trên 127.0.0.1, ký bằng khoá THỬ: bản mới được báo;
cùng bản / bản cũ là "latest"; mất mạng, JSON hỏng là câu NETWORK; tải xong + chữ ký khớp đúng bản thì nhờ vỏ chạy bộ cài; chữ
ký sai, khoá khác, chữ ký của bản khác, đường tải đứng yên đều bị từ chối và không bao giờ tới bước chạy bộ cài."""
from __future__ import annotations

import base64
import hashlib
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from abook.webui import updater
from abook.webui.updater import Updater, config, newer

INTERNAL = Path(__file__).resolve().parents[1]
SETUP = b"MZ fake ABook installer " * 4000


def _b64(*lines: str) -> str:
    return base64.b64encode(("\n".join(lines) + "\n").encode()).decode()


def _key() -> tuple[Ed25519PrivateKey, str]:
    secret = Ed25519PrivateKey.generate()
    raw = secret.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return secret, _b64("untrusted comment: minisign public key", base64.b64encode(b"Ed" + b"testkey1" + raw).decode())


def _sign(secret: Ed25519PrivateKey, data: bytes, version: str) -> str:
    trusted = f"timestamp:1\tfile:ABook_{version}_x64-setup.exe\tversion:{version}"
    signature = secret.sign(hashlib.blake2b(data, digest_size=64).digest())
    return _b64("untrusted comment: signature from tauri secret key", base64.b64encode(b"ED" + b"testkey1" + signature).decode(),
                "trusted comment: " + trusted, base64.b64encode(secret.sign(signature + trusted.encode())).decode())


class Site:
    """Trang phát hành giả: /latest.json và mọi đường tận cùng `_x64-setup.exe` (trừ dưới /missing/); `stall_after` byte thì
    đứng yên `stall_for` giây rồi đóng. `requests`: các đường đã được hỏi."""

    def __init__(self) -> None:
        self.manifest: bytes = b"{}"
        self.setup = SETUP
        self.stall_after: int | None = None
        self.stall_for = 0.0
        self.requests: list[str] = []
        site = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_GET(self) -> None:
                site.requests.append(self.path)
                package = self.path.endswith("_x64-setup.exe") and not self.path.startswith("/missing/")
                body = site.manifest if self.path == "/latest.json" else site.setup if package else None
                if body is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if site.stall_after is not None and package:
                    self.wfile.write(body[:site.stall_after])
                    self.wfile.flush()
                    time.sleep(site.stall_for)
                    return
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def publish(self, version: str, signature: str, url: str | None = None) -> None:
        url = url or f"{self.url}/download/ABook_{version}_x64-setup.exe"
        self.manifest = json.dumps({"version": version, "notes": "Sửa lỗi", "platforms": {
            "windows-x86_64": {"url": url, "signature": signature}}}).encode()

    def packages(self) -> list[str]:
        return [path for path in self.requests if path != "/latest.json"]


@pytest.fixture
def site():
    server = Site()
    yield server
    server.server.shutdown()


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("ABOOK_UPDATE_URL", raising=False)


class Shell:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.found: list[dict] = []
        self.logs: list[str] = []

    def events(self, name: str) -> list:
        return [m["detail"] for m in self.sent if m.get("event") == name]

    def installers(self) -> list[dict]:
        return [m for m in self.sent if "run_installer" in m]


def _updater(site: Site, shell: Shell, key: str, tmp_path: Path, version: str = "1.2.3", **kw) -> Updater:
    return Updater(version, shell.sent.append, shell.found.append, {"endpoints": [f"{site.url}/latest.json"], "pubkey": key},
                   folder=tmp_path / "dl", log=shell.logs.append, **kw)


@pytest.mark.parametrize("a, b, expected", [
    ("0.4.150", "0.4.149", True), ("0.4.149", "0.4.149", False), ("0.4.148", "0.4.149", False), ("0.5.0", "0.4.999", True),
    ("v0.4.150", "0.4.149", True), ("0.4.150-rc1", "0.4.150", False), ("0.4.150", "0.4.150-rc1", True),
    ("0.4.10", "0.4.9", True), ("rác", "0.4.149", False), ("0.4.150", "", False)])
def test_newer(a, b, expected):
    assert newer(a, b) is expected


def test_config_comes_from_tauri_conf_or_the_packaged_copy(tmp_path):
    tauri = json.loads((INTERNAL / "shell/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))["plugins"]["updater"]
    assert config() == {"endpoints": tauri["endpoints"], "pubkey": tauri["pubkey"]}
    (tmp_path / "updater.json").write_text(json.dumps({"endpoints": ["https://x/latest.json"], "pubkey": "k"}), encoding="utf-8")
    assert config(tmp_path) == {"endpoints": ["https://x/latest.json"], "pubkey": "k"}


def test_newer_release_is_reported_then_installed(site, tmp_path):
    secret, key = _key()
    site.publish("1.2.4", _sign(secret, SETUP, "1.2.4"))
    shell = Shell()
    up = _updater(site, shell, key, tmp_path)
    up.check(manual=True)
    assert shell.found == [{"version": "1.2.4", "notes": "Sửa lỗi"}]
    assert shell.events(updater.CHECKED_EVENT) == [{"state": "found"}]
    up.install()
    [run] = shell.installers()
    assert run["args"] == ["/P", "/UPDATE", "/R"]
    assert Path(run["run_installer"]).read_bytes() == SETUP
    assert Path(run["run_installer"]) == tmp_path / "dl" / "ABook_1.2.4_x64-setup.exe"
    assert not list((tmp_path / "dl").glob("*.part"))
    assert shell.events(updater.FAILED_EVENT) == []


def test_same_or_older_release_is_latest(site, tmp_path):
    secret, key = _key()
    shell = Shell()
    for version in ("1.2.3", "1.2.2"):
        site.publish(version, _sign(secret, SETUP, version))
        _updater(site, shell, key, tmp_path).check(manual=True)
    assert shell.found == []
    assert shell.events(updater.CHECKED_EVENT) == [{"state": "latest"}, {"state": "latest"}]


def test_startup_check_is_silent(site, tmp_path):
    secret, key = _key()
    shell = Shell()
    site.manifest = b"not json"
    _updater(site, shell, key, tmp_path).check(manual=False)
    site.publish("1.2.3", _sign(secret, SETUP, "1.2.3"))
    _updater(site, shell, key, tmp_path).check(manual=False)
    assert shell.sent == [] and shell.found == []


@pytest.mark.parametrize("manifest", [b"not json", b"{}", b'{"version": "9.9.9"}', b'{"version": "9.9.9", "platforms": {}}'])
def test_broken_manifest_is_a_network_failure(site, tmp_path, manifest):
    _secret, key = _key()
    site.manifest = manifest
    shell = Shell()
    _updater(site, shell, key, tmp_path).check(manual=True)
    assert shell.events(updater.CHECKED_EVENT) == [{"state": "failed", "message": updater.NETWORK}]
    assert shell.found == [] and shell.logs


def test_no_network_is_a_network_failure(tmp_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    shell = Shell()
    up = Updater("1.2.3", shell.sent.append, shell.found.append, {"endpoints": [f"http://127.0.0.1:{port}/latest.json"],
                 "pubkey": "k"}, folder=tmp_path, log=shell.logs.append)
    up.check(manual=True)
    assert shell.events(updater.CHECKED_EVENT) == [{"state": "failed", "message": updater.NETWORK}]


def test_override_url_replaces_the_endpoints(site, tmp_path, monkeypatch):
    secret, key = _key()
    site.publish("1.2.4", _sign(secret, SETUP, "1.2.4"))
    monkeypatch.setenv("ABOOK_UPDATE_URL", f"{site.url}/latest.json")
    shell = Shell()
    Updater("1.2.3", shell.sent.append, shell.found.append, {"endpoints": ["http://127.0.0.1:9/none"], "pubkey": key},
            folder=tmp_path, log=shell.logs.append).check(manual=True)
    assert shell.found == [{"version": "1.2.4", "notes": "Sửa lỗi"}]


def _refused(site: Site, tmp_path: Path, key: str, signature: str, version: str = "1.2.4") -> Shell:
    site.publish(version, signature)
    shell = Shell()
    up = _updater(site, shell, key, tmp_path)
    up.check()
    assert shell.found, "bản mới phải được thấy trước đã"
    up.install()
    assert shell.installers() == []
    assert not list((tmp_path / "dl").glob("*")), "gói không khớp chữ ký không được nằm lại"
    return shell


def test_wrong_signature_is_refused(site, tmp_path):
    secret, key = _key()
    raw = base64.b64decode(_sign(secret, SETUP, "1.2.4")).decode().splitlines()
    sig = bytearray(base64.b64decode(raw[1]))
    sig[30] ^= 0x01
    broken = _b64(raw[0], base64.b64encode(bytes(sig)).decode(), raw[2], raw[3])
    assert _refused(site, tmp_path, key, broken).events(updater.FAILED_EVENT) == [updater.SIGNATURE]


def test_other_key_is_refused(site, tmp_path):
    secret, _key_a = _key()
    _other, key_b = _key()
    assert _refused(site, tmp_path, key_b, _sign(secret, SETUP, "1.2.4")).events(updater.FAILED_EVENT) == [updater.SIGNATURE]


def test_changed_installer_is_refused(site, tmp_path):
    secret, key = _key()
    site.setup = SETUP[:-1] + b"?"
    assert _refused(site, tmp_path, key, _sign(secret, SETUP, "1.2.4")).events(updater.FAILED_EVENT) == [updater.SIGNATURE]


def test_signature_of_another_version_is_refused(site, tmp_path):
    """latest.json nói 1.2.4 mà chữ ký là của gói 1.2.3 đã ký thật: không cài (chặn đẩy lùi bằng gói cũ)."""
    secret, key = _key()
    assert _refused(site, tmp_path, key, _sign(secret, SETUP, "1.2.3")).events(updater.FAILED_EVENT) == [updater.SIGNATURE]


def test_stalled_download_is_refused(site, tmp_path):
    secret, key = _key()
    site.publish("1.2.4", _sign(secret, SETUP, "1.2.4"))
    site.stall_after, site.stall_for = 1000, 3.0
    shell = Shell()
    up = _updater(site, shell, key, tmp_path, stall=0.5)
    up.check()
    started = time.monotonic()
    up.install()
    assert time.monotonic() - started < 2.5
    assert shell.events(updater.FAILED_EVENT) == [updater.STALLED]
    assert shell.installers() == [] and not list((tmp_path / "dl").glob("*"))
    # Bấm lại được: lần sau mạng tốt thì cài.
    site.stall_after = None
    up.install()
    assert len(shell.installers()) == 1


def test_missing_installer_is_a_network_failure(site, tmp_path):
    secret, key = _key()
    site.publish("1.2.4", _sign(secret, SETUP, "1.2.4"), f"{site.url}/missing/ABook_1.2.4_x64-setup.exe")
    shell = Shell()
    up = _updater(site, shell, key, tmp_path)
    up.check()
    up.install()
    assert shell.events(updater.FAILED_EVENT) == [updater.NETWORK] and shell.installers() == []


def test_install_without_a_found_release_does_nothing(site, tmp_path):
    _secret, key = _key()
    shell = Shell()
    _updater(site, shell, key, tmp_path).install()
    assert shell.sent == []


def test_handle_routes_the_two_requests_and_passes_the_rest(site, tmp_path):
    secret, key = _key()
    site.publish("1.2.4", _sign(secret, SETUP, "1.2.4"))
    shell = Shell()
    up = _updater(site, shell, key, tmp_path)
    up.handle({"check_update": True})
    deadline = time.monotonic() + 10
    while not shell.events(updater.CHECKED_EVENT) and time.monotonic() < deadline:
        time.sleep(0.02)
    up.handle({"install_update": True})
    while not shell.installers() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert len(shell.installers()) == 1
    up.handle({"something": 1})
    assert shell.sent[-1] == {"something": 1}


def test_version_of_latest_json_is_always_checked(site, tmp_path, monkeypatch):
    """Lead 31-10: file_ok luôn nhận version= của latest.json, không có nhánh version=None."""
    secret, key = _key()
    seen: list[dict] = []
    real = updater.file_ok
    monkeypatch.setattr(updater, "file_ok", lambda *args, **kw: seen.append(kw) or real(*args, **kw))
    site.publish("v1.2.4", _sign(secret, SETUP, "1.2.4"), f"{site.url}/download/ABook_1.2.4_x64-setup.exe")
    shell = Shell()
    up = _updater(site, shell, key, tmp_path)
    up.check()
    up.install()
    assert seen == [{"version": "1.2.4"}] and len(shell.installers()) == 1


@pytest.mark.parametrize("last", [
    "setup.exe", "ABook_1.2.5_x64-setup.exe", "ABook_1.2.4_x64-setup.exe.bat", "abook_1.2.4_x64-setup.exe",
    "ABook_1.2.4-rc1_x64-setup.exe", "..\\x.exe", "%2e%2e%5cx.exe", "%2e%2e%2fx.exe", "ABook_1.2.4_x64-setup.exe%2f..%2fx.exe",
    "..%5CABook_1.2.4_x64-setup.exe"])
def test_odd_package_name_is_never_downloaded(site, tmp_path, last):
    """Tên gói phải đúng ABook_<số của latest.json>_x64-setup.exe: không tải, không ghi gì, trang được báo."""
    secret, key = _key()
    site.publish("1.2.4", _sign(secret, SETUP, "1.2.4"), f"{site.url}/download/{last}")
    shell = Shell()
    up = _updater(site, shell, key, tmp_path)
    up.check()
    up.install()
    assert shell.events(updater.FAILED_EVENT) == [updater.PACKAGE] and shell.installers() == []
    assert site.packages() == [] and not (tmp_path / "dl").exists()
    assert not [p for p in tmp_path.parent.rglob("x.exe")]


def test_traversal_in_the_folder_part_still_writes_inside_the_download_folder(site, tmp_path):
    """Thư mục trong URL không bao giờ thành đường ghi: chỉ tên gói (đã kiểm) ghép vào thư mục tải."""
    secret, key = _key()
    site.publish("1.2.4", _sign(secret, SETUP, "1.2.4"), f"{site.url}/%2e%2e/%2e%2e/ABook_1.2.4_x64-setup.exe")
    shell = Shell()
    up = _updater(site, shell, key, tmp_path)
    up.check()
    up.install()
    [run] = shell.installers()
    assert Path(run["run_installer"]) == tmp_path / "dl" / "ABook_1.2.4_x64-setup.exe"


@pytest.mark.parametrize("url, ok", [
    ("https://github.com/x/releases/latest/download/latest.json", True), ("http://127.0.0.1:8/latest.json", True),
    ("http://localhost:8/latest.json", True), ("http://example.com/latest.json", False), ("ftp://127.0.0.1/latest.json", False),
    ("file:///C:/latest.json", False), ("http://127.0.0.1.example.com/latest.json", False), ("https:///latest.json", False)])
def test_allowed_url(url, ok):
    assert updater.allowed_url(url) is ok


def test_plain_http_endpoint_is_refused(tmp_path, monkeypatch):
    called: list[str] = []
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda url, **kw: called.append(url))
    shell = Shell()
    Updater("1.2.3", shell.sent.append, shell.found.append, {"endpoints": ["http://example.com/latest.json"], "pubkey": "k"},
            folder=tmp_path / "dl", log=shell.logs.append).check(manual=True)
    assert called == [] and shell.found == []
    assert shell.events(updater.CHECKED_EVENT) == [{"state": "failed", "message": updater.NETWORK}]


def test_plain_http_package_is_refused(site, tmp_path):
    secret, key = _key()
    site.publish("1.2.4", _sign(secret, SETUP, "1.2.4"), "http://example.com/ABook_1.2.4_x64-setup.exe")
    shell = Shell()
    up = _updater(site, shell, key, tmp_path)
    up.check()
    up.install()
    assert shell.events(updater.FAILED_EVENT) == [updater.PACKAGE] and shell.installers() == []
    assert not (tmp_path / "dl").exists()


def test_cut_download_is_refused(site, tmp_path):
    """Máy chủ đóng giữa chừng (ít byte hơn Content-Length): không đổi tên, không kiểm chữ ký, không cài."""
    secret, key = _key()
    site.publish("1.2.4", _sign(secret, SETUP, "1.2.4"))
    site.stall_after, site.stall_for = 1000, 0.0
    shell = Shell()
    up = _updater(site, shell, key, tmp_path)
    up.check()
    up.install()
    assert shell.events(updater.FAILED_EVENT) == [updater.NETWORK] and shell.installers() == []
    assert not list((tmp_path / "dl").glob("*"))


def test_download_folder_is_rebuilt_each_time(site, tmp_path):
    """Gói cũ / tải dở cùng tên trong thư mục tải không bao giờ được dùng lại."""
    secret, key = _key()
    site.publish("1.2.4", _sign(secret, SETUP, "1.2.4"))
    (tmp_path / "dl").mkdir()
    (tmp_path / "dl" / "ABook_1.2.4_x64-setup.exe").write_bytes(b"old")
    (tmp_path / "dl" / "stale.exe").write_bytes(b"old")
    shell = Shell()
    up = _updater(site, shell, key, tmp_path)
    up.check()
    up.install()
    assert sorted(p.name for p in (tmp_path / "dl").iterdir()) == ["ABook_1.2.4_x64-setup.exe"]
    assert (tmp_path / "dl" / "ABook_1.2.4_x64-setup.exe").read_bytes() == SETUP


def test_linked_download_folder_is_refused(site, tmp_path):
    """Thư mục tải là junction: không xoá theo liên kết (đích còn nguyên), không cài."""
    import _winapi
    secret, key = _key()
    site.publish("1.2.4", _sign(secret, SETUP, "1.2.4"))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep.txt").write_text("not ours", encoding="utf-8")
    _winapi.CreateJunction(str(elsewhere), str(tmp_path / "dl"))
    shell = Shell()
    up = _updater(site, shell, key, tmp_path)
    up.check()
    up.install()
    assert shell.events(updater.FAILED_EVENT) == [updater.INSTALL] and shell.installers() == []
    assert (elsewhere / "keep.txt").read_text(encoding="utf-8") == "not ours" and site.packages() == []
