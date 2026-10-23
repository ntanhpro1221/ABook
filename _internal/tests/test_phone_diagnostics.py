"""Chẩn đoán từ xa (a114): máy tính đọc nhật ký + trạng thái của điện thoại đã ghép qua cổng đồng bộ của điện thoại (TLS ghim vân tay,
cùng mã thiết bị), không cần adb; và "Gửi nhật ký" của chính máy tính là một gói .zip không mang mã / vân tay.

Điện thoại giả: máy chủ TLS tự dựng (LibraryServer.kt nói cùng giao thức; phần Kotlin có bài thử JVM riêng)."""
from __future__ import annotations

import http.server
import json
import threading
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from abook.webui import diagnostics, remote_books, tls
from abook.webui.server import ApiError, App, Server
from tests.test_sync_tls_pinning import _this_computer
from tests.test_webui_listen_and_sync import _request

TOKEN = "ma-thiet-bi-bi-mat-0123456789abcdef"


class FakePhone:
    """Một "điện thoại" nghe TLS: `mode` chọn cách đáp /sync/v1/diagnostics ("ok", "old" = bản app cũ chưa có đường này -> 404 như
    LibraryServer cũ, "boom" = lỗi 500)."""

    def __init__(self, tmp: Path, mode: str = "ok") -> None:
        self.mode = mode
        self.asked: list[str] = []
        self.identity = tls.load_or_create(tmp / "phone-tls.pem")
        phone = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:  # noqa: D102
                pass

            def _send(self, status: int, payload: dict) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                parts = urlsplit(self.path)
                if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                    return self._send(401, {"error": "Thiết bị chưa ghép nối"})
                if parts.path != "/sync/v1/diagnostics" or phone.mode == "old":
                    return self._send(404, {"error": "Không có sách này"})
                phone.asked.append(self.path)
                if phone.mode == "boom":
                    return self._send(500, {"error": "IllegalStateException: hỏng"})
                lines = int(parse_qs(parts.query).get("lines", ["2000"])[0])
                self._send(200, {"schema": 1, "app": {"versionName": "0.4.133", "debug": False},
                                 "battery": {"percent": 63, "charging": False},
                                 "log": [f"dòng {n}" for n in range(lines)][-lines:]})

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.socket = self.identity.server_context().wrap_socket(self.httpd.socket, server_side=True)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def _paired(tmp_path: Path, phone: FakePhone, *, token: str = TOKEN, fingerprint: str | None = None) -> tuple[App, str]:
    app = _this_computer(tmp_path)
    entry = {"name": "Pixel của tôi", "host": "127.0.0.1", "port": phone.port, "token": token,
             "fingerprint": fingerprint or phone.identity.fingerprint, "pairedAt": 1.0, "lastSeen": 1.0, "error": "", "kind": "phone"}
    app.computers._write({"computers": {"a1b2c3d4e5f6": entry}})
    return app, "a1b2c3d4e5f6"


@pytest.fixture()
def phone(tmp_path: Path):
    fake = FakePhone(tmp_path)
    yield fake
    fake.stop()


def test_the_desktop_reads_the_phone_diagnostics_and_caps_the_lines(tmp_path: Path, phone: FakePhone) -> None:
    app, device = _paired(tmp_path, phone)
    report = app.phone_diagnostics(device, "7")
    assert report["battery"]["percent"] == 63 and report["log"][-1] == "dòng 6" and len(report["log"]) == 7
    assert "lines=7" in phone.asked[-1]
    remote_books.diagnostics(device, 10**9)
    assert phone.asked[-1].endswith(f"lines={remote_books.DIAGNOSTICS_MAX_LINES}"), "trần số dòng ở phía máy tính"
    remote_books.diagnostics(device, 0)
    assert phone.asked[-1].endswith("lines=1")


