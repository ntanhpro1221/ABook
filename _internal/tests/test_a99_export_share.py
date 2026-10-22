"""a99: xuất và chia sẻ sách - "Lưu thành…" không ghi đè, gói dự án không hỏng lặng lẽ, lớp sửa không thành "file hỏng",
ước cỡ .abook đủ các phần."""
from __future__ import annotations

import io
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from abook.webui import book_edits, bookfile, covers, export, packages, projectfile
from abook.webui.server import Handler
from tests.test_webui_listen_and_sync import make_project

FIXTURE = Path(__file__).parent / "fixtures" / "book_edits" / "base"


def image_bytes(color: str) -> bytes:
    sink = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(sink, format="JPEG")
    return sink.getvalue()


def _save(folder: Path, destination: Path, kind: str) -> tuple[int, dict]:
    handler = object.__new__(Handler)
    handler.app = SimpleNamespace(_editable=lambda value: folder, exports=set())
    handler._body = lambda: {"as": kind, "target": str(destination)}
    handler._export_root = lambda body: destination
    reply: list = []
    handler._send_json = lambda status, body: reply.append((status, body))
    Handler.post_save(handler, {}, "book")
    return int(reply[0][0]), reply[0][1]


@pytest.mark.parametrize("kind", ["abook", "abookproj"])
def test_save_as_never_overwrites_an_existing_file(tmp_path, kind):
    folder = tmp_path / "imported"
    shutil.copytree(FIXTURE, folder)
    destination = tmp_path / "chosen"
    destination.mkdir()
    title = "Tên trùng tiếng Việt"
    book_edits.set_title(folder, title)
    pack = bookfile.repack if kind == "abook" else projectfile.repack
    name = bookfile.default_name(title) if kind == "abook" else projectfile.default_name(title)
    old = pack(folder, destination / name)
    original = old.read_bytes()
    book_edits.set_author(folder, "Tác giả vừa sửa")
    status, reply = _save(folder, destination, kind)
    assert status == 200
    saved = Path(reply["file"])
    assert saved != old and saved.name.endswith(f" (2){old.suffix}")
    assert old.read_bytes() == original
    assert len(list(destination.iterdir())) == 2


def test_save_as_into_the_folder_of_the_original_keeps_the_original(tmp_path):
    folder = tmp_path / "imported"
    shutil.copytree(FIXTURE, folder)
    title = "Sách gốc"
    book_edits.set_title(folder, title)
    original = bookfile.repack(folder, tmp_path / bookfile.default_name(title))
    before = original.read_bytes()
    book_edits.set_author(folder, "Người nghe sửa")
    _, reply = _save(folder, tmp_path, "abook")
    assert Path(reply["file"]) != original
    assert original.read_bytes() == before


def test_project_pack_refuses_a_cover_changed_while_packing_and_keeps_the_old_export(tmp_path):
    project = make_project(tmp_path)
    covers.save_cover_bytes(project, image_bytes("red"))
    destination = tmp_path / "sao lưu.abookproj"
    destination.write_bytes(b"previous export")
    changed = False

    def progress(phase, done, total):
        nonlocal changed
        if phase == "write" and not changed:
            changed = True
            covers.save_cover_bytes(project, image_bytes("blue"))

    with pytest.raises(projectfile.ProjectFileError, match="thay đổi"):
        projectfile.pack(project, destination, running=False, progress=progress)
    assert changed
    assert destination.read_bytes() == b"previous export"
    assert not list(tmp_path.glob("*.part"))


def _received(tmp_path, monkeypatch=None):
    from abook.webui.fingerprints import Fingerprints

    folder = tmp_path / "holder"
    shutil.copytree(FIXTURE, folder)
    book_edits.set_title(folder, "Tên mang trong file")
    book_edits.set_character_name(folder, "LUCIEN", "Lu-xi-en")
    out = bookfile.repack(folder, tmp_path / "gửi.abook")
    library = tmp_path / "recipient"
    prints = Fingerprints(tmp_path / "fingerprints.json")
    target, how = packages.import_file(out, library, [], prints)
    assert how == "new"
    return out, library, prints, target


def test_editing_a_book_does_not_make_its_edit_layer_a_damaged_file(tmp_path):
    out, library, prints, target = _received(tmp_path)
    assert packages.damaged_files(target) == []
    book_edits.set_author(target, "Tác giả bạn vừa điền")
    assert packages.damaged_files(target) == []
    again, how = packages.import_file(out, library, [], prints)
    assert again == target and how == "existing"
    assert packages.edited_manifest(target)["author"] == "Tác giả bạn vừa điền"


def test_reopening_a_complete_book_after_an_edit_needs_no_disk_space(tmp_path, monkeypatch):
    from collections import namedtuple

    out, library, prints, target = _received(tmp_path)
    book_edits.set_author(target, "Tác giả bạn vừa điền")
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(bookfile.shutil, "disk_usage", lambda path: usage(10**9, 10**9, 0))
    again, how = packages.import_file(out, library, [], prints)
    assert again == target and how == "existing"


def test_a_missing_chapter_audio_is_still_repaired_by_reopening_the_file(tmp_path):
    out, library, prints, target = _received(tmp_path)
    chapter = next(p for p in (target / "chapters").rglob("*.mp3"))
    chapter.unlink()
    assert packages.damaged_files(target)
    again, how = packages.import_file(out, library, [], prints)
    assert again == target and how == "repaired"
    assert chapter.is_file()


