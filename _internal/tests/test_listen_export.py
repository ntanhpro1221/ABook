"""Xuất sách nói (MP3 / M4B) cho sách Nghe ngay trên máy tính (webui/listen_export.py + /api/listen/books/<id>/audiobook).

Giọng giả đọc mỗi chữ 0,2 giây thành sóng sin WAV (xác định, đếm được số lần gọi); ffmpeg của venv ghép, ffprobe đọc lại file xuất.
Bộ chia đoạn được thử riêng ở test_listen_paragraphs_shared.py.
"""
from __future__ import annotations

import io
import json
import math
import shutil
import struct
import subprocess
import threading
import time
import wave
from pathlib import Path
from typing import Any

import pytest

from abook.io_utils import ffmpeg_available
from abook.readaloud.mapping import Boundary
from abook.readaloud.model import Synthesis, Voice, VoiceError
from abook.readaloud.service import ReadAloud
from abook.webui import export, export_jobs, ffmpeg_setup, listen_export
from abook.webui.server import Server
from tests.test_project_file import _app
from tests.test_webui_listen_and_sync import _request

FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(not ffmpeg_available() or FFPROBE is None, reason="cần ffmpeg + ffprobe")
TOKEN = {"X-Ebook-Token": "t"}
NL = chr(10)
WORD = 0.2  # giây mỗi chữ của giọng giả
GAP = 1.5  # giây lặng ở dòng ngăn cảnh
VOICE = "fake:ngoc"
CHAPTERS = {
    "001.txt": NL.join(["Chương một", "", "Một hai ba.", "", "***", "", "Bốn năm.", ""]),
    "002.txt": NL.join(["Chương hai", "", "Sáu bảy tám chín.", ""]),
}
# thời lượng mong đợi của từng chương: số chữ x 0,2 s (+ 1,5 s ở dòng ngăn cảnh giữa hai đoạn đọc được)
EXPECTED = {1: (2 + 3 + 2) * WORD + GAP, 2: (2 + 4) * WORD}