def test_the_route_serves_it_and_unknown_or_bad_requests_are_plain(tmp_path: Path, phone: FakePhone) -> None:
    app, device = _paired(tmp_path, phone)
    server = Server(app, port=0).start()
    try:
        headers = {"X-Ebook-Token": "t"}
        status, data, _ = _request(server.port, "GET", f"/api/remote/{device}/diagnostics?lines=3", headers=headers)
        assert status == 200 and json.loads(data)["log"] == ["dòng 0", "dòng 1", "dòng 2"]
        status, data, _ = _request(server.port, "GET", "/api/remote/ffffffffffff/diagnostics", headers=headers)
        assert status == 404 and "không ghép" in json.loads(data)["error"]
        status, _data, _ = _request(server.port, "GET", f"/api/remote/{device}/diagnostics?lines=abc", headers=headers)
        assert status == 400
    finally:
        server.stop()


def test_an_old_phone_app_is_told_apart_from_a_revoked_code_and_from_a_closed_door(tmp_path: Path, phone: FakePhone) -> None:
    app, device = _paired(tmp_path, phone)
    phone.mode = "old"
    with pytest.raises(ApiError) as old:
        app.phone_diagnostics(device)
    assert old.value.extra == {"reason": "needs-newer"} and "cần bản ABook mới hơn" in str(old.value)
    assert "Pixel của tôi" in str(old.value)

    phone.mode = "boom"
    with pytest.raises(ApiError) as boom:
        app.phone_diagnostics(device)
    assert boom.value.extra == {} and "IllegalStateException" in str(boom.value)

    (tmp_path / "khac").mkdir()
    revoked, device2 = _paired(tmp_path / "khac", phone, token="ma-da-bi-thu-hoi")
    with pytest.raises(ApiError) as gone:
        revoked.phone_diagnostics(device2)
    assert "không nhận máy này" in str(gone.value) and "ghép lại" in str(gone.value)


def test_a_phone_that_is_off_or_has_sharing_switched_off_says_so(tmp_path: Path) -> None:
    fake = FakePhone(tmp_path)
    app, device = _paired(tmp_path, fake)
    fake.stop()  # cổng đóng: "Cho máy khác nghe thư viện này" chưa bật / ABook chưa mở
    with pytest.raises(ApiError) as caught:
        app.phone_diagnostics(device)
    assert "Cho phép thiết bị khác kết nối qua Wi-Fi" in str(caught.value) or "chưa bật" in str(caught.value)
    assert "Pixel" in str(caught.value), "lời báo nói tên máy"


def test_a_changed_certificate_is_refused_before_the_token_leaves(tmp_path: Path, phone: FakePhone) -> None:
    app, device = _paired(tmp_path, phone, fingerprint="0" * 64)
    with pytest.raises(ApiError) as caught:
        app.phone_diagnostics(device)
    assert "ghép lại" in str(caught.value) and not phone.asked


def test_saving_the_phone_report_writes_one_json_file(tmp_path: Path, phone: FakePhone) -> None:
    app, device = _paired(tmp_path, phone)
    folder = tmp_path / "luu"
    done = app.save_phone_diagnostics(device, 5, str(folder))
    saved = folder / done["name"]
    assert done["name"].startswith("abook-nhat-ky-Pixel") and saved.suffix == ".json"
    assert json.loads(saved.read_bytes())["log"][-1] == "dòng 4"
    assert b"\r" not in saved.read_bytes()


def test_the_phone_routes_are_not_open_to_remote_studio() -> None:
    from abook.webui import remote_studio

    allowed = " ".join(str(item) for item in vars(remote_studio).values() if isinstance(item, (list, tuple, set, frozenset, dict, str)))
    assert "diagnostics" not in allowed, "nhật ký điện thoại / máy tính không ra khỏi máy bằng Studio từ xa"


# ---- gói chẩn đoán của chính máy tính -------------------------------------------------------------------


