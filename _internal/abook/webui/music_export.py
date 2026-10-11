"""Xuất sách nói "Kèm nhạc nền" (MP3 / M4B): nhạc nền trộn thẳng vào file, theo đúng mốc của trình phát.

Một bộ trộn cho cả hai đường xuất: Studio (export.py `export_book` / `export_m4b`) và sách Nghe ngay (listen_export.py). Mỗi chương:
mốc nhạc của chương (đã đóng gói - `music_plan.package` của dự án, mục `music` của gói sách) -> dòng thời gian thuần
`music_mix.music_timeline` (mờ vào/ra, mờ chéo anh em, bước âm lượng trượt, lặp mờ chéo trong đoạn nghe được, vòng cuối của mốc
`tail` - y như trình phát) -> bus nhạc + bộ chặn đỉnh CHỈ trên bus (`music_render`: giọng không đổi một mẫu, đỉnh thật sau trộn
<= exportCeilingDbtp - exportGuardHeadroomDb). Hằng số đều đọc từ assets/music_mix.json.

Đường đi của âm thanh: giọng PCM 16-bit đổ vào `MixSink.write` (thay chỗ ống của bộ mã hoá), ra PCM 16-bit đã trộn cùng số mẫu
(`finish` xả phần bộ chặn còn giữ). Bài nhạc giải mã một lần về tần số / kênh của chương rồi giữ trong RAM (`TrackPcm`, có trần):
mốc nối sang chương sau thường cùng bài. Bài không lấy được (tải hỏng, file hỏng): đoạn ấy im, bản xuất vẫn xong, kết quả đếm
`musicMissing` ("N đoạn thiếu nhạc vì chưa tải được bài").
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import logging
import math
import re
import subprocess
import tempfile
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..io_utils import atomic_write_json
from . import book_edits, music_mix, music_plan, music_render, packages
from .export import _HIDDEN, audio_format, pump_pcm

log = logging.getLogger(__name__)

TRACK_CACHE_BYTES = 768 * 1024 * 1024  # PCM bài nhạc giữ lại giữa các chương; bài dài nhất danh mục (59 phút, 48 kHz mono) ~340 MB
# Chương một kênh: bài stereo bị ffmpeg gộp (L+R)/2 - hai kênh khác nhau thì nhỏ hơn lúc phát hai loa tới ~3 dB (MIX-QA tmp50: 2,5-4 dB).
# Bù đúng chênh độ to BS.1770 của ĐOẠN ĐƯỢC PHÁT của bài trong chương (bản hai kênh - bản gộp; bài dài chỉ phát phần đầu thì đo phần
# đầu - bài 48 phút đầu rộng stereo, cả bài gần mono: bù cả bài thiếu 2 dB), đo một lần mỗi đoạn, ghi cạnh file bài; trần MONO_MAX_DB.
MONO_SIDECAR = ".mono.json"
MONO_MAX_DB = 4.0


@dataclass(frozen=True)
class ChapterMusic:
    """Nhạc của một chương trong bản xuất: mốc đã đóng gói ({start, end, track, gainDb, sibling?, tail?, steps?, audibleStart?,
    audibleEnd?} - `track` là khoá vào `files`), file từng bài, và số mốc của kế hoạch bị bỏ vì không lấy được bài nào."""

    cues: list[dict[str, Any]]
    files: dict[str, Path]
    dropped: int = 0

    def fingerprint(self) -> str:
        """Đổi mốc, mức hay bài (kể cả bài tải lại khác cỡ) thì đổi - bản tạm chương trộn sẵn không dùng lại được."""
        files = {name: [path.name, path.stat().st_size if path.is_file() else None] for name, path in self.files.items()}
        data = json.dumps([self.cues, files, self.dropped], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


def studio_music(project_root: Path, chapter_ids: Iterable[int], track_file: Callable[[str], Path | None]) -> dict[int, ChapterMusic]:
    """Nhạc các chương của một dự án Studio, lấy bài như gói `.abook` (`music_plan.package`: bộ đệm, tải khi cần, bài thay thế khi
    bài đã chọn không lấy được). Rãnh nhạc đang tắt vẫn lấy - người dùng đã tích "Kèm nhạc nền"."""
    ids = [int(chapter_id) for chapter_id in chapter_ids]
    dropped: list[int] = []
    packed = music_plan.package(project_root, ids, track_file, include_disabled=True, dropped=dropped)
    chapters, files = (packed[0]["chapters"], packed[1]) if packed is not None else ({}, {})
    out: dict[int, ChapterMusic] = {}
    for chapter_id in ids:
        cues = chapters.get(str(chapter_id)) or []
        if cues or chapter_id in dropped:
            out[chapter_id] = ChapterMusic(cues, {cue["track"]: files[cue["track"]] for cue in cues}, dropped.count(chapter_id))
    return out


def studio_state(project_root: Path) -> dict[str, bool]:
    """Cho ô "Kèm nhạc nền" của hộp xuất Studio: `available` = cuốn có kế hoạch nhạc (có đoạn mang bài), `enabled` = rãnh nhạc đang bật
    (mặc định của ô, như công tắc ở tab Nhạc nền)."""
    plan = music_plan.read_plan(project_root)
    available = plan is not None and any(scene.get("link") for scene in plan.get("scenes") or [])
    return {"available": available, "enabled": available and bool(plan and plan.get("enabled"))}


def _book_music(path: Path, include_disabled: bool) -> dict[str, Any] | None:
    """Mục `music` của gói sách sau lớp sửa của người nghe; `include_disabled`: bỏ qua riêng công tắc tắt (vẫn giữ mức, đoạn im lặng, bài ghim)."""
    edits = book_edits.load(path)
    if include_disabled and "enabled" in (edits.get("music") or {}):
        edits = {**edits, "music": {key: value for key, value in edits["music"].items() if key != "enabled"}}
    return book_edits.apply_music(packages.manifest(path).get("music"), edits)


def packaged_music(path: Path, chapter_ids: Iterable[int]) -> dict[int, ChapterMusic]:
    """Nhạc các chương của sách mở từ gói (sách Nghe ngay): nhạc người làm sách gắn sẵn trong gói (`music_plan.packaged_playable`), file
    bài nằm trong gói. Công tắc tắt được bỏ qua - người dùng đã tích "Kèm nhạc nền"."""
    music = _book_music(path, include_disabled=True)
    out: dict[int, ChapterMusic] = {}
    for chapter_id in chapter_ids:
        cues, _level, _tracks = music_plan.packaged_playable(music, int(chapter_id))
        files = {cue["track"]: file for cue in cues if (file := packages.music_file(path, cue["track"])) is not None}
        kept = [cue for cue in cues if cue["track"] in files]
        if cues:
            out[int(chapter_id)] = ChapterMusic(kept, files, len(cues) - len(kept))
    return out


def packaged_state(path: Path) -> dict[str, bool]:
    """Như `studio_state` cho sách mở từ gói: có nhạc người làm sách gắn sẵn, và công tắc "Nhạc nền" của cuốn đang bật. Danh sách phát
    của sách chỉ có chữ (music_playlist) không phải kế hoạch nhạc theo chương - không tính."""
    music = _book_music(path, include_disabled=True)
    available = isinstance(music, dict) and any((music.get("chapters") or {}).values())
    return {"available": available, "enabled": available and (book_edits.load(path).get("music") or {}).get("enabled") is not False}


class _Pcm:
    """PCM 16-bit của một bài (khung, kênh) đọc như mảng float64 [-1, 1) nhân `gain` - dạng `music_render.render_bus` cần."""

    def __init__(self, raw: np.ndarray, gain: float = 1.0) -> None:
        self.raw, self.scale = raw, gain / 32768.0

    def __len__(self) -> int:
        return len(self.raw)

    def __getitem__(self, index: Any) -> np.ndarray:
        return self.raw[index].astype(np.float64) * self.scale


def _lufs(ffmpeg: str, rate: int, channels: int, feed: Callable[[Any], Any], *, dualmono: bool = False) -> float | None:
    """Độ to tích hợp BS.1770 (ebur128 của ffmpeg) của PCM 16-bit `feed(ống)` đổ vào; `dualmono`: một kênh tính như phát ra hai loa
    (+3,01 dB, như `music_plan.stereo_lufs`). Không đo được -> None."""
    meter = f"ebur128{'=dualmono=true' if dualmono else ''}"
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([ffmpeg, "-hide_banner", "-nostats", "-f", "s16le", "-ar", str(rate), "-ac", str(channels), "-i", "pipe:0",
                                    "-af", meter, "-f", "null", "-"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors,
                                   creationflags=_HIDDEN)
        assert process.stdin is not None
        try:
            feed(process.stdin)
        except (OSError, ValueError):
            process.kill()
            return None
        finally:
            with contextlib.suppress(OSError):
                process.stdin.close()
        if process.wait() != 0:
            return None
        errors.seek(0)
        found = re.findall(r"I:\s+(-?[\d.]+) LUFS", errors.read().decode("utf-8", "replace"))
    return float(found[-1]) if found and float(found[-1]) > -70 else None


def played_span(elements: Iterable[dict[str, Any]], seconds: float) -> tuple[int, int]:
    """Khoảng phát (giây trong bài, đầu làm tròn xuống, cuối làm tròn lên) của MỘT bài trong một chương: bao các phần tử dòng thời gian
    của bài ấy - phần tử thường [position, position + (to - from)], phần tử `loop` hay không rõ điểm hết (`to` vô hạn) tới hết bài
    (`loop`: cả bài); kẹp vào [0, `seconds`]."""
    lo, hi = math.inf, -math.inf
    for element in elements:
        start = 0.0 if element.get("loop") else float(element["position"])
        to = float(element["to"])
        end = seconds if element.get("loop") or not math.isfinite(to) else start + to - float(element["from"])
        lo, hi = min(lo, start), max(hi, end)
    if lo > hi:
        return 0, math.ceil(seconds)
    return math.floor(max(0.0, lo)), math.ceil(min(seconds, hi))


class _Window:
    """Ống chỉ cho qua byte [lo, hi) của luồng ghi vào nó (đoạn phát của bài, đo độ to)."""

    def __init__(self, sink: Any, lo: int, hi: int) -> None:
        self.sink, self.lo, self.hi, self.at = sink, lo, hi, 0

    def write(self, data: bytes) -> int:
        a, b = max(self.lo - self.at, 0), min(self.hi - self.at, len(data))
        if a < b:
            self.sink.write(bytes(data[a:b]))
        self.at += len(data)
        return len(data)


def mono_offset_db(ffmpeg: str, path: Path, mono: np.ndarray, rate: int, span: tuple[int, int]) -> float:
    """dB bù cho bản gộp một kênh `mono` (int16, đúng PCM sẽ trộn - cả bài) của bài `path`, đo trên ĐOẠN PHÁT `span` (giây, `played_span`):
    độ to đoạn ấy lúc phát hai loa (bài giải mã hai kênh) - độ to cùng đoạn của bản gộp phát hai loa, cả hai BS.1770; kẹp <= MONO_MAX_DB.
    Bài một kênh -> 0. Ghi vào `<tên>.mono.json` cạnh bài, khoá "đầu-cuối" (đọc lại lần sau); không đo được thì 0 và không ghi."""
    sidecar = Path(path).with_suffix(MONO_SIDECAR)
    key = f"{span[0]}-{span[1]}"
    try:
        spans = json.loads(sidecar.read_text(encoding="utf-8")).get("spans")
    except (OSError, ValueError, AttributeError):
        spans = None
    spans = spans if isinstance(spans, dict) else {}
    cached = (spans.get(key) or {}).get("offsetDb") if isinstance(spans.get(key), dict) else None
    if isinstance(cached, (int, float)):
        return float(cached)
    try:
        if audio_format(ffmpeg, Path(path))[1] < 2:
            return 0.0  # bài một kênh: trình phát cũng phát một kênh ra hai loa, không mất gì khi gộp
    except (OSError, ValueError):
        return 0.0
    lo, hi = span[0] * rate, span[1] * rate
    stereo = _lufs(ffmpeg, rate, 2, lambda sink: pump_pcm(ffmpeg, Path(path), rate, 2, _Window(sink, 4 * lo, 4 * hi)))
    folded = _lufs(ffmpeg, rate, 1, lambda sink: sink.write(np.ascontiguousarray(mono[lo:hi], dtype="<i2").tobytes()), dualmono=True)
    if stereo is None or folded is None:
        return 0.0
    offset = round(min(MONO_MAX_DB, stereo - folded), 2)
    with contextlib.suppress(OSError):
        atomic_write_json(sidecar, {"spans": {**spans, key: {"offsetDb": offset, "stereoLufs": stereo, "foldedLufs": folded}}})
    return offset


class TrackPcm:
    """Bài nhạc đã giải mã (ffmpeg của app, về đúng tần số / kênh của chương - như giọng), giữ lại giữa các chương tới trần
    `TRACK_CACHE_BYTES` (bài dùng lâu nhất bị bỏ trước). Giải mã hỏng -> None, nhớ luôn để không thử lại ở mỗi chương."""

    def __init__(self, ffmpeg: str, budget: int = TRACK_CACHE_BYTES) -> None:
        self.ffmpeg, self.budget = ffmpeg, budget
        self._kept: OrderedDict[tuple[str, int, int], _Pcm | None] = OrderedDict()

    def get(self, path: Path, rate: int, channels: int) -> _Pcm | None:
        key = (str(path), rate, channels)
        if key in self._kept:
            self._kept.move_to_end(key)
            return self._kept[key]
        buffer = io.BytesIO()
        try:
            pump_pcm(self.ffmpeg, Path(path), rate, channels, buffer)
            pcm: _Pcm | None = _Pcm(np.frombuffer(buffer.getvalue(), dtype="<i2").reshape(-1, channels))
        except (OSError, ValueError):
            log.warning("Không giải mã được bài nhạc nền %s - đoạn ấy không có nhạc", path, exc_info=True)
            pcm = None
        self._kept[key] = pcm
        while sum(item.raw.nbytes for item in self._kept.values() if item is not None) > self.budget and len(self._kept) > 1:
            self._kept.popitem(last=False)
        return pcm


class MixSink:
    """Đứng thay ống của bộ mã hoá cho MỘT chương: `write(PCM giọng 16-bit)` -> ghi PCM đã trộn vào `sink`; `finish()` xả phần bộ chặn còn
    giữ (ra đúng bằng số mẫu giọng). Chỗ không có nhạc: từng mẫu y hệt giọng."""

    def __init__(self, sink: Any, rate: int, channels: int, timeline: list[dict[str, Any]], pcm: dict[str, _Pcm | None]) -> None:
        self.sink, self.rate, self.channels, self.timeline, self.pcm = sink, rate, channels, timeline, pcm
        self.stream = music_render.GuardStream(rate, channels)
        self.position = 0
        self.carry = b""

    def write(self, data: bytes) -> int:
        block = self.carry + bytes(data)
        usable = len(block) - len(block) % (2 * self.channels)
        self.carry = block[usable:]
        if usable:
            voice = np.frombuffer(block[:usable], dtype="<i2").reshape(-1, self.channels).astype(np.float64) / 32768.0
            bus, _missing = music_render.render_bus(self.timeline, len(voice), self.rate, self.channels, self.pcm.get, start=self.position)
            self.position += len(voice)
            self._out(self.stream.feed(voice, bus))
        return len(data)

    def finish(self) -> None:
        self._out(self.stream.finish())

    def _out(self, mixed: np.ndarray) -> None:
        if len(mixed):
            self.sink.write(music_render.to_int16(mixed).astype("<i2", copy=False).tobytes())


@dataclass
class Mixer:
    """Bộ trộn của MỘT lượt xuất: nhạc từng chương (`studio_music` / `packaged_music`), bộ đệm bài, và số đoạn thiếu nhạc."""

    ffmpeg: str
    music: dict[int, ChapterMusic]
    tracks: TrackPcm | None = None
    lost: dict[int, int] = field(default_factory=dict)  # chương -> số đoạn thiếu nhạc (bài không lấy / không giải mã được)

    def __post_init__(self) -> None:
        if self.tracks is None:
            self.tracks = TrackPcm(self.ffmpeg)

    def chapter(self, chapter_id: int) -> ChapterMusic | None:
        """Nhạc của chương nếu có gì để trộn (có mốc lấy được bài); không thì None - chương ấy xuất y như không kèm nhạc."""
        music = self.music.get(int(chapter_id))
        return music if music is not None and music.cues else None

    def has(self, chapter_id: int) -> bool:
        return self.chapter(chapter_id) is not None

    def wrap(self, chapter_id: int, sink: Any, rate: int, channels: int, seconds: float | None = None) -> MixSink:
        """`MixSink` cho chương `chapter_id` (đã `has`). `seconds`: độ dài chương nếu biết (mốc cuối kẹp như trình phát)."""
        music = self.music[int(chapter_id)]
        assert self.tracks is not None
        pcm = {name: self.tracks.get(path, rate, channels) for name, path in music.files.items()}
        info: dict[str, dict[str, Any]] = {name: {"seconds": len(data) / rate} for name, data in pcm.items() if data is not None}
        for cue in music.cues:  # đoạn nghe được của bài (A, E) đi theo mốc trong gói
            if cue["track"] in info and "audibleEnd" in cue:
                info[cue["track"]].update(audibleStart=cue.get("audibleStart"), audibleEnd=cue["audibleEnd"])
        timeline = music_mix.music_timeline(music.cues, seconds, info)
        self.lost[int(chapter_id)] = len({element["cue"] for element in timeline if pcm.get(element["track"]) is None}) + music.dropped
        if channels == 1:  # bài hai kênh gộp làm một: bù phần độ to mất khi gộp, đo trên đúng đoạn chương này phát
            timeline = self._fold_offsets(timeline, music.files, pcm, rate)
        return MixSink(sink, rate, channels, timeline, pcm)

    def _fold_offsets(self, timeline: list[dict[str, Any]], files: dict[str, Path], pcm: dict[str, _Pcm | None],
                      rate: int) -> list[dict[str, Any]]:
        """Cộng dB bù gộp của từng bài (`mono_offset_db` trên `played_span` của bài trong chương) vào mọi điểm gain của các phần tử của
        bài ấy; điểm câm (None) giữ nguyên."""
        out = []
        offsets: dict[str, float] = {}
        for element in timeline:
            name, data = element["track"], pcm.get(element["track"])
            if data is None:
                out.append(element)
                continue
            if name not in offsets:
                span = played_span((e for e in timeline if e["track"] == name), len(data) / rate)
                offsets[name] = mono_offset_db(self.ffmpeg, files[name], data.raw, rate, span)
            db = offsets[name]
            out.append({**element, "gain": [[at, None if level is None else level + db] for at, level in element["gain"]]} if db else element)
        return out

    def note(self, chapter_ids: Iterable[int]) -> dict[str, int]:
        """Phần thêm vào kết quả xuất: {"musicMissing": N} khi N đoạn của các chương đã xuất thiếu nhạc (kể cả chương mọi bài đều hỏng)."""
        missing = 0
        for chapter_id in chapter_ids:
            music = self.music.get(int(chapter_id))
            missing += self.lost.get(int(chapter_id), music.dropped if music is not None else 0)
        return {"musicMissing": missing} if missing else {}
