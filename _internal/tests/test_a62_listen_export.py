"""Soát a62 (xuất sách nói của sách Nghe ngay trên máy tính, webui/listen_export.py):
1. `export_work/<mã sách>` của lượt bỏ dở không bao giờ được dọn;
2. Huỷ ở pha đọc chờ hết đoạn đang đọc (7 giây), Huỷ ở pha kiểm đỉnh bị bỏ qua;
3. "còn khoảng 4 phút" từ một đoạn đo (thật còn 51 giây);
4. hộp Xuất nói "khoảng 10 phút" cho cuốn thật 8:44 và không nói phần đã có trong bộ đệm Nghe ngay;
5. mất mạng quá ~3 giây là dừng cả lượt.
Giọng giả và sách thử dùng chung với test_listen_export.py."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from abook.readaloud import edge
from abook.readaloud.model import VoiceError
from abook.readaloud.service import EdgeProvider, ReadAloud
from abook.webui import export_jobs, listen_export
from tests.test_listen_export import EXPECTED, GAP, VOICE, WORD, FakeVoice, _library, _run, tmp_work

pytestmark = pytest.mark.skipif(not listen_export.ffmpeg_available(), reason="cần ffmpeg")

EDGE_VOICE = "edge:vi-VN-HoaiMyNeural"


class Clock:
    """Đồng hồ giả: `sleep` chỉ đẩy giờ."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now = round(self.now + seconds, 9)  # bước 0,2 giây cộng dồn không lệch số thực


# ---- 2. Huỷ: lượt đọc Edge đang bay bị cắt, pha kiểm đỉnh và mã hoá MP3 cũng nghe Huỷ ----------------------------------------------

class HangingEdge(edge.EdgeClient):
    """Edge "chậm": mảnh nào cũng treo tới khi clip của nó bị cắt (`_Clip.abort`, như ổ cắm bị đóng)."""

    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.cut: list[str] = []

    def _speak_piece(self, voice: str, piece: str, deadline: float, clip: Any = None, rank: int = edge.RANK_BACKGROUND, part: Any = None) -> Any:
        self.started.set()
        end = time.monotonic() + 20
        while time.monotonic() < end:
            if clip is not None and clip.aborted:
                self.cut.append(piece)
                raise edge._ClipAborted("Clip đã bỏ.")
            time.sleep(0.01)
        raise AssertionError("mảnh không bao giờ bị cắt")