def _own(tmp_path: Path) -> tuple[App, str]:
    """Máy tính có một máy đã ghép (mã + vân tay thật trong computers.json) và một thư mục nhật ký đầy ắp."""
    app = _this_computer(tmp_path)
    fingerprint = "ab" * 32
    app.computers._write({"computers": {"a1b2c3d4e5f6": {
        "name": "Pixel", "host": "192.168.1.9", "port": 47630, "token": TOKEN, "fingerprint": fingerprint,
        "pairedAt": 1.0, "lastSeen": 2.0, "error": "", "kind": "phone"}}})
    logs = app.preferences.path.parent / "logs"
    logs.mkdir(parents=True)
    (logs / "host.log").write_text("bắt đầu\n" + "x" * (diagnostics.TAIL_BYTES * 2) + f"\nAuthorization: Bearer {TOKEN}\nvân tay {fingerprint}\ncuối\n",
                                   encoding="utf-8", newline="\n")
    return app, fingerprint


def test_the_computer_bundle_is_capped_and_carries_no_token_or_fingerprint(tmp_path: Path) -> None:
    app, fingerprint = _own(tmp_path)
    data = app.own_diagnostics()
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as archive:
        names = archive.namelist()
        blob = b"".join(archive.read(name) for name in names)
        info = json.loads(archive.read("thong-tin.json"))
        log = archive.read("nhat-ky/host.log")
    assert "thong-tin.json" in names and "nhat-ky/host.log" in names
    assert len(log) <= diagnostics.TAIL_BYTES and log.rstrip().endswith("cuối".encode()), "chỉ đuôi, có trần dung lượng"
    assert TOKEN.encode() not in blob and fingerprint.encode() not in blob
    assert b"token" not in blob.lower(), "không chỗ nào nhắc tới mã thiết bị"
    assert b"192.168.1.9" not in blob, "địa chỉ máy đã ghép ở lại trong máy"
    assert info["pairedMachines"] == [{"name": "Pixel", "kind": "phone", "lastSeen": 2.0, "error": ""}]
    assert "version" in info and info["system"]["platform"]


def test_a_bundle_without_logs_still_explains_itself(tmp_path: Path) -> None:
    data = diagnostics.bundle({"version": "x"}, tmp_path / "khong-co")
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as archive:
        assert "nhat-ky/trong.txt" in archive.namelist()


def test_the_total_log_budget_holds_across_many_files(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    for index in range(diagnostics.MAX_LOG_FILES + 3):
        (logs / f"f{index}.log").write_bytes(b"y" * diagnostics.TAIL_BYTES)
    with zipfile.ZipFile(__import__("io").BytesIO(diagnostics.bundle({}, logs))) as archive:
        parts = [name for name in archive.namelist() if name.startswith("nhat-ky/")]
        assert len(parts) <= diagnostics.MAX_LOG_FILES
        assert sum(len(archive.read(name)) for name in parts) <= diagnostics.TOTAL_LOG_BYTES


def test_saving_the_computer_bundle_writes_a_zip_where_the_user_chose(tmp_path: Path) -> None:
    app, _fingerprint = _own(tmp_path)
    folder = tmp_path / "chon"
    done = app.save_own_diagnostics(str(folder))
    assert zipfile.is_zipfile(folder / done["name"]) and done["name"].startswith(diagnostics.FILE_PREFIX)
    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", "/api/diagnostics/save", body={"target": str(folder)}, headers={"X-Ebook-Token": "t"})
        assert status == 200 and zipfile.is_zipfile(folder / json.loads(data)["name"])
    finally:
        server.stop()


def test_redact_hides_codes_but_keeps_ordinary_lines() -> None:
    assert diagnostics.redact("GET /x Authorization: Bearer abcdefghijkl123") == "GET /x Authorization: Bearer ***"
    assert diagnostics.redact("api_key=sk-abcdefghijklmnopqrstuvwx rồi") == "api_key=*** rồi"
    assert diagnostics.redact("hash " + "f" * 64) == "hash ***"
    assert diagnostics.redact("Chương 3 xong, 12 câu") == "Chương 3 xong, 12 câu"
