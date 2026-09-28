"""Cài Studio từ trong app Windows đóng gói (webui/studio_setup.py): làm đủ các bước, dừng ở bước hỏng với lời báo đọc
được, bấm lại thì làm tiếp từ bước dở; tải có Range và kiểm SHA-256; sách không chạy được khi chưa cài."""
from __future__ import annotations

import hashlib
import json
import shutil
import threading
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from ebook_reader.webui import studio_setup
from ebook_reader.webui.actions import StudioRunner
from ebook_reader.webui.studio_setup import Download, SetupError, StudioSetup


def _zip_with(path: Path, files: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as bundle:
        for name, data in files.items():
            bundle.writestr(name, data)
    return path


class FakeOllama(BaseHTTPRequestHandler):
    pulled: list[str] = []

    def log_message(self, *_args: object) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.OK)
        self.end_headers()
        self.wfile.write(b'{"models": []}')

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.pulled.append(body["model"])
        self.send_response(HTTPStatus.OK)
        self.end_headers()
        for event in ({"status": "pulling manifest"}, {"status": "downloading", "completed": 50, "total": 100},
                      {"status": "downloading", "completed": 100, "total": 100}, {"status": "success"}):
            self.wfile.write(json.dumps(event).encode() + b"\n")


@pytest.fixture
def ollama():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    FakeOllama.pulled = []
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _setup(tmp_path: Path, ollama: str, commands: list[str], *, fail_on: str = "") -> StudioSetup:
    app = tmp_path / "app"
    app.mkdir()
    (app / "studio-requirements.txt").write_text("torch==2.11.0+cu128\n", encoding="utf-8")
    fetched: list[str] = []

    def fetch(item: Download, target: Path, progress, cancelled) -> Path:
        fetched.append(item.name)
        progress(item.size, item.size)
        inner = {"uv": "uv.exe", "git": "cmd/git.exe", "ollama": "ollama.exe"}[item.name]
        return _zip_with(target, {inner: b"exe"})

    setup = StudioSetup(tmp_path / "Studio", app, fetch=fetch, gpu=lambda: {"name": "Card thử", "memory": 8 << 30},
                        ollama_address=ollama)
    setup.fetched = fetched  # type: ignore[attr-defined]
    setup._run = _runner(setup, commands, fail_on)  # type: ignore[method-assign]
    return setup


def _runner(setup: StudioSetup, commands: list[str], fail_on: str = ""):
    """Thay lệnh thật (uv, python của Studio): ghi lại, tạo venv giả, hỏng đúng bước được bảo."""
    def run(command: list[str], what: str) -> str:
        commands.append(what)
        if fail_on and what == fail_on:
            raise SetupError(f"{what} hỏng (thử)")
        if command[1:3] == ["venv", "--python"]:
            scripts = setup.venv / "Scripts"
            scripts.mkdir(parents=True)
            (scripts / "python.exe").write_bytes(b"")
            (scripts / "pythonw.exe").write_bytes(b"")
        return ""

    return run


