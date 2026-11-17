"""ffmpeg của mô-đun "Phân tích nhạc" (webui/ffmpeg_setup.py): bản app chỉ-nghe không có ffmpeg; mô-đun tải nó khi người dùng bấm (không phải lúc
nhập nhạc - nhập đọc thẻ bằng tinytag). Không chạm mạng: studio_setup.download được thay bằng bản giả ghi một gói zip nhỏ."""
from __future__ import annotations

import sys
import hashlib
import zlib
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
    monkeypatch.setattr(ffmpeg_setup.zip_range, "member_offset", lambda *args: 0)
    monkeypatch.setattr(ffmpeg_setup, "EXE_SIZE", len(b"MZ fake ffmpeg"))
    monkeypatch.setattr(ffmpeg_setup, "EXE_SHA256", hashlib.sha256(b"MZ fake ffmpeg").hexdigest())
    monkeypatch.setattr(ffmpeg_setup, "EXE_CRC", zlib.crc32(b"MZ fake ffmpeg"))
    folder = tmp_path / "tools" / "ffmpeg"
    ffmpeg_setup.configure(folder)
    yield folder
    ffmpeg_setup.configure(None)


def _fake_download(calls: list, payload: bytes = b"MZ fake ffmpeg"):
    def download(item, target: Path, progress, cancelled, **kwargs):
        calls.append(item)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zlib.compress(payload)[2:-4])
        progress(item.size // 2, item.size)
        progress(item.size, item.size)
        return target

    return download


def test_install_unpacks_the_exe_removes_the_archive_and_registers_it(bare_machine: Path, monkeypatch) -> None:
    calls: list = []
    seen: list[tuple[int, int]] = []
    monkeypatch.setattr(studio_setup, "download", _fake_download(calls))
    assert not ffmpeg_setup.ready() and not ffmpeg_setup.downloaded() and not ffmpeg_setup.external()
    exe = ffmpeg_setup.install(lambda done, total: seen.append((done, total)))
    slot = ffmpeg_setup.pin()[:16]
    assert exe == bare_machine / slot / "ffmpeg.exe" and exe.read_bytes() == b"MZ fake ffmpeg", "mỗi pin một thư mục riêng"
    assert len(calls) == 1 and calls[0] is ffmpeg_setup.WHEEL and seen[-1] == (ffmpeg_setup.WHEEL.size, ffmpeg_setup.WHEEL.size)
    assert sorted(path.name for path in bare_machine.iterdir()) == sorted([slot, "install.lock", "installed.sha256"]), "gói đã xoá, chỉ còn exe, khoá và con trỏ"
    assert [path.name for path in (bare_machine / slot).iterdir()] == ["ffmpeg.exe"]
    assert io_utils.ffmpeg_executable() == str(exe) and ffmpeg_setup.ready() and ffmpeg_setup.downloaded()


def test_the_archive_is_pinned_and_only_the_member_is_taken() -> None:
    assert ffmpeg_setup.WHEEL.url.startswith("https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/autobuild-2026-10-31-12-59/")
    assert len(ffmpeg_setup.WHEEL.sha256) == 64 and ffmpeg_setup.WHEEL.size > 0
    assert ffmpeg_setup.MEMBER == "ffmpeg-n8.1.3-27-g8dca1586f4-win64-gpl-8.1/bin/ffmpeg.exe"
    assert ffmpeg_setup.WHEEL.url.endswith("/" + ffmpeg_setup.MEMBER.split("/")[0] + ".zip"), "exe nằm trong đúng ZIP đã ghim"
    assert ffmpeg_setup.pin() == ffmpeg_setup.WHEEL.sha256


def test_the_pinned_build_is_a_month_end_build_that_is_not_deleted() -> None:
    """FFmpeg-Builds giữ bản cuối mỗi tháng 2 năm nhưng xoá bản ngày sau 14 ngày (README "The last build of each month is kept for
    two years"): ghim bản ngày thì đường tải 404 sau hai tuần. Thẻ ghim phải là ngày cuối tháng."""
    import calendar
    import re

    found = re.search(r"/releases/download/autobuild-(\d{4})-(\d{2})-(\d{2})-\d{2}-\d{2}/", ffmpeg_setup.WHEEL.url)
    assert found, "thẻ có ngày, không phải `latest`"
    year, month, day = (int(part) for part in found.groups())
    assert day == calendar.monthrange(year, month)[1], f"autobuild-{year}-{month:02d}-{day:02d} không phải bản cuối tháng: sẽ bị xoá sau 14 ngày"
    # Một ngày cuối tháng có thể có hai bản dựng: chỉ bản MUỘN NHẤT được giữ. Danh sách thẻ của tháng do scripts/ffmpeg_pinned_codecs.py
    # đọc từ GitHub khi đổi pin (từ chối chạy khi tháng chưa hết) và ghi vào fixture.
    import json

    recorded = json.loads((Path(__file__).parent / "fixtures" / "ffmpeg_pinned_codecs.json").read_text(encoding="utf-8"))
    tag = re.search(r"/releases/download/([^/]+)/", ffmpeg_setup.WHEEL.url).group(1)
    assert recorded["release_tag"] == tag, "fixture ghi cho thẻ khác: chạy lại scripts/ffmpeg_pinned_codecs.py"
    prefix = f"autobuild-{year}-{month:02d}-"
    assert recorded["month_tags"] and all(t.startswith(prefix) for t in recorded["month_tags"])
    assert max(recorded["month_tags"]) == tag, f"{tag} không phải bản muộn nhất của tháng: {recorded['month_tags']}"
    assert recorded["checked_utc"] > f"{year}-{month:02d}-31", "danh sách thẻ phải đọc sau khi tháng đã hết"


@pytest.mark.parametrize("stamp", ["older-pin", "current"])
def test_export_reports_own_stamp_and_updates_only_after_click(bare_machine, monkeypatch, stamp):
    pointer = ffmpeg_setup.pin() if stamp == "current" else "0123456789abcdef" + "0" * 48
    exe = bare_machine / pointer[:16] / "ffmpeg.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ old ffmpeg")
    (bare_machine / "installed.sha256").write_text(pointer, encoding="utf-8")
    calls = []
    monkeypatch.setattr(studio_setup, "download", _fake_download(calls))
    monkeypatch.setattr(ffmpeg_setup, "_state", {"downloading": False, "done": 0, "total": 0, "error": ""})
    ffmpeg_setup.configure(bare_machine)
    status = ffmpeg_setup.status()
    assert status["ready"]
    assert status["outdated"] == (stamp != "current")
    assert calls == [], "opening Export must never download in the background"
    ffmpeg_setup.start()
    ffmpeg_setup.join(10)
    assert len(calls) == (0 if stamp == "current" else 1)
    assert not ffmpeg_setup.status()["outdated"]


