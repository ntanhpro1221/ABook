"""Bộ ví dụ DÙNG CHUNG cho lớp sửa của người nghe (webui/book_edits.py, docs/EDITING.md): pytest và test JVM của app Android
(BookEditsTest.kt, LocalStudioTest.kt) cùng đọc `tests/fixtures/book_edits/` - hai bản cài (Python, Kotlin) phải ra ĐÚNG
những file này.

    fixtures/book_edits/base/             một cuốn đã nhập (thư mục như `bookfile.extract` giải ra): hai chương, ba mốc nhạc,
                                          hai nhân vật (một người nhà làm sách đã đổi tên), bìa, câu mẫu
    fixtures/book_edits/series/book.json  cả bộ hai phần (phiên bản 3): chỉ phần mô tả, cho tên các phần và mã chương chung
    fixtures/book_edits/edits/<ca>.json   phần sửa hợp lệ (cùng `edits/<ca>/edits/cover.jpg` khi có bìa sửa)
    fixtures/book_edits/invalid/<ca>.json phần sửa phải bị từ chối
    fixtures/book_edits/expected/<ca>.json  {manifest, cast, scripts{mã chương: script}} người nghe thấy khi áp `<ca>` lên base
    fixtures/book_edits/merge/<ca>.json   {local, incoming, merged, report}: hợp hai lớp sửa khi nhập lại
    fixtures/book_edits/contract/<ca>.json chuỗi yêu cầu / lời đáp của máy chủ Python cho từng đường "áp ngay" và đường ý muốn
                                          chờ Studio - LocalStudio.kt phải đáp y hệt (trừ trường dễ đổi: `volatile`). Trong thân
                                          yêu cầu, chuỗi "$requestedAt#N" là `requestedAt` của lời đáp bước N (để rút đúng lần bấm)
    fixtures/book_edits/written/python_v4.abook, kotlin_v4.abook   file phiên bản 4 do từng bên ghi, bên kia phải mở được
                                          (python_v4_pins.abook / kotlin_v4_pins.abook: thêm bài nhạc người nghe đã ghim)
    fixtures/book_edits/written/python_workshop.abookproj, python_pending.abookproj   file dự án phiên bản 3 do Python ghi: một
                                          dự án có xưởng (bí danh, views/, sources/) và một cuốn "chờ dựng xưởng" mang lớp sửa;
                                          kotlin_workshop.abookproj / kotlin_pending.abookproj là bản Kotlin ghi lại từ chúng
    fixtures/book_edits/track/tone.wav    một bài nhạc nhỏ ("Nhạc của tôi") cho các ca ghim bài: nhập vào kho nhạc của máy rồi ghim
    fixtures/book_edits/readings/speech.json  cách đọc riêng (`readings`) khi đọc to: cùng đoạn chữ -> cùng chữ đem đọc (giọng trên máy:
                                          `vieneu.spoken_tokens`; giọng khác: `readings.spoken_text`) và cùng khoá bộ đệm clip ở hai bên

Sinh lại (chỉ khi cố ý đổi hành vi hay giao ước):  runtime/.venv/Scripts/python.exe -m tests.book_edits_fixtures
(thêm --rebuild-base để dựng lại cả `base`; không thì giữ nguyên nó và chỉ sinh lại các file mong đợi)
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import shutil
import sqlite3
import struct
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures" / "book_edits"
BASE = FIXTURES / "base"

def tone_wav() -> bytes:
    """Bài nhạc mẫu: một giây sin 440 Hz, một kênh, 8 kHz, 16 bit - đủ nhỏ để nằm trong bộ ví dụ, cùng byte mỗi lần."""
    import math

    out = io.BytesIO()
    with wave.open(out, "wb") as sink:
        sink.setnchannels(1)
        sink.setsampwidth(2)
        sink.setframerate(8000)
        sink.writeframes(b"".join(struct.pack("<h", round(3000 * math.sin(2 * math.pi * 440 * n / 8000))) for n in range(8000)))
    return out.getvalue()


TRACK_SHA = hashlib.sha1(tone_wav()).hexdigest()
TRACK_LINK = f"local:{TRACK_SHA}"
TRACK_INFO = {"ext": "wav", "title": "Bài của tôi", "creator": "Tôi", "duration": 1.0, "lufs": -23.0}
OTHER_SHA = "0123456789abcdef0123456789abcdef01234567"
PINS = {"pins": {"1:0": TRACK_LINK}, "tracks": {TRACK_SHA: TRACK_INFO}}

# Mốc nhạc của base (xem tests/test_bookfile_music._plan): chương 1, hai bài, mốc 0-60 s (hai đoạn liền cùng bài gộp) và 60-90 s.
CASES: dict[str, dict[str, Any]] = {
    "title_only": {"title": "Tên mới của tôi"},
    "names": {"characters": {"LUCIEN": "Lu-xi-en", "HEIDI": "Heidi"}},
    "chapters": {"chapters": {"1": {"title": "Chương Một", "subtitle": ""}, "2": {"subtitle": "Hết rồi"}}},
    "music_level_and_silence": {"music": {"levelDb": -24.0, "silenced": ["1:60000"]}},
    "music_off": {"music": {"enabled": False}},
    "music_pin": {"music": dict(PINS)},
    "music_pin_level_silence": {"music": {"levelDb": -24.0, "silenced": ["1:60000"], **PINS}},
    "music_pin_two_cues": {"music": {"pins": {"1:0": TRACK_LINK, "1:60000": TRACK_LINK}, "tracks": {TRACK_SHA: TRACK_INFO}}},
    "music_pin_music_off": {"music": {"enabled": False, **PINS}},
    "music_playlist": {"music": {"playlist": "fantasy_calm"}},
    "cover_removed": {"cover": None},
    "skip_lines": {"skip": {"1": ["Dịch: Nhóm Thử", "Biên tập: Ai Đó"], "2": ["Trans: Tôi"]}},
    "readings": {"readings": {"Lucien": "Lu-xi-en", "Hailkes": "Hên khơ", "Tôkyô": "Tô ky ô"}},
    "cover_set": {"cover": {"color": "#aa5522", "width": 96, "height": 128, "version": 1759400000}},
    "everything": {
        "title": "Sách của tôi",
        "cover": {"color": "#aa5522", "width": 96, "height": 128, "version": 1759400000},
        "characters": {"LUCIEN": "Lu-xi-en"},
        "chapters": {"1": {"title": "Chương Một"}, "2": {"title": "Chương Hai", "subtitle": ""}},
        "music": {"enabled": True, "levelDb": -12.0, "silenced": ["1:0"]},
    },
}

# Các câu của base (chương 2 chưa thu; mã ổn định của dự án mẫu đều mở bằng c1_ nên tra câu phải duyệt cả hai chương).
HEADING = ("c1_s0001_aa6eb2", "aa6eb21ef4206a0795ca5793883e40eb49b958ae12f60f879c0806d1f8138ab0")
NARRATION = ("c1_s0002_c58b67", "c58b6788498e1756635f89b55a9906af2fa37a0d3ffbc49083eb56c5c5c5483c")
LUCIEN_LINE = ("c1_s0003_fa1fe2", "fa1fe25f1922819e9fd94d48eeef9fddcaeb06be1653b73d618873e572498ea5")
HEIDI_LINE = ("c1_s0006_34534a", "34534ad5d25c0cc74935800b021272b15ac53406accd068020698cea262c6ec0")
SECOND_CHAPTER = ("c1_s0005_dd2e97", "dd2e97ef858a191e7163818f82551c5462dd647c3e2836e5e261a241552d1242")
WISHES = {
    "pronunciations": {"hailkes": {"requested_at": 1759400001.5, "spoken_form": "Hên-khơ", "surface": "Hailkes"}},
    "speakers": {LUCIEN_LINE[0]: {"requested_at": 1759400002.0, "speaker": "HEIDI", "text_sha256": LUCIEN_LINE[1]}},
    "lines": {HEIDI_LINE[0]: {"emotion": "tender", "intensity": 1, "kind": "", "requested_at": 1759400003.25,
                              "spoken": "Chào anh nhé.", "text_sha256": HEIDI_LINE[1]}},
    "voices": {"HEIDI": {"avoid": "", "gender": "male", "preset": "", "requested_at": 1759400004.0,
                         "replaced": {"avoid": "", "gender": "female", "preset": "", "requested_at": 1759400000.5}}},
    "retakes": {NARRATION[0]: {"requested_at": 1759400005.0, "text_sha256": NARRATION[1]},
                SECOND_CHAPTER[0]: {"requested_at": 1759400005.0, "text_sha256": SECOND_CHAPTER[1]}},
    "aliases": [{"alias": "Hây-đi", "at": 1759400002.0, "person": "LUCIEN"}],
}
CASES["wishes"] = {"wishes": WISHES}
CASES["wishes_beside_edits"] = {
    "title": "Sách của tôi",
    "characters": {"LUCIEN": "Lu-xi-en"},
    "wishes": {"voices": {"LUCIEN": {"avoid": "preset_a", "gender": "", "preset": "Thiện Minh", "requested_at": 1759400004.0}},
               "speakers": {HEIDI_LINE[0]: {"new": {"gender": "female"}, "requested_at": 1759400006.0, "speaker": "Tiểu Mai",
                                            "text_sha256": HEIDI_LINE[1]}}},
}
HEAD = {"format": "abook-edits", "version": 1}


def _wish(section: str, entries: Any) -> dict[str, Any]:
    return {**HEAD, "wishes": {section: entries}}


INVALID: dict[str, Any] = {
    "not_an_object": [],
    "unknown_key": {**HEAD, "pins": []},
    "wrong_format": {"format": "abook", "version": 1},
    "newer_version": {"format": "abook-edits", "version": 2},
    "title_empty": {**HEAD, "title": ""},
    "title_too_long": {**HEAD, "title": "a" * 161},
    "title_not_text": {**HEAD, "title": 7},
    "title_control_character": {**HEAD, "title": "Tên\u0007sách"},
    "title_double_space": {**HEAD, "title": "Tên  sách"},
    "title_padded": {**HEAD, "title": " Tên sách"},
    "title_tab": {**HEAD, "title": "Tên\tsách"},
    "character_name_too_long": {**HEAD, "characters": {"LUCIEN": "b" * 81}},
    "character_name_empty": {**HEAD, "characters": {"LUCIEN": ""}},
    "characters_not_an_object": {**HEAD, "characters": ["LUCIEN"]},
    "chapter_id_not_a_number": {**HEAD, "chapters": {"x": {"title": "A"}}},
    "chapter_entry_empty": {**HEAD, "chapters": {"1": {}}},
    "chapter_entry_unknown_field": {**HEAD, "chapters": {"1": {"title": "A", "color": "red"}}},
    "chapter_title_empty": {**HEAD, "chapters": {"1": {"title": ""}}},
    "level_too_loud": {**HEAD, "music": {"levelDb": -3}},
    "level_too_quiet": {**HEAD, "music": {"levelDb": -41}},
    "level_not_a_number": {**HEAD, "music": {"levelDb": "-20"}},
    "enabled_not_a_boolean": {**HEAD, "music": {"enabled": 1}},
    "music_unknown_field": {**HEAD, "music": {"fade": 2}},
    "pins_bad_key": {**HEAD, "music": {"pins": {"x": TRACK_LINK}, "tracks": {TRACK_SHA: TRACK_INFO}}},
    "pins_not_an_object": {**HEAD, "music": {"pins": [TRACK_LINK], "tracks": {TRACK_SHA: TRACK_INFO}}},
    "pins_not_a_local_link": {**HEAD, "music": {"pins": {"1:0": "https://x/y.mp3"}, "tracks": {TRACK_SHA: TRACK_INFO}}},
    "pins_link_not_a_sha": {**HEAD, "music": {"pins": {"1:0": "local:ABC"}, "tracks": {}}},
    "pins_without_tracks": {**HEAD, "music": {"pins": {"1:0": TRACK_LINK}}},
    "tracks_without_pins": {**HEAD, "music": {"tracks": {TRACK_SHA: TRACK_INFO}}},
    "tracks_one_unused": {**HEAD, "music": {**PINS, "tracks": {TRACK_SHA: TRACK_INFO, OTHER_SHA: TRACK_INFO}}},
    "track_bad_extension": {**HEAD, "music": {**PINS, "tracks": {TRACK_SHA: {**TRACK_INFO, "ext": "exe"}}}},
    "track_unknown_field": {**HEAD, "music": {**PINS, "tracks": {TRACK_SHA: {**TRACK_INFO, "path": "/sdcard/x.wav"}}}},
    "track_title_padded": {**HEAD, "music": {**PINS, "tracks": {TRACK_SHA: {**TRACK_INFO, "title": " Bài"}}}},
    "track_title_empty": {**HEAD, "music": {**PINS, "tracks": {TRACK_SHA: {**TRACK_INFO, "title": ""}}}},
    "track_duration_zero": {**HEAD, "music": {**PINS, "tracks": {TRACK_SHA: {**TRACK_INFO, "duration": 0}}}},
    "track_loudness_too_high": {**HEAD, "music": {**PINS, "tracks": {TRACK_SHA: {**TRACK_INFO, "lufs": 21}}}},
    "track_loudness_a_string": {**HEAD, "music": {**PINS, "tracks": {TRACK_SHA: {**TRACK_INFO, "lufs": "-23"}}}},
    "music_empty": {**HEAD, "music": {}},
    "playlist_bad_id": {**HEAD, "music": {"playlist": "Kỳ ảo"}},
    "playlist_empty": {**HEAD, "music": {"playlist": ""}},
    "playlist_not_text": {**HEAD, "music": {"playlist": 3}},
    "silenced_bad_key": {**HEAD, "music": {"silenced": ["abc"]}},
    "silenced_duplicate": {**HEAD, "music": {"silenced": ["1:0", "1:0"]}},
    "cover_bad_color": {**HEAD, "cover": {"color": "red", "width": 1, "height": 1, "version": 1}},
    "cover_negative_size": {**HEAD, "cover": {"color": "", "width": -1, "height": 1, "version": 1}},
    "cover_unknown_field": {**HEAD, "cover": {"color": "", "width": 1, "height": 1, "version": 1, "url": "x"}},
    "wishes_not_an_object": {**HEAD, "wishes": []},
    "wishes_empty": {**HEAD, "wishes": {}},
    "wishes_unknown_section": {**HEAD, "wishes": {"dreams": {}}},
    "wishes_section_empty": _wish("retakes", {}),
    "wishes_section_not_an_object": _wish("retakes", [NARRATION[0]]),
    "wish_bad_line_id": _wish("retakes", {"c1 s2": {"requested_at": 1.5, "text_sha256": NARRATION[1]}}),
    "wish_bad_hash": _wish("retakes", {NARRATION[0]: {"requested_at": 1.5, "text_sha256": "abc"}}),
    "wish_unknown_field": _wish("retakes", {NARRATION[0]: {"requested_at": 1.5, "text_sha256": NARRATION[1], "who": "x"}}),
    "wish_time_missing": _wish("retakes", {NARRATION[0]: {"text_sha256": NARRATION[1]}}),
    "wish_time_negative": _wish("retakes", {NARRATION[0]: {"requested_at": -1, "text_sha256": NARRATION[1]}}),
    "wish_time_a_boolean": _wish("retakes", {NARRATION[0]: {"requested_at": True, "text_sha256": NARRATION[1]}}),
    "wish_retake_replaced": _wish("retakes", {NARRATION[0]: {"requested_at": 1.5, "text_sha256": NARRATION[1],
                                                           "replaced": {"requested_at": 1.0, "text_sha256": NARRATION[1]}}}),
    "wish_replaced_twice": _wish("voices", {"HEIDI": {"avoid": "", "gender": "male", "preset": "", "requested_at": 3.0,
                                                    "replaced": {"avoid": "", "gender": "male", "preset": "", "requested_at": 2.0,
                                                                 "replaced": {"avoid": "", "gender": "", "preset": "", "requested_at": 1.0}}}}),
    "wish_pronunciation_two_words": _wish("pronunciations", {"hai kes": {"requested_at": 1.5, "spoken_form": "Hên-khơ", "surface": "Hai kes"}}),
    "wish_pronunciation_padded": _wish("pronunciations", {"hailkes": {"requested_at": 1.5, "spoken_form": " Hên-khơ", "surface": "Hailkes"}}),
    "wish_pronunciation_empty_reading": _wish("pronunciations", {"hailkes": {"requested_at": 1.5, "spoken_form": "", "surface": "Hailkes"}}),
    "wish_speaker_bad_new_gender": _wish("speakers", {LUCIEN_LINE[0]: {"new": {"gender": "robot"}, "requested_at": 1.5, "speaker": "A",
                                                                      "text_sha256": LUCIEN_LINE[1]}}),
    "wish_speaker_new_has_extra": _wish("speakers", {LUCIEN_LINE[0]: {"new": {"gender": "male", "age": "old"}, "requested_at": 1.5,
                                                                    "speaker": "A", "text_sha256": LUCIEN_LINE[1]}}),
    "wish_line_bad_kind": _wish("lines", {HEIDI_LINE[0]: {"emotion": "", "intensity": None, "kind": "shout", "requested_at": 1.5,
                                                          "text_sha256": HEIDI_LINE[1]}}),
    "wish_line_bad_emotion": _wish("lines", {HEIDI_LINE[0]: {"emotion": "bored", "intensity": None, "kind": "", "requested_at": 1.5,
                                                             "text_sha256": HEIDI_LINE[1]}}),
    "wish_line_intensity_too_high": _wish("lines", {HEIDI_LINE[0]: {"emotion": "", "intensity": 4, "kind": "", "requested_at": 1.5,
                                                                    "text_sha256": HEIDI_LINE[1]}}),
    "wish_line_intensity_a_float": _wish("lines", {HEIDI_LINE[0]: {"emotion": "", "intensity": 1.5, "kind": "", "requested_at": 1.5,
                                                                   "text_sha256": HEIDI_LINE[1]}}),
    "wish_line_spoken_double_space": _wish("lines", {HEIDI_LINE[0]: {"emotion": "", "intensity": None, "kind": "", "requested_at": 1.5,
                                                                     "spoken": "Chào  anh", "text_sha256": HEIDI_LINE[1]}}),
    "wish_line_spoken_too_long": _wish("lines", {HEIDI_LINE[0]: {"emotion": "", "intensity": None, "kind": "", "requested_at": 1.5,
                                                                 "spoken": "a" * 2001, "text_sha256": HEIDI_LINE[1]}}),
    "wish_voice_bad_gender": _wish("voices", {"HEIDI": {"avoid": "", "gender": "robot", "preset": "", "requested_at": 1.5}}),
    "wish_voice_missing_field": _wish("voices", {"HEIDI": {"gender": "male", "preset": "", "requested_at": 1.5}}),
    "wish_alias_duplicate": _wish("aliases", [{"alias": "A", "at": 1.5, "person": "B"}, {"alias": "A", "at": 2.5, "person": "C"}]),
    "wish_alias_missing_field": _wish("aliases", [{"alias": "A", "person": "B"}]),
    "wish_alias_not_a_list": _wish("aliases", {"A": "B"}),
    "skip_not_a_list": {**HEAD, "skip": {"1": "Dịch: A"}},
    "skip_empty_list": {**HEAD, "skip": {"1": []}},
    "skip_line_empty": {**HEAD, "skip": {"1": [""]}},
    "skip_line_padded": {**HEAD, "skip": {"1": [" Dịch: A"]}},
    "skip_line_twice": {**HEAD, "skip": {"1": ["Dịch: A", "Dịch: A"]}},
    "skip_line_too_long": {**HEAD, "skip": {"1": ["a" * 301]}},
    "skip_bad_chapter": {**HEAD, "skip": {"một": ["Dịch: A"]}},
    "readings_not_an_object": {**HEAD, "readings": [["Haruto", "Ha-ru-tô"]]},
    "readings_empty": {**HEAD, "readings": {}},
    "reading_seven_words": {**HEAD, "readings": {"a b c d e f g": "Hên-khơ"}},
    "reading_phrase_with_punctuation": {**HEAD, "readings": {"Hạ, Vy": "Hà Vi"}},
    "reading_phrase_double_space": {**HEAD, "readings": {"Hạ  Vy": "Hà Vi"}},
    "reading_word_with_punctuation": {**HEAD, "readings": {"Haruto,": "Ha-ru-tô"}},
    "reading_word_not_nfc": {**HEAD, "readings": {"To\u0302kyo\u0302": "Tô-ky-ô"}},
    "reading_word_too_long": {**HEAD, "readings": {"a" * 81: "a"}},
    "reading_spoken_empty": {**HEAD, "readings": {"Haruto": ""}},
    "reading_spoken_padded": {**HEAD, "readings": {"Haruto": " Ha-ru-tô"}},
    "reading_spoken_double_space": {**HEAD, "readings": {"Haruto": "Ha  ru tô"}},
    "reading_spoken_too_long": {**HEAD, "readings": {"Haruto": "a" * 201}},
    "reading_spoken_not_text": {**HEAD, "readings": {"Haruto": 3}},
    "reading_same_as_word": {**HEAD, "readings": {"Haruto": "Haruto"}},
}
INVALID_RAW = {  # văn bản thô: không phải JSON hợp lệ hay chứa hằng số JSON không chuẩn
    "not_json": "{",
    "nan_level": '{"format": "abook-edits", "version": 1, "music": {"levelDb": NaN}}',
}
MERGE_CASES = {
    "disjoint": ({**HEAD, "title": "Của tôi"}, {**HEAD, "characters": {"LUCIEN": "Lu-xi-en"}}),
    "conflict_local_wins": (
        {**HEAD, "title": "Của tôi", "characters": {"LUCIEN": "A"}, "chapters": {"1": {"title": "X"}}},
        {**HEAD, "title": "Của bạn", "characters": {"LUCIEN": "B"}, "chapters": {"1": {"title": "Y", "subtitle": "Z"}}},
    ),
    "silence_is_a_union": (
        {**HEAD, "music": {"levelDb": -20.0, "silenced": ["1:0"]}},
        {**HEAD, "music": {"enabled": False, "levelDb": -30.0, "silenced": ["1:60000"]}},
    ),
    "pins_local_wins_and_unused_tracks_go": (
        {**HEAD, "music": {"pins": {"1:0": TRACK_LINK}, "tracks": {TRACK_SHA: TRACK_INFO}}},
        {**HEAD, "music": {"pins": {"1:0": f"local:{OTHER_SHA}", "1:60000": f"local:{OTHER_SHA}"},
                           "tracks": {OTHER_SHA: {**TRACK_INFO, "title": "Bài khác"}}}},
    ),
    "pins_next_to_the_levels": (
        {**HEAD, "music": {"levelDb": -20.0}},
        {**HEAD, "music": {"silenced": ["1:0"], **PINS}},
    ),
    "skip_is_a_union": (
        {**HEAD, "skip": {"1": ["Dịch: A"]}},
        {**HEAD, "skip": {"1": ["Biên tập: B", "Dịch: A"], "2": ["Trans: C"]}},
    ),
    "playlist_local_wins": (
        {**HEAD, "music": {"playlist": "fantasy_calm"}},
        {**HEAD, "music": {"playlist": "mine", "levelDb": -24.0}},
    ),
    "readings_local_wins": (
        {**HEAD, "readings": {"Haruto": "Ha-ru-tô", "Kate": "Kết"}},
        {**HEAD, "readings": {"Haruto": "Ha-ru-to", "Lucien": "Lu-xi-en"}},
    ),
    "cover_follows_the_winner": (
        {**HEAD, "title": "Của tôi"},
        {**HEAD, "cover": {"color": "#112233", "width": 10, "height": 10, "version": 5}},
    ),
    "wishes_are_a_union": (
        {**HEAD, "wishes": {"voices": {"HEIDI": {"avoid": "", "gender": "male", "preset": "", "requested_at": 1759400004.0}}}},
        {**HEAD, "wishes": {"retakes": {NARRATION[0]: {"requested_at": 1759400005.0, "text_sha256": NARRATION[1]}},
                            "pronunciations": {"hailkes": {"requested_at": 1759400001.5, "spoken_form": "Hên-khơ", "surface": "Hailkes"}}}},
    ),
    "wishes_conflict_local_wins": (
        {**HEAD, "title": "Của tôi",
         "wishes": {"voices": {"HEIDI": {"avoid": "", "gender": "male", "preset": "", "requested_at": 1759400004.0}},
                    "aliases": [{"alias": "Hây-đi", "at": 1759400004.0, "person": "LUCIEN"}]}},
        {**HEAD, "wishes": {"voices": {"HEIDI": {"avoid": "", "gender": "female", "preset": "", "requested_at": 1759400009.0}},
                            "speakers": {LUCIEN_LINE[0]: {"requested_at": 1759400002.0, "speaker": "HEIDI", "text_sha256": LUCIEN_LINE[1]}},
                            "aliases": [{"alias": "Hây-đi", "at": 1759400002.0, "person": "NOBODY"},
                                        {"alias": "Cô bé", "at": 1759400002.0, "person": "HEIDI"}]}},
    ),
    "wishes_next_to_other_edits": (
        {**HEAD, "characters": {"LUCIEN": "A"}},
        {**HEAD, "title": "Của bạn", "wishes": {"retakes": {NARRATION[0]: {"requested_at": 1759400005.0, "text_sha256": NARRATION[1]}}}},
    ),
}
# Chuỗi yêu cầu mỗi ca của hợp đồng máy chủ <-> LocalStudio (đường tính từ `/api/books/<mã>`). Ảnh bìa: `$cover` là data URL
# của ảnh nhỏ (xem `tiny_cover`). Trường dễ đổi giữa hai bản cài (màu chủ đạo, phiên bản bìa) không so.
VOLATILE = ["color", "version", "requestedAt"]
_LUCIEN = {"stableId": LUCIEN_LINE[0], "textSha256": LUCIEN_LINE[1]}
_HEIDI = {"stableId": HEIDI_LINE[0], "textSha256": HEIDI_LINE[1]}
_NARRATION = {"stableId": NARRATION[0], "textSha256": NARRATION[1]}
CONTRACT: dict[str, list[dict[str, Any]]] = {
    "title": [
        {"method": "PUT", "path": "/title", "body": {"title": "  Tên \t mới \n"}},
        {"method": "PUT", "path": "/title", "body": {"title": "   "}},
        {"method": "GET", "path": "/edits"},
        {"method": "PUT", "path": "/title", "body": {"title": "Sách thử · Tập 1"}},
        {"method": "GET", "path": "/edits"},
    ],
    "characters": [
        {"method": "POST", "path": "/characters/rename", "body": {"character": "LUCIEN", "name": "Lu-xi-en"}},
        {"method": "GET", "path": "/cast"},
        {"method": "GET", "path": "/chapters/1/script"},
        {"method": "POST", "path": "/characters/rename", "body": {"character": "HEIDI", "name": ""}},
        {"method": "POST", "path": "/characters/rename", "body": {"character": "LUCIEN", "name": ""}},
        {"method": "POST", "path": "/characters/rename", "body": {"character": "NOBODY", "name": "x"}},
        {"method": "POST", "path": "/characters/rename", "body": {"character": "NARRATOR", "name": "x"}},
        {"method": "GET", "path": "/edits"},
    ],
    "chapters": [
        {"method": "PUT", "path": "/chapters/1/title", "body": {"title": "Chương Một", "subtitle": ""}},
        {"method": "PUT", "path": "/chapters/2/title", "body": {"subtitle": "Hết rồi"}},
        {"method": "GET", "path": "/chapters/1/script"},
        {"method": "GET", "path": "/cast"},
        {"method": "PUT", "path": "/chapters/9/title", "body": {"title": "Không có"}},
        {"method": "PUT", "path": "/chapters/1/title", "body": {"revert": True}},
        {"method": "GET", "path": "/edits"},
    ],
    "music": [
        {"method": "GET", "path": "/music"},
        {"method": "PUT", "path": "/music", "body": {"levelDb": -24}},
        {"method": "PUT", "path": "/music", "body": {"silence": {"1:60000": True}}},
        {"method": "PUT", "path": "/music", "body": {"silence": {"1:12345": True}}},
        {"method": "PUT", "path": "/music", "body": {"levelDb": -3}},
        {"method": "PUT", "path": "/music", "body": {"pins": {"1:1": "https://x/y.mp3"}}},
        {"method": "PUT", "path": "/music", "body": {"enabled": False}},
        {"method": "PUT", "path": "/music", "body": {"enabled": True, "levelDb": -20, "silence": {"1:60000": False}}},
        {"method": "GET", "path": "/edits"},
    ],
    # Danh sách nhạc nền của "Nghe ngay" (music_playlist.py): chọn, đổi, chọn sai, tắt.
    "music_playlist": [
        {"method": "PUT", "path": "/music", "body": {"playlist": "fantasy_calm"}},
        {"method": "GET", "path": "/music"},
        {"method": "PUT", "path": "/music", "body": {"playlist": "mine"}},
        {"method": "PUT", "path": "/music", "body": {"playlist": "Kỳ ảo"}},
        {"method": "PUT", "path": "/music", "body": {"playlist": 3}},
        {"method": "GET", "path": "/edits"},
        {"method": "PUT", "path": "/music", "body": {"playlist": None}},
        {"method": "GET", "path": "/edits"},
    ],
    # "Nhạc của tôi" trên sách không có xưởng: bước {"import": tên} nhập file mẫu vào kho nhạc của máy (bên Kotlin: MusicStore).
    "music_pins": [
        {"method": "GET", "path": "/music/scenes/1:0/alternatives"},
        {"import": "tone.wav"},
        {"method": "GET", "path": "/music/scenes/1:0/alternatives"},
        {"method": "GET", "path": "/music/scenes/9:9/alternatives"},
        {"method": "PUT", "path": "/music", "body": {"pins": {"1:0": TRACK_LINK}}},
        {"method": "PUT", "path": "/music", "body": {"pins": {"1:0": TRACK_LINK}}},
        {"method": "GET", "path": "/edits"},
        {"method": "GET", "path": "/music/scenes/1:0/alternatives"},
        {"method": "GET", "path": "/music/scenes/1:60000/alternatives"},
        {"method": "PUT", "path": "/music", "body": {"pins": {"1:60000": f"local:{OTHER_SHA}"}}},
        {"method": "PUT", "path": "/music", "body": {"pins": {"1:60000": "https://x/y.mp3"}}},
        {"method": "PUT", "path": "/music", "body": {"pins": {"7:7": TRACK_LINK}}},
        {"method": "PUT", "path": "/music", "body": {"pins": "tone"}},
        {"method": "PUT", "path": "/music", "body": {"levelDb": -24, "silence": {"1:60000": True}}},
        {"method": "PUT", "path": "/music", "body": {"pins": {"1:60000": TRACK_LINK}}},
        {"method": "GET", "path": "/edits"},
        {"method": "PUT", "path": "/music", "body": {"pins": {"1:0": None}}},
        {"method": "PUT", "path": "/music", "body": {"pins": {"1:60000": None}}},
        {"method": "GET", "path": "/edits"},
        {"method": "PUT", "path": "/music", "body": {"pins": {"1:0": TRACK_LINK}}},
        {"method": "DELETE", "path": "/edits"},
        {"method": "GET", "path": "/music"},
        {"method": "GET", "path": "/edits"},
    ],
    "cover": [
        {"method": "PUT", "path": "/cover", "body": {"image": "$cover"}},
        {"method": "PUT", "path": "/cover", "body": {"image": "data:text/plain;base64,AAAA"}},
        {"method": "DELETE", "path": "/cover"},
        {"method": "GET", "path": "/edits"},
    ],
    "revert": [
        {"method": "PUT", "path": "/title", "body": {"title": "A"}},
        {"method": "POST", "path": "/characters/rename", "body": {"character": "LUCIEN", "name": "B"}},
        {"method": "GET", "path": "/edits"},
        {"method": "DELETE", "path": "/edits"},
        {"method": "GET", "path": "/edits"},
    ],
    # Ý muốn chờ Studio (docs/EDITING.md, P2a): ghi vào lớp sửa, liệt kê, rút - không bao giờ áp vào chữ hay audio.
    "wishes_pronunciation": [
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Hailkes", "spokenForm": "Hên-khơ", "everywhere": True}},
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Hai kes", "spokenForm": "Hên-khơ"}},
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Hailkes", "spokenForm": "Xă-mon"}},
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Hailkes", "spokenForm": "Hên-kơ"}},
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Hailkes", "spokenForm": ""}},
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Hailkes", "spokenForm": "Hên-xơ"}},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "GET", "path": "/edits"},
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Hailkes", "withdraw": True, "requestedAt": "$requestedAt#6"}},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Hailkes", "withdraw": True, "requestedAt": "$requestedAt#6"}},
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Hailkes", "withdraw": True, "requestedAt": "$requestedAt#1"}},
        {"method": "GET", "path": "/edits"},
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Hailkes", "withdraw": True}},
    ],
    "wishes_speaker": [
        {"method": "POST", "path": "/speaker", "body": {**_LUCIEN, "speaker": "HEIDI"}},
        {"method": "POST", "path": "/speaker", "body": {**_LUCIEN, "speaker": "NOBODY"}},
        {"method": "POST", "path": "/speaker", "body": {**_NARRATION, "speaker": "HEIDI"}},
        {"method": "POST", "path": "/speaker", "body": {"stableId": "c1_s9999_aaaaaa", "textSha256": LUCIEN_LINE[1], "speaker": "HEIDI"}},
        {"method": "POST", "path": "/speaker", "body": {**_LUCIEN, "textSha256": HEIDI_LINE[1], "speaker": "HEIDI"}},
        {"method": "POST", "path": "/speaker", "body": {**_LUCIEN, "speaker": "Tiểu Mai", "newGender": "female", "alias": "Cô gái lạ"}},
        {"method": "POST", "path": "/speaker", "body": {**_LUCIEN, "speaker": "Tiểu Mai", "newGender": "robot"}},
        {"method": "POST", "path": "/speaker", "body": {**_LUCIEN, "speaker": "LUCIEN", "bracketRule": True}},
        {"method": "POST", "path": "/speaker", "body": {"lines": [_HEIDI, _LUCIEN], "speaker": "UNNAMED"}},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "GET", "path": "/edits"},
        {"method": "POST", "path": "/speaker", "body": {"withdraw": True, "lines": [_LUCIEN, _HEIDI], "requestedAt": "$requestedAt#9"}},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "POST", "path": "/speaker", "body": {"withdraw": True, "lines": [_LUCIEN], "requestedAt": "$requestedAt#8"}},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "POST", "path": "/speaker", "body": {"withdraw": True, "lines": [_LUCIEN], "requestedAt": "$requestedAt#6"}},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "DELETE", "path": "/edits"},
        {"method": "GET", "path": "/pending-changes"},
    ],
    "wishes_line": [
        {"method": "POST", "path": "/line", "body": {**_HEIDI, "emotion": "tender", "intensity": 1}},
        {"method": "POST", "path": "/line", "body": {**_HEIDI, "spoken": "Chào   anh nhé."}},
        {"method": "POST", "path": "/line", "body": {**_HEIDI, "kind": "shout"}},
        {"method": "POST", "path": "/line", "body": {**_HEIDI, "emotion": "bored"}},
        {"method": "POST", "path": "/line", "body": {**_HEIDI, "spoken": "!!!"}},
        {"method": "POST", "path": "/line", "body": {**_HEIDI, "intensity": 7}},
        {"method": "POST", "path": "/line", "body": {**_NARRATION, "kind": "dialogue", "speaker": "HEIDI"}},
        {"method": "POST", "path": "/line", "body": {**_NARRATION, "speaker": "LUCIEN"}},
        {"method": "POST", "path": "/line", "body": {**_NARRATION, "kind": "dialogue", "speaker": "NOBODY"}},
        {"method": "POST", "path": "/line", "body": dict(_HEIDI)},
        {"method": "POST", "path": "/line", "body": {"stableId": "c1_s9999_aaaaaa", "textSha256": HEIDI_LINE[1], "emotion": "sad"}},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "GET", "path": "/edits"},
        {"method": "POST", "path": "/line", "body": {**_HEIDI, "spoken": ""}},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "GET", "path": "/chapters/1/script"},
    ],
    "wishes_voice": [
        {"method": "POST", "path": "/voice", "body": {"character": "HEIDI", "gender": "male"}},
        {"method": "POST", "path": "/voice", "body": {"character": "HEIDI", "gender": "robot"}},
        {"method": "POST", "path": "/voice", "body": {"character": "NARRATOR", "gender": "male"}},
        {"method": "POST", "path": "/voice", "body": {"character": "NOBODY", "gender": "male"}},
        {"method": "POST", "path": "/voice", "body": {"character": "HEIDI"}},
        {"method": "POST", "path": "/voice", "body": {"character": "", "gender": "male"}},
        {"method": "GET", "path": "/cast"},
        {"method": "POST", "path": "/voice", "body": {"character": "heidi", "preset": "Thiện Minh", "avoid": "preset_a"}},
        {"method": "GET", "path": "/cast"},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "POST", "path": "/voice", "body": {"character": "HEIDI", "withdraw": True, "requestedAt": "$requestedAt#8"}},
        {"method": "GET", "path": "/cast"},
        {"method": "POST", "path": "/voice", "body": {"character": "HEIDI", "withdraw": True, "requestedAt": "$requestedAt#1"}},
        {"method": "GET", "path": "/edits"},
    ],
    "wishes_retake_and_merge": [
        {"method": "POST", "path": "/chapters/1/retake"},
        {"method": "POST", "path": "/chapters/9/retake"},
        {"method": "POST", "path": "/review", "body": {"verdict": "redo", **_LUCIEN, "chapterId": 1}},
        {"method": "POST", "path": "/review", "body": {"verdict": "bogus", **_LUCIEN}},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "POST", "path": "/characters/merge", "body": {"from": "HEIDI", "into": "LUCIEN"}},
        {"method": "POST", "path": "/characters/merge", "body": {"from": "LUCIEN", "into": "lucien"}},
        {"method": "POST", "path": "/characters/merge", "body": {"from": "NOBODY", "into": "LUCIEN"}},
        {"method": "POST", "path": "/characters/merge", "body": {"from": "HEIDI", "into": "NOBODY"}},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "GET", "path": "/edits"},
        {"method": "POST", "path": "/pending-changes/withdraw", "body": {"section": "speakers", "key": HEIDI_LINE[0], "keys": [HEIDI_LINE[0]], "requestedAt": "$requestedAt#6"}},
        {"method": "POST", "path": "/pending-changes/withdraw", "body": {"section": "retakes", "key": HEADING[0], "keys": [HEADING[0], NARRATION[0], HEIDI_LINE[0]], "requestedAt": "$requestedAt#1"}},
        {"method": "POST", "path": "/pending-changes/withdraw", "body": {"section": "retakes", "key": HEADING[0], "keys": [HEADING[0]], "requestedAt": "$requestedAt#1"}},
        {"method": "POST", "path": "/pending-changes/withdraw", "body": {"section": "dreams", "key": "x", "requestedAt": 5}},
        {"method": "POST", "path": "/review", "body": {"verdict": None, **_LUCIEN}},
        {"method": "GET", "path": "/pending-changes"},
        {"method": "GET", "path": "/edits"},
    ],
    # Trang đọc: ý muốn theo từng câu (đánh dấu "đang chờ Studio" ngay trên câu), cạnh cách đọc tên của cả cuốn.
    "wishes_by_line": [
        {"method": "GET", "path": "/wishes"},
        {"method": "POST", "path": "/speaker", "body": {**_LUCIEN, "speaker": "HEIDI"}},
        {"method": "POST", "path": "/speaker", "body": {**_HEIDI, "speaker": "Tiểu Mai", "newGender": "female"}},
        {"method": "POST", "path": "/line", "body": {**_HEIDI, "emotion": "tender", "intensity": 1, "spoken": "Chào anh nhé."}},
        {"method": "POST", "path": "/line", "body": {**_NARRATION, "kind": "dialogue", "speaker": "LUCIEN"}},
        {"method": "POST", "path": "/review", "body": {"verdict": "redo", **_NARRATION, "chapterId": 1}},
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Hailkes", "spokenForm": "Hên-khơ"}},
        {"method": "POST", "path": "/pronunciation", "body": {"surface": "Lucien", "spokenForm": "Lu-xi-en"}},
        {"method": "POST", "path": "/voice", "body": {"character": "HEIDI", "gender": "male"}},
        {"method": "GET", "path": "/wishes"},
        {"method": "POST", "path": "/pending-changes/withdraw", "body": {"section": "speakers", "key": LUCIEN_LINE[0], "keys": [LUCIEN_LINE[0]], "requestedAt": "$requestedAt#2"}},
        {"method": "POST", "path": "/review", "body": {"verdict": None, **_NARRATION}},
        {"method": "GET", "path": "/wishes"},
        {"method": "DELETE", "path": "/edits"},
        {"method": "GET", "path": "/wishes"},
    ],
    # "Đọc từ này là…" (cách đọc riêng của Nghe ngay - readaloud/readings.py): đặt, làm sạch, từ chối, bỏ.
    "readings": [
        {"method": "GET", "path": "/readings"},
        {"method": "PUT", "path": "/readings", "body": {"surface": "Hailkes", "spoken": "Hên khơ"}},
        {"method": "PUT", "path": "/readings", "body": {"surface": "“Hailkes,”", "spoken": "  Hên-khơ \n"}},
        {"method": "PUT", "path": "/readings", "body": {"surface": "Lucien", "spoken": "Lu xi en"}},
        {"method": "PUT", "path": "/readings", "body": {"surface": "“Hạ  Vy,”", "spoken": "Hà Vi"}},
        {"method": "PUT", "path": "/readings", "body": {"surface": "Hạ, Vy", "spoken": "Hà Vi"}},
        {"method": "PUT", "path": "/readings", "body": {"surface": "a b c d e f g", "spoken": "bảy chữ"}},
        {"method": "PUT", "path": "/readings", "body": {"surface": "...", "spoken": "chấm"}},
        {"method": "PUT", "path": "/readings", "body": {"surface": 3, "spoken": "ba"}},
        {"method": "PUT", "path": "/readings", "body": {"surface": "Heidi", "spoken": "Heidi"}},
        {"method": "GET", "path": "/edits"},
        {"method": "PUT", "path": "/readings", "body": {"surface": "Hailkes", "spoken": ""}},
        {"method": "GET", "path": "/readings"},
        {"method": "DELETE", "path": "/edits"},
        {"method": "GET", "path": "/readings"},
    ],
    "wishes_beside_other_edits": [
        {"method": "PUT", "path": "/title", "body": {"title": "Tên khác"}},
        {"method": "POST", "path": "/voice", "body": {"character": "LUCIEN", "gender": "female"}},
        {"method": "GET", "path": "/edits"},
        {"method": "GET", "path": "/cast"},
        {"method": "GET", "path": "/chapters/1/script"},
        {"method": "DELETE", "path": "/edits"},
        {"method": "GET", "path": "/edits"},
        {"method": "GET", "path": "/pending-changes"},
    ],
}


READINGS = {"Haruto": "Ha ru tô", "Kate": "Kết", "Lucien": "Lu-xi-en", "Tôkyô": "Tô ky ô", "MP": "ma lực",
            "Hạ Vy": "Hà Vi", "Hạ": "Há", "Lý Tiểu": "Lý Tiểu Long", "ông Tư": "Tứ"}
# (giọng, chữ, gốc của cuốn): mỗi ca so chữ đem đọc và khoá clip. Có dấu câu dính hai đầu, từ lặp, chữ thường không khớp (phân biệt hoa
# thường), từ dài hơn ("Harutoo", "Haruto-kun" - chỉ khớp cả từ), chữ NFD, đoạn không có từ nào (khoá như trước).
SPEECH_CASES = [
    ("edge:vi-VN-HoaiMyNeural", "“Haruto,” Kate nói.", None),
    ("vieneu:turbo/Thường", "“Haruto,” Kate nói.", None),
    ("vieneu:turbo/Thường", "“Haruto,” Kate nói.", "ja"),
    ("edge:vi-VN-NamMinhNeural", "Kate gặp Kate ở To\u0302kyo\u0302 - còn haruto, Harutoo và Haruto-kun thì không.", None),
    ("vieneu:nano/Nhẹ", "Kate gặp Kate ở To\u0302kyo\u0302 - còn haruto, Harutoo và Haruto-kun thì không.", "ja"),
    ("edge:vi-VN-HoaiMyNeural", "Không có tên nào cả.", None),
    ("vieneu:turbo/Thường", "Lucien còn 30 MP… (Lucien!)", "ko"),
    ("azure:vi-VN-HoaiMyNeural", "[Lucien]\nKate\tđi tiếp.", None),
    # Supertonic (giọng trên máy như VieNeu): cách đọc riêng sau bước đọc tên, khoá có cả gốc cuốn lẫn dấu cách đọc.
    ("supertonic:F1", "“Haruto,” Kate nói.", "ja"),
    ("supertonic:M4", "Haruto gặp Kyouko ở Tôkyô, còn 30 MP.", "ja"),
    ("supertonic:F3", "Không có tên nào cả.", "ja"),
    # Cụm nhiều chữ: số từ đọc bằng số chữ (Hạ Vy), nhiều hơn (Lý Tiểu), ít hơn (ông Tư - chữ hiện cuối không còn từ nào); khoá dài nhất thắng
    # ("Hạ Vy" trước "Hạ"); dấu câu hai đầu cụm giữ nguyên, dấu câu GIỮA hay chữ hoa thường khác thì không khớp.
    ("edge:vi-VN-HoaiMyNeural", "“Hạ Vy,” Kate nói.", None),
    ("vieneu:turbo/Thường", "“Hạ Vy,” Kate nói.", None),
    ("edge:vi-VN-NamMinhNeural", "Lý Tiểu gặp ông Tư rồi Hạ Vy và Hạ.", None),
    ("vieneu:nano/Nhẹ", "Lý Tiểu gặp ông Tư rồi Hạ Vy và Hạ.", None),
    ("edge:vi-VN-HoaiMyNeural", "Anh gọi: ông Tư! Ông Tư nói.", None),
    ("supertonic:F1", "Anh gọi: ông Tư! Ông Tư nói.", None),
    ("edge:vi-VN-HoaiMyNeural", "Hạ, Vy đi; hạ vy ở lại.", None),
    ("vieneu:turbo/Thường", "Hạ, Vy đi; hạ vy ở lại.", None),
]


def speech_cases() -> dict[str, Any]:
    """Bộ ví dụ `readings/speech.json`: cùng chữ + cùng cách đọc riêng -> cùng chữ hiện, chữ đem đọc, dấu và khoá clip ở Python và Kotlin."""
    from abook.readaloud import cache, readings, supertonic, vieneu
    from abook.webui.word_timing import tokens

    on_this_computer = {provider.id: provider for provider in (vieneu.VieneuProvider, supertonic.SupertonicProvider)}  # giọng có `reading_tag`
    cases = []
    for voice, text, origin in SPEECH_CASES:
        provider, _, native = voice.partition(":")
        local = on_this_computer.get(provider)
        tag = readings.tag(text, READINGS)
        reading = "+".join(part for part in ((vieneu.reading_tag(text, origin, local.speaks_english) if local else ""), tag) if part)
        layout = None if local else readings.spoken_layout(text, READINGS)
        cases.append({"voice": voice, "text": text, "origin": origin, "tokens": tokens(text),
                      "spokenTokens": vieneu.spoken_tokens(tokens(text), origin, local.speaks_english, READINGS) if local else None,
                      "spokenText": layout and layout[0], "spokenSlots": layout and layout[1],
                      "tag": tag, "key": cache.clip_key(provider, native, text, reading)})
    return {"readings": READINGS, "cases": cases}


def tiny_cover() -> bytes:
    """Ảnh JPEG nhỏ (96x128) để thử đặt bìa; sinh bằng Pillow, cùng byte mỗi lần cùng phiên bản Pillow."""
    from PIL import Image

    image = Image.new("RGB", (96, 128), (170, 85, 34))
    for x in range(0, 96, 8):
        for y in range(0, 128, 8):
            if (x // 8 + y // 8) % 2:
                image.paste((30, 60, 90), (x, y, x + 8, y + 8))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=85)
    return out.getvalue()


def cover_data_url() -> str:
    return "data:image/jpeg;base64," + base64.b64encode(tiny_cover()).decode("ascii")


def make_base_project(root: Path) -> Path:
    """Dự án nguồn của `base`: `make_project` của test đồng bộ + người nói thứ hai (đã được người làm sách đổi tên) + mã ổn định
    của câu - để lớp sách mang `stableId` / `textSha256` và `originalName`."""
    from abook import names as renames
    from tests.test_webui_listen_and_sync import make_project

    project = make_project(root)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("INSERT INTO characters VALUES (2, 'HEIDI', 'Heidi', 'female', 'young', 'main', 12, '')")
    db.execute("INSERT INTO segments VALUES (6, 1, 4, 1, 0, '“Chào anh.”', 'dialogue', 'HEIDI', 2, 'verified', '', 'x', 2.5, 0)")
    db.execute("ALTER TABLE segments ADD COLUMN stable_id TEXT")
    db.execute("ALTER TABLE segments ADD COLUMN text_sha256 TEXT")
    for row, text in db.execute("SELECT id, text FROM segments").fetchall():
        import hashlib

        db.execute("UPDATE segments SET stable_id=?, text_sha256=? WHERE id=?",
                   (f"c1_s{row:04d}_{hashlib.sha256(text.encode()).hexdigest()[:6]}",
                    hashlib.sha256(text.encode()).hexdigest(), row))
    db.commit()
    db.close()
    renames.set_name(project, "HEIDI", "Hây-đi", "Heidi")
    return project


def build_base(work: Path) -> Path:
    """Dựng thư mục `base` (cuốn đã nhập) trong `work`: đóng gói dự án bằng `bookfile.pack`, giải nén như app khi nhập file."""
    from abook.webui import bookfile, covers
    from tests.test_bookfile_music import _plan, _tracks

    project = make_base_project(work)
    _plan(project)
    covers.save_cover_bytes(project, tiny_cover())
    packed = bookfile.pack(project, work / "base.abook", music_track=_tracks(work))
    with bookfile.BookFile(packed) as book:
        folder = book.extract(work / "library", "base")
    (folder / covers.META_FILE).write_text(json.dumps(
        {key: book.book["cover"][key] for key in ("color", "width", "height")}), encoding="utf-8")
    return folder


def series_manifest() -> dict[str, Any]:
    """`book.json` của một file cả bộ hai phần (chỉ phần mô tả): tên các phần và mã chương chung `phần x 100000 + mã`."""
    chapters = [
        {"id": 100001, "index": 1, "part": 1, "title": "Chương 1", "subtitle": "", "fullTitle": "Chương 1", "duration": 5.0,
         "available": True, "file": "chapters/1/a.mp3", "size": 1, "script": "scripts/100001.json"},
        {"id": 200001, "index": 1, "part": 2, "title": "Chương 1", "subtitle": "Mở đầu", "fullTitle": "Chương 1 · Mở đầu",
         "duration": 6.0, "available": True, "file": "chapters/2/a.mp3", "size": 1, "script": "scripts/200001.json"},
    ]
    return {"format": "abook-book/1", "title": "Bộ truyện", "narrator": "Đức Trí", "duration": 11.0, "chaptersTotal": 2,
            "chaptersAvailable": 2, "complete": True, "version": "v", "chapters": chapters, "cast": "cast.json",
            "samples": [], "cover": None,
            "parts": [{"part": 1, "title": "Bộ truyện · Phần 1", "chapters": [100001, 100001], "duration": 5.0, "narrator": "Đức Trí"},
                      {"part": 2, "title": "Bộ truyện · Phần 2", "chapters": [200001, 200001], "duration": 6.0, "narrator": "Đức Trí"}],
            "package": {"format": "abook", "version": 3, "createdAt": "2026-10-03T00:00:00+00:00", "producer": "ABook", "files": {}}}


def overlay_views(folder: Path, edits: dict[str, Any]) -> dict[str, Any]:
    """Những gì người nghe thấy khi áp `edits` lên cuốn ở `folder`: `book.json`, `cast.json`, mọi `scripts/<n>.json`."""
    from abook.webui import book_edits

    base = json.loads((folder / "book.json").read_text(encoding="utf-8"))
    cast = json.loads((folder / "cast.json").read_text(encoding="utf-8"))
    scripts = {}
    for chapter in base["chapters"]:
        script = json.loads((folder / chapter["script"]).read_text(encoding="utf-8"))
        scripts[str(chapter["id"])] = book_edits.apply_script(script, cast, edits, chapter)
    shown = book_edits.apply_manifest(base, edits)
    return {"manifest": {key: value for key, value in shown.items() if key != "package"},
            "cast": book_edits.apply_cast(cast, edits, base), "scripts": scripts}


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def record_contract(folder: Path, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chạy `steps` qua MÁY CHỦ THẬT (Server + App) trên một bản sao của `folder` đặt làm sách nhập; ghi lời đáp."""
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import _request

    with tempfile.TemporaryDirectory() as raw:
        work = Path(raw)
        library = work / "library"
        copy = library / "Sách đã nhập" / "base"
        shutil.copytree(folder, copy)
        preferences = Preferences(work / "prefs" / "preferences.json")
        preferences.update({"libraryRoot": str(library)})
        app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(work / "prefs" / "listening.json"))
        server = Server(app, port=0).start()
        try:
            identifier = book_id(copy)
            recorded: list[dict[str, Any]] = []
            for step in steps:
                if "import" in step:  # nhập một bài mẫu vào kho "Nhạc của tôi" của máy này
                    app.my_music.import_file(FIXTURES / "track" / step["import"])
                    recorded.append(step)
                    continue
                body = step.get("body")
                if body is not None:
                    text = json.dumps(body).replace('"$cover"', json.dumps(cover_data_url()))
                    text = re.sub(r'"\$requestedAt#(\d+)"', lambda match: json.dumps(recorded[int(match.group(1)) - 1]["response"]["requestedAt"]), text)
                    body = json.loads(text)
                status, data, _ = _request(server.port, step["method"], f"/api/books/{identifier}{step['path']}",
                                           headers={"X-Ebook-Token": "t"}, body=body)
                recorded.append({**step, "status": status, "response": json.loads(data or b"null")})
        finally:
            server.stop()
    return recorded