def test_the_studio_installs_step_by_step_and_resumes_where_it_stopped(tmp_path: Path, ollama: str,
                                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    # Máy thử không có Ollama sẵn (máy có thì Studio dùng lại bản ấy, không tải thêm 1,5 GB).
    monkeypatch.setattr(studio_setup.shutil, "which", lambda _name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    commands: list[str] = []
    setup = _setup(tmp_path, ollama, commands, fail_on="Tải Whisper")
    assert setup.status()["installed"] is False
    setup.start()
    setup.wait(30)
    status = setup.status()
    assert status["installed"] is False and "Tải Whisper hỏng" in status["error"], "dừng ở bước hỏng, nói rõ"
    done = [step["id"] for step in status["steps"] if step["done"]]
    assert done == ["check", "uv", "git", "python", "packages", "ollama", "llm", "voice"]
    assert FakeOllama.pulled == ["qwen3:8b"], "model phân tích kéo qua API của Ollama"
    assert (setup.tools / "ollama" / "ollama.exe").is_file() and not list((setup.root / "downloads").glob("*.zip"))

    # Bấm "Cài tiếp": không tải lại gì, làm tiếp từ Whisper.
    setup._run = _runner(setup, commands)  # type: ignore[method-assign]
    commands.clear()
    setup.start()
    setup.wait(30)
    status = setup.status()
    assert status["error"] is None and status["installed"] is True
    assert commands == ["Tải Whisper", "Tải model chấm chất lượng", "Kiểm tra lần cuối"]
    assert setup.fetched == ["uv", "git", "ollama"], "không tải lại công cụ đã có"  # type: ignore[attr-defined]
    marker = json.loads((setup.runtime / ".setup_complete").read_text(encoding="utf-8"))
    assert marker["schema_version"] == 2, "đúng dấu cài đặt runtime_contract đòi"

    environment = setup.environment()
    assert environment["EBOOK_READER_RUNTIME"] == str(setup.runtime)
    assert environment["PYTHONPATH"] == str(setup.app_root), "worker chạy mã của app"
    assert environment["PATH"].startswith(str(setup.tools / "ollama")), "dây chuyền tìm thấy Ollama của Studio"


def test_a_machine_without_an_nvidia_card_is_told_so_before_anything_downloads(tmp_path: Path, ollama: str) -> None:
    commands: list[str] = []
    setup = _setup(tmp_path, ollama, commands)
    setup.gpu = lambda: None
    setup.start()
    setup.wait(30)
    status = setup.status()
    assert "NVIDIA" in status["error"] and "nghe sách vẫn dùng" in status["error"]
    assert setup.fetched == [] and commands == []  # type: ignore[attr-defined]


def test_a_book_cannot_start_before_the_studio_is_installed(tmp_path: Path, ollama: str) -> None:
    setup = _setup(tmp_path, ollama, [])
    with pytest.raises(RuntimeError, match="chưa cài Studio"):
        StudioRunner(setup).start(tmp_path / "sach")


def test_a_book_keeps_the_code_that_started_it_across_app_updates(tmp_path: Path, ollama: str,
                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    """App tự cập nhật; đổi một file khoá chất lượng là sách dở không làm tiếp được - nên mỗi cuốn chạy bằng đúng bản
    mã đã bắt đầu nó."""
    from ebook_reader import quality_policy

    setup = _setup(tmp_path, ollama, [])
    package = setup.app_root / "ebook_reader"
    package.mkdir()
    (package / "pipeline.py").write_text("PHIEN_BAN = 1\n", encoding="utf-8")
    (package / "__pycache__").mkdir()
    (setup.app_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    monkeypatch.setattr(quality_policy, "quality_implementation_hash", lambda: "a" * 64)

    old_book, new_book = tmp_path / "cuon_cu", tmp_path / "cuon_moi"
    old_book.mkdir()
    new_book.mkdir()
    first = setup.code_for(old_book)
    assert first == setup.root / "code" / ("a" * 16)
    assert (first / "ebook_reader" / "pipeline.py").read_text(encoding="utf-8") == "PHIEN_BAN = 1\n"
    assert (first / "pyproject.toml").is_file() and not (first / "ebook_reader" / "__pycache__").exists()
    assert setup.environment(first)["PYTHONPATH"] == str(first)

    # App lên bản mới, đổi mã dây chuyền.
    (package / "pipeline.py").write_text("PHIEN_BAN = 2\n", encoding="utf-8")
    monkeypatch.setattr(quality_policy, "quality_implementation_hash", lambda: "b" * 64)
    assert setup.code_for(old_book) == first, "cuốn đang làm dở chạy tiếp bằng mã cũ"
    assert (first / "ebook_reader" / "pipeline.py").read_text(encoding="utf-8") == "PHIEN_BAN = 1\n"
    second = setup.code_for(new_book)
    assert second == setup.root / "code" / ("b" * 16), "cuốn mới dùng mã mới"
    assert (second / "ebook_reader" / "pipeline.py").read_text(encoding="utf-8") == "PHIEN_BAN = 2\n"

    shutil.rmtree(first)
    with pytest.raises(SetupError, match="làm lại bằng bản hiện tại"):
        setup.code_for(old_book)


def test_removing_the_studio_deletes_its_folder_even_read_only_files(tmp_path: Path, ollama: str) -> None:
    import os
    import stat

    setup = _setup(tmp_path, ollama, [])
    locked = setup.tools / "git" / "etc" / "gitconfig"
    locked.parent.mkdir(parents=True)
    locked.write_text("[core]\n", encoding="utf-8")
    os.chmod(locked, stat.S_IREAD)  # MinGit giải nén ra file chỉ-đọc
    (setup.runtime).mkdir(parents=True)
    (setup.runtime / ".setup_complete").write_text("{}", encoding="utf-8")
    status = setup.remove()
    assert not setup.root.exists() and status["installed"] is False
    assert setup.app_root.is_dir(), "mã của app không bị đụng"


class Blob(BaseHTTPRequestHandler):
    data = b""
    ranges: list[str] = []

    def log_message(self, *_args: object) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        start = 0
        header = self.headers.get("Range")
        if header:
            Blob.ranges.append(header)
            start = int(header.removeprefix("bytes=").split("-")[0])
        self.send_response(HTTPStatus.PARTIAL_CONTENT if header else HTTPStatus.OK)
        self.send_header("Content-Length", str(len(Blob.data) - start))
        self.end_headers()
        self.wfile.write(Blob.data[start:])


def test_a_download_resumes_where_it_stopped_and_refuses_a_wrong_file(tmp_path: Path) -> None:
    Blob.data = bytes(range(256)) * 12_000  # ~3 MB: nhiều khúc 1 MB
    Blob.ranges = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Blob)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/uv.zip"
    item = Download("uv", url, hashlib.sha256(Blob.data).hexdigest(), len(Blob.data))
    target = tmp_path / "downloads" / "uv.zip"
    try:
        seen: list[int] = []
        with pytest.raises(studio_setup.Cancelled):
            studio_setup.download(item, target, lambda done, _total: seen.append(done), lambda: len(seen) >= 1)
        partial = target.with_name("uv.zip.part").stat().st_size
        assert 0 < partial < len(Blob.data) and not target.exists(), "bản dở giữ ở .part"

        studio_setup.download(item, target, lambda *_: None, lambda: False)
        assert Blob.ranges == [f"bytes={partial}-"], "tải tiếp từ chỗ dở, không tải lại từ đầu"
        assert target.read_bytes() == Blob.data and not target.with_name("uv.zip.part").exists()

        wrong = Download("uv", url, "0" * 64, len(Blob.data))
        with pytest.raises(SetupError, match="không đúng bản đã ghim"):
            studio_setup.download(wrong, tmp_path / "other" / "uv.zip", lambda *_: None, lambda: False)
        assert not list((tmp_path / "other").iterdir()), "file sai băm bị xoá"
    finally:
        server.shutdown()
