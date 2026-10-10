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
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .. import continuation
from ..io_utils import ffmpeg_available, ffmpeg_executable, run_hidden
from . import covers, listen_view, music_plan, store

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(text: str, limit: int = 120) -> str:
    """Tên file hợp lệ trên Windows, giữ nguyên chữ tiếng Việt."""
    cleaned = _UNSAFE.sub(" ", text).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:limit].rstrip() or "Sach"


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


def copy_real_cover(source: Path | None, folder: Path) -> Path | None:
    """Ảnh bìa thật người dùng đã đặt (covers.py; sách Nghe ngay: book_edits.cover_file) thắng bìa tự vẽ mà giao diện gửi kèm; chép vào thư mục xuất."""
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
    run_hidden(command, timeout=300)
    os.replace(partial, final)


def playlist_text(title: str, entries: list[tuple[float, str, str]]) -> str:
    """Danh sách phát `.m3u8` của bản xuất; `entries`: (thời lượng giây, tên chương, tên file)."""
    lines = ["#EXTM3U", f"#PLAYLIST:{title}"]
    for duration, full_title, name in entries:
        lines += [f"#EXTINF:{int(round(duration))},{full_title}", name]
    return "\n".join(lines) + "\n"


def write_mp3_folder(ffmpeg: str, folder: Path, chapters: Iterable[tuple[str, Path, float]], *, title: str, narrator: str,
                     cover_path: Path | None, total: int) -> int:
    """Mỗi chương một MP3 trong `folder` (tag + bìa, `write_chapter`) kèm `.m3u8`; trả số file. `chapters`: (tên chương, file MP3 nguồn, thời lượng giây) - có thể là
    bộ sinh làm ra file nguồn từng chương một (sách Nghe ngay mã hoá từ bản tạm: file nguồn dùng xong, bộ sinh mới được chạy tiếp và dọn nó). `total`: số chương sẽ có.
    Chung cho xuất MP3 của Studio (`export_book`) và của sách Nghe ngay (listen_export.py)."""
    entries: list[tuple[float, str, str]] = []
    for number, (full_title, source, duration) in enumerate(chapters, start=1):
        name = chapter_file_name(number, total, full_title)
        write_chapter(ffmpeg, source, folder / name, cover_path, title=full_title, album=title,
                      narrator=narrator, number=number, total=total)
        entries.append((duration, full_title, name))
    (folder / f"{safe_name(title)}.m3u8").write_text(playlist_text(title, entries), encoding="utf-8")
    return len(entries)


def export_book(project_root: Path, target_root: Path, *, cover: str | None = None,
                folder_name: str | None = None) -> dict[str, Any]:
    """`folder_name`: tên thư mục thay cho tên sách - bản xuất cả bộ đặt mỗi phần vào "Phần N - ..."."""
    summary = store.summarize(project_root)
    title = summary["title"] or project_root.name
    narrator = summary["settings"]["narrator"] or ""
    chapters = _listenable(project_root)
    if not chapters:
        raise ValueError("Sách chưa có chương nào nghe được để xuất")
    folder = target_root / safe_name(folder_name or title)
    folder.mkdir(parents=True, exist_ok=True)
    cover_path = copy_real_cover(covers.cover_file(project_root), folder) or drawn_cover(folder, cover)
    ffmpeg = ffmpeg_executable()
    sources = [(chapter["fullTitle"], path, chapter["duration"]) for chapter in chapters
               if (path := store.chapter_audio_path(project_root, chapter["id"])) is not None]
    files = write_mp3_folder(ffmpeg, folder, sources, title=title, narrator=narrator, cover_path=cover_path, total=len(sources))
    return {"folder": str(folder), "files": files, "chaptersTotal": summary["chapters"]["total"]}


# ---- M4B: cả cuốn trong một file, có mục lục chương ------------------------------------------------------------------
# Trình phát sách nói (Apple Books, Smart AudioBook Player, BookPlayer...) đọc `.m4b` là MỘT cuốn có danh sách chương, nhớ chỗ
# nghe theo cuốn. Ghép là giải mã từng chương ra PCM rồi đổ liên tục vào MỘT bộ mã hoá AAC: đếm mẫu đi qua nên mốc chương đúng
# tới từng mẫu (không tin thời lượng ước của DB hay của container), không có khoảng câm/lệch như nối các đoạn AAC mã hoá riêng.
# Lượt hai chỉ chép luồng (không mã hoá lại) để gắn mục lục chương, bìa và tag.

M4B_EXTENSION = ".m4b"
# AAC-LC 64 kb/s cho giọng đọc mono đã nghe như bản gốc (MP3 chương của dây chuyền là giọng nói, không phải nhạc) và chỉ
# ~29 MB một giờ - cuốn 20 giờ vừa ~600 MB. Nguồn stereo (hai kênh khác nhau) mới cần 96 kb/s để không vỡ tiếng.
_AAC_BITRATE = {1: "64k", 2: "96k"}
_CHUNK = 1 << 16
_HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def audio_layout(ffmpeg: str, source: Path) -> tuple[int, int]:
    """(tần số mẫu, số kênh 1|2) của một file, đọc từ dòng "Audio:" ffmpeg in khi chỉ mở file (app không mang ffprobe)."""
    probe = run_hidden([ffmpeg, "-hide_banner", "-i", str(source)], timeout=60, check=False)
    match = re.search(r"Audio: [^\n]*?(\d+) Hz, ([^,\n]+)", probe.stderr)
    if not match:
        raise ValueError(f"Không đọc được âm thanh của {source.name}")
    return int(match.group(1)), 1 if match.group(2).strip() in ("mono", "1 channels") else 2


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


