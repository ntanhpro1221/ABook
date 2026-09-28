"""Host của app Windows đóng gói (webui/host.py): vỏ Tauri nói chuyện với server giao diện qua ống, JSON từng dòng."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from ebook_reader.webui import host

ROOT = Path(__file__).resolve().parents[1]


class Shell:
    """Phía vỏ của ống: chạy `host.run` ở một luồng, đọc/ghi như vỏ Tauri."""

    def __init__(self) -> None:
        to_host_r, self._to_host_w = os.pipe()
        self._from_host_r, from_host_w = os.pipe()
        self.host_reader = os.fdopen(to_host_r, "r", encoding="utf-8")
        self.host_writer = os.fdopen(from_host_w, "w", encoding="utf-8")
        self.writer = os.fdopen(self._to_host_w, "w", encoding="utf-8")
        self.reader = os.fdopen(self._from_host_r, "r", encoding="utf-8")
        self.result: list[int] = []
        self.thread = threading.Thread(
            target=lambda: self.result.append(host.run(self.host_reader, self.host_writer, ["--fake-runner"])),
            daemon=True)

    def start(self) -> str:
        self.thread.start()
        return self.receive()["ready"]

    def receive(self) -> dict:
        return json.loads(self.reader.readline())

    def send(self, message: dict) -> None:
        self.writer.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.writer.flush()


def _request(url: str, path: str, body: dict | None = None) -> dict:
    base, _, query = url.partition("?")
    request = urllib.request.Request(base.rstrip("/") + path, method="POST" if body is not None else "GET",
                                     data=json.dumps(body).encode("utf-8") if body is not None else None,
                                     headers={"X-Ebook-Token": query.removeprefix("t="),
                                              "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


@pytest.fixture
def app_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    preferences = tmp_path / "ABook" / "preferences.json"
    preferences.parent.mkdir(parents=True)
    preferences.write_text(json.dumps({"libraryRoot": str(tmp_path / "thu_vien")}), encoding="utf-8")
    monkeypatch.setenv("EBOOK_READER_PREFERENCES", str(preferences))
    return tmp_path


def test_the_shell_opens_windows_dialogs_and_book_files_for_the_page(app_data: Path) -> None:
    shell = Shell()
    url = shell.start()
    assert _request(url, "/api/app")["dialogs"] is True, "trang biết app có hộp thoại (nút Chọn thư mục hiện ra)"

    # Trang bấm "Chọn thư mục": server nhờ vỏ mở hộp thoại Windows rồi chờ người dùng chọn.
    answer: dict = {}
    clicked = threading.Thread(target=lambda: answer.update(_request(url, "/api/dialog/folder", {"title": "Thư viện"})))
    clicked.start()
    asked = shell.receive()
    assert asked["kind"] == "folder" and asked["title"] == "Thư viện"
    shell.send({"dialog": asked["dialog"], "result": "D:\\Sách nói"})
    clicked.join(10)
    assert answer == {"path": "D:\\Sách nói"}

    # Huỷ hộp thoại chọn file: danh sách rỗng, không treo.
    clicked = threading.Thread(target=lambda: answer.update(_request(url, "/api/dialog/files", {})))
    clicked.start()
    asked = shell.receive()
    assert asked["kind"] == "files"
    shell.send({"dialog": asked["dialog"], "result": None})
    clicked.join(10)
    assert answer["paths"] == []

    # Bấm đúp một file .abook khi app đang mở: vỏ chuyển đường dẫn, host nhập rồi nhờ vỏ báo trang.
    shell.send({"open": str(app_data / "khong_co.abook")})
    opened = shell.receive()
    assert opened["event"] == host.OPENED_EVENT
    assert opened["detail"]["id"] is None and opened["detail"]["error"], "lỗi đọc được, không phải im lặng"

    shell.send({"quit": True})
    shell.thread.join(10)
    assert shell.result == [0]
    with pytest.raises(OSError):
        _request(url, "/api/app")


def test_a_shell_that_dies_mid_dialog_never_leaves_the_page_hanging(app_data: Path) -> None:
    shell = Shell()
    url = shell.start()
    answer: dict = {}
    clicked = threading.Thread(target=lambda: answer.update(_request(url, "/api/dialog/folder", {})))
    clicked.start()
    shell.receive()
    shell.writer.close()  # vỏ chết: stdin của host đóng
    clicked.join(10)
    shell.thread.join(10)
    assert answer == {"path": None}
    assert shell.result == [0]


def test_the_host_process_exits_when_the_shell_goes_away(app_data: Path) -> None:
    """Tiến trình thật như vỏ chạy nó: stdout là của giao thức (print lạc sang stderr), đóng stdin là thoát - không
    bao giờ bỏ lại một server mồ côi giữ cổng."""
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    process = subprocess.Popen([sys.executable, "-m", "ebook_reader.webui.host", "--fake-runner", "--version", "9.9.9"],
                               cwd=ROOT, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        ready = json.loads(process.stdout.readline())
        assert _request(ready["ready"], "/api/app")["version"] == "9.9.9"
        started = time.monotonic()
        process.stdin.close()
        assert process.wait(15) == 0
        assert time.monotonic() - started < 15
        assert process.stdout.read() == "", "không có gì ngoài giao thức trên stdout"
    finally:
        if process.poll() is None:
            process.kill()