def generate(*, rebuild_base: bool = False) -> None:
    """Sinh lại mọi file mong đợi từ `base`. `base` chỉ dựng lại khi `rebuild_base` (nó mang giờ đóng gói và phiên bản bìa nên
    mỗi lần dựng ra byte khác - đổi nó là đổi cả bộ ví dụ)."""
    from abook.webui import book_edits

    if rebuild_base or not BASE.exists():
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            folder = build_base(work)
            if BASE.exists():
                shutil.rmtree(BASE)
            shutil.copytree(folder, BASE)
            # Readium manifest sinh lại được từ book.json, nên bỏ khỏi bộ ví dụ
            (BASE / "manifest.json").unlink(missing_ok=True)
    for old in ("edits", "invalid", "expected", "merge", "contract", "series", "track", "readings"):
        shutil.rmtree(FIXTURES / old, ignore_errors=True)
    (FIXTURES / "track").mkdir(parents=True)
    (FIXTURES / "track" / "tone.wav").write_bytes(tone_wav())
    _write(FIXTURES / "series" / "book.json", series_manifest())
    for name, case in CASES.items():
        edits = book_edits.validate({**HEAD, **case})
        _write(FIXTURES / "edits" / f"{name}.json", book_edits._ordered(edits))
        if isinstance(edits.get("cover"), dict):
            target = FIXTURES / "edits" / f"{name}.cover.jpg"
            target.write_bytes(tiny_cover())
        _write(FIXTURES / "expected" / f"{name}.json", overlay_views(BASE, edits))
    series = json.loads((FIXTURES / "series" / "book.json").read_text(encoding="utf-8"))
    shown = book_edits.apply_manifest(series, book_edits.validate({**HEAD, "title": "Tên khác", "chapters": {"200001": {"title": "Chương Một"}}}))
    _write(FIXTURES / "expected" / "series_title_and_chapter.json",
           {"manifest": {key: value for key, value in shown.items() if key != "package"}})
    for name, value in INVALID.items():
        _write(FIXTURES / "invalid" / f"{name}.json", value)
    for name, text in INVALID_RAW.items():
        (FIXTURES / "invalid").mkdir(parents=True, exist_ok=True)
        (FIXTURES / "invalid" / f"{name}.json").write_bytes(text.encode("utf-8"))
    for name, (local, incoming) in MERGE_CASES.items():
        local, incoming = book_edits.validate(local), book_edits.validate(incoming)
        merged, report = book_edits.merge(local, incoming)
        _write(FIXTURES / "merge" / f"{name}.json", {"local": book_edits._ordered(local), "incoming": book_edits._ordered(incoming),
                                                     "merged": book_edits._ordered(merged), "report": report})
    for name, steps in CONTRACT.items():
        _write(FIXTURES / "contract" / f"{name}.json", {"volatile": VOLATILE, "steps": record_contract(BASE, steps)})
    _write(FIXTURES / "readings" / "speech.json", speech_cases())
    python_file = FIXTURES / "written" / "python_v4.abook"
    if rebuild_base or not python_file.exists():
        write_python_v4(python_file)
    pins_file = FIXTURES / "written" / "python_v4_pins.abook"
    if rebuild_base or not pins_file.exists():
        write_python_v4(pins_file, pinned=True)
    workshop_file = FIXTURES / "written" / "python_workshop.abookproj"
    pending_file = FIXTURES / "written" / "python_pending.abookproj"
    if rebuild_base or not workshop_file.exists() or not pending_file.exists():
        write_python_projects(workshop_file, pending_file)


