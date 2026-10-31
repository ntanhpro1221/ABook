"""Bộ cập nhật của bản đóng gói (webui/updater.py, docs/QT_INSTALLER.md Q6) trước một trang phát hành giả trên 127.0.0.1.

Host của resources/ chạy với `--self-update`, `ABOOK_UPDATE_URL` trỏ trang giả, hồ sơ giả (LOCALAPPDATA / TEMP / USERPROFILE
riêng), không cửa sổ. Trang giả rao bản 9.9.9 với gói ký bằng khoá THỬ sinh tại chỗ. Bản đóng gói tin khoá thật
(resources/app/updater.json, chép từ tauri.conf.json), nên phải:
- thấy bản mới (sự kiện abook-update);
- bấm "Cập nhật" (POST /api/app/update) thì tải gói về rồi TỪ CHỐI nó (abook-update-failed, câu SIGNATURE);
- không bao giờ nhờ vỏ chạy bộ cài (run_installer), và không để gói nằm lại.
Ca dương (gói ký khoá thật tới tay bộ cài) là việc của Q7.

smoke_update.py <dist có resources/> [--seconds 60]   -> UPDATE_OK / UPDATE_FAIL <lý do>
smoke_packaged.py gọi `check` trên bản chép của nó.
"""
import argparse
import base64
import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

INTERNAL = Path(__file__).resolve().parents[2]
VERSION = "9.9.9"
NAME = f"ABook_{VERSION}_x64-setup.exe"
SETUP = b"MZ not an installer " * 5000


def _b64(*lines: str) -> str:
    return base64.b64encode(("\n".join(lines) + "\n").encode()).decode()


def test_signature(data: bytes, version: str) -> str:
    """Chữ ký minisign (dạng .sig của Tauri) bằng một khoá thử vừa sinh - không bao giờ là khoá thật."""
    secret = Ed25519PrivateKey.generate()
    trusted = f"timestamp:1\tfile:ABook_{version}_x64-setup.exe\tversion:{version}"
    signature = secret.sign(hashlib.blake2b(data, digest_size=64).digest())
    return _b64("untrusted comment: signature from a smoke test key", base64.b64encode(b"ED" + b"smoketst" + signature).decode(),
                "trusted comment: " + trusted, base64.b64encode(secret.sign(signature + trusted.encode())).decode())


