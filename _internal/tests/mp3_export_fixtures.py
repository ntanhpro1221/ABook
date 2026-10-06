"""Bộ ví dụ DÙNG CHUNG cho "Xuất MP3" (webui/export.py): pytest (test_mp3_export_fixtures.py) và test JVM của app Android
(Id3TagTest.kt, Mp3ExportTest.kt) cùng đọc `tests/fixtures/mp3_export/` - máy tính ghi tag bằng ffmpeg, điện thoại ghi bằng tay,
hai bên phải ra cùng những byte này.

    fixtures/mp3_export/source.mp3         MP3 chương như dây chuyền ghi: 0,3 giây lặng, tag nội bộ ("645", "lo16") ở cả
                                           ID3v2 lẫn ID3v1 - bản xuất phải bỏ chúng
    fixtures/mp3_export/cover.jpg          bìa thật của sách (covers.COVER_FILE)
    fixtures/mp3_export/cover.png          bìa giao diện tự vẽ khi sách không có bìa
    fixtures/mp3_export/tags.json          các ca ghi tag: tên chương, tên sách, giọng kể, số thứ tự, bìa -> expected/<ca>.mp3
    fixtures/mp3_export/expected/<ca>.mp3  file do `export.write_chapter` (ffmpeg) ghi cho ca ấy
    fixtures/mp3_export/names.json         tên thư mục / tên file: safe_name và chapter_file_name
    fixtures/mp3_export/playlist.json      danh sách phát .m3u8 (playlist_text)

Sinh lại (chỉ khi cố ý đổi hành vi):  runtime/.venv/Scripts/python.exe -m tests.mp3_export_fixtures
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from abook.io_utils import ffmpeg_executable, run_hidden  # noqa: E402
from abook.webui import export  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "mp3_export"

TAG_CASES: list[dict[str, Any]] = [
    {"name": "vietnamese_drawn_cover", "title": "Chương 1: Mở đầu", "album": "Sách thử", "narrator": "Đức Trí",
     "number": 1, "total": 2, "cover": "cover.png"},
    # ID3v1 cắt ở byte thứ 30, giữa một chữ có dấu; ký tự ngoài BMP (cặp UTF-16); giọng kể trống thì không có TPE1/TPE2.
    {"name": "long_titles_real_cover", "title": "Chương mười hai: Người đàn ông bí ẩn ở cuối con đường 🌙",
     "album": "Tên sách rất dài để thử cắt ID3v1 xem sao nhé", "narrator": "", "number": 12, "total": 120,
     "cover": "cover.jpg"},
    # Chữ ASCII ghi bằng ISO-8859-1; số chương quá 255 trong ID3v1 chỉ còn byte thấp.
    {"name": "ascii_no_cover", "title": "Plain", "album": "Book", "narrator": "Narr", "number": 300, "total": 300,
     "cover": None},
]

SAFE_NAME_CASES: list[tuple[str, int]] = [
    ("Chương 646: Trở về/1?", 120),
    ('  "..."  ', 120),
    (". a .", 120),
    ("Tên\tcó　nhiều    khoảng\ntrắng", 120),
    ("..Sách.. ", 120),
    ("<>:\"/\\|?*\x01\x1f", 120),
    ("Một tên chương rất dài " * 6, 90),
    ("A" * 89 + " B", 90),
    ("🌙" * 100, 90),
    ("", 120),
]

FILE_NAME_CASES: list[tuple[int, int, str]] = [
    (1, 2, "Chương 1 · Mở đầu"),
    (7, 99, "Chương 7: Trở về/1?"),
    (12, 120, "Chương mười hai"),
    (1, 1000, "Kết"),
    (3, 5, "   "),
]

PLAYLIST = {
    "title": "Sách thử · Tập 1",
    "entries": [[12.2, "Chương 1 · Mở đầu", "01 - Chương 1 · Mở đầu.mp3"],
                [2.5, "Chương 2", "02 - Chương 2.mp3"],
                [3.5, "Chương 3", "03 - Chương 3.mp3"],
                [0.0, "Chương 4", "04 - Chương 4.mp3"]],
}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def _media(ffmpeg: str) -> None:
    lavfi = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i"]
    run_hidden(lavfi + ["anullsrc=r=24000:cl=mono", "-t", "0.3", "-c:a", "libmp3lame", "-b:a", "32k",
                        "-metadata", "title=645", "-metadata", "album=lo16", "-id3v2_version", "3", "-write_id3v1", "1",
                        str(FIXTURES / "source.mp3")], timeout=60)
    run_hidden(lavfi + ["color=c=blue:s=8x8", "-frames:v", "1", str(FIXTURES / "cover.jpg")], timeout=60)
    run_hidden(lavfi + ["color=c=red:s=8x8", "-frames:v", "1", str(FIXTURES / "cover.png")], timeout=60)


def write_case(ffmpeg: str, case: dict[str, Any], target: Path) -> None:
    """Ghi file mong đợi của một ca bằng đúng đường xuất của máy tính."""
    cover = FIXTURES / case["cover"] if case["cover"] else None
    export.write_chapter(ffmpeg, FIXTURES / "source.mp3", target, cover, title=case["title"], album=case["album"],
                         narrator=case["narrator"], number=case["number"], total=case["total"])


def names() -> dict[str, Any]:
    return {
        "safeName": [{"text": text, "limit": limit, "name": export.safe_name(text, limit)} for text, limit in SAFE_NAME_CASES],
        "chapterFileName": [{"number": number, "total": total, "fullTitle": title,
                             "name": export.chapter_file_name(number, total, title)}
                            for number, total, title in FILE_NAME_CASES],
    }


def playlist() -> dict[str, Any]:
    entries = [tuple(entry) for entry in PLAYLIST["entries"]]
    return {**PLAYLIST, "text": export.playlist_text(PLAYLIST["title"], entries)}  # type: ignore[arg-type]


def main() -> None:
    ffmpeg = ffmpeg_executable()
    (FIXTURES / "expected").mkdir(parents=True, exist_ok=True)
    _media(ffmpeg)
    for case in TAG_CASES:
        write_case(ffmpeg, case, FIXTURES / "expected" / f"{case['name']}.mp3")
    cases = [{**case, "expected": f"expected/{case['name']}.mp3"} for case in TAG_CASES]
    (FIXTURES / "tags.json").write_bytes(_json_bytes(cases))
    (FIXTURES / "names.json").write_bytes(_json_bytes(names()))
    (FIXTURES / "playlist.json").write_bytes(_json_bytes(playlist()))


if __name__ == "__main__":
    main()