def write_python_v4(target: Path, *, pinned: bool = False) -> None:
    """`base` + phần sửa `everything` -> file phiên bản 4 do `bookfile.repack` ghi (Kotlin phải mở và kiểm được). `pinned`: phần sửa
    `music_pin` thay vì `everything`, kèm file bài nhạc ghim ở music/<sha1>.wav (không bìa sửa)."""
    from abook.webui import bookfile

    with tempfile.TemporaryDirectory() as raw:
        copy = Path(raw) / "base"
        shutil.copytree(BASE, copy)
        if pinned:
            shutil.copy2(FIXTURES / "edits" / "music_pin.json", copy / "edits.json")
            shutil.copy2(FIXTURES / "track" / "tone.wav", copy / "music" / f"{TRACK_SHA}.wav")
        else:
            shutil.copy2(FIXTURES / "edits" / "everything.json", copy / "edits.json")
            (copy / "edits").mkdir()
            shutil.copy2(FIXTURES / "edits" / "everything.cover.jpg", copy / "edits" / "cover.jpg")
        target.parent.mkdir(parents=True, exist_ok=True)
        bookfile.repack(copy, target)


NEUTRAL_ROOT = "D:\\Studio\\sach_thu"
NEUTRAL_SOURCES = {"645.txt": "D:\\Studio\\nguon\\645.txt", "646.txt": "D:\\Studio\\nguon\\646.txt"}
WORKSHOP_VIEWS = {
    "work": {"castReady": True, "items": [{"id": "name:Hailkes", "kind": "name", "title": "Hailkes"}]},
    "casting": {"castReady": True, "chapters": [{"chapterId": 1, "index": 1, "title": "Chương 646", "lines": 4, "speech": 2, "hints": 0, "decided": 0}]},
    "names": {"items": [{"surface": "Hailkes", "spoken": "Hên-khơ"}], "unseen": 0},
}