def check(app: Path, seconds: float) -> str | None:
    """`app`: thư mục bản đóng gói (có resources/). None khi qua; không thì lý do."""
    packaged = json.loads((app / "resources/app/updater.json").read_text(encoding="utf-8"))
    tauri = json.loads((INTERNAL / "shell/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))["plugins"]["updater"]
    if packaged != {"endpoints": tauri["endpoints"], "pubkey": tauri["pubkey"]}:
        return "resources/app/updater.json khác plugins.updater của tauri.conf.json"
    requests: list[str] = []
    manifest = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def do_GET(self) -> None:
            requests.append(self.path)
            body = json.dumps(manifest).encode() if self.path == "/latest.json" else SETUP if self.path == "/" + NAME else None
            if body is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    site = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    base = f"http://127.0.0.1:{site.server_address[1]}"
    manifest.update(version=VERSION, notes="Bản thử", platforms={"windows-x86_64": {"url": f"{base}/{NAME}",
                                                                                     "signature": test_signature(SETUP, VERSION)}})
    threading.Thread(target=site.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix="abook-update-", ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        for name in ("local", "roaming", "temp", "profile"):
            (root / name).mkdir()
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("QT_", "QML", "ABOOK_"))}
        env.update(LOCALAPPDATA=str(root / "local"), APPDATA=str(root / "roaming"), TEMP=str(root / "temp"), TMP=str(root / "temp"),
                   USERPROFILE=str(root / "profile"), ABOOK_PREFERENCES=str(root / "prefs.json"),
                   ABOOK_UPDATE_URL=f"{base}/latest.json", PYTHONIOENCODING="utf-8")
        host = subprocess.Popen([str(app / "resources/python/python.exe"), "-X", "utf8", "-m", "abook.webui.host", "--self-update",
                                 "--version", "0.0.1", "--fake-runner"], cwd=str(app / "resources/app"), env=env,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        lines: queue.Queue = queue.Queue()
        seen: list[dict] = []

        def pump() -> None:
            for raw in host.stdout:
                try:
                    lines.put(json.loads(raw.decode("utf-8")))
                except ValueError:
                    pass
            lines.put(None)
        threading.Thread(target=pump, daemon=True).start()
        deadline = time.monotonic() + seconds

        def wait(want) -> dict | None:
            while time.monotonic() < deadline:
                try:
                    message = lines.get(timeout=max(0.05, deadline - time.monotonic()))
                except queue.Empty:
                    return None
                if message is None:
                    return None
                seen.append(message)
                if want(message):
                    return message
            return None

        def event(name):
            return lambda m: m.get("event") == name
        try:
            ready = wait(lambda m: "ready" in m)
            if not ready:
                return f"host không tới Ready (mã {host.poll()})"
            found = wait(event("abook-update"))
            if not found or (found.get("detail") or {}).get("version") != VERSION:
                return f"host không thấy bản {VERSION} ({found})"
            url = urllib.parse.urlsplit(ready["ready"])
            token = urllib.parse.parse_qs(url.query).get("t", [""])[0]
            request = urllib.request.Request(f"{url.scheme}://{url.netloc}/api/app/update", data=b"{}", method="POST",
                                             headers={"X-Ebook-Token": token, "Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=30) as response:
                answer = json.loads(response.read())
            if answer.get("installing") != VERSION:
                return f"POST /api/app/update trả {answer}"
            failed = wait(event("abook-update-failed"))
            if not failed or "chữ ký" not in str(failed.get("detail")):
                return f"gói ký khoá thử không bị từ chối vì chữ ký ({failed})"
            if "/" + NAME not in requests:
                return "gói không được tải - phép thử không tới bước kiểm chữ ký"
            time.sleep(1)   # một lời nhờ chạy bộ cài tới muộn vẫn phải bị thấy
            while not lines.empty():
                message = lines.get()
                if message is not None:
                    seen.append(message)
            if any("run_installer" in m for m in seen):
                return "host nhờ vỏ chạy một gói ký khoá thử"
            left = [p.name for p in (root / "temp" / "ABook-update").glob("*")] if (root / "temp" / "ABook-update").exists() else []
            if left:
                return f"gói bị từ chối còn nằm lại: {left}"
            return None
        finally:
            try:
                host.stdin.write(b'{"quit": true}\n')
                host.stdin.flush()
                host.wait(15)
            except (OSError, subprocess.TimeoutExpired):
                host.kill()
                host.wait(10)
            site.shutdown()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dist", type=Path)
    ap.add_argument("--seconds", type=float, default=60)
    args = ap.parse_args()
    dist = args.dist.resolve()
    for need in ("resources/python/python.exe", "resources/app/abook/webui/updater.py", "resources/app/updater.json"):
        if not (dist / need).is_file():
            print(f"UPDATE_FAIL thiếu {need} (build.bat package trước)")
            return 1
    # Bản chép ngoài cây nguồn, như smoke_packaged.py.
    copy = Path(tempfile.mkdtemp(prefix="abook-update-app-"))
    try:
        shutil.copytree(dist / "resources", copy / "ABook" / "resources")
        why = check(copy / "ABook", args.seconds)
    finally:
        shutil.rmtree(copy, ignore_errors=True)
    print("UPDATE_OK gói ký khoá thử bị từ chối, không chạy bộ cài" if why is None else f"UPDATE_FAIL {why}")
    return 0 if why is None else 1


if __name__ == "__main__":
    sys.exit(main())
