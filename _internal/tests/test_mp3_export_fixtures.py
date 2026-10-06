"""Bộ ví dụ chung của "Xuất MP3" (tests/mp3_export_fixtures.py) vẫn đúng với mã máy tính hiện tại: tên file, danh sách phát, và tag
ffmpeg ghi. Điện thoại (Id3TagTest.kt, Mp3ExportTest.kt) so với đúng những file này."""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from abook.io_utils import ffmpeg_executable
from tests import mp3_export_fixtures as fixtures


def _stored(name: str) -> object:
    return json.loads((fixtures.FIXTURES / name).read_text(encoding="utf-8"))


def _frames(data: bytes) -> list[tuple[bytes, bytes]]:
    """Các khung của thẻ ID3v2.3 đầu file (cỡ khung là số nguyên thường, không phải syncsafe)."""
    assert data[:3] == b"ID3" and data[3] == 3
    size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
    body, out, at = data[10:10 + size], [], 0
    while at + 10 <= len(body) and body[at:at + 4] != b"\0\0\0\0":
        length = struct.unpack(">I", body[at + 4:at + 8])[0]
        out.append((body[at:at + 4], body[at + 10:at + 10 + length]))
        at += 10 + length
    return out


def test_names_and_playlist_match_the_desktop_code() -> None:
    assert _stored("names.json") == fixtures.names()
    assert _stored("playlist.json") == fixtures.playlist()


@pytest.mark.parametrize("case", fixtures.TAG_CASES, ids=[case["name"] for case in fixtures.TAG_CASES])
def test_expected_tags_are_what_ffmpeg_writes_today(case: dict, tmp_path: Path) -> None:
    ffmpeg = ffmpeg_executable()
    if not Path(ffmpeg).is_file():
        pytest.skip("không có ffmpeg")
    fresh = tmp_path / "out.mp3"
    fixtures.write_case(ffmpeg, case, fresh)
    stored = (fixtures.FIXTURES / "expected" / f"{case['name']}.mp3").read_bytes()
    now = fresh.read_bytes()
    # TSSE là tên phiên bản ffmpeg ("Lavf61.7.100") - đổi theo bản ffmpeg, điện thoại không ghi nó.
    assert [frame for frame in _frames(now) if frame[0] != b"TSSE"] == [frame for frame in _frames(stored) if frame[0] != b"TSSE"]
    assert now[-128:] == stored[-128:]
