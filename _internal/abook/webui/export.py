"""Xuất sách ra một thư mục MP3 nghe được bằng MỌI trình phát (điện thoại, xe hơi, Voice, Smart AudioBook Player...).

MP3 chương do dây chuyền ghi mang tag của nội bộ sản xuất: album là tên project của lô ("lo16"), title là tên file
nguồn ("645"). Mở bằng trình phát khác thì thấy sách "lo16" với các chương "645", "646" (thử 26-09 trên Voice). Code
ghi MP3 nằm trong các file bị khoá của dây chuyền, nên sửa ở đây: chép nguyên luồng âm thanh (không mã hoá lại - nhanh,
không mất chất lượng) sang thư mục mới với tag đúng - tên sách, tên chương thật, giọng kể, số thứ tự, ảnh bìa - kèm
danh sách phát `.m3u8`. File chưa xong ghi ra `.part` rồi mới đổi tên, như mọi file âm thanh khác của dự án.

`export_m4b`: cả cuốn trong MỘT file `.m4b` có mục lục chương - kiểu trình phát sách nói quen dùng (xem phần M4B bên dưới).
"""
from __future__ import annotations

import base64
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

from .. import continuation
from ..io_utils import ffmpeg_available, ffmpeg_executable, run_hidden
from ..readaloud import mp3
from . import covers, listen_view, music_plan, store
from .export_jobs import Cancelled
from .music_mix import MIX

log = logging.getLogger(__name__)

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(text: str, limit: int = 120) -> str:
    """Tên file hợp lệ trên Windows, giữ nguyên chữ tiếng Việt."""
    cleaned = _UNSAFE.sub(" ", text).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:limit].rstrip() or "Sach"


def free_path(path: Path) -> Path:
    """`path` nếu chưa có gì ở đó; không thì "tên (2).đuôi", "tên (3).đuôi"... - xuất lần hai vào cùng thư mục không ghi đè im lặng
    lên bản xuất trước (soát UX a20: "Chuyến phà cuối ngày.m4b" bị thay mà không một lời)."""
    if not path.exists():
        return path
    for number in range(2, 1000):
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}") if path.suffix and path.is_file() else path.with_name(f"{path.name} ({number})")
        if not candidate.exists():
            return candidate
    return path


def drawn_cover(folder: Path, cover: str | None) -> Path | None:
    """Ảnh bìa gửi từ giao diện (data URL PNG do trình duyệt vẽ, cùng kiểu bìa trong app)."""
    match = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/=]+)", cover or "")
    if not match:
        return None
    data = base64.b64decode(match.group(1))
    if not data.startswith(b"\x89PNG") or len(data) > 4 * 1024 * 1024:
        return None
    path = folder / "cover.png"
    path.write_bytes(data)
    return path


def usable_cover(source: Path | None) -> Path | None:
    """`source` nếu là ảnh đọc được; ảnh hỏng (file rác, cắt cụt) thì None - ffmpeg gặp bìa hỏng thì hỏng cả lượt xuất MP3 / M4B (soát a28 lỗi 8),
    nơi gọi dùng bìa vẽ từ tên thay. Máy không có Pillow (bản chỉ-nghe): không kiểm được, giữ nguyên."""
    if source is None:
        return None
    try:
        from PIL import Image  # Pillow chỉ cần khi sách có ảnh bìa thật
    except ImportError:
        return source
    try:
        with Image.open(source) as image:
            image.verify()
    except Exception:  # PIL ném đủ kiểu cho ảnh hỏng (UnidentifiedImageError, SyntaxError, OSError...)
        log.warning("Bìa hỏng, xuất bằng bìa vẽ từ tên: %s", source, exc_info=True)
        return None
    return source


def copy_real_cover(source: Path | None, folder: Path) -> Path | None:
    """Ảnh bìa thật người dùng đã đặt (covers.py; sách Nghe ngay: book_edits.cover_file) thắng bìa tự vẽ mà giao diện gửi kèm; chép vào thư mục xuất.
    Ảnh hỏng (`usable_cover`): None - bìa vẽ thay."""
    source = usable_cover(source)
    if source is None:
        return None
    target = folder / f"cover{source.suffix}"
    shutil.copyfile(source, target)
    return target


def _listenable(project_root: Path) -> list[dict[str, Any]]:
    """Các chương đã nghe được - đúng những chương mọi kiểu xuất lấy."""
    return [chapter for chapter in listen_view.chapters(project_root) if chapter["available"]]


def chapter_file_name(number: int, total: int, full_title: str) -> str:
    """Tên file MP3 của chương thứ `number` trong `total` chương được xuất. Điện thoại (Mp3Export.kt) đặt đúng tên này -
    bộ ví dụ chung tests/fixtures/mp3_export."""
    width = max(2, len(str(total)))
    return f"{number:0{width}d} - {safe_name(full_title, 90)}.mp3"