class FakeVoice:
    id = "fake"
    speaks_english = True

    def __init__(self, *, fail: VoiceError | None = None) -> None:
        self.calls: list[str] = []
        self.fail = fail

    def voices(self) -> list[Voice]:
        return [Voice(VOICE, "Ngọc", "fake", False, True)]

    def synthesize(self, text: str, native_voice: str) -> Synthesis:
        self.calls.append(text)
        if self.fail:
            raise self.fail
        words = len(text.split())
        rate = 24000
        frames = int(rate * WORD * words)
        samples = struct.pack("<" + "h" * frames, *(int(3000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(frames)))
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(samples)
        spans = [[round(i * WORD * 1000), round((i + 1) * WORD * 1000) - 20] for i in range(words)]
        return Synthesis(buffer.getvalue(), [Boundary(w, s, e) for w, (s, e) in zip(text.split(), spans)], round(WORD * 1000 * words),
                         ext="wav", mime="audio/wav", words=spans)


def _library(tmp_path: Path):
    """App với một sách Nghe ngay (2 chương TXT) và giọng giả; trả (app, mã sách, thư mục sách, giọng giả)."""
    source = tmp_path / "nguon"
    source.mkdir()
    for name, text in CHAPTERS.items():
        (source / name).write_bytes(text.encode("utf-8"))
    app = _app(tmp_path / "studio", tmp_path / "thu_vien")
    added = app.add_text_book(str(source), "Truyện thử")
    fake = FakeVoice()
    app.readaloud = ReadAloud(tmp_path / "studio" / "prefs" / "cache", [fake])
    return app, added["id"], app._listenable(added["id"]), fake


def _probe(path: Path) -> dict[str, Any]:
    done = subprocess.run([FFPROBE, "-v", "error", "-show_chapters", "-show_streams", "-show_format", "-of", "json", str(path)],
                          capture_output=True, check=True)
    return json.loads(done.stdout.decode("utf-8"))


def _run(app, book_id: str, path: Path, target: Path, fmt: str, **options: Any) -> dict[str, Any]:
    return listen_export.export_audiobook(app.readaloud, path, target, tmp_work(target), fmt=fmt, reading=listen_export.Reading(VOICE, None, {}),
                                          book_id=book_id, **options)


def tmp_work(target: Path) -> Path:
    return target.parent / "export_work"


def test_the_chapters_are_cut_like_the_player_and_the_title_is_read(tmp_path: Path) -> None:
    _app_, _id, path, _fake = _library(tmp_path)
    chapters = listen_export.load_chapters(path)
    assert [chapter.title for chapter in chapters] == ["Chương một", "Chương hai"]
    assert [[paragraph.text for paragraph in chapter.paragraphs] for chapter in chapters] == [
        ["Chương một", "Một hai ba.", "***", "Bốn năm."], ["Chương hai", "Sáu bảy tám chín."]]
    assert chapters[0].gaps == [0, 0, 1500, 0] and chapters[1].gaps == [0, 0]
    assert chapters[0].chars == len("Chương một") + len("Một hai ba.") + len("Bốn năm.")


def test_an_mp3_folder_has_one_tagged_file_per_chapter_and_a_playlist(tmp_path: Path) -> None:
    app, book_id, path, fake = _library(tmp_path)
    steps: list[dict[str, Any]] = []
    result = _run(app, book_id, path, tmp_path / "xuat", "mp3", progress=lambda **fields: steps.append(fields))
    folder = tmp_path / "xuat" / "Truyện thử"
    names = sorted(file.name for file in folder.iterdir())
    assert names == ["01 - Chương một.mp3", "02 - Chương hai.mp3", "Truyện thử.m3u8"]
    assert Path(result["folder"]) == folder and result["files"] == 2 and result["chapters"] == 2 and result["chaptersTotal"] == 2
    assert result["format"] == "mp3" and result["size"] == sum(file.stat().st_size for file in folder.glob("*.mp3"))
    for number, name in ((1, names[0]), (2, names[1])):
        probe = _probe(folder / name)
        tags = probe["format"]["tags"]
        assert (tags["title"], tags["album"], tags["track"]) == (["Chương một", "Chương hai"][number - 1], "Truyện thử", f"{number}/2")
        audio = probe["streams"][0]
        assert audio["codec_name"] == "mp3" and audio["channels"] == 1
        assert abs(float(probe["format"]["duration"]) - EXPECTED[number]) <= 0.15, (number, probe["format"]["duration"])
    playlist = (folder / "Truyện thử.m3u8").read_bytes().decode("utf-8")
    assert playlist.splitlines()[:2] == ["#EXTM3U", "#PLAYLIST:Truyện thử"] and "01 - Chương một.mp3" in playlist
    assert sorted(fake.calls) == sorted(["Chương một", "Một hai ba.", "Bốn năm.", "Chương hai", "Sáu bảy tám chín."])
    assert not (tmp_path / "export_work" / listen_export.work_folder(Path("."), book_id).name).exists(), "thư mục tạm bị xoá khi xong"
    assert steps and steps[-1]["percent"] == 100 and {step["phase"] for step in steps} == {"voice", "encode"}
    assert max(step["chapter"] for step in steps) == 2 and all(step["chapters"] == 2 for step in steps)


def test_an_m4b_is_one_file_with_a_chapter_list(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    result = _run(app, book_id, path, tmp_path / "xuat", "m4b")
    file = tmp_path / "xuat" / "Truyện thử.m4b"
    assert Path(result["file"]) == file and result["chapters"] == 2 and result["size"] == file.stat().st_size and result["format"] == "m4b"
    probe = _probe(file)
    assert [chapter["tags"]["title"] for chapter in probe["chapters"]] == ["Chương một", "Chương hai"]
    bounds = [(float(chapter["start_time"]), float(chapter["end_time"])) for chapter in probe["chapters"]]
    for (start, end), want in zip(bounds, [(0.0, EXPECTED[1]), (EXPECTED[1], EXPECTED[1] + EXPECTED[2])]):
        assert abs(start - want[0]) <= 0.1 and abs(end - want[1]) <= 0.1, bounds
    assert probe["format"]["tags"]["major_brand"] == "M4B " and probe["format"]["tags"]["album"] == "Truyện thử"
    assert [file.name for file in (tmp_path / "xuat").iterdir()] == ["Truyện thử.m4b"], "không để lại file tạm"


def test_a_clip_already_in_the_cache_is_not_read_again(tmp_path: Path) -> None:
    app, book_id, path, fake = _library(tmp_path)
    app.readaloud.clip(VOICE, "Một hai ba.")  # người nghe đã nghe đoạn này
    fake.calls.clear()
    _run(app, book_id, path, tmp_path / "xuat", "mp3")
    assert "Một hai ba." not in fake.calls and len(fake.calls) == 4
    fake.calls.clear()
    _run(app, book_id, path, tmp_path / "xuat2", "m4b")
    assert fake.calls == [], "lần xuất thứ hai chỉ dùng clip trong bộ đệm"


def test_cancelling_keeps_the_finished_chapters_and_the_next_export_continues_from_them(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    stop = threading.Event()
    with pytest.raises(export_jobs.Cancelled):
        _run(app, book_id, path, tmp_path / "xuat", "mp3", cancelled=stop.is_set,
             progress=lambda **fields: stop.set() if fields["chapter"] == 2 else None)
    work = listen_export.work_folder(tmp_path / "export_work", book_id)
    assert (work / "1.done").is_file() and (work / "1.flac").is_file() and not (work / "2.done").exists()
    assert not (tmp_path / "xuat" / "Truyện thử").exists(), "chưa mã hoá gì khi huỷ giữa pha đọc"

    pumped: list[str] = []
    real = export.pump_pcm
    monkeypatch.setattr(export, "pump_pcm", lambda ffmpeg, source, rate, channels, sink: (pumped.append(source.name), real(ffmpeg, source, rate, channels, sink))[1])
    _run(app, book_id, path, tmp_path / "xuat", "mp3")
    # chương 1 không ghép lại: chỉ 2 đoạn của chương 2 qua ống PCM (cộng 0 đoạn của chương 1)
    assert len(pumped) == 2
    assert sorted(file.name for file in (tmp_path / "xuat" / "Truyện thử").glob("*.mp3")) == ["01 - Chương một.mp3", "02 - Chương hai.mp3"]
    assert not work.exists()


def test_a_chapter_made_with_another_voice_or_reading_is_not_reused(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    stop = threading.Event()
    with pytest.raises(export_jobs.Cancelled):
        _run(app, book_id, path, tmp_path / "xuat", "m4b", cancelled=stop.is_set, progress=lambda **fields: stop.set() if fields["chapter"] == 2 else None)
    work = listen_export.work_folder(tmp_path / "export_work", book_id)
    chapters = listen_export.load_chapters(path)
    same = listen_export.Reading(VOICE, None, {})
    assert listen_export.chapter_ready(work, chapters[0], same) is not None
    assert listen_export.chapter_ready(work, chapters[0], listen_export.Reading("fake:khac", None, {})) is None
    assert listen_export.chapter_ready(work, chapters[0], listen_export.Reading(VOICE, "ja", {})) is None
    assert listen_export.chapter_ready(work, chapters[0], listen_export.Reading(VOICE, None, {"Một": "Nhất"})) is None
    assert listen_export.chapter_ready(work, chapters[1], same) is None, "chương chưa làm xong không có dấu"


def test_a_listener_who_is_hearing_a_clip_goes_first(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    app.readaloud._live = 1
    waits: list[float] = []
    seen: list[Any] = []

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        if len(waits) == 3:
            app.readaloud._live = 0  # người nghe nghe xong đoạn của họ

    _run(app, book_id, path, tmp_path / "xuat", "mp3", sleep=sleep, progress=lambda **fields: seen.append(fields["waiting"]))
    assert len(waits) == 3 and "listening" in seen and seen[-1] is None


def test_a_voice_that_fails_stops_the_export_in_words_and_keeps_the_work(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    app.readaloud = ReadAloud(tmp_path / "cache2", [FakeVoice(fail=VoiceError("Khoá Azure không dùng được", "auth"))])
    with pytest.raises(listen_export.ExportError, match="Chương một.*Khoá Azure không dùng được.*xuất lại"):
        _run(app, book_id, path, tmp_path / "xuat", "mp3")
    # lỗi thoáng qua được thử lại rồi mới dừng
    sleeps: list[float] = []
    flaky = FakeVoice(fail=VoiceError("mất mạng", "offline"))
    app.readaloud = ReadAloud(tmp_path / "cache3", [flaky])
    with pytest.raises(listen_export.ExportError, match="mất mạng"):
        _run(app, book_id, path, tmp_path / "xuat", "mp3", sleep=sleeps.append)
    assert len(flaky.calls) == 1 + listen_export.RETRIES and sleeps == [1.0, 2.0]


def test_a_paragraph_the_voice_cannot_read_is_skipped_like_prepare_does(tmp_path: Path) -> None:
    class Quiet(FakeVoice):
        def synthesize(self, text: str, native_voice: str) -> Synthesis:
            if text == "Bốn năm.":
                raise VoiceError("không có gì để đọc", "empty")
            return super().synthesize(text, native_voice)

    app, book_id, path, _fake = _library(tmp_path)
    app.readaloud = ReadAloud(tmp_path / "cache4", [Quiet()])
    _run(app, book_id, path, tmp_path / "xuat", "mp3")
    probe = _probe(tmp_path / "xuat" / "Truyện thử" / "01 - Chương một.mp3")
    assert abs(float(probe["format"]["duration"]) - (5 * WORD + GAP)) <= 0.15


def test_the_plan_counts_the_book_and_knows_what_is_ready(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    chapters = listen_export.load_chapters(path)
    work = listen_export.work_folder(tmp_path / "export_work", book_id)
    reading = listen_export.Reading(VOICE, None, {})
    plan = listen_export.plan(chapters, reading, work, None)
    chars = sum(chapter.chars for chapter in chapters)
    assert plan == {"chapters": 2, "chars": chars, "audioSeconds": round(chars / 14), "rtf": None, "secondsEstimate": None, "readyChapters": 0}
    assert listen_export.plan(chapters, reading, work, 0.5)["secondsEstimate"] == round(chars / 14 * 0.5)


# ---- đường dẫn của máy chủ giao diện --------------------------------------------------------------------------------------------


def _wait(port: int, book_id: str, states: tuple[str, ...]) -> dict[str, Any]:
    deadline = time.time() + 60
    while time.time() < deadline:
        job = json.loads(_request(port, "GET", f"/api/listen/books/{book_id}/audiobook", headers=TOKEN)[1])
        if job["state"] in states:
            return job
        time.sleep(0.1)
    raise AssertionError("việc xuất không xong")


def test_the_server_exports_a_text_book_in_the_background_and_reports_progress(tmp_path: Path) -> None:
    app, book_id, _path, fake = _library(tmp_path)
    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "GET", f"/api/listen/books/{book_id}/audiobook/plan?voice={VOICE}", headers=TOKEN)
        plan = json.loads(data)
        assert status == 200 and plan["chapters"] == 2 and plan["chars"] > 0 and plan["ffmpeg"]["ready"] is True and plan["readyChapters"] == 0
        assert json.loads(_request(server.port, "GET", f"/api/listen/books/{book_id}/audiobook", headers=TOKEN)[1]) == {"state": "idle"}
        body = {"format": "m4b", "voice": VOICE, "target": str(tmp_path / "xuat")}
        status, data, _ = _request(server.port, "POST", f"/api/listen/books/{book_id}/audiobook", headers=TOKEN, body=body)
        assert status == 202 and json.loads(data)["state"] in ("running", "done")
        job = _wait(server.port, book_id, ("done", "error"))
        assert job["state"] == "done", job
        assert job["result"]["file"] == str(tmp_path / "xuat" / "Truyện thử.m4b") and job["result"]["chapters"] == 2
        assert job["percent"] == 100 and job["chapters"] == 2 and "finishedAgo" in job
        assert str(tmp_path / "xuat") in app.exports, "Mở thư mục được phép"
        assert len(fake.calls) == 5
    finally:
        server.stop()


def test_the_server_cancels_a_running_export(tmp_path: Path) -> None:
    app, book_id, _path, fake = _library(tmp_path)
    app.readaloud._live = 1  # người nghe giữ đường: lượt xuất đứng chờ nên huỷ chắc chắn bắt được nó đang chạy
    server = Server(app, port=0).start()
    try:
        body = {"format": "mp3", "voice": VOICE, "target": str(tmp_path / "xuat")}
        assert _request(server.port, "POST", f"/api/listen/books/{book_id}/audiobook", headers=TOKEN, body=body)[0] == 202
        running = _wait(server.port, book_id, ("running",))
        deadline = time.time() + 20
        while running.get("waiting") != "listening" and time.time() < deadline:
            time.sleep(0.05)
            running = _wait(server.port, book_id, ("running",))
        assert running.get("waiting") == "listening"
        status, data, _ = _request(server.port, "POST", f"/api/listen/books/{book_id}/audiobook/cancel", headers=TOKEN, body={})
        assert status == 200
        job = _wait(server.port, book_id, ("cancelled", "error", "done"))
        assert job["state"] == "cancelled" and fake.calls == []
    finally:
        server.stop()


def test_the_server_refuses_what_cannot_be_exported_in_words(tmp_path: Path) -> None:
    app, book_id, _path, _fake = _library(tmp_path)
    server = Server(app, port=0).start()
    try:
        post = lambda body, book=book_id: _request(server.port, "POST", f"/api/listen/books/{book}/audiobook", headers=TOKEN, body=body)  # noqa: E731
        assert post({"format": "wav", "voice": VOICE})[0] == 400
        assert post({"format": "mp3"})[0] == 400, "thiếu giọng"
        assert post({"format": "mp3", "voice": "fake:khac"})[0] == 400, "giọng không có trên máy"
        assert post({"format": "mp3", "voice": VOICE}, "khong-co-sach")[0] == 404
        assert _request(server.port, "GET", f"/api/listen/books/{book_id}/audiobook/plan?voice=", headers=TOKEN)[0] == 400
        assert _request(server.port, "POST", f"/api/listen/books/{book_id}/audiobook", body={"format": "mp3", "voice": VOICE})[0] == 401
    finally:
        server.stop()


def test_a_studio_book_with_audio_is_not_exported_this_way(tmp_path: Path) -> None:
    from tests.test_export_series import _part

    library = tmp_path / "lib"
    library.mkdir()
    project = _part(tmp_path, library, "p1", "Truyện X")
    app = _app(tmp_path / "studio", library)
    app.readaloud = ReadAloud(tmp_path / "cache", [FakeVoice()])
    from abook.webui.library import book_id

    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", f"/api/listen/books/{book_id(project)}/audiobook", headers=TOKEN,
                                   body={"format": "mp3", "voice": VOICE})
        assert status == 409 and "chỉ có chữ" in json.loads(data)["error"]
    finally:
        server.stop()


# ---- tải ffmpeg và việc nền ---------------------------------------------------------------------------------------------------


def test_the_ffmpeg_download_runs_in_the_background_and_says_why_it_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    installed: list[bool] = []
    monkeypatch.setattr(ffmpeg_setup, "ready", lambda: bool(installed))
    monkeypatch.setattr(ffmpeg_setup, "cannot_download", lambda: "")

    def install(progress, cancelled=lambda: False):
        progress(10, 20)
        installed.append(True)

    monkeypatch.setattr(ffmpeg_setup, "install", install)
    assert ffmpeg_setup.status()["ready"] is False and ffmpeg_setup.status()["bytes"] == ffmpeg_setup.WHEEL.size
    ffmpeg_setup.start()
    ffmpeg_setup.join(10)
    status = ffmpeg_setup.status()
    assert status["ready"] is True and status["downloading"] is False and status["error"] == ""

    installed.clear()
    monkeypatch.setattr(ffmpeg_setup, "cannot_download", lambda: "tải bộ đọc nhạc đang bị tắt trên máy này")
    ffmpeg_setup.start()
    assert ffmpeg_setup.status()["error"] == "Tải bộ đọc nhạc đang bị tắt trên máy này." and ffmpeg_setup.status()["downloading"] is False

    monkeypatch.setattr(ffmpeg_setup, "cannot_download", lambda: "")
    monkeypatch.setattr(ffmpeg_setup, "install", lambda progress, cancelled=lambda: False: (_ for _ in ()).throw(OSError(28, "No space left")))
    ffmpeg_setup.start()
    ffmpeg_setup.join(10)
    assert "Không ghi được vào ổ đĩa" in str(ffmpeg_setup.status()["error"])


def test_a_job_reports_progress_and_ends_cancelled_when_asked() -> None:
    jobs = export_jobs.BookFileJobs()
    release = threading.Event()

    def work() -> dict[str, Any]:
        jobs.update("k", percent=40)
        while not jobs.cancelled("k"):
            if release.wait(0.01):
                break
        raise export_jobs.Cancelled()

    jobs.start("k", work)
    deadline = time.time() + 5
    while jobs.status("k").get("percent") != 40 and time.time() < deadline:
        time.sleep(0.01)
    assert jobs.status("k")["state"] == "running" and jobs.status("k")["percent"] == 40
    assert jobs.cancel("k") is True
    while jobs.status("k")["state"] == "running" and time.time() < deadline:
        time.sleep(0.01)
    final = jobs.status("k")
    assert final["state"] == "cancelled" and "finishedAgo" in final and "error" not in final
    assert jobs.cancel("k") is False, "không còn việc nào để huỷ"
    jobs.update("k", percent=99)  # việc đã xong: không ghi thêm
    assert jobs.status("k")["percent"] == 40
