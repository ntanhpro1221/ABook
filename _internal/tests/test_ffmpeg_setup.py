"""ffmpeg của mô-đun "Phân tích nhạc" (webui/ffmpeg_setup.py): bản app chỉ-nghe không có ffmpeg; mô-đun tải nó khi người dùng bấm (không phải lúc
nhập nhạc - nhập đọc thẻ bằng tinytag). Không chạm mạng: studio_setup.download được thay bằng bản giả ghi một gói zip nhỏ."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

from abook import io_utils
from abook.webui import ffmpeg_setup, studio_setup


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


def test_install_unpacks_the_exe_removes_the_wheel_and_registers_it(bare_machine: Path, monkeypatch) -> None:
    calls: list = []
    seen: list[tuple[int, int]] = []
    monkeypatch.setattr(studio_setup, "download", _fake_download(calls))
    assert not ffmpeg_setup.ready() and not ffmpeg_setup.downloaded() and not ffmpeg_setup.external()
    exe = ffmpeg_setup.install(lambda done, total: seen.append((done, total)))
    assert exe == bare_machine / "ffmpeg.exe" and exe.read_bytes() == b"MZ fake ffmpeg"
    assert len(calls) == 1 and calls[0] is ffmpeg_setup.WHEEL and seen[-1] == (ffmpeg_setup.WHEEL.size, ffmpeg_setup.WHEEL.size)
    assert sorted(path.name for path in bare_machine.iterdir()) == ["ffmpeg.exe"], "gói đã xoá, không còn file .part"
    assert io_utils.ffmpeg_executable() == str(exe) and ffmpeg_setup.ready() and ffmpeg_setup.downloaded()


def test_the_wheel_is_pinned_and_only_the_member_is_taken() -> None:
    assert ffmpeg_setup.WHEEL.url.startswith("https://files.pythonhosted.org/") and len(ffmpeg_setup.WHEEL.sha256) == 64
    assert ffmpeg_setup.MEMBER.startswith("imageio_ffmpeg/binaries/ffmpeg-win-x86_64")
    assert ffmpeg_setup.pin() == ffmpeg_setup.WHEEL.sha256


def test_an_exe_already_downloaded_is_registered_at_startup(bare_machine: Path) -> None:
    (bare_machine).mkdir(parents=True)
    (bare_machine / "ffmpeg.exe").write_bytes(b"MZ")
    ffmpeg_setup.configure(bare_machine)
    assert ffmpeg_setup.ready() and ffmpeg_setup.downloaded() and not ffmpeg_setup.external(), "của mô-đun, không phải ffmpeg có sẵn"


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
    assert io_utils.ffmpeg_executable() == str(exe) and ffmpeg_setup.external()


def test_ffmpeg_in_the_path_is_used_when_nothing_was_downloaded(bare_machine: Path, monkeypatch, tmp_path: Path) -> None:
    found = tmp_path / "ffmpeg.exe"
    found.write_bytes(b"MZ")
    monkeypatch.setattr(io_utils.shutil, "which", lambda name: str(found))
    monkeypatch.setattr(ffmpeg_setup.shutil, "which", lambda name: str(found))
    assert io_utils.ffmpeg_executable() == str(found) and ffmpeg_setup.ready() and ffmpeg_setup.external()


def test_each_failure_gets_its_own_reason(bare_machine: Path, monkeypatch) -> None:
    def broken(item, target, progress, cancelled):
        raise studio_setup.SetupError("Không tải được") from OSError("không có mạng")

    def wrong_hash(item, target, progress, cancelled):
        raise studio_setup.SetupError("không đúng bản đã ghim")

    def not_a_zip(item, target, progress, cancelled):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"khong phai zip")
        return target

    def disk_full(item, target, progress, cancelled):
        raise OSError(28, "Không còn chỗ trống trên ổ đĩa")

    reasons = {}
    for name, fake in (("network", broken), ("hash", wrong_hash), ("zip", not_a_zip), ("disk", disk_full)):
        monkeypatch.setattr(studio_setup, "download", fake)
        with pytest.raises(Exception) as error:
            ffmpeg_setup.install(lambda done, total: None)
        reasons[name] = ffmpeg_setup.reason(error.value)
    assert "mạng" in reasons["network"] and "không đúng bản đã ghim" in reasons["hash"]
    assert "ffmpeg" in reasons["zip"] and "ổ đĩa" in reasons["disk"]
    assert not (bare_machine / "ffmpeg.exe").exists() and not (bare_machine / "ffmpeg.exe.part").exists()


def test_the_download_can_be_switched_off_and_other_platforms_are_told_to_install_ffmpeg(bare_machine: Path, monkeypatch) -> None:
    assert ffmpeg_setup.cannot_download() == "" or sys.platform != "win32"
    monkeypatch.setenv(ffmpeg_setup.ENV_DOWNLOAD, "0")
    assert "tắt" in ffmpeg_setup.cannot_download()
    monkeypatch.setenv(ffmpeg_setup.ENV_DOWNLOAD, "1")
    monkeypatch.setattr(sys, "platform", "linux")
    assert "cài ffmpeg" in ffmpeg_setup.cannot_download()
