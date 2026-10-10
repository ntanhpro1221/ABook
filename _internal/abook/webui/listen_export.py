"""Xuất sách nói (MP3 từng chương / một file M4B) cho sách Nghe ngay - sách chỉ có chữ (EPUB, TXT...) đọc bằng giọng của máy.

Người dùng muốn mang sách sang trình phát khác (điện thoại, xe hơi) thì cần file âm thanh. Mỗi chương được chia ra ĐÚNG các đoạn như trình phát
(`readaloud.paragraphs`: cùng chia đoạn, cùng khoảng lặng ở dòng ngăn cảnh), mỗi đoạn qua `ReadAloud.clip` - clip đã có trong bộ đệm (đã nghe, đã Làm trước,
đã xuất lần trước) dùng luôn, chỉ đoạn chưa có mới đọc mới. Việc NGHE luôn đi trước: có clip của người nghe đang đọc dở (`ReadAloud.live`) thì việc xuất đứng chờ.

Mỗi chương ghép thành MỘT file FLAC tạm (không mất tiếng, nhỏ hơn nửa WAV - sách 20 giờ ở 48 kHz mà để WAV là hơn 6 GB) trong `<dữ liệu app>/export_work/<mã sách>/`
cùng một dấu `.done` ghi dấu vân tay của chương (giọng + cách đọc + chữ). Huỷ hay tắt app giữa chừng rồi xuất lại thì chương nào còn dấu đúng được bỏ qua; xong cả
cuốn thì thư mục tạm bị xoá. Rồi mã hoá bằng ffmpeg của app: MP3 = mỗi chương một file (`export.write_mp3_folder`, cùng tag và danh sách phát với MP3 của Studio),
M4B = một file AAC có mục lục chương (`export.m4b_from_files`, cùng file với M4B của Studio).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..io_utils import ffmpeg_available, ffmpeg_executable, run_hidden
from ..readaloud import paragraphs as px
from ..readaloud.model import VoiceError
from ..readaloud.service import MAX_TEXT, ReadAloud
from . import book_edits, export, packages
from .export_jobs import Cancelled

WORK_FOLDER = "export_work"  # dưới thư mục dữ liệu của app
FORMATS = ("mp3", "m4b")
CHAPTER_CHANNELS = 1  # sách nói giọng đọc: mono (MP3 64 kb/s mono; AAC 64 kb/s mono như M4B của Studio)
MP3_ARGS = ["-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1", "-f", "mp3"]
FLAC_ARGS = ["-c:a", "flac", "-f", "flac"]
CHARS_PER_SECOND = 14  # như trình phát ước đoạn chưa đọc (readAloud.ts, readaloud/prepare.py)
CACHED_SECONDS = 0.05  # clip trả nhanh hơn thế là từ bộ đệm: không nói gì về tốc độ giọng
RETRIES = 2  # lỗi thoáng qua của giọng trực tuyến (502...): thử lại như trình phát, rồi mới dừng
TRANSIENT = ("offline", "timeout", "service", "rejected")


class ExportError(ValueError):
    """Lỗi có lời cho người dùng (hiện nguyên văn ở thông báo)."""


@dataclass(frozen=True)
class Chapter:
    id: int
    title: str
    paragraphs: list[px.Paragraph]
    gaps: list[int]  # quãng lặng (ms) sau từng đoạn - px.scene_break_gaps

    @property
    def speakable(self) -> list[px.Paragraph]:
        return [paragraph for paragraph in self.paragraphs if px.is_speakable(paragraph.text)]

    @property
    def chars(self) -> int:
        return sum(len(paragraph.text) for paragraph in self.speakable)


@dataclass(frozen=True)
class Reading:
    """Cách đọc cuốn: giọng + gốc Nhật / Hàn + cách đọc riêng - cùng thứ người nghe dùng, nên cùng khoá bộ đệm clip."""

    voice: str
    origin: str | None
    readings: dict[str, str]


def load_chapters(path: Path) -> list[Chapter]:
    """Các chương có chữ của một cuốn Nghe ngay, đã bỏ các dòng người nghe chọn bỏ (lớp sửa `skip`) và cắt thành đoạn như trình phát; chương không có gì đọc được bị bỏ."""
    out: list[Chapter] = []
    for chapter in packages.edited_manifest(path).get("chapters") or []:
        if not isinstance(chapter, dict) or not chapter.get("text") or not isinstance(chapter.get("id"), int):
            continue
        text = packages.chapter_text(path, chapter["id"]) or ""
        split = px.split_paragraphs(px.without_lines(text, chapter.get("skip") or []))
        item = Chapter(chapter["id"], str(chapter.get("fullTitle") or chapter.get("title") or f"Chương {chapter.get('index') or chapter['id']}"),
                       split, px.scene_break_gaps(split))
        if item.speakable:
            out.append(item)
    return out


def fingerprint(chapter: Chapter, reading: Reading) -> str:
    """Dấu vân tay của chương đã ghép: đổi giọng, cách đọc, gốc hay chữ (kể cả dòng bỏ) thì chương tạm cũ không dùng lại được."""
    data = json.dumps([reading.voice, reading.origin, sorted(reading.readings.items()),
                       [[paragraph.text, gap] for paragraph, gap in zip(chapter.paragraphs, chapter.gaps)]], ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def work_folder(root: Path, book_id: str) -> Path:
    return Path(root) / re.sub(r"[^A-Za-z0-9_-]", "_", book_id)


def _done_path(work: Path, chapter: Chapter) -> Path:
    return work / f"{chapter.id}.done"


def _flac_path(work: Path, chapter: Chapter) -> Path:
    return work / f"{chapter.id}.flac"


def chapter_ready(work: Path, chapter: Chapter, reading: Reading) -> dict[str, Any] | None:
    """Dấu `.done` của chương nếu chương tạm còn nguyên và đúng dấu vân tay; không thì None."""
    try:
        done = json.loads(_done_path(work, chapter).read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(done, dict) or done.get("fingerprint") != fingerprint(chapter, reading) or not _flac_path(work, chapter).is_file():
        return None
    return done


def plan(chapters: list[Chapter], reading: Reading, work: Path, speed: float | None) -> dict[str, Any]:
    """Cho hộp Xuất: số chương, số chữ, thời gian nghe, ước thời gian máy làm (chỉ khi giọng đã đo tốc độ `speed`), và số chương đã làm sẵn từ lần trước."""
    chars = sum(chapter.chars for chapter in chapters)
    audio = chars / CHARS_PER_SECOND
    ready = sum(1 for chapter in chapters if chapter_ready(work, chapter, reading))
    return {"chapters": len(chapters), "chars": chars, "audioSeconds": round(audio), "rtf": speed,
            "secondsEstimate": round(audio * speed) if speed else None, "readyChapters": ready}


class _Run:
    """Một lượt xuất: giữ tiến độ (theo số chữ) và mọi thứ các bước cần."""

    def __init__(self, reader: ReadAloud, ffmpeg: str, chapters: list[Chapter], reading: Reading, work: Path,
                 progress: Callable[..., None], cancelled: Callable[[], bool], sleep: Callable[[float], None]) -> None:
        self.reader, self.ffmpeg, self.chapters, self.reading, self.work = reader, ffmpeg, chapters, reading, work
        self._progress, self._cancelled, self._sleep = progress, cancelled, sleep
        self.chars = sum(chapter.chars for chapter in chapters)
        self.done_chars = 0
        self.timed_chars = 0
        self.timed_seconds = 0.0

    def check(self) -> None:
        if self._cancelled():
            raise Cancelled()

    def report(self, index: int, chapter: Chapter, phase: str, waiting: str | None = None) -> None:
        left = None
        if self.timed_chars and self.timed_seconds:
            left = round(self.timed_seconds / self.timed_chars * (self.chars - self.done_chars))
        self._progress(phase=phase, chapter=index + 1, chapters=len(self.chapters), chapterTitle=chapter.title, waiting=waiting,
                       percent=min(100, round(100 * self.done_chars / self.chars)) if self.chars else 100,
                       chars=self.chars, charsDone=self.done_chars, secondsLeft=left)

    def clip_file(self, index: int, chapter: Chapter, text: str) -> Path | None:
        """Clip của một đoạn (từ bộ đệm hay đọc mới); None khi đoạn không có gì giọng đọc được (như Làm trước, bỏ qua). Người nghe đi trước; lỗi thoáng qua thử lại,
        lỗi thật dừng cả lượt với lời nói rõ."""
        failures = 0
        while True:
            waiting = False
            while self.reader.live > 0:  # người đang nghe: nhường
                self.check()
                if not waiting:
                    self.report(index, chapter, "voice", "listening")
                    waiting = True
                self._sleep(0.2)
            self.check()
            if waiting:
                self.report(index, chapter, "voice")
            began = time.perf_counter()
            try:
                clip = self.reader.clip(self.reading.voice, text, background=True, origin=self.reading.origin, readings=self.reading.readings)
            except VoiceError as error:
                if error.reason == "empty":
                    return None
                if error.reason in TRANSIENT and failures < RETRIES:
                    failures += 1
                    self._sleep(float(failures))
                    continue
                raise ExportError(f"Giọng đọc không đọc được một đoạn ở “{chapter.title}”: {error} Phần đã làm được giữ - bấm xuất lại để làm tiếp.") from error
            spent = time.perf_counter() - began
            if spent > CACHED_SECONDS:
                self.timed_chars += len(text)
                self.timed_seconds += spent
            path = self.reader.cache.path(clip["file"])
            if path is None:
                raise ExportError("Bộ đệm giọng đọc vừa mất một đoạn - bấm xuất lại để làm tiếp.")
            return path

    def build_chapter(self, index: int, chapter: Chapter) -> dict[str, Any]:
        """Ghép chương thành FLAC tạm: clip từng đoạn đọc được + quãng lặng ở dòng ngăn cảnh, đúng như trình phát."""
        self.report(index, chapter, "voice")
        # Tần số mẫu của chương theo clip đầu đọc được (clip đã vào bộ đệm: lần gọi trong `feed` sau đó trả ngay).
        rate = next((export.audio_layout(self.ffmpeg, source)[0] for paragraph in chapter.speakable
                     if (source := self.clip_file(index, chapter, paragraph.text)) is not None), 0)
        if not rate:
            raise ExportError(f"Giọng đọc không đọc được gì ở “{chapter.title}”.")
        final = _flac_path(self.work, chapter)
        partial = final.with_name(final.name + ".part")
        done = _done_path(self.work, chapter)
        done.unlink(missing_ok=True)

        def feed(sink: Any) -> int:
            samples = 0
            for paragraph, gap in zip(chapter.paragraphs, chapter.gaps):
                if px.is_speakable(paragraph.text):
                    if len(paragraph.text) > MAX_TEXT:
                        raise ExportError(f"Một đoạn của “{chapter.title}” dài quá để đọc một lượt.")
                    source = self.clip_file(index, chapter, paragraph.text)
                    if source is not None:
                        samples += export.pump_pcm(self.ffmpeg, source, rate, CHAPTER_CHANNELS, sink) // (2 * CHAPTER_CHANNELS)
                    self.done_chars += len(paragraph.text)
                    self.report(index, chapter, "voice")
                elif gap:
                    silence = round(rate * gap / 1000)
                    sink.write(bytes(2 * CHAPTER_CHANNELS * silence))
                    samples += silence
                self.check()
            return samples

        samples = export.encode_stream(self.ffmpeg, rate, CHAPTER_CHANNELS, FLAC_ARGS, partial, feed, "FLAC")
        os.replace(partial, final)
        stamp = {"fingerprint": fingerprint(chapter, self.reading), "rate": rate, "seconds": samples / rate}
        done.write_bytes(json.dumps(stamp).encode("utf-8"))
        return stamp


def export_audiobook(reader: ReadAloud, path: Path, target_root: Path, work_root: Path, *, fmt: str, reading: Reading, book_id: str,
                     cover_drawn: str | None = None, progress: Callable[..., None] = lambda **_fields: None,
                     cancelled: Callable[[], bool] = lambda: False, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Cả cuốn Nghe ngay `path` thành sách nói trong `target_root`: `fmt` "mp3" (thư mục `<tên sách>` mỗi chương một file + .m3u8) hay "m4b" (một file có mục lục chương).
    `progress(**trường)` nhận tiến độ (xem `_Run.report`); `cancelled()` đúng thì dừng ở chỗ an toàn kế (ném `export_jobs.Cancelled`, phần đã làm được giữ trong
    `work_root`). Trả kết quả như xuất của Studio: MP3 {folder, files, chapters, chaptersTotal, size}; M4B {file, folder, size, chapters, chaptersTotal}."""
    if fmt not in FORMATS:
        raise ExportError("Chỉ xuất được MP3 hoặc M4B")
    if not ffmpeg_available():
        raise ExportError("Máy này chưa có công cụ ghép âm thanh (ffmpeg) - tải nó trong hộp Xuất sách nói rồi bấm lại.")
    manifest = packages.edited_manifest(path)
    title = str(manifest.get("title") or path.name)
    author = str(manifest.get("author") or "")
    chapters = load_chapters(path)
    if not chapters:
        raise ExportError("Sách chưa có chương nào có chữ để đọc")
    ffmpeg = ffmpeg_executable()
    work = work_folder(work_root, book_id)
    work.mkdir(parents=True, exist_ok=True)
    run = _Run(reader, ffmpeg, chapters, reading, work, progress, cancelled, sleep)
    stamps: list[dict[str, Any]] = []
    for index, chapter in enumerate(chapters):
        run.check()
        stamp = chapter_ready(work, chapter, reading)
        if stamp is not None:
            run.done_chars += chapter.chars
            run.report(index, chapter, "voice")
        else:
            stamp = run.build_chapter(index, chapter)
        stamps.append(stamp)
    cover_source = book_edits.cover_file(path)
    try:
        if fmt == "mp3":
            result = _write_mp3(run, chapters, stamps, target_root, title, author, cover_source, cover_drawn)
        else:
            result = _write_m4b(run, chapters, target_root, title, author, cover_source, cover_drawn)
    except subprocess.CalledProcessError as error:
        raise ExportError(f"Không ghép được file âm thanh: {(error.stderr or '').strip()[-300:]}") from error
    shutil.rmtree(work, ignore_errors=True)
    return {**result, "format": fmt, "chapters": len(chapters), "chaptersTotal": len(packages.edited_manifest(path).get("chapters") or [])}


