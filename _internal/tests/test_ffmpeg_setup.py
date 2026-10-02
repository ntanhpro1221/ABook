"""Bộ đọc nhạc (webui/ffmpeg_setup.py): bản app chỉ-nghe không có ffmpeg nên tải ở lần nhập nhạc đầu tiên. Không chạm mạng:
studio_setup.download được thay bằng bản giả ghi một gói zip nhỏ."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

from abook import io_utils
from abook.webui import ffmpeg_setup, studio_setup
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung


@pytest.fixture
def bare_machine(tmp_path: Path, monkeypatch):
    """Máy chỉ-nghe: không imageio_ffmpeg, không ffmpeg trong PATH; được phép tải (bộ kiểm mặc định tắt tải)."""
    monkeypatch.setenv(ffmpeg_setup.ENV_DOWNLOAD, "1")
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    monkeypatch.setattr(io_utils.shutil, "which", lambda name: None)
    folder = tmp_path / "tools" / "ffmpeg"
    ffmpeg_setup.configure(folder)
    yield folder
    ffmpeg_setup.configure(None)


def _fake_download(calls: list, payload: bytes = b"MZ fake ffmpeg"):
    def download(item, target: Path, progress, cancelled):
        calls.append(item)
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w") as bundle:
            bundle.writestr(ffmpeg_setup.MEMBER, payload)
        progress(item.size // 2, item.size)
        progress(item.size, item.size)
        return target

    return download


def test_the_first_download_unpacks_the_exe_removes_the_wheel_and_registers_it(bare_machine: Path, monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(studio_setup, "download", _fake_download(calls))
    assert not ffmpeg_setup.ready() and ffmpeg_setup.status()["state"] == "idle"
    ffmpeg_setup.start()
    ffmpeg_setup.start()  # gọi lại khi đang tải: không thành hai lượt
    ffmpeg_setup.join(10)
    exe = bare_machine / "ffmpeg.exe"
    assert ffmpeg_setup.status() == {"state": "ready", "done": ffmpeg_setup.WHEEL.size, "total": ffmpeg_setup.WHEEL.size, "error": ""}
    assert exe.read_bytes() == b"MZ fake ffmpeg" and len(calls) == 1 and calls[0] is ffmpeg_setup.WHEEL
    assert sorted(path.name for path in bare_machine.iterdir()) == ["ffmpeg.exe"], "gói đã xoá, không còn file .part"
    assert io_utils.ffmpeg_executable() == str(exe) and ffmpeg_setup.ready()


def test_the_wheel_is_pinned_and_only_the_member_is_taken() -> None:
    assert ffmpeg_setup.WHEEL.url.startswith("https://files.pythonhosted.org/") and len(ffmpeg_setup.WHEEL.sha256) == 64
    assert ffmpeg_setup.MEMBER.startswith("imageio_ffmpeg/binaries/ffmpeg-win-x86_64")


def test_an_exe_already_downloaded_is_registered_at_startup_and_nothing_is_fetched(bare_machine: Path, monkeypatch) -> None:
    (bare_machine).mkdir(parents=True)
    (bare_machine / "ffmpeg.exe").write_bytes(b"MZ")
    ffmpeg_setup.configure(bare_machine)
    monkeypatch.setattr(studio_setup, "download", lambda *a: pytest.fail("không được tải"))
    assert ffmpeg_setup.ready()
    ffmpeg_setup.start()
    assert ffmpeg_setup.status()["state"] == "ready"


def test_imageio_ffmpeg_still_wins_when_it_exists(bare_machine: Path, monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "ffmpeg.exe"
    exe.write_bytes(b"MZ")
    (bare_machine).mkdir(parents=True)
    (bare_machine / "ffmpeg.exe").write_bytes(b"MZ")
    ffmpeg_setup.configure(bare_machine)

    class Fake:
        @staticmethod
        def get_ffmpeg_exe() -> str:
            return str(exe)

    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", Fake)
    assert io_utils.ffmpeg_executable() == str(exe)


def test_ffmpeg_in_the_path_is_used_when_nothing_was_downloaded(bare_machine: Path, monkeypatch, tmp_path: Path) -> None:
    found = tmp_path / "ffmpeg.exe"
    found.write_bytes(b"MZ")
    monkeypatch.setattr(io_utils.shutil, "which", lambda name: str(found))
    assert io_utils.ffmpeg_executable() == str(found) and ffmpeg_setup.ready()


def test_a_failed_download_says_why_and_retrying_works(bare_machine: Path, monkeypatch) -> None:
    def broken(item, target, progress, cancelled):
        raise studio_setup.SetupError("Không tải được") from OSError("không có mạng")

    monkeypatch.setattr(studio_setup, "download", broken)
    ffmpeg_setup.start()
    ffmpeg_setup.join(10)
    failed = ffmpeg_setup.status()
    assert failed["state"] == "error" and "mạng" in failed["error"] and not ffmpeg_setup.ready()
    monkeypatch.setattr(studio_setup, "download", _fake_download([]))
    ffmpeg_setup.start()
    ffmpeg_setup.join(10)
    assert ffmpeg_setup.status()["state"] == "ready" and ffmpeg_setup.status()["error"] == "" and ffmpeg_setup.ready()


def test_a_wrong_hash_a_broken_wheel_and_a_full_disk_each_get_their_own_reason(bare_machine: Path, monkeypatch) -> None:
    def wrong_hash(item, target, progress, cancelled):
        raise studio_setup.SetupError("không đúng bản đã ghim")

    monkeypatch.setattr(studio_setup, "download", wrong_hash)
    ffmpeg_setup.start()
    ffmpeg_setup.join(10)
    assert "không đúng bản đã ghim" in ffmpeg_setup.status()["error"]

    def not_a_zip(item, target, progress, cancelled):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"khong phai zip")
        return target

    monkeypatch.setattr(studio_setup, "download", not_a_zip)
    ffmpeg_setup.start()
    ffmpeg_setup.join(10)
    assert ffmpeg_setup.status()["state"] == "error" and "ffmpeg" in ffmpeg_setup.status()["error"]
    assert not (bare_machine / "ffmpeg.exe").exists() and not (bare_machine / "ffmpeg.exe.part").exists()

    def disk_full(item, target, progress, cancelled):
        raise OSError(28, "Không còn chỗ trống trên ổ đĩa")

    monkeypatch.setattr(studio_setup, "download", disk_full)
    ffmpeg_setup.start()
    ffmpeg_setup.join(10)
    assert "ổ đĩa" in ffmpeg_setup.status()["error"]


def test_the_download_can_be_switched_off(bare_machine: Path, monkeypatch) -> None:
    monkeypatch.setenv(ffmpeg_setup.ENV_DOWNLOAD, "0")
    monkeypatch.setattr(studio_setup, "download", lambda *a: pytest.fail("không được tải"))
    ffmpeg_setup.start()
    assert ffmpeg_setup.status()["state"] == "error" and "tắt" in ffmpeg_setup.status()["error"]


def test_other_platforms_are_told_to_install_ffmpeg(bare_machine: Path, monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(studio_setup, "download", lambda *a: pytest.fail("không được tải"))
    ffmpeg_setup.start()
    assert ffmpeg_setup.status()["state"] == "error" and "cài ffmpeg" in ffmpeg_setup.status()["error"]


def test_the_import_waits_for_the_reader_instead_of_importing_without_it(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    started: list[bool] = []
    monkeypatch.setattr(ffmpeg_setup, "ready", lambda: False)
    monkeypatch.setattr(ffmpeg_setup, "start", lambda: started.append(True))
    song = tmp_path / "a.mp3"
    song.write_bytes(b"khong can doc duoc")
    status, answer = _call(server, "POST", "/api/music/local/import", {"paths": [str(song)]})
    assert status == 200 and answer["needsReader"] is True and started == [True]
    assert answer["added"] == [] and answer["existing"] == [] and answer["failed"] == []
    assert answer["reader"]["ready"] is False and answer["tracks"] == [], "chưa nhập gì, kể cả file hỏng cũng không bị đọc"
    status, view = _call(server, "GET", "/api/music/local")
    assert status == 200 and view["reader"]["ready"] is False and "needsReader" not in view
    status, retried = _call(server, "POST", "/api/music/local/reader")
    assert status == 200 and started == [True, True] and retried["reader"]["ready"] is False


def test_the_reader_route_is_not_open_to_a_remote_studio() -> None:
    from abook.webui import remote_studio

    assert not remote_studio.permitted("POST", "/api/music/local/reader")
