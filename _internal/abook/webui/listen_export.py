"""Xuất sách nói (MP3 từng chương / một file M4B) cho sách Nghe ngay - sách chỉ có chữ (EPUB, TXT...) đọc bằng giọng của máy.

Người dùng muốn mang sách sang trình phát khác (điện thoại, xe hơi) thì cần file âm thanh. Mỗi chương được chia ra ĐÚNG các đoạn như trình phát
(`readaloud.paragraphs`: cùng chia đoạn, cùng khoảng lặng ở dòng ngăn cảnh), mỗi đoạn qua `ReadAloud.clip` - clip đã có trong bộ đệm (đã nghe, đã Làm trước,
đã xuất lần trước) dùng luôn, chỉ đoạn chưa có mới đọc mới. Việc NGHE luôn đi trước: có clip của người nghe đang đọc dở (`ReadAloud.live`) thì việc xuất đứng chờ.

Mỗi chương ghép thành MỘT file FLAC tạm (không mất tiếng, nhỏ hơn nửa WAV - sách 20 giờ ở 48 kHz mà để WAV là hơn 6 GB) trong `<dữ liệu app>/export_work/<mã sách>/`
cùng một dấu `.done` ghi dấu vân tay của chương (giọng + cách đọc + chữ). Huỷ hay tắt app giữa chừng rồi xuất lại thì chương nào còn dấu đúng được bỏ qua; xong cả
cuốn thì thư mục tạm bị xoá; lượt bỏ dở thì thư mục của nó được dọn lúc mở app sau STALE_DAYS ngày không ai đụng tới, hay khi sách bị xoá (`sweep_work`). Rồi mã hoá bằng ffmpeg của app: MP3 = mỗi chương một file (`export.write_mp3_folder`, cùng tag và danh sách phát với MP3 của Studio),
M4B = một file AAC có mục lục chương (`export.m4b_from_files`, cùng file với M4B của Studio).

"Kèm nhạc nền" (music_export.py, cùng bộ trộn với Studio): chương có nhạc được trộn từ FLAC giọng ra một FLAC tạm thứ hai `<mã>.music.flac` có dấu
`.music.done` riêng - dấu vân tay gồm cả nhạc của chương, nên đổi nhạc thì chỉ chương ấy trộn lại (giọng đã đọc không phải đọc lại).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..io_utils import atomic_write_bytes, ffmpeg_available, ffmpeg_executable
from ..readaloud import paragraphs as px
from ..readaloud.prepare import listening_seconds
from ..readaloud.edge import EdgeDropped
from ..readaloud.model import VoiceError
from ..readaloud.service import MAX_TEXT, ReadAloud
from . import book_edits, export, packages
from .export_jobs import Cancelled
from .music_export import ChapterMusic, Mixer

WORK_FOLDER = "export_work"  # dưới thư mục dữ liệu của app
FORMATS = ("mp3", "m4b")
CHAPTER_CHANNELS = 1  # sách nói giọng đọc: mono (MP3 64 kb/s mono; AAC 64 kb/s mono như M4B của Studio)
MP3_ARGS = ["-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1", "-f", "mp3"]
FLAC_ARGS = ["-c:a", "flac", "-f", "flac"]
CACHED_SECONDS = 0.05  # clip trả nhanh hơn thế là từ bộ đệm: không nói gì về tốc độ giọng
RETRIES = 2  # lỗi thoáng qua khác của giọng trực tuyến (502, bị từ chối...): thử lại như trình phát, rồi mới dừng
TRANSIENT = ("service", "rejected")
# Lỗi MẠNG (mất mạng, quá giờ, bị cắt kết nối): lượt xuất đứng chờ mạng ("Đang chờ mạng…") thay vì dừng - soát a62: mất mạng 3 giây là dừng cả lượt.
NETWORK = ("offline", "timeout")
NETWORK_WAITS = (1.0, 2.0, 4.0, 8.0, 15.0)  # giây nghỉ giữa các lần thử lại; hết dãy thì giữ số cuối
OUTAGE_SECONDS = 30.0  # mất mạng liên tục quá chừng này thì mới dừng (phần đã làm được giữ)
CANCEL_POLL = 0.2  # giây: lúc nghỉ chờ mạng vẫn hỏi Huỷ chừng này một lần
# "còn khoảng ..." chỉ hiện khi đã đo đủ: chừng này đoạn đọc MỚI và chừng này giây chạy (soát a62: 1 đoạn đầu cho "còn 4 phút" khi thật còn 51 giây)
ETA_READS = 3
ETA_SECONDS = 20.0
STALE_DAYS = 7  # thư mục làm việc không ai đụng tới quá chừng này ngày bị dọn lúc mở app (`sweep_work`)


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


def fingerprint(chapter: Chapter, reading: Reading, music: ChapterMusic | None = None) -> str:
    """Dấu vân tay của chương đã ghép: đổi giọng, cách đọc, gốc hay chữ (kể cả dòng bỏ) thì chương tạm cũ không dùng lại được. `music`: bản trộn
    "Kèm nhạc nền" - dấu gồm thêm nhạc của chương (mốc, mức, bài), đổi nhạc thì bản trộn cũ không dùng lại được."""
    parts: list[Any] = [reading.voice, reading.origin, sorted(reading.readings.items()),
                        [[paragraph.text, gap] for paragraph, gap in zip(chapter.paragraphs, chapter.gaps)]]
    if music is not None:
        parts.append(["music", music.fingerprint()])
    data = json.dumps(parts, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def work_folder(root: Path, book_id: str) -> Path:
    return Path(root) / re.sub(r"[^A-Za-z0-9_-]", "_", book_id)


def _touched(folder: Path) -> float:
    """Lần cuối có gì trong `folder` được ghi: mtime mới nhất của chính nó và mọi file trong đó."""
    newest = folder.stat().st_mtime
    for entry in folder.rglob("*"):
        try:
            newest = max(newest, entry.stat().st_mtime)
        except OSError:
            continue
    return newest


def sweep_work(root: Path, books: Iterable[str] | None, busy: Iterable[str] = (), *, now: float | None = None,
               max_age: float = STALE_DAYS * 86400) -> list[Path]:
    """Dọn thư mục làm việc của các lượt xuất bỏ dở (soát a62: chưa bao giờ được dọn, ~80 MB mỗi giờ giọng): của sách không còn trong thư viện (`books`: mã các sách
    còn; None = không xét luật này) hay không ai đụng tới quá `max_age` giây. Sách đang xuất (`busy`) không bao giờ bị đụng. Trả các thư mục đã xoá."""
    root = Path(root)
    keep = {work_folder(root, book).name for book in busy}
    known = None if books is None else {work_folder(root, book).name for book in books}
    moment = time.time() if now is None else now
    removed: list[Path] = []
    try:
        folders = [entry for entry in root.iterdir() if entry.is_dir()]
    except OSError:
        return removed
    for folder in folders:
        if folder.name in keep:
            continue
        try:
            stale = (known is not None and folder.name not in known) or moment - _touched(folder) > max_age
        except OSError:
            continue
        if stale:
            shutil.rmtree(folder, ignore_errors=True)
            if not folder.exists():
                removed.append(folder)
    return removed


def remove_work(root: Path, book_id: str) -> None:
    """Sách bị xoá khỏi thư viện: thư mục làm việc của nó đi theo."""
    shutil.rmtree(work_folder(root, book_id), ignore_errors=True)


def cached_lookup(reader: ReadAloud, reading: Reading, book_id: str) -> Callable[[str], int | None]:
    """Tra đoạn nào đã có clip bậc chất lượng trong bộ đệm Nghe ngay (đã nghe, Làm trước, xuất trước; clip bậc "Nhanh hơn" không tính - voice_speed.py) - không
    đọc gì mới: hàm trả độ dài clip (ms) hay None. Cuốn chưa có clip nào trong sổ của nó (`ReadAloud.books`) thì khỏi tính khoá từng đoạn (bước chuẩn hoá
    chữ mất ~1 ms mỗi đoạn - cuốn dài vài giây)."""
    if not reader.books.keys(book_id):
        return lambda _text: None

    def lookup(text: str) -> int | None:
        try:
            clip = reader.clip(reading.voice, text, cached_only=True, origin=reading.origin, readings=reading.readings, quality=True)
        except (VoiceError, ValueError):
            return None
        return int(clip["duration_ms"])

    return lookup


def _done_path(work: Path, chapter: Chapter, music: ChapterMusic | None = None) -> Path:
    return work / f"{chapter.id}{'.music' if music is not None else ''}.done"


def _flac_path(work: Path, chapter: Chapter, music: ChapterMusic | None = None) -> Path:
    return work / f"{chapter.id}{'.music' if music is not None else ''}.flac"


def chapter_ready(work: Path, chapter: Chapter, reading: Reading, music: ChapterMusic | None = None) -> dict[str, Any] | None:
    """Dấu `.done` của chương nếu chương tạm còn nguyên và đúng dấu vân tay; không thì None. `music`: bản đã trộn nhạc của chương."""
    try:
        done = json.loads(_done_path(work, chapter, music).read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return None
    if (not isinstance(done, dict) or done.get("fingerprint") != fingerprint(chapter, reading, music)
            or not _flac_path(work, chapter, music).is_file()):
        return None
    return done


def plan(chapters: list[Chapter], reading: Reading, work: Path, speed: float | None,
         cached: Callable[[str], int | None] = lambda _text: None) -> dict[str, Any]:
    """Cho hộp Xuất: số chương, số chữ, thời gian nghe, ước thời gian máy làm (chỉ khi giọng đã đo tốc độ `speed`), và phần đã có sẵn.
    `cached(chữ)`: độ dài (ms) clip của đoạn ấy trong bộ đệm Nghe ngay, None nếu chưa có (`cached_lookup`). Thời gian nghe = độ dài thật của phần đã có (chương đã
    ghép từ lần xuất trước + clip trong bộ đệm + quãng lặng) + phần chưa có ước theo số chữ với tốc độ ĐO trên chính các clip ấy (chưa có clip nào: hằng chung
    của prepare.listening_seconds - cùng số trình tạo sách nói dùng);
    soát a62: "khoảng 10 phút" cho cuốn thật 8:44. `readyChapters`: chương có đủ (đã ghép hay mọi đoạn có clip) - xuất ngay, không đọc lại; `readySeconds`: giây nghe
    đã có sẵn; máy chỉ phải đọc phần chưa có (`secondsEstimate`)."""
    chars = sum(chapter.chars for chapter in chapters)
    heard_chars, heard_seconds, gaps, open_chars, ready = 0, 0.0, 0.0, 0, 0
    for chapter in chapters:
        silence = sum(chapter.gaps) / 1000
        stamp = chapter_ready(work, chapter, reading)
        if stamp is not None:
            heard_chars += chapter.chars
            heard_seconds += max(0.0, float(stamp.get("seconds") or 0) - silence)
            gaps += silence
            ready += 1
            continue
        missing = 0
        for paragraph in chapter.speakable:
            length = cached(paragraph.text)
            if length is None:
                missing += len(paragraph.text)
            else:
                heard_chars += len(paragraph.text)
                heard_seconds += length / 1000
        gaps += silence
        open_chars += missing
        ready += missing == 0
    left = listening_seconds(open_chars, heard_chars / heard_seconds if heard_chars and heard_seconds > 0 else None)
    return {"chapters": len(chapters), "chars": chars, "audioSeconds": round(heard_seconds + gaps + left), "rtf": speed,
            "secondsEstimate": round(left * speed) if speed else None, "readyChapters": ready, "readySeconds": round(heard_seconds)}


class _Run:
    """Một lượt xuất: giữ tiến độ (theo số chữ) và mọi thứ các bước cần."""

    def __init__(self, reader: ReadAloud, ffmpeg: str, chapters: list[Chapter], reading: Reading, work: Path,
                 progress: Callable[..., None], cancelled: Callable[[], bool], sleep: Callable[[float], None],
                 clock: Callable[[], float] = time.monotonic, book_id: str | None = None) -> None:
        self.reader, self.ffmpeg, self.chapters, self.reading, self.work = reader, ffmpeg, chapters, reading, work
        self._progress, self.cancelled, self._sleep, self._clock, self.book_id = progress, cancelled, sleep, clock, book_id
        self.chars = sum(chapter.chars for chapter in chapters)
        self.done_chars = 0
        self.timed_chars = 0
        self.timed_seconds = 0.0
        self.reads = 0  # đoạn đọc MỚI (không từ bộ đệm) - đủ ETA_READS mới ước thời gian còn lại
        self.began = clock()
        self.open: set[tuple[int, int]] = set()  # (chương, số thứ tự đoạn) chưa có clip lúc bắt đầu: phần máy còn phải đọc (`count_open`)
        self.open_chars = 0

    def check(self) -> None:
        if self.cancelled():
            raise Cancelled()

    def count_open(self, chapters: list[Chapter]) -> None:
        """Đoạn của `chapters` (các chương sẽ ghép) chưa có clip trong bộ đệm: thời gian còn lại chỉ tính theo chúng, đoạn có sẵn gần như không tốn gì."""
        cached = cached_lookup(self.reader, self.reading, self.book_id) if self.book_id else (lambda _text: None)
        for chapter in chapters:
            for at, paragraph in enumerate(chapter.paragraphs):
                if px.is_speakable(paragraph.text) and cached(paragraph.text) is None:
                    self.open.add((chapter.id, at))
                    self.open_chars += len(paragraph.text)

    def seconds_left(self) -> int | None:
        """Ước giây còn lại: số chữ CHƯA CÓ clip còn lại / tốc độ đo trên các đoạn đọc mới. None khi chưa đo đủ (ETA_READS đoạn mới và ETA_SECONDS giây)."""
        if self.reads < ETA_READS or self._clock() - self.began < ETA_SECONDS or not self.timed_chars or not self.timed_seconds:
            return None
        return round(self.timed_seconds / self.timed_chars * self.open_chars)

    def report(self, index: int, chapter: Chapter, phase: str, waiting: str | None = None) -> None:
        self._progress(phase=phase, chapter=index + 1, chapters=len(self.chapters), chapterTitle=chapter.title, waiting=waiting,
                       percent=min(100, round(100 * self.done_chars / self.chars)) if self.chars else 100,
                       chars=self.chars, charsDone=self.done_chars, secondsLeft=self.seconds_left())

    def report_peaks(self, round_: int, over: int) -> None:
        """Bước kiểm đỉnh AAC của M4B (`export.m4b_from_files` on_peaks): (k, 0) đang đo, (k, N) mã hoá lại lượt k vì N chương vượt."""
        self.check()
        self._progress(phase="reencode" if over else "peaks", peakRound=round_, peakOver=over, chapters=len(self.chapters))

    def pause(self, seconds: float) -> None:
        """Nghỉ `seconds` giây mà vẫn nghe Huỷ (hỏi mỗi CANCEL_POLL giây)."""
        end = self._clock() + seconds
        while (left := end - self._clock()) > 0:
            self.check()
            self._sleep(min(CANCEL_POLL, left))
        self.check()

    def clip_file(self, index: int, chapter: Chapter, text: str) -> Path | None:
        """Clip của một đoạn (từ bộ đệm hay đọc mới); None khi đoạn không có gì giọng đọc được (như Làm trước, bỏ qua). Người nghe đi trước; Huỷ cắt cả lượt đọc đang
        bay (Edge: ổ cắm đóng, clip dở không vào bộ đệm); mất mạng thì chờ mạng (NETWORK_WAITS) tới khi mất liên tục quá OUTAGE_SECONDS; lỗi thoáng qua khác thử lại
        RETRIES lần; lỗi thật dừng cả lượt với lời nói rõ."""
        failures = 0
        outage: float | None = None  # lúc lần lỗi mạng đầu của chuỗi lỗi liền nhau
        while True:
            waiting = False
            while self.reader.live > 0:  # người đang nghe: nhường
                self.check()
                if not waiting:
                    self.report(index, chapter, "voice", "listening")
                    waiting = True
                self._sleep(0.2)
            self.check()
            if waiting or outage is not None:
                self.report(index, chapter, "voice")
            began = time.perf_counter()
            try:
                clip = self.reader.clip(self.reading.voice, text, background=True, origin=self.reading.origin, readings=self.reading.readings,
                                        book=self.book_id, cancelled=self.cancelled, quality=True)  # sách xuất ra luôn bậc chất lượng
            except VoiceError as error:
                if error.reason == "empty":
                    return None
                if error.reason == "cancelled":
                    raise Cancelled() from error
                if error.reason in NETWORK or isinstance(error, EdgeDropped):
                    now = self._clock()
                    outage = now if outage is None else outage
                    if now - outage <= OUTAGE_SECONDS:
                        self.report(index, chapter, "voice", "network")
                        self.pause(NETWORK_WAITS[min(failures, len(NETWORK_WAITS) - 1)])
                        failures += 1
                        continue
                elif error.reason in TRANSIENT and failures < RETRIES:
                    failures += 1
                    self.pause(float(failures))
                    continue
                raise ExportError(f"Giọng đọc không đọc được một đoạn ở “{chapter.title}”: {error} Phần đã làm được giữ - bấm xuất lại để làm tiếp.") from error
            spent = time.perf_counter() - began
            if spent > CACHED_SECONDS:
                self.timed_chars += len(text)
                self.timed_seconds += spent
                self.reads += 1
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
            for at, (paragraph, gap) in enumerate(zip(chapter.paragraphs, chapter.gaps)):
                if px.is_speakable(paragraph.text):
                    if len(paragraph.text) > MAX_TEXT:
                        raise ExportError(f"Một đoạn của “{chapter.title}” dài quá để đọc một lượt.")
                    source = self.clip_file(index, chapter, paragraph.text)
                    if source is not None:
                        samples += export.pump_pcm(self.ffmpeg, source, rate, CHAPTER_CHANNELS, sink) // (2 * CHAPTER_CHANNELS)
                    self.done_chars += len(paragraph.text)
                    if (chapter.id, at) in self.open:
                        self.open.discard((chapter.id, at))
                        self.open_chars -= len(paragraph.text)
                    self.report(index, chapter, "voice")
                elif gap:
                    silence = round(rate * gap / 1000)
                    sink.write(bytes(2 * CHAPTER_CHANNELS * silence))
                    samples += silence
                self.check()
            return samples

        samples = self.encode(rate, partial, feed)
        os.replace(partial, final)
        stamp = {"fingerprint": fingerprint(chapter, self.reading), "rate": rate, "seconds": samples / rate}
        atomic_write_bytes(done, json.dumps(stamp).encode("utf-8"))
        return stamp

    def mix_chapter(self, index: int, chapter: Chapter, voice: dict[str, Any], mixer: Mixer) -> dict[str, Any]:
        """Trộn nhạc nền vào chương đã ghép (FLAC giọng -> `<mã>.music.flac`, cùng số mẫu), dấu `.music.done` mang vân tay gồm cả nhạc."""
        music = mixer.chapter(chapter.id)
        assert music is not None
        self.check()
        self.report(index, chapter, "music")
        final = _flac_path(self.work, chapter, music)
        partial = final.with_name(final.name + ".part")
        done = _done_path(self.work, chapter, music)
        done.unlink(missing_ok=True)
        rate = int(voice["rate"])
        samples = self.encode(rate, partial, lambda sink: export.pump_mixed(
            self.ffmpeg, mixer, chapter.id, _flac_path(self.work, chapter), rate, CHAPTER_CHANNELS, export.watched(sink, self.cancelled),
            voice["seconds"]) // (2 * CHAPTER_CHANNELS))
        os.replace(partial, final)
        stamp = {"fingerprint": fingerprint(chapter, self.reading, music), "rate": rate, "seconds": samples / rate,
                 "musicMissing": mixer.lost.get(chapter.id, 0)}
        atomic_write_bytes(done, json.dumps(stamp).encode("utf-8"))
        return stamp

    def encode(self, rate: int, partial: Path, feed: Callable[[Any], int], args: list[str] = FLAC_ARGS, what: str = "FLAC") -> int:
        """`export.encode_stream` vào `partial`; hỏng hay Huỷ giữa chừng thì file dở bị xoá (chỉ clip / chương đã xong mới nằm lại cho lần sau)."""
        try:
            return export.encode_stream(self.ffmpeg, rate, CHAPTER_CHANNELS, args, partial, feed, what)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise


def export_audiobook(reader: ReadAloud, path: Path, target_root: Path, work_root: Path, *, fmt: str, reading: Reading, book_id: str,
                     cover_drawn: str | None = None, progress: Callable[..., None] = lambda **_fields: None,
                     cancelled: Callable[[], bool] = lambda: False, sleep: Callable[[float], None] = time.sleep,
                     music: dict[int, ChapterMusic] | None = None, clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """Cả cuốn Nghe ngay `path` thành sách nói trong `target_root`: `fmt` "mp3" (thư mục `<tên sách>` mỗi chương một file + .m3u8) hay "m4b" (một file có mục lục chương).
    `progress(**trường)` nhận tiến độ (xem `_Run.report`); `cancelled()` đúng thì dừng ở chỗ an toàn kế (ném `export_jobs.Cancelled`, phần đã làm được giữ trong
    `work_root`). Trả kết quả như xuất của Studio: MP3 {folder, files, chapters, chaptersTotal, size}; M4B {file, folder, size, chapters, chaptersTotal}.
    `music` (music_export.packaged_music): "Kèm nhạc nền" - chương có nhạc trộn vào bản tạm trước khi mã hoá (pha tiến độ "music"); kết quả thêm
    `musicMissing` khi có đoạn thiếu nhạc. `sleep` / `clock`: đồng hồ của các lần chờ (bài thử thay)."""
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
    run = _Run(reader, ffmpeg, chapters, reading, work, progress, cancelled, sleep, clock, book_id)
    mixer = Mixer(ffmpeg, music) if music is not None else None
    run.count_open([chapter for chapter in chapters if chapter_ready(work, chapter, reading) is None])
    sources: list[Path] = []
    rates: list[int] = []
    with reader.holding(reading.voice):  # giọng trên máy: model không bị nhả trong lúc việc xuất đứng chờ người nghe (ReadAloud.release_idle)
        for index, chapter in enumerate(chapters):
            run.check()
            chapter_music = mixer.chapter(chapter.id) if mixer is not None else None
            mixed = chapter_ready(work, chapter, reading, chapter_music) if chapter_music is not None else None
            stamp = mixed or chapter_ready(work, chapter, reading)
            if stamp is not None:
                run.done_chars += chapter.chars
                run.report(index, chapter, "voice")
            else:
                stamp = run.build_chapter(index, chapter)
            if chapter_music is not None and mixer is not None:
                if mixed is None:
                    stamp = run.mix_chapter(index, chapter, stamp, mixer)
                mixer.lost[chapter.id] = int(stamp.get("musicMissing") or 0)
            sources.append(_flac_path(work, chapter, chapter_music))
            rates.append(int(stamp["rate"]))
    cover_source = book_edits.cover_file(path)
    try:
        if fmt == "mp3":
            result = _write_mp3(run, chapters, sources, rates, target_root, title, author, cover_source, cover_drawn)
        else:
            result = _write_m4b(run, chapters, sources, target_root, title, author, cover_source, cover_drawn)
    except subprocess.CalledProcessError as error:
        raise ExportError(f"Không ghép được file âm thanh: {(error.stderr or '').strip()[-300:]}") from error
    shutil.rmtree(work, ignore_errors=True)
    return {**result, "format": fmt, "chapters": len(chapters), "chaptersTotal": len(packages.edited_manifest(path).get("chapters") or []),
            **(mixer.note(chapter.id for chapter in chapters) if mixer is not None else {})}


def _write_mp3(run: _Run, chapters: list[Chapter], sources: list[Path], rates: list[int], target_root: Path, title: str, author: str,
               cover_source: Path | None, cover_drawn: str | None) -> dict[str, Any]:
    folder = target_root / export.safe_name(title)
    folder.mkdir(parents=True, exist_ok=True)
    cover_path = export.copy_real_cover(cover_source, folder) or export.drawn_cover(folder, cover_drawn)

    def items() -> Any:
        for index, (chapter, source, rate) in enumerate(zip(chapters, sources, rates)):
            run.check()
            run.report(index, chapter, "encode")
            temp = run.work / f"{chapter.id}.mp3"
            # Qua ống PCM có hỏi Huỷ từng khúc (chương dài mã hoá mất hàng chục giây).
            run.encode(rate, temp, lambda sink, source=source, rate=rate: export.pump_pcm(
                run.ffmpeg, source, rate, CHAPTER_CHANNELS, export.watched(sink, run.cancelled)) // (2 * CHAPTER_CHANNELS), MP3_ARGS, "MP3")
            yield chapter.title, temp
            temp.unlink(missing_ok=True)

    files = export.write_mp3_folder(run.ffmpeg, folder, items(), title=title, narrator=author, cover_path=cover_path, total=len(chapters))
    return {"folder": str(folder), "files": files, "size": sum(file.stat().st_size for file in folder.glob("*.mp3"))}


def _write_m4b(run: _Run, chapters: list[Chapter], sources: list[Path], target_root: Path, title: str, author: str,
               cover_source: Path | None, cover_drawn: str | None) -> dict[str, Any]:
    def before(index: int) -> None:
        run.check()
        run.report(index, chapters[index], "encode")

    final, _count = export.m4b_from_files(run.ffmpeg, [(chapter.title, source) for chapter, source in zip(chapters, sources)], target_root, title=title,
                                          narrator=author, cover_for=lambda scratch: export.usable_cover(cover_source) or export.drawn_cover(scratch, cover_drawn), on_chapter=before,
                                          on_peaks=run.report_peaks, cancelled=run.cancelled)
    return {"file": str(final), "folder": str(target_root), "size": final.stat().st_size}