def _write_mp3(run: _Run, chapters: list[Chapter], stamps: list[dict[str, Any]], target_root: Path, title: str, author: str,
               cover_source: Path | None, cover_drawn: str | None) -> dict[str, Any]:
    folder = target_root / export.safe_name(title)
    folder.mkdir(parents=True, exist_ok=True)
    cover_path = export.copy_real_cover(cover_source, folder) or export.drawn_cover(folder, cover_drawn)

    def items() -> Any:
        for index, (chapter, stamp) in enumerate(zip(chapters, stamps)):
            run.check()
            run.report(index, chapter, "encode")
            temp = run.work / f"{chapter.id}.mp3"
            run_hidden([run.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(_flac_path(run.work, chapter)), *MP3_ARGS, str(temp)], timeout=3600)
            yield chapter.title, temp, stamp["seconds"]
            temp.unlink(missing_ok=True)

    files = export.write_mp3_folder(run.ffmpeg, folder, items(), title=title, narrator=author, cover_path=cover_path, total=len(chapters))
    return {"folder": str(folder), "files": files, "size": sum(file.stat().st_size for file in folder.glob("*.mp3"))}


def _write_m4b(run: _Run, chapters: list[Chapter], target_root: Path, title: str, author: str,
               cover_source: Path | None, cover_drawn: str | None) -> dict[str, Any]:
    def before(index: int) -> None:
        run.check()
        run.report(index, chapters[index], "encode")

    final, _count = export.m4b_from_files(run.ffmpeg, [(chapter.title, _flac_path(run.work, chapter)) for chapter in chapters], target_root, title=title,
                                          narrator=author, cover_for=lambda scratch: cover_source or export.drawn_cover(scratch, cover_drawn), on_chapter=before)
    return {"file": str(final), "folder": str(target_root), "size": final.stat().st_size}