# ---- V4: sách nhận từ file `.abook` xuất MP3 / M4B ngay từ player ----------------------------------------------------


@pytest.fixture
def limited_ffmpeg(monkeypatch):
    """ffmpeg thật nhưng một luồng (máy thử dùng chung)."""
    import subprocess

    original = subprocess.Popen

    def limited(command, *args, **kwargs):
        if isinstance(command, (list, tuple)) and "ffmpeg" in Path(str(command[0])).name.lower():
            command = [command[0], "-cpucount", "1", "-threads", "1", "-filter_threads", "1", "-filter_complex_threads", "1", *command[1:]]
        return original(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", limited)


def _imported_audio_book(tmp_path):
    import subprocess

    from abook.io_utils import ffmpeg_executable
    from abook.webui.fingerprints import Fingerprints

    project = make_project(tmp_path, "Truyện tiếng Việt")
    for name, frequency in (("00001_645.mp3", "440"), ("00002_646.mp3", "660")):
        subprocess.run([ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency={frequency}:sample_rate=24000", "-t", "0.7", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "48k",
                        str(project / "output" / "chapters" / name)], check=True)
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE chapters SET status='completed', output_mp3=? WHERE id=2", (str(project / "output/chapters/00002_646.mp3"),))
        db.execute("UPDATE segments SET status='verified', wav_duration=0.2 WHERE chapter_id=2")
    covers.save_cover_bytes(project, image_bytes("red"))
    packed = bookfile.pack(project, tmp_path / "gửi.abook")
    target, how = packages.import_file(packed, tmp_path / "recipient", [], Fingerprints(tmp_path / "fingerprints.json"))
    assert how == "new"
    return target


def _probe(path):
    import json
    import shutil as shutil_
    import subprocess

    probe = shutil_.which("ffprobe")
    assert probe
    result = subprocess.run([probe, "-v", "error", "-show_chapters", "-show_format", "-show_streams", "-of", "json", str(path)],
                            check=True, capture_output=True)
    return json.loads(result.stdout)


def test_an_imported_book_exports_mp3_with_the_listeners_edited_title(tmp_path, limited_ffmpeg):
    folder = _imported_audio_book(tmp_path)
    book_edits.set_title(folder, "Tên người nghe đặt")
    result = export.export_book(folder, tmp_path / "mp3")
    assert result["files"] == 2 and Path(result["folder"]).name == "Tên người nghe đặt"
    files = sorted(Path(result["folder"]).glob("*.mp3"))
    first = _probe(files[0])
    assert first["format"]["tags"]["album"] == "Tên người nghe đặt" and first["format"]["tags"]["track"] == "1/2"
    assert any(s.get("disposition", {}).get("attached_pic") for s in first["streams"])
    assert not (folder / "output").exists()


def test_an_imported_book_exports_m4b_with_chapter_marks(tmp_path, limited_ffmpeg):
    folder = _imported_audio_book(tmp_path)
    result = export.export_m4b(folder, tmp_path / "m4b")
    probed = _probe(result["file"])
    assert len(probed["chapters"]) == 2 and probed["format"]["tags"]["title"] == "Truyện tiếng Việt"
    assert float(probed["chapters"][1]["start_time"]) > 0.5
    assert any(s.get("disposition", {}).get("attached_pic") for s in probed["streams"])


def _wait_job(server, folder, route, seconds=60.0):
    import time

    from tests.test_export_series import _get

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        job = _get(server, folder, route)[1]
        if job["state"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("việc xuất không kết thúc")


def test_the_server_exports_an_imported_book_as_mp3_and_m4b_in_the_background(tmp_path, limited_ffmpeg):
    from tests.test_export_series import _get, _post, _studio

    folder = _imported_audio_book(tmp_path)
    app, server = _studio(tmp_path, tmp_path / "recipient")
    try:
        assert _get(server, folder, "export-music")[1] == {"available": False, "enabled": False}
        status, started = _post(server, folder, "mp3-job", {"target": str(tmp_path / "xuat")})
        assert status == 202 and started["state"] in ("running", "done"), started
        mp3_job = _wait_job(server, folder, "mp3-job")
        status, started = _post(server, folder, "m4b-job", {"target": str(tmp_path / "xuat"), "music": True})
        assert status == 202, started
        m4b_job = _wait_job(server, folder, "m4b-job")
    finally:
        server.stop()
    assert mp3_job["state"] == "done" and mp3_job["result"]["files"] == 2, mp3_job
    assert m4b_job["state"] == "done" and Path(m4b_job["result"]["file"]).is_file(), m4b_job


def test_the_abook_size_estimate_counts_voice_samples_cover_scripts_and_cast(tmp_path):
    project = make_project(tmp_path)
    sample = project / "work/s3.wav"
    sample.write_bytes(b"RIFF" + bytes(range(256)) * 4096)  # ~1 MiB câu mẫu của nhân vật
    covers.save_cover_bytes(project, image_bytes("red"))
    estimated, _pending = export.audio_bytes([project])
    packed = bookfile.pack(project, tmp_path / "full.abook")
    actual = packed.stat().st_size
    assert estimated >= sample.stat().st_size, "câu mẫu WAV phải nằm trong số ước"
    assert actual * 0.9 <= estimated <= actual * 1.5, (estimated, actual)
