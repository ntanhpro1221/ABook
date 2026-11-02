"""Cổng "phát được tới chỗ bài thôi kêu" của nhạc đang tải dở: Qt, web và điện thoại ĐỌC cùng các khoá underrun* của music_mix.json.

Bài đang tải dở chỉ vào khi phần đã tải cùng tốc độ tải (trung bình trượt, gộp đợt dồn đầu, chia lề) đủ để phát từ chỗ vào tới chỗ bài thôi kêu
(hết chuỗi mốc liền nhau cùng bài + mờ ra - `playEnd`), có sẵn một đoạn trước con trỏ; hụt giữa bài thì mờ ra / vào trong cùng một khoảng
(musicmixer.cpp `keepsUp`, musicBed.ts `playsThrough`, StreamPace.kt `playsThrough`). Một bản chép tay con số là cùng một mạng mà nhạc vào sớm / muộn
khác nhau giữa các máy, nên test này hỏng khi một nền tảng không đọc từ file (Qt qua CMakeLists.txt -> ABOOK_MIX_*, web import, Android MusicMix).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIX = ROOT / "abook" / "webui" / "assets" / "music_mix.json"
CMAKE = ROOT / "desktop_qt" / "CMakeLists.txt"
QT = ROOT / "desktop_qt" / "src" / "musicmixer.cpp"
QT_LOGIC = ROOT / "desktop_qt" / "src" / "musiclogic.h"
WEB = ROOT / "ui" / "src" / "listen" / "musicBed.ts"
PHONE = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player"

# khoá json -> (hằng Qt hay None khi Qt không dùng, hằng web, thuộc tính MusicMix của Android)
KEYS = {
    "underrunRateWindowSeconds": ("RATE_WINDOW_S", "DOWNLOAD_WINDOW_SECONDS", "underrunRateWindowMs"),
    "underrunBurstSeconds": ("BURST_S", "DOWNLOAD_BURST_SECONDS", "underrunBurstMs"),
    "underrunMargin": ("DOWNLOAD_MARGIN", "DOWNLOAD_MARGIN", "underrunMargin"),
    "underrunLeadSeconds": ("DECODE_LEAD_S", "DOWNLOAD_LEAD_SECONDS", "underrunLeadMs"),
    "underrunFadeSeconds": ("UNDERRUN_FADE_S", "UNDERRUN_FADE_SECONDS", "underrunFadeMs"),
    # Qt canh vòng PCM chỉ khi bộ giải mã đã tới mép tải: lúc ấy vòng = phần đã tải trước con trỏ, cùng đại lượng web / điện thoại canh.
    "underrunLowSeconds": ("UNDERRUN_LOW_S", "UNDERRUN_LOW_SECONDS", "underrunLowMs"),
}


def macro(key: str) -> str:
    return "ABOOK_MIX_" + re.sub(r"(?<!^)(?=[A-Z])", "_", key).upper()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_mix_file_carries_every_gate_constant():
    values = json.loads(read(MIX))
    for key in KEYS:
        assert isinstance(values[key], (int, float)) and not isinstance(values[key], bool) and values[key] > 0, key


@pytest.mark.parametrize("key", sorted(KEYS))
def test_qt_compiles_the_constant_from_the_mix_file(key):
    name = KEYS[key][0]
    if name is None:
        return
    pairs = re.search(r"foreach\(pair ([^)]*)\)", read(CMAKE)).group(1).split()
    assert f"{key}:{macro(key)[len('ABOOK_MIX_'):]}" in pairs, f"CMakeLists.txt không sinh {macro(key)} từ {key}"
    found = re.search(rf"\bconstexpr double {name} = (.+?);", read(QT))
    assert found, f"musicmixer.cpp: không thấy {name}"
    assert found.group(1).strip() == f"double({macro(key)})", f"musicmixer.cpp chép tay {name} = {found.group(1)}"


@pytest.mark.parametrize("key", sorted(KEYS))
def test_web_reads_the_constant_from_the_mix_file(key):
    name = KEYS[key][1]
    found = re.search(rf"\bconst {name} = (.+?);", read(WEB))
    assert found, f"musicBed.ts: không thấy {name}"
    assert found.group(1).strip() == f"mix.{key}", f"musicBed.ts chép tay {name} = {found.group(1)}"


@pytest.mark.parametrize("key", sorted(KEYS))
def test_the_phone_reads_the_constant_from_the_mix_file(key):
    name = KEYS[key][2]
    reads = f'millis(json, "{key}")' if name.endswith("Ms") else f'json.getDouble("{key}")'
    assert f"val {name} = {reads}" in read(PHONE / "MusicMix.kt"), f"MusicMix.kt không đọc {key} vào {name}"


def test_the_phone_gate_keeps_no_copy_of_the_numbers():
    pace = read(PHONE / "StreamPace.kt")
    # Chỉ BUFFER_MS (đệm của ExoPlayer, riêng điện thoại) được là hằng trong code.
    assert re.findall(r"const val (\w+)", pace) == ["BUFFER_MS"], re.findall(r"const val (\w+)", pace)
    for name in ("underrunRateWindowMs", "underrunBurstMs", "underrunMargin", "underrunLeadMs"):
        assert f"mix.{name}" in pace, f"StreamPace.kt không dùng mix.{name}"
    bed = read(PHONE / "MusicBed.kt")
    # Mờ ra khi hụt và mờ vào lại: cả hai nhịp đều theo underrunFadeMs, không nhịp nào chia cho một con số chép tay.
    # Phần đệm trước khi vào (underrunLeadMs) đi qua StreamPace (ở trên) và qua ngưỡng không chớp underrunMinEntryMs.
    for name, uses in (("underrunFadeMs", 2), ("underrunLowMs", 1), ("underrunMinEntryMs", 1)):
        assert bed.count(f"MusicCues.mix.{name}") >= uses, f"MusicBed.kt dùng MusicCues.mix.{name} ít hơn {uses} chỗ"
    assert not re.search(r"STEP_MS / \d", bed), re.findall(r".*STEP_MS / \d.*", bed)


def test_all_three_derive_the_no_blip_threshold_from_the_same_constants():
    # Lần vào (cả vào lại sau hụt) phải còn tới chỗ thôi kêu ít nhất lead + low + mờ vào + mờ ra: cùng công thức trên các hằng đã đọc từ file,
    # không con số riêng nào (Lead 02-11: luật đồng nhất giữa nền tảng; trước đó Qt chép tay low = 0,5 nên ngưỡng 3,1 s thay vì 3,6 s).
    assert "constexpr double MIN_ENTRY_S = DECODE_LEAD_S + UNDERRUN_LOW_S + 2 * UNDERRUN_FADE_S;" in read(QT)
    assert "const MIN_ENTRY_SECONDS = DOWNLOAD_LEAD_SECONDS + UNDERRUN_LOW_SECONDS + 2 * UNDERRUN_FADE_SECONDS;" in read(WEB)
    assert "val underrunMinEntryMs = underrunLeadMs + underrunLowMs + 2 * underrunFadeMs" in read(PHONE / "MusicMix.kt")
    assert "UNDERRUN_RESUME_S" not in read(QT), "Qt vào lại theo một mức riêng, không phải UNDERRUN_LOW_S như web / điện thoại"


def test_all_three_measure_the_horizon_to_where_the_track_stops_sounding():
    # Chân trời = chỗ bài thôi kêu (playEnd), không phải hết bài: bài 863 s mà mốc dùng 342 s (U30F 02-11).
    assert "inline double playEnd(" in read(QT_LOGIC) and "setPlayUntil(" in read(ROOT / "desktop_qt" / "src" / "musicbed.cpp")
    assert "export function playEnd(" in read(WEB) and "playEnd(this.cues, playing.cue)" in read(WEB)
    assert "fun playEnd(" in read(PHONE / "MusicCues.kt") and "MusicCues.playEnd(cues, it)" in read(PHONE / "MusicBed.kt")