def write_chapter(ffmpeg: str, source: Path, final: Path, cover_path: Path | None, *, title: str, album: str,
                  narrator: str, number: int, total: int) -> None:
    """Chép nguyên luồng âm thanh của `source` sang `final` với tag mới: ID3v2.3 + ID3v1, kèm bìa nếu có. Điện thoại ghi tag
    bằng tay (Id3Tag.kt) cho ra đúng những byte này, trừ khung TSSE (tên phiên bản ffmpeg)."""
    partial = final.with_name(f"{final.name}.part")
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
    if cover_path:
        command += ["-i", str(cover_path), "-map", "0:a", "-map", "1:v", "-c:v", "copy",
                    "-disposition:v", "attached_pic", "-metadata:s:v", "title=Album cover",
                    "-metadata:s:v", "comment=Cover (front)"]
    else:
        command += ["-map", "0:a"]
    command += [
        "-c:a", "copy", "-map_metadata", "-1", "-id3v2_version", "3", "-write_id3v1", "1",
        "-metadata", f"title={title}",
        "-metadata", f"album={album}",
        "-metadata", f"artist={narrator}",
        "-metadata", f"album_artist={narrator}",
        "-metadata", f"track={number}/{total}",
        "-metadata", "genre=Audiobook",
        "-f", "mp3", str(partial),
    ]
    try:
        run_hidden(command, timeout=300)
    except subprocess.CalledProcessError as error:
        # Không để file `.part` nằm lại, không dán lệnh / lời ffmpeg cho người dùng (soát a28 lỗi 8) - lời ffmpeg vào nhật ký.
        partial.unlink(missing_ok=True)
        log.warning("ffmpeg không ghi được %s: %s", final.name, (error.stderr or "").strip()[-600:])
        raise ValueError(f"Không ghi được chương “{title}” - file âm thanh của chương hay ảnh bìa không đọc được.") from error
    os.replace(partial, final)


def playlist_text(title: str, entries: list[tuple[float, str, str]]) -> str:
    """Danh sách phát `.m3u8` của bản xuất; `entries`: (thời lượng giây, tên chương, tên file)."""
    lines = ["#EXTM3U", f"#PLAYLIST:{title}"]
    for duration, full_title, name in entries:
        lines += [f"#EXTINF:{int(round(duration))},{full_title}", name]
    return "\n".join(lines) + "\n"


def write_mp3_folder(ffmpeg: str, folder: Path, chapters: Iterable[tuple[str, Path]], *, title: str, narrator: str,
                     cover_path: Path | None, total: int) -> int:
    """Mỗi chương một MP3 trong `folder` (tag + bìa, `write_chapter`) kèm `.m3u8`; trả số file. `chapters`: (tên chương, file MP3 nguồn) - có thể là
    bộ sinh làm ra file nguồn từng chương một (sách Nghe ngay mã hoá từ bản tạm: file nguồn dùng xong, bộ sinh mới được chạy tiếp và dọn nó). `total`: số chương sẽ có.
    Thời lượng trong `.m3u8` đếm từ khung MP3 của chính file đã ghi (readaloud/mp3.py) - không lấy độ dài ước của sổ (soát a61: lệch 4-9 giây).
    Chung cho xuất MP3 của Studio (`export_book`) và của sách Nghe ngay (listen_export.py)."""
    entries: list[tuple[float, str, str]] = []
    for number, (full_title, source) in enumerate(chapters, start=1):
        name = chapter_file_name(number, total, full_title)
        write_chapter(ffmpeg, source, folder / name, cover_path, title=full_title, album=title,
                      narrator=narrator, number=number, total=total)
        entries.append((mp3.duration_ms((folder / name).read_bytes()) / 1000, full_title, name))
    (folder / f"{safe_name(title)}.m3u8").write_text(playlist_text(title, entries), encoding="utf-8")
    return len(entries)