def test_an_exe_already_downloaded_is_registered_at_startup(bare_machine: Path) -> None:
    exe = bare_machine / ffmpeg_setup.pin()[:16] / "ffmpeg.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    (bare_machine / "installed.sha256").write_text(ffmpeg_setup.pin(), encoding="utf-8")
    ffmpeg_setup.configure(bare_machine)
    assert io_utils.ffmpeg_executable() == str(exe)
    assert ffmpeg_setup.ready() and ffmpeg_setup.downloaded() and not ffmpeg_setup.external(), "của mô-đun, không phải ffmpeg có sẵn"


def test_imageio_ffmpeg_still_wins_when_it_exists(bare_machine: Path, monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "ffmpeg.exe"
    exe.write_bytes(b"MZ")
    (bare_machine / ffmpeg_setup.pin()[:16]).mkdir(parents=True)
    (bare_machine / ffmpeg_setup.pin()[:16] / "ffmpeg.exe").write_bytes(b"MZ")
    (bare_machine / "installed.sha256").write_text(ffmpeg_setup.pin(), encoding="utf-8")
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
    def broken(item, target, progress, cancelled, **kwargs):
        raise studio_setup.SetupError("Không tải được") from OSError("không có mạng")

    def wrong_hash(item, target, progress, cancelled, **kwargs):
        raise studio_setup.SetupError("không đúng bản đã ghim")

    def not_a_zip(item, target, progress, cancelled, **kwargs):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"khong phai zip")
        return target

    def disk_full(item, target, progress, cancelled, **kwargs):
        raise OSError(28, "Không còn chỗ trống trên ổ đĩa")

    reasons = {}
    for name, fake in (("network", broken), ("hash", wrong_hash), ("zip", not_a_zip), ("disk", disk_full)):
        monkeypatch.setattr(studio_setup, "download", fake)
        with pytest.raises(Exception) as error:
            ffmpeg_setup.install(lambda done, total: None)
        reasons[name] = studio_setup.download_failure(ffmpeg_setup.NOUN, error.value)[0]
    assert reasons["network"] == studio_setup.NETWORK_FAILURE.format(retry="Thử lại") and "tải về sai bản" in reasons["hash"]
    assert "ffmpeg" in reasons["zip"] and "ổ đĩa" in reasons["disk"]
    assert not (bare_machine / "ffmpeg.exe").exists() and not (bare_machine / "ffmpeg.exe.part").exists()


def test_the_download_can_be_switched_off_and_other_platforms_are_told_to_install_ffmpeg(bare_machine: Path, monkeypatch) -> None:
    assert ffmpeg_setup.cannot_download() == "" or sys.platform != "win32"
    monkeypatch.setenv(ffmpeg_setup.ENV_DOWNLOAD, "0")
    assert "tắt" in ffmpeg_setup.cannot_download()
    monkeypatch.setenv(ffmpeg_setup.ENV_DOWNLOAD, "1")
    monkeypatch.setattr(sys, "platform", "linux")
    assert ffmpeg_setup.cannot_download() == "Máy này chưa có bản tải sẵn của bộ xuất âm thanh — bạn xem Chi tiết để nhờ hỗ trợ."