def pump_pcm(ffmpeg: str, source: Path, rate: int, channels: int, sink: Any) -> int:
    """Giải mã một chương ra PCM 16-bit (đổi về `rate`/`channels` chung của cuốn) đổ vào `sink`; trả số byte đã đổ."""
    with tempfile.TemporaryFile() as errors:
        decoder = subprocess.Popen([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(source), "-map", "0:a:0",
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


def m4b_from_files(ffmpeg: str, chapters: list[tuple[str, Path]], target_root: Path, *, title: str, narrator: str,
                   cover_for: Callable[[Path], Path | None], on_chapter: Callable[[int], None] | None = None) -> tuple[Path, int]:
    """Cả cuốn thành `<tên sách>.m4b` trong `target_root` từ các file chương `chapters` (tên chương, file âm thanh bất kỳ ffmpeg đọc được): AAC, mỗi chương một mục,
    bìa và tag. `cover_for(thư mục làm việc)` trả file bìa (hay None). `on_chapter(i)` gọi trước khi chương thứ i (từ 0) được ghép - chỗ báo tiến độ / dừng (ném
    lỗi để dừng). Trả (file, số chương)."""
    # Định dạng chung theo chương đầu; chương khác tần số / số kênh được ffmpeg đổi theo lúc giải mã - mốc vẫn đúng.
    rate, channels = audio_layout(ffmpeg, chapters[0][1])
    target_root.mkdir(parents=True, exist_ok=True)
    final = target_root / f"{safe_name(title)}{M4B_EXTENSION}"
    # File trung gian nằm cạnh file đích (cùng ổ - cuốn dài ra vài trăm MB), thư mục tạm tự dọn kể cả khi hỏng.
    with tempfile.TemporaryDirectory(prefix=".m4b-", dir=target_root) as scratch:
        work = Path(scratch)
        audio = work / "audio.m4a"
        marks: list[tuple[str, int, int]] = []

        def feed(sink: Any) -> int:
            frame = 2 * channels
            position = 0
            for index, (name, source) in enumerate(chapters):
                if on_chapter is not None:
                    on_chapter(index)
                length = pump_pcm(ffmpeg, source, rate, channels, sink) // frame
                marks.append((name, position, position + length))
                position += length
            return position

        encode_stream(ffmpeg, rate, channels, ["-c:a", "aac", "-b:a", _AAC_BITRATE[channels], "-f", "mp4"], audio, feed, "AAC")
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
            raise ValueError(f"Không ghép được file M4B: {(error.stderr or '').strip()[-300:]}") from error
        os.replace(partial, final)
    return final, len(marks)


def export_m4b(project_root: Path, target_root: Path, *, cover: str | None = None) -> dict[str, Any]:
    """Cả cuốn thành một file `<tên sách>.m4b` trong `target_root`: AAC, mỗi chương một mục (tên chương thật), bìa và tag như
    bản xuất MP3. Chỉ chương đã nghe được, như mọi kiểu xuất; `chaptersTotal` để giao diện nói chương nào chưa có."""
    summary = store.summarize(project_root)
    title = summary["title"] or project_root.name
    narrator = summary["settings"]["narrator"] or ""
    chapters = [(chapter["fullTitle"], path) for chapter in _listenable(project_root)
                if (path := store.chapter_audio_path(project_root, chapter["id"])) is not None]
    if not chapters:
        raise ValueError("Sách chưa có chương nào nghe được để xuất")
    if not ffmpeg_available():
        raise ValueError("Máy này chưa có ffmpeg để làm file M4B")
    final, count = m4b_from_files(ffmpeg_executable(), chapters, target_root, title=title, narrator=narrator,
                                  cover_for=lambda work: covers.cover_file(project_root) or drawn_cover(work, cover))
    return {"file": str(final), "folder": str(target_root), "size": final.stat().st_size,
            "chapters": count, "chaptersTotal": summary["chapters"]["total"]}


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
        for chapter in _listenable(project):
            path = store.chapter_audio_path(project, chapter["id"])
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
    folder = target_root / safe_name(continuation.base_title(_title_of(parts[0])))
    done = [{"part": number, "title": _title_of(project),
             **export_part(project, folder, f"Phần {number} - {continuation.base_title(_title_of(project))}")}
            for number, project in listed]
    return {"folder": str(folder), "parts": done, "skipped": skipped, "partsTotal": len(parts)}


def export_series_file(parts: list[Path], target_root: Path,
                       pack: Callable[[list[tuple[int, Path]], Path], Path]) -> dict[str, Any]:
    """Cả bộ trong MỘT file `.abook` (phiên bản 3, bookfile.pack_series) nằm thẳng trong `target_root`, tên theo tên bộ.
    `pack(các phần, đường file)` ghi file và trả đường dẫn. Kết quả cùng hình dạng với `export_series` (parts, skipped,
    partsTotal) cộng `file` + `size`: giao diện phân biệt "một file" với "mỗi phần một file" bằng chỗ có `file`."""
    from .bookfile import default_name

    listed, skipped = series_split(parts)
    path = pack(listed, target_root / default_name(continuation.base_title(_title_of(parts[0]))))
    return {"folder": str(path.parent), "file": str(path), "size": path.stat().st_size,
            "parts": [{"part": number, "title": _title_of(project)} for number, project in listed],
            "skipped": skipped, "partsTotal": len(parts)}