def write_python_projects(workshop: Path, pending: Path) -> None:
    """Hai file dự án phiên bản 3 do `projectfile` ghi cho Kotlin đối chiếu. `workshop`: dự án nguồn của `base` đóng gói thật (bí danh
    cho audio chương / câu mẫu / bìa, `views/` cố định, `sources/` hai chương) - đường dẫn của máy sinh được viết lại thành đường
    dẫn trung tính (không để tên người dùng nằm trong kho mã). `pending`: `base` + phần sửa `everything` lưu thành dự án không xưởng."""
    from abook.webui import covers, project_views, projectfile

    with tempfile.TemporaryDirectory() as raw:
        work = Path(raw)
        project = make_base_project(work / "may_cu")
        covers.save_cover_bytes(project, tiny_cover())
        sources = work / "nguon"
        sources.mkdir()
        for name, text in (("645.txt", "Chương 646 - Trở về (1)\n\nTrời đã sáng.\n"), ("646.txt", "Chương 647 - Trở về (2)\n\nChưa thu.\n")):
            (sources / name).write_bytes(text.encode("utf-8"))
        db = sqlite3.connect(project / "project.sqlite3")
        try:
            with db:
                db.execute("ALTER TABLE book ADD COLUMN project_root TEXT")
                db.execute("UPDATE book SET project_root = ?", (str(project.resolve()),))
                db.execute("UPDATE chapters SET input_path = ? WHERE id = 1", (str(sources / "645.txt"),))
                db.execute("UPDATE chapters SET input_path = ? WHERE id = 2", (str(sources / "646.txt"),))
        finally:
            db.close()
        saved = dict(project_views.VIEWS)
        try:
            for name, data in WORKSHOP_VIEWS.items():
                project_views.VIEWS[name] = lambda _root, data=data: data
            projectfile.pack(project, work / "workshop.abookproj")
        finally:
            project_views.VIEWS.clear()
            project_views.VIEWS.update(saved)
        old = {str(sources / name): neutral for name, neutral in NEUTRAL_SOURCES.items()}
        _neutralize(work / "workshop.abookproj", workshop, str(project.resolve()), old)
        copy = work / "base"
        shutil.copytree(BASE, copy)
        shutil.copy2(FIXTURES / "edits" / "everything.json", copy / "edits.json")
        (copy / "edits").mkdir()
        shutil.copy2(FIXTURES / "edits" / "everything.cover.jpg", copy / "edits" / "cover.jpg")
        projectfile.repack(copy, pending)