def test_cancel_cuts_the_edge_read_in_flight_within_a_second_and_caches_nothing(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    hanging = HangingEdge()
    app.readaloud = ReadAloud(tmp_path / "cache_edge", [EdgeProvider(hanging)])
    stop = threading.Event()
    outcome: dict[str, Any] = {}

    def export() -> None:
        try:
            listen_export.export_audiobook(app.readaloud, path, tmp_path / "xuat", tmp_work(tmp_path / "xuat"), fmt="m4b", book_id=book_id,
                                           reading=listen_export.Reading(EDGE_VOICE, None, {}), cancelled=stop.is_set)
        except BaseException as error:  # noqa: BLE001 - bài thử ghi lại để kiểm
            outcome["error"] = error
        outcome["at"] = time.monotonic()

    worker = threading.Thread(target=export)
    worker.start()
    assert hanging.started.wait(20), "lượt đọc chưa bắt đầu"
    time.sleep(0.3)
    asked = time.monotonic()
    stop.set()
    worker.join(10)
    assert not worker.is_alive()
    assert isinstance(outcome.get("error"), export_jobs.Cancelled), outcome
    assert outcome["at"] - asked <= 1.5, outcome["at"] - asked
    deadline = time.monotonic() + 2
    while not hanging.cut and time.monotonic() < deadline:  # luồng của mảnh thấy cắt ở lần hỏi kế của nó
        time.sleep(0.01)
    assert hanging.cut, "ổ cắm của mảnh đang đọc bị cắt"
    assert not list((tmp_path / "cache_edge").glob("*.mp3")), "clip dở không vào bộ đệm"
    work = listen_export.work_folder(tmp_work(tmp_path / "xuat"), book_id)
    assert not list(work.glob("*.part")) and not list(work.glob("*.done"))


def test_cancel_while_the_m4b_peaks_are_measured_writes_no_file_and_keeps_the_chapters(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    stop = threading.Event()
    phases: list[str] = []

    def progress(**fields: Any) -> None:
        phases.append(fields["phase"])
        if fields["phase"] == "peaks":
            stop.set()

    with pytest.raises(export_jobs.Cancelled):
        _run(app, book_id, path, tmp_path / "xuat", "m4b", cancelled=stop.is_set, progress=progress)
    assert "peaks" in phases
    assert not list((tmp_path / "xuat").glob("*.m4b")) and not list((tmp_path / "xuat").glob(".m4b-*")), "không ghi file đích, không để thư mục tạm"
    work = listen_export.work_folder(tmp_work(tmp_path / "xuat"), book_id)
    assert (work / "1.done").is_file() and (work / "2.done").is_file(), "chương đã ghép được giữ cho lần sau"


def test_cancel_while_encoding_an_mp3_chapter_stops_and_leaves_no_half_file(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    stop = threading.Event()
    with pytest.raises(export_jobs.Cancelled):
        _run(app, book_id, path, tmp_path / "xuat", "mp3", cancelled=stop.is_set,
             progress=lambda **fields: stop.set() if fields["phase"] == "encode" else None)
    work = listen_export.work_folder(tmp_work(tmp_path / "xuat"), book_id)
    assert not list(work.glob("*.mp3")), "MP3 dở của chương bị xoá"
    assert not list((tmp_path / "xuat" / "Truyện thử").glob("*.mp3"))
    assert (work / "1.done").is_file() and (work / "2.done").is_file()


def test_waiting_for_another_read_of_the_same_paragraph_can_be_cancelled(tmp_path: Path) -> None:
    reader = ReadAloud(tmp_path / "cache", [FakeVoice()])
    gate = threading.Lock()
    gate.acquire()  # lượt đọc khác của cùng đoạn đang giữ khoá
    flag = threading.Event()
    threading.Timer(0.3, flag.set).start()
    began = time.monotonic()
    from abook.readaloud import service

    with pytest.raises(VoiceError) as caught:
        service._take(gate, flag.is_set)
    assert caught.value.reason == "cancelled" and time.monotonic() - began < 1.0


# ---- 3. "còn khoảng ..." chỉ khi đã đo đủ, theo phần chưa có clip -----------------------------------------------------------------

def _bare_run(app: Any, path: Path, book_id: str, clock: Clock) -> listen_export._Run:
    chapters = listen_export.load_chapters(path)
    return listen_export._Run(app.readaloud, "ffmpeg", chapters, listen_export.Reading(VOICE, None, {}), tmp_path_work(path), lambda **_f: None,
                              lambda: False, clock.sleep, clock, book_id)


def tmp_path_work(path: Path) -> Path:
    return path.parent / "work_eta"


def test_time_left_is_hidden_until_three_new_reads_and_twenty_seconds(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    clock = Clock()
    run = _bare_run(app, path, book_id, clock)
    run.count_open(run.chapters)
    total = sum(chapter.chars for chapter in run.chapters)
    assert run.open_chars == total, "bộ đệm trống: mọi đoạn phải đọc mới"
    run.timed_chars, run.timed_seconds, run.reads = 20, 4.0, 1  # một đoạn đo (soát a62: "còn khoảng 4 phút" từ đúng một mẫu)
    clock.now = 60
    assert run.seconds_left() is None
    run.reads = 3
    clock.now = 19
    assert run.seconds_left() is None, "chưa đủ 20 giây chạy"
    clock.now = 20
    assert run.seconds_left() == round(4.0 / 20 * total)


def test_time_left_counts_only_paragraphs_without_a_clip(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    app.readaloud.clip(VOICE, "Một hai ba.", book=book_id)  # người nghe đã nghe đoạn này
    app.readaloud.clip(VOICE, "Chương hai", book=book_id)
    run = _bare_run(app, path, book_id, Clock())
    run.count_open(run.chapters)
    total = sum(chapter.chars for chapter in run.chapters)
    assert run.open_chars == total - len("Một hai ba.") - len("Chương hai")


def test_a_short_export_never_shows_a_time_left(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    steps: list[dict[str, Any]] = []
    _run(app, book_id, path, tmp_path / "xuat", "mp3", progress=lambda **fields: steps.append(fields))
    assert steps and all(step.get("secondsLeft") is None for step in steps)


# ---- 4. hộp Xuất: độ dài từ clip đã có, nói phần đã có sẵn ----------------------------------------------------------------------

def test_the_plan_takes_the_length_of_clips_already_heard_and_counts_them_as_ready(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    for text in ("Chương một", "Một hai ba.", "Bốn năm."):  # cả chương 1 đã nghe
        app.readaloud.clip(VOICE, text, book=book_id)
    chapters = listen_export.load_chapters(path)
    reading = listen_export.Reading(VOICE, None, {})
    plan = listen_export.plan(chapters, reading, tmp_path / "w", 0.5, listen_export.cached_lookup(app.readaloud, reading, book_id))
    heard = (2 + 3 + 2) * WORD  # giây clip thật của chương 1
    rate = chapters[0].chars / heard  # chữ mỗi giây ĐO trên clip của chính cuốn / giọng này
    left = chapters[1].chars / rate
    assert plan["readyChapters"] == 1 and plan["readySeconds"] == round(heard)
    assert plan["audioSeconds"] == round(heard + GAP + left)
    assert abs(plan["audioSeconds"] - (EXPECTED[1] + EXPECTED[2])) <= 1, "gần độ dài thật của cuốn"
    assert plan["secondsEstimate"] == round(left * 0.5), "máy chỉ phải đọc phần chưa có"


def test_the_plan_without_any_clip_of_the_book_keeps_the_old_rate(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    app.readaloud.clip(VOICE, "Một hai ba.")  # clip không ghi vào sổ của cuốn: tra nhanh bỏ qua
    chapters = listen_export.load_chapters(path)
    reading = listen_export.Reading(VOICE, None, {})
    plan = listen_export.plan(chapters, reading, tmp_path / "w", None, listen_export.cached_lookup(app.readaloud, reading, book_id))
    chars = sum(chapter.chars for chapter in chapters)
    assert plan["readyChapters"] == 0 and plan["audioSeconds"] == round(chars / listen_export.CHARS_PER_SECOND + GAP)


def test_an_export_notes_its_clips_in_the_book_so_the_next_plan_sees_them(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    stop = threading.Event()
    with pytest.raises(export_jobs.Cancelled):
        _run(app, book_id, path, tmp_path / "xuat", "mp3", cancelled=stop.is_set, progress=lambda **fields: stop.set() if fields["chapter"] == 2 else None)
    listen_export.remove_work(tmp_work(tmp_path / "xuat"), book_id)  # chỉ còn clip trong bộ đệm
    chapters = listen_export.load_chapters(path)
    reading = listen_export.Reading(VOICE, None, {})
    plan = listen_export.plan(chapters, reading, tmp_path / "w", None, listen_export.cached_lookup(app.readaloud, reading, book_id))
    assert plan["readyChapters"] >= 1


# ---- 5. mất mạng: chờ tới 30 giây liền, "Đang chờ mạng…" -----------------------------------------------------------------------

class Outage(FakeVoice):
    """Mất mạng `fails` lần đầu (VoiceError "offline"), sau đó đọc bình thường."""

    def __init__(self, fails: int, reason: str = "offline") -> None:
        super().__init__()
        self.fails, self.reason = fails, reason

    def synthesize(self, text: str, native_voice: str) -> Any:
        if self.fails > 0:
            self.fails -= 1
            self.calls.append(text)
            raise VoiceError("Không có mạng để dùng giọng trực tuyến.", self.reason)
        return super().synthesize(text, native_voice)


def test_a_short_outage_waits_for_the_network_and_the_export_finishes(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    app.readaloud = ReadAloud(tmp_path / "cache_net", [Outage(4)])
    clock = Clock()
    seen: list[tuple[float, Any]] = []
    result = _run(app, book_id, path, tmp_path / "xuat", "m4b", sleep=clock.sleep, clock=clock,
                  progress=lambda **fields: seen.append((clock.now, fields.get("waiting"))))
    assert result["chapters"] == 2
    waits = [moment for moment, waiting in seen if waiting == "network"]
    assert [round(b - a, 3) for a, b in zip(waits, waits[1:])] == [1.0, 2.0, 4.0], "nghỉ 1, 2, 4, 8 giây"
    assert clock.now == pytest.approx(15.0)
    assert seen[-1][1] is None and any(waiting is None and moment == pytest.approx(15.0) for moment, waiting in seen), "hết chờ mạng"


def test_an_outage_longer_than_thirty_seconds_stops_in_words_and_keeps_the_work(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    outage = Outage(10**6)
    app.readaloud = ReadAloud(tmp_path / "cache_net", [outage])
    clock = Clock()
    with pytest.raises(listen_export.ExportError, match="Không có mạng.*xuất lại"):
        _run(app, book_id, path, tmp_path / "xuat", "mp3", sleep=clock.sleep, clock=clock)
    assert clock.now == pytest.approx(1 + 2 + 4 + 8 + 15 + 15), "thử tới khi mất liên tục quá 30 giây"
    assert len(outage.calls) == 7


def test_a_timeout_counts_as_network_but_a_refusal_does_not(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    app.readaloud = ReadAloud(tmp_path / "cache_t", [Outage(3, "timeout")])
    clock = Clock()
    _run(app, book_id, path, tmp_path / "xuat", "mp3", sleep=clock.sleep, clock=clock)
    assert clock.now == pytest.approx(1 + 2 + 4)
    refused = Outage(10**6, "rejected")
    app.readaloud = ReadAloud(tmp_path / "cache_r", [refused])
    clock = Clock()
    with pytest.raises(listen_export.ExportError):
        _run(app, book_id, path, tmp_path / "xuat2", "mp3", sleep=clock.sleep, clock=clock)
    assert len(refused.calls) == 1 + listen_export.RETRIES and clock.now == pytest.approx(1 + 2), "403 / bị từ chối: như cũ"


def test_cancel_while_waiting_for_the_network_stops_at_once(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    app.readaloud = ReadAloud(tmp_path / "cache_net", [Outage(10**6)])
    clock = Clock()
    stop = threading.Event()

    def sleep(seconds: float) -> None:
        clock.sleep(seconds)
        if clock.now >= 2.5:
            stop.set()

    with pytest.raises(export_jobs.Cancelled):
        _run(app, book_id, path, tmp_path / "xuat", "mp3", sleep=sleep, clock=clock, cancelled=stop.is_set)
    assert clock.now <= 2.5 + listen_export.CANCEL_POLL + 1e-9


# ---- 1. thư mục làm việc được dọn -----------------------------------------------------------------------------------------

def _work_with_file(root: Path, book: str, age_days: float = 0) -> Path:
    folder = listen_export.work_folder(root, book)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "1.flac").write_bytes(b"x" * 10)
    if age_days:
        moment = time.time() - age_days * 86400
        for item in (folder / "1.flac", folder):
            os.utime(item, (moment, moment))
    return folder


def test_sweep_removes_old_and_orphaned_work_but_never_a_running_one(tmp_path: Path) -> None:
    root = tmp_path / "export_work"
    old = _work_with_file(root, "sach_cu", 8)
    fresh = _work_with_file(root, "sach_moi", 1)
    orphan = _work_with_file(root, "sach_da_xoa")
    busy_old = _work_with_file(root, "dang_xuat", 30)
    busy_orphan = _work_with_file(root, "dang_xuat_mat")
    touched = _work_with_file(root, "vua_dung", 9)
    (touched / "2.flac").write_bytes(b"y")  # một chương vừa ghép hôm nay: thư mục còn được dùng
    removed = listen_export.sweep_work(root, ["sach_cu", "sach_moi", "dang_xuat", "vua_dung"], ["dang_xuat", "dang_xuat_mat"])
    assert sorted(removed) == sorted([old, orphan])
    assert not old.exists() and not orphan.exists()
    assert fresh.exists() and busy_old.exists() and busy_orphan.exists() and touched.exists()
    assert listen_export.sweep_work(tmp_path / "khong_co", None) == []


def test_the_app_sweeps_work_at_start_and_when_a_book_is_removed(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    root = app.export_work_dir
    mine = _work_with_file(root, book_id)
    gone = _work_with_file(root, "0123456789abcdef01234567")  # sách đã xoá từ trước
    removed = app.sweep_export_leftovers()
    assert gone in removed and not gone.exists() and mine.exists()

    # đang xuất: xoá sách không đụng thư mục làm việc của lượt ấy
    release = threading.Event()
    app.listen_exports.start(str(path), lambda: (release.wait(20), {})[1])
    try:
        assert book_id in app._listen_exporting()
        for item in (mine / "1.flac", mine):
            os.utime(item, (time.time() - 30 * 86400,) * 2)
        app.sweep_export_leftovers()
        assert mine.exists(), "lượt đang chạy: không dọn dù cũ"
    finally:
        release.set()
    deadline = time.time() + 10
    while app.listen_exports.running() and time.time() < deadline:
        time.sleep(0.02)
    app.remove_imported(book_id, undo=True)
    assert not mine.exists(), "xoá sách: thư mục làm việc của nó đi theo"


def test_removing_a_book_while_it_exports_keeps_its_work(tmp_path: Path) -> None:
    app, book_id, path, _fake = _library(tmp_path)
    mine = _work_with_file(app.export_work_dir, book_id)
    release = threading.Event()
    app.listen_exports.start(str(path), lambda: (release.wait(20), {})[1])
    try:
        app.remove_imported(book_id, undo=True)
        assert mine.exists()
    finally:
        release.set()