def export_book(project_root: Path, target_root: Path, *, cover: str | None = None,
                folder_name: str | None = None, music: Callable[[str], Path | None] | None = None,
                cancelled: Callable[[], bool] | None = None) -> dict[str, Any]:
    """`folder_name`: tên thư mục thay cho tên sách - bản xuất cả bộ đặt mỗi phần vào "Phần N - ...".
    `music`: nguồn file bài nhạc (như gói `.abook`, music_plan.TrackSource) = "Kèm nhạc nền": chương có nhạc được giải mã, trộn
    (music_export.py) rồi mã hoá lại MP3 cùng bitrate; không có thì chép nguyên luồng như cũ.
    `cancelled()` True (người dùng bấm Huỷ): dừng trước chương kế / giữa lúc trộn, xoá thư mục bản xuất dở và ném `export_jobs.Cancelled`."""
    summary = store.summarize(project_root)
    title = summary["title"] or project_root.name
    narrator = summary["settings"]["narrator"] or ""
    chapters = _listenable(project_root)
    if not chapters:
        raise ValueError("Sách chưa có chương nào nghe được để xuất")
    folder = free_path(target_root / safe_name(folder_name or title))
    folder.mkdir(parents=True, exist_ok=True)
    real = covers.cover_file(project_root)
    cover_path = copy_real_cover(real, folder) or drawn_cover(folder, cover)
    ffmpeg = ffmpeg_executable()
    audio = store.chapter_audio_paths(project_root)
    listed = [(chapter["id"], chapter["fullTitle"], path) for chapter in chapters if (path := audio.get(chapter["id"])) is not None]
    sources = [(full_title, path) for _id, full_title, path in listed]
    noted: dict[str, Any] = {}
    try:
        if music is None:
            files = write_mp3_folder(ffmpeg, folder, _checked(sources, cancelled), title=title, narrator=narrator, cover_path=cover_path,
                                     total=len(sources))
        else:
            from .music_export import Mixer, studio_music  # nhập muộn: music_export dùng pump_pcm của module này

            mixer = Mixer(ffmpeg, studio_music(project_root, [item[0] for item in listed], music))
            with tempfile.TemporaryDirectory(prefix=".music-", dir=target_root) as scratch:
                files = write_mp3_folder(ffmpeg, folder, _mixed_mp3(ffmpeg, mixer, listed, Path(scratch), cancelled), title=title,
                                         narrator=narrator, cover_path=cover_path, total=len(sources))
            noted = mixer.note(item[0] for item in listed)
    except Cancelled:
        shutil.rmtree(folder, ignore_errors=True)  # thư mục mới của chính lượt này (free_path): bản xuất dở không được nằm lại như một bản xuất
        raise
    # Ảnh bìa hỏng: bản xuất mang bìa vẽ từ tên - giao diện nói một câu (coverBroken).
    return {"folder": str(folder), "files": files, "chaptersTotal": summary["chapters"]["total"], **noted,
            **({"coverBroken": True} if real is not None and usable_cover(real) is None else {})}


def _mixed_mp3(ffmpeg: str, mixer: Any, listed: list[tuple[int, str, Path]], scratch: Path,
               cancelled: Callable[[], bool] | None = None) -> Iterator[tuple[str, Path]]:
    """Nguồn MP3 từng chương cho `write_mp3_folder` khi kèm nhạc: chương có nhạc trộn rồi mã hoá lại (LAME, cùng bitrate với MP3 của
    chương) vào `scratch` - file dùng xong mới làm chương kế; chương không có nhạc dùng nguyên file. Huỷ (`cancelled`) dừng ngay giữa chương."""
    for chapter_id, full_title, source in listed:
        _stop_if(cancelled)
        if not mixer.has(chapter_id):
            yield full_title, source
            continue
        rate, channels, kbps = audio_format(ffmpeg, source)
        temp = scratch / f"{chapter_id}.mp3"
        encode_stream(ffmpeg, rate, channels, ["-c:a", "libmp3lame", "-b:a", f"{kbps or 128}k", "-f", "mp3"], temp,
                      lambda sink, c=chapter_id, s=source, r=rate, n=channels: pump_mixed(ffmpeg, mixer, c, s, r, n, watched(sink, cancelled)) // (2 * n),
                      "MP3")
        yield full_title, temp
        temp.unlink(missing_ok=True)


# ---- Huỷ giữa lượt xuất (MP3 / M4B của Studio) ---------------------------------------------------------------------------
# Người dùng bấm Huỷ: lượt dừng ở khúc PCM kế (vài phần trăm giây), không chờ hết chương. `export_jobs.Cancelled` đi lên qua `encode_stream`
# (giết bộ mã hoá) và các `TemporaryDirectory` (xoá file tạm); chỗ gọi đổi nó thành trạng thái "Đã huỷ".