def _neutralize(packed: Path, target: Path, old_root: str, old_sources: dict[str, str]) -> None:
    """Viết lại đường dẫn của máy sinh (trong project.json và sổ dự án) thành đường dẫn trung tính, rồi ghi lại mô tả."""
    import zipfile

    from abook.webui import bookfile, projectfile

    with zipfile.ZipFile(packed) as source:
        manifest = json.loads(source.read("project.json"))
        entries = {info.filename: (info, source.read(info.filename)) for info in source.infolist()}
    with tempfile.TemporaryDirectory() as raw:
        database = Path(raw) / "project.sqlite3"
        database.write_bytes(entries["project/project.sqlite3"][1])
        projectfile.relocate(database, old_root, NEUTRAL_ROOT, old_sources)
        vacuum = sqlite3.connect(database)  # trang cũ vẫn giữ chữ cũ trong chỗ trống của file: dồn lại cho sạch
        try:
            vacuum.execute("VACUUM")
        finally:
            vacuum.close()
        entries["project/project.sqlite3"] = (entries["project/project.sqlite3"][0], database.read_bytes())
    manifest["files"]["project/project.sqlite3"] = bookfile.describe(entries["project/project.sqlite3"][1])
    manifest["projectRoot"] = NEUTRAL_ROOT
    manifest["sources"] = [{**item, "path": old_sources[item["path"]]} for item in manifest["sources"]]
    manifest["missingSources"] = []
    entries["project.json"] = (entries["project.json"][0], (json.dumps(manifest, ensure_ascii=False, indent=1)).encode("utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", allowZip64=True) as sink:
        for name, (info, data) in entries.items():
            sink.writestr(info, data)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    generate(rebuild_base="--rebuild-base" in sys.argv)
    print("generated", FIXTURES)
