"""Cổng "phát được tới hết bài" của nhạc đang tải dở dùng cùng hằng số ở Qt, web và điện thoại.

Bài đang tải dở chỉ vào khi phần đã tải cùng tốc độ tải (trung bình trượt, gộp đợt dồn đầu, chia lề) đủ để phát từ chỗ vào tới hết bài,
có sẵn một đoạn trước con trỏ; hụt giữa bài thì mờ ra / vào trong cùng một khoảng (musicmixer.cpp `keepsUp`, musicBed.ts `playsThrough`,
StreamPace.kt `playsThrough`). Một bản lệch số là cùng một mạng mà nhạc vào sớm / muộn khác nhau giữa các máy.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
QT = ROOT / "desktop_qt" / "src" / "musicmixer.cpp"
WEB = ROOT / "ui" / "src" / "listen" / "musicBed.ts"
PHONE = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player" / "StreamPace.kt"

# Tên hằng ở mỗi bản, quy về giây: (Qt, web, điện thoại tính bằng ms).
NAMES = {
    "window": ("RATE_WINDOW_S", "DOWNLOAD_WINDOW_SECONDS", "WINDOW_MS"),
    "burst": ("BURST_S", "DOWNLOAD_BURST_SECONDS", "BURST_MS"),
    "margin": ("DOWNLOAD_MARGIN", "DOWNLOAD_MARGIN", "MARGIN"),
    "lead": ("DECODE_LEAD_S", "DOWNLOAD_LEAD_SECONDS", "LEAD_MS"),
    "fade": ("UNDERRUN_FADE_S", "UNDERRUN_FADE_SECONDS", "FADE_MS"),
}


def constant(path: Path, name: str) -> float:
    text = path.read_text(encoding="utf-8")
    found = re.search(rf"\b{name}\s*=\s*([\d_.]+)L?\b", text)
    assert found, f"{path.name}: không thấy hằng {name}"
    return float(found.group(1).replace("_", ""))


@pytest.mark.parametrize("key", sorted(NAMES))
def test_the_three_players_share_the_gate_constants(key):
    qt, web, phone = NAMES[key]
    scale = 1 if key == "margin" else 1000
    values = {"qt": constant(QT, qt), "web": constant(WEB, web), "phone": constant(PHONE, phone) / scale}
    assert len(set(values.values())) == 1, f"{key}: {values}"


def test_web_and_phone_start_fading_at_the_same_buffered_lead():
    # Qt canh vòng PCM đã giải mã (UNDERRUN_LOW_S), web và điện thoại canh phần đã tải trước con trỏ: hai bản sau phải như nhau.
    assert constant(WEB, "UNDERRUN_LOW_SECONDS") == constant(PHONE, "LOW_MS") / 1000