def _stop_if(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        raise Cancelled()


def _checked(items: Iterable[Any], cancelled: Callable[[], bool] | None) -> Iterator[Any]:
    """`items` từng cái một, hỏi huỷ trước mỗi cái (mỗi chương của bản xuất)."""
    for item in items:
        _stop_if(cancelled)
        yield item


class _Watched:
    """Ống PCM tới `sink` hỏi huỷ trước mỗi khúc."""

    def __init__(self, sink: Any, cancelled: Callable[[], bool]) -> None:
        self.sink, self.cancelled = sink, cancelled

    def write(self, data: bytes) -> int:
        _stop_if(self.cancelled)
        return self.sink.write(data)


def watched(sink: Any, cancelled: Callable[[], bool] | None) -> Any:
    """`sink` hỏi Huỷ trước mỗi khúc PCM (ném `Cancelled`); không có `cancelled` thì chính `sink`. Chung cho M4B, MP3 kèm nhạc và xuất sách nói (listen_export.py)."""
    return sink if cancelled is None else _Watched(sink, cancelled)


# ---- M4B: cả cuốn trong một file, có mục lục chương ------------------------------------------------------------------
# Trình phát sách nói (Apple Books, Smart AudioBook Player, BookPlayer...) đọc `.m4b` là MỘT cuốn có danh sách chương, nhớ chỗ
# nghe theo cuốn. Ghép là giải mã từng chương ra PCM rồi đổ liên tục vào MỘT bộ mã hoá AAC: đếm mẫu đi qua nên mốc chương đúng
# tới từng mẫu (không tin thời lượng ước của DB hay của container), không có khoảng câm/lệch như nối các đoạn AAC mã hoá riêng.
# Lượt hai chỉ chép luồng (không mã hoá lại) để gắn mục lục chương, bìa và tag.

M4B_EXTENSION = ".m4b"
# AAC-LC 64 kb/s cho giọng đọc mono đã nghe như bản gốc (MP3 chương của dây chuyền là giọng nói, không phải nhạc) và chỉ
# ~29 MB một giờ - cuốn 20 giờ vừa ~600 MB. Nguồn stereo (hai kênh khác nhau) mới cần 96 kb/s để không vỡ tiếng.
_AAC_BITRATE = {1: "64k", 2: "96k"}
# Bộ aac của ffmpeg ở 64k thỉnh thoảng vọt đỉnh ~+1,5 dB SAU mã hoá (có nhạc hay không; MUSIC_RENDER.md 3b, 5 - không đệm trước mã
# hoá nào chặn được): mã hoá xong đo đỉnh thật từng chương của file AAC, chương vượt trần (exportCeilingDbtp) được hạ đầu vào đúng phần
# vượt + _PEAK_MARGIN_DB rồi mã hoá lại cả luồng (vẫn 64k). Mã hoá lại xáo gai sang chương khác, nên hạ CỘNG DỒN: chương đã vượt ở
# lượt nào cũng giữ mức hạ, lượt sau chỉ hạ thêm - mức chỉ giảm nên hội tụ; tối đa _PEAK_RETRIES lượt, còn vượt thì vẫn xong (ghi log).
# Không chương nào vượt thì file y như trước.
_PEAK_MARGIN_DB = 0.1
_PEAK_RETRIES = 4
_CHUNK = 1 << 16
_HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def audio_format(ffmpeg: str, source: Path) -> tuple[int, int, int | None]:
    """(tần số mẫu, số kênh 1|2, kb/s hay None) của một file, đọc từ dòng "Audio:" ffmpeg in khi chỉ mở file (app không mang ffprobe)."""
    probe = run_hidden([ffmpeg, "-hide_banner", "-i", str(source)], timeout=60, check=False)
    match = re.search(r"Audio: [^\n]*?(\d+) Hz, ([^,\n]+)([^\n]*)", probe.stderr)
    if not match:
        raise ValueError(f"Không đọc được âm thanh của {source.name}")
    bitrate = re.search(r"(\d+) kb/s", match.group(3))
    return int(match.group(1)), 1 if match.group(2).strip() in ("mono", "1 channels") else 2, int(bitrate.group(1)) if bitrate else None


def audio_layout(ffmpeg: str, source: Path) -> tuple[int, int]:
    """(tần số mẫu, số kênh 1|2) của một file (`audio_format`)."""
    rate, channels, _bitrate = audio_format(ffmpeg, source)
    return rate, channels


def _ffmetadata(text: str) -> str:
    """Giá trị trong file ffmetadata: `=`, `;`, `#`, `\\` và xuống dòng phải có `\\` đứng trước."""
    return re.sub(r"([=;#\\\n])", r"\\\1", text)


def _chapter_marks(chapters: list[tuple[str, int, int]], rate: int) -> str:
    """Mục lục chương dạng ffmetadata: (tên, mẫu đầu, mẫu cuối) đổi ra mili giây."""
    lines = [";FFMETADATA1"]
    for title, start, end in chapters:
        lines += ["", "[CHAPTER]", "TIMEBASE=1/1000", f"START={round(start * 1000 / rate)}",
                  f"END={round(end * 1000 / rate)}", f"title={_ffmetadata(title)}"]
    return "\n".join(lines) + "\n"


def _tail(errors: Any) -> str:
    """Đuôi lời ffmpeg in ra (file tạm hứng stderr) - đủ để biết vì sao hỏng."""
    errors.seek(0)
    return errors.read().decode("utf-8", "replace").strip()[-300:]


def pump_pcm(ffmpeg: str, source: Path, rate: int, channels: int, sink: Any, lower_db: float = 0.0) -> int:
    """Giải mã một chương ra PCM 16-bit (đổi về `rate`/`channels` chung của cuốn) đổ vào `sink`; trả số byte đã đổ. `lower_db` > 0: hạ
    mức ngay trong ffmpeg (lần mã hoá lại M4B có chương vượt trần - không cần numpy, bản cài chỉ để nghe không có nó)."""
    lowering = ["-af", f"volume={-lower_db:.4f}dB"] if lower_db > 0 else []
    with tempfile.TemporaryFile() as errors:
        decoder = subprocess.Popen([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(source), "-map", "0:a:0", *lowering,
                                    "-f", "s16le", "-ar", str(rate), "-ac", str(channels), "pipe:1"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errors, creationflags=_HIDDEN)
        assert decoder.stdout is not None
        size = 0
        try:
            while block := decoder.stdout.read(_CHUNK):
                sink.write(block)
                size += len(block)
        finally:
            decoder.stdout.close()
            code = decoder.wait()
        if code != 0:
            raise ValueError(f"Không đọc được {source.name}: {_tail(errors)}")
    return size


def pump_mixed(ffmpeg: str, mixer: Any, chapter_id: int, source: Path, rate: int, channels: int, sink: Any,
               seconds: float | None = None) -> int:
    """Như `pump_pcm` nhưng giọng đi qua bộ trộn nhạc nền của chương (`music_export.Mixer.wrap`): `sink` nhận PCM đã trộn, đúng bằng số
    byte của giọng (trả lại số ấy). Chung cho MP3 / M4B của Studio và bản tạm chương của sách Nghe ngay."""
    mixed = mixer.wrap(chapter_id, sink, rate, channels, seconds)
    size = pump_pcm(ffmpeg, source, rate, channels, mixed)
    mixed.finish()
    return size


def encode_stream(ffmpeg: str, rate: int, channels: int, codec_args: list[str], destination: Path, feed: Callable[[Any], int], what: str = "âm thanh") -> int:
    """Một bộ mã hoá ffmpeg đọc PCM 16-bit (`rate`, `channels`) từ ống rồi ghi `destination` bằng `codec_args` (codec + bitrate + `-f`). `feed(sink)` đổ PCM
    vào `sink` và trả số mẫu đã đổ; hàm trả lại số ấy. Bộ mã hoá chết giữa chừng / feed hỏng thì dọn tiến trình và ném lỗi có lời. Chung cho M4B (cả cuốn một
    bộ mã hoá AAC, mốc chương đếm theo mẫu) và bản tạm từng chương của sách Nghe ngay (listen_export.py)."""
    with tempfile.TemporaryFile() as errors:
        encoder = subprocess.Popen([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(rate),
                                    "-ac", str(channels), "-i", "pipe:0", *codec_args, str(destination)],
                                   stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors, creationflags=_HIDDEN)
        assert encoder.stdin is not None
        fed = False
        try:
            samples = feed(encoder.stdin)
            encoder.stdin.close()
            fed = True
        except OSError as error:
            # Bộ mã hoá chết giữa chừng thì ống bị đóng (Windows báo EINVAL); lý do thật nằm trong lời nó in.
            raise ValueError(f"Không mã hoá được {what}: {_tail(errors)}") from error
        finally:
            if not fed:
                encoder.kill()
                encoder.wait()
        if encoder.wait() != 0:
            raise ValueError(f"Không mã hoá được {what}: {_tail(errors)}")
    return samples


def true_peak_dbtp(ffmpeg: str, path: Path, start: float = 0.0, seconds: float | None = None) -> float:
    """Đỉnh thật (dBTP, ebur128 của ffmpeg - lấy mẫu dày x4) của file âm thanh, hay của đoạn [start, start + seconds); -inf khi im hẳn."""
    span = ["-ss", f"{start:.6f}", "-t", f"{seconds:.6f}"] if seconds is not None else []
    run = subprocess.run([ffmpeg, "-hide_banner", "-nostats", *span, "-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, encoding="utf-8", errors="replace", check=False, creationflags=_HIDDEN)
    if run.returncode != 0:
        raise ValueError(f"Không đo được đỉnh âm thanh: {(run.stderr or '').strip()[-300:]}")
    found = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", run.stderr or "")
    return float(found[-1]) if found else -math.inf


class _Lowered:
    """Ống PCM 16-bit hạ `db` dB trước khi tới `sink` (chương có đỉnh AAC vượt trần, lần mã hoá lại) - chỉ cho chương đi qua bộ trộn nhạc
    (`decode`), nơi numpy đã có (music_export.Mixer bảo đảm); chương không nhạc được hạ ngay trong ffmpeg (`pump_pcm(lower_db=)`)."""

    def __init__(self, sink: Any, db: float) -> None:
        import numpy as np

        self.np, self.sink, self.factor, self.carry = np, sink, 10 ** (-db / 20), b""

    def write(self, data: bytes) -> int:
        np = self.np
        block = self.carry + bytes(data)
        usable = len(block) - len(block) % 2
        self.carry = block[usable:]
        if usable:
            scaled = np.rint(np.frombuffer(block[:usable], dtype="<i2") * self.factor)
            self.sink.write(np.clip(scaled, -32768, 32767).astype("<i2").tobytes())
        return len(data)


def m4b_from_files(ffmpeg: str, chapters: list[tuple[str, Path]], target_root: Path, *, title: str, narrator: str,
                   cover_for: Callable[[Path], Path | None], on_chapter: Callable[[int], None] | None = None,
                   decode: Callable[[int, Path, int, int, Any], int] | None = None,
                   on_peaks: Callable[[int, int], None] | None = None, cancelled: Callable[[], bool] | None = None) -> tuple[Path, int]:
    """Cả cuốn thành `<tên sách>.m4b` trong `target_root` từ các file chương `chapters` (tên chương, file âm thanh bất kỳ ffmpeg đọc được): AAC, mỗi chương một mục,
    bìa và tag. `cover_for(thư mục làm việc)` trả file bìa (hay None). `on_chapter(i)` gọi trước khi chương thứ i (từ 0) được ghép - chỗ báo tiến độ / dừng (ném
    lỗi để dừng). `decode(i, file, tần số, kênh, sink)` thay `pump_pcm` cho chương thứ i nếu có (kèm nhạc nền: `pump_mixed`), trả số byte
    đã đổ. Chương có đỉnh thật AAC vượt trần thì cả luồng được mã hoá lại với chương ấy hạ mức (`_PEAK_RETRIES`; `on_chapter` /
    `decode` được gọi lại từ đầu). `on_peaks(lượt, số chương vượt)` báo bước ấy: (k, 0) = đang đo đỉnh (sau lần mã hoá thứ k+1),
    (k, N) = đang mã hoá lại lượt k vì N chương vượt. `cancelled()` True: dừng ở khúc PCM kế / trước chương kế được đo đỉnh / trước lượt
    ghép cuối, ném `export_jobs.Cancelled` - thư mục tạm bị xoá, không ghi file đích. Trả (file, số chương)."""
    # Định dạng chung theo chương đầu; chương khác tần số / số kênh được ffmpeg đổi theo lúc giải mã - mốc vẫn đúng.
    rate, channels = audio_layout(ffmpeg, chapters[0][1])
    target_root.mkdir(parents=True, exist_ok=True)
    final = free_path(target_root / f"{safe_name(title)}{M4B_EXTENSION}")
    # File trung gian nằm cạnh file đích (cùng ổ - cuốn dài ra vài trăm MB), thư mục tạm tự dọn kể cả khi hỏng.
    with tempfile.TemporaryDirectory(prefix=".m4b-", dir=target_root) as scratch:
        work = Path(scratch)
        audio = work / "audio.m4a"
        marks: list[tuple[str, int, int]] = []
        lowered: dict[int, float] = {}  # chương (từ 0) -> dB hạ đầu vào ở lần mã hoá lại

        def feed(sink: Any) -> int:
            sink = watched(sink, cancelled)
            frame = 2 * channels
            position = 0
            marks.clear()
            for index, (name, source) in enumerate(chapters):
                if on_chapter is not None:
                    on_chapter(index)
                if decode is not None:
                    size = decode(index, source, rate, channels, _Lowered(sink, lowered[index]) if index in lowered else sink)
                elif index in lowered:
                    size = pump_pcm(ffmpeg, source, rate, channels, sink, lower_db=lowered[index])
                else:
                    size = pump_pcm(ffmpeg, source, rate, channels, sink)
                length = size // frame
                marks.append((name, position, position + length))
                position += length
            return position

        codec = ["-c:a", "aac", "-b:a", _AAC_BITRATE[channels], "-f", "mp4"]
        encode_stream(ffmpeg, rate, channels, codec, audio, feed, "AAC")
        ceiling = MIX["exportCeilingDbtp"]
        report = on_peaks or (lambda _round, _over: None)
        report(0, 0)

        def measure() -> list[float]:
            return [true_peak_dbtp(ffmpeg, audio, start / rate, (end - start) / rate) for _name, start, end in _checked(marks, cancelled)]

        peaks = measure()
        for attempt in range(1, _PEAK_RETRIES + 1):
            over = {index: peak for index, peak in enumerate(peaks) if peak > ceiling}
            if not over:
                break
            for index, peak in over.items():
                lowered[index] = lowered.get(index, 0.0) + peak - ceiling + _PEAK_MARGIN_DB
            report(attempt, len(over))
            encode_stream(ffmpeg, rate, channels, codec, audio, feed, "AAC")
            report(attempt, 0)
            peaks = measure()
            log.info("M4B: đỉnh AAC vượt %.1f dBTP ở %d chương, lần mã hoá lại %d (hạ %s) -> đỉnh %s", ceiling, len(over), attempt,
                     {index + 1: round(db, 2) for index, db in lowered.items()}, {index + 1: round(peaks[index], 2) for index in lowered})
        if left := {index + 1: round(peak, 2) for index, peak in enumerate(peaks) if peak > ceiling}:
            log.warning("M4B: sau %d lần mã hoá lại vẫn còn đỉnh AAC vượt %.1f dBTP: %s", _PEAK_RETRIES, ceiling, left)
        _stop_if(cancelled)
        meta = work / "chapters.txt"
        meta.write_bytes(_chapter_marks(marks, rate).encode("utf-8"))
        cover_path = cover_for(work)
        partial = final.with_name(final.name + ".part")
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(audio), "-f", "ffmetadata", "-i", str(meta)]
        if cover_path:
            command += ["-i", str(cover_path), "-map", "0:a", "-map", "2:v", "-c:v", "copy", "-disposition:v", "attached_pic"]
        else:
            command += ["-map", "0:a"]
        command += [
            # Tag chung lấy từ file mục lục (không có gì) thay vì từ file trung gian; `-map_metadata -1` thì ffmpeg bỏ luôn tên chương.
            "-c:a", "copy", "-map_metadata", "1", "-map_chapters", "1",
            "-metadata", f"title={title}",
            "-metadata", f"album={title}",
            "-metadata", f"artist={narrator}",
            "-metadata", f"album_artist={narrator}",
            "-metadata", "genre=Audiobook",
            # Bộ ghi "ipod" là bộ ffmpeg dùng cho .m4b; nhãn "M4B " để Apple Books / iTunes xếp vào sách nói, không phải nhạc.
            "-brand", "M4B ", "-f", "ipod", str(partial),
        ]
        try:
            run_hidden(command, timeout=3600)
        except subprocess.CalledProcessError as error:
            partial.unlink(missing_ok=True)
            log.warning("ffmpeg không ghép được M4B: %s", (error.stderr or "").strip()[-600:])
            raise ValueError("Không ghép được file M4B - ảnh bìa hay một chương không đọc được.") from error
        os.replace(partial, final)
    return final, len(marks)


def export_m4b(project_root: Path, target_root: Path, *, cover: str | None = None, music: Callable[[str], Path | None] | None = None,
               progress: Callable[[int, int], None] | None = None, peaks: Callable[[int, int], None] | None = None,
               cancelled: Callable[[], bool] | None = None) -> dict[str, Any]:
    """Cả cuốn thành một file `<tên sách>.m4b` trong `target_root`: AAC, mỗi chương một mục (tên chương thật), bìa và tag như
    bản xuất MP3. Chỉ chương đã nghe được, như mọi kiểu xuất; `chaptersTotal` để giao diện nói chương nào chưa có.
    `music`: nguồn file bài nhạc = "Kèm nhạc nền" (như `export_book`): nhạc trộn vào PCM trước bộ mã hoá AAC; `progress(i, N)` báo đang
    trộn nhạc chương thứ i (từ 1) trong N; `peaks(lượt, số chương vượt)`: bước kiểm đỉnh AAC (`m4b_from_files` on_peaks). `cancelled()`: Huỷ
    (`m4b_from_files`) - bài nhạc còn phải tải thì do nguồn `music` tự dừng (server.music_exporting)."""
    summary = store.summarize(project_root)
    title = summary["title"] or project_root.name
    narrator = summary["settings"]["narrator"] or ""
    audio = store.chapter_audio_paths(project_root)
    listed = [(chapter["id"], chapter["fullTitle"], path) for chapter in _listenable(project_root)
              if (path := audio.get(chapter["id"])) is not None]
    chapters = [(full_title, path) for _id, full_title, path in listed]
    if not chapters:
        raise ValueError("Sách chưa có chương nào nghe được để xuất")
    if not ffmpeg_available():
        raise ValueError("Cần tải thêm công cụ ghép âm thanh (khoảng 31 MB) để làm file M4B - mở Xuất, chọn Sách nói M4B rồi bấm Tải công cụ.")
    ffmpeg = ffmpeg_executable()
    ids = [chapter_id for chapter_id, _title, _path in listed]
    mixer: Any = None
    if music is not None:
        from .music_export import Mixer, studio_music  # nhập muộn: music_export dùng pump_pcm của module này

        mixer = Mixer(ffmpeg, studio_music(project_root, ids, music))

    def decode(index: int, source: Path, rate: int, channels: int, sink: Any) -> int:
        if mixer is None or not mixer.has(ids[index]):
            return pump_pcm(ffmpeg, source, rate, channels, sink)
        if progress is not None:
            progress(index + 1, len(ids))
        return pump_mixed(ffmpeg, mixer, ids[index], source, rate, channels, sink)

    final, count = m4b_from_files(ffmpeg, chapters, target_root, title=title, narrator=narrator,
                                  cover_for=lambda work: usable_cover(covers.cover_file(project_root)) or drawn_cover(work, cover),
                                  decode=decode if mixer is not None else None, on_peaks=peaks, cancelled=cancelled)
    real = covers.cover_file(project_root)
    return {"file": str(final), "folder": str(target_root), "size": final.stat().st_size,
            "chapters": count, "chaptersTotal": summary["chapters"]["total"], **(mixer.note(ids) if mixer is not None else {}),
            **({"coverBroken": True} if real is not None and usable_cover(real) is None else {})}


def _title_of(project: Path) -> str:
    return store.summarize(project)["title"] or project.name


def series_split(parts: list[Path]) -> tuple[list[tuple[int, Path]], list[dict[str, Any]]]:
    """Các phần của bộ chia làm hai: phần có chương nghe được [(số phần, dự án)] và phần chưa có chương nào [{part, title}].
    Số phần là vị trí trong bộ, không đếm lại sau khi bỏ qua - "Phần 3" vẫn là phần 3. Mọi kiểu xuất cả bộ dùng chung."""
    listed: list[tuple[int, Path]] = []
    skipped: list[dict[str, Any]] = []
    for number, project in enumerate(parts, start=1):
        if _listenable(project):
            listed.append((number, project))
        else:
            skipped.append({"part": number, "title": _title_of(project)})
    if not listed:
        raise ValueError("Chưa phần nào của bộ có chương nghe được để xuất")
    return listed, skipped


def audio_bytes(projects: list[Path], music_track: Callable[[str], Path | None] | None = None) -> tuple[int, int]:
    """(cỡ, số bài nhạc chưa tải) ước lượng của file `.abook` trước khi xuất: audio các chương nghe được + các bài nhạc nền
    sẽ đóng kèm (đoạn nhạc của các chương ấy trong rãnh nhạc đang bật; mỗi bài một lần dù nhiều đoạn, nhiều phần). Không tải gì:
    `music_track(link)` chỉ trả bài đã có trong bộ đệm; bài chưa tải được đếm riêng - lúc xuất mới tải và thêm vào."""
    total = 0
    links: set[str] = set()
    for project in projects:
        plan = music_plan.read_plan(project) if music_track is not None else None
        audio = store.chapter_audio_paths(project)
        for chapter in _listenable(project):
            path = audio.get(chapter["id"])
            if path is not None:
                total += path.stat().st_size
            if plan is not None:
                links.update(cue["link"] for cue in music_plan.chapter_cues(plan, chapter["id"]))
    pending = 0
    for link in links:
        path = music_track(link) if music_track is not None else None
        if path is None:
            pending += 1
        else:
            total += path.stat().st_size
    return total, pending


def export_series(parts: list[Path], target_root: Path,
                  export_part: Callable[[Path, Path, str], dict[str, Any]]) -> dict[str, Any]:
    """Xuất cả bộ ("Làm tiếp cuốn này" chia một truyện thành nhiều dự án): một thư mục cho bộ, mỗi phần xuất bằng đúng đường
    xuất một phần. `export_part(dự án, thư mục bộ, "Phần N - tên")` làm một phần và trả kết quả của nó (MP3: thư mục
    con theo nhãn; .abook: một file mang nhãn). Chỉ chương đã xong như xuất một phần; phần chưa có chương nào bị bỏ qua và
    được kể tên - người dùng thấy bộ thiếu phần nào thay vì nghĩ là xuất sót."""
    listed, skipped = series_split(parts)
    folder = free_path(target_root / safe_name(continuation.base_title(_title_of(parts[0]))))
    try:
        done = [{"part": number, "title": _title_of(project),
                 **export_part(project, folder, f"Phần {number} - {continuation.base_title(_title_of(project))}")}
                for number, project in listed]
    except Cancelled:
        shutil.rmtree(folder, ignore_errors=True)  # huỷ giữa bộ: các phần đã xong của lượt này cũng đi theo - không để lại nửa bộ
        raise
    return {"folder": str(folder), "parts": done, "skipped": skipped, "partsTotal": len(parts)}


def export_series_file(parts: list[Path], target_root: Path,
                       pack: Callable[[list[tuple[int, Path]], Path], Path]) -> dict[str, Any]:
    """Cả bộ trong MỘT file `.abook` (phiên bản 3, bookfile.pack_series) nằm thẳng trong `target_root`, tên theo tên bộ.
    `pack(các phần, đường file)` ghi file và trả đường dẫn. Kết quả cùng hình dạng với `export_series` (parts, skipped,
    partsTotal) cộng `file` + `size`: giao diện phân biệt "một file" với "mỗi phần một file" bằng chỗ có `file`."""
    from .bookfile import default_name

    listed, skipped = series_split(parts)
    path = pack(listed, free_path(target_root / default_name(continuation.base_title(_title_of(parts[0])))))
    return {"folder": str(path.parent), "file": str(path), "size": path.stat().st_size,
            "parts": [{"part": number, "title": _title_of(project)} for number, project in listed],
            "skipped": skipped, "partsTotal": len(parts)}
