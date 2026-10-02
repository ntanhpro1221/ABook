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

Sinh lại (chỉ khi cố ý đổi hành vi hay giao ước):  runtime/.venv/Scripts/python.exe -m tests.book_edits_fixtures
(thêm --rebuild-base để dựng lại cả `base`; không thì giữ nguyên nó và chỉ sinh lại các file mong đợi)
"""
from __future__ import annotations

import base64
import io
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures" / "book_edits"
BASE = FIXTURES / "base"

# Mốc nhạc của base (xem tests/test_bookfile_music._plan): chương 1, hai bài, mốc 0-60 s (hai đoạn liền cùng bài gộp) và 60-90 s.
CASES: dict[str, dict[str, Any]] = {
    "title_only": {"title": "Tên mới của tôi"},
    "names": {"characters": {"LUCIEN": "Lu-xi-en", "HEIDI": "Heidi"}},
    "chapters": {"chapters": {"1": {"title": "Chương Một", "subtitle": ""}, "2": {"subtitle": "Hết rồi"}}},
    "music_level_and_silence": {"music": {"levelDb": -24.0, "silenced": ["1:60000"]}},
    "music_off": {"music": {"enabled": False}},
    "cover_removed": {"cover": None},
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
    "music_unknown_field": {**HEAD, "music": {"pins": {}}},
    "music_empty": {**HEAD, "music": {}},
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
    for old in ("edits", "invalid", "expected", "merge", "contract", "series"):
        shutil.rmtree(FIXTURES / old, ignore_errors=True)
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
    python_file = FIXTURES / "written" / "python_v4.abook"
    if rebuild_base or not python_file.exists():
        write_python_v4(python_file)


def write_python_v4(target: Path) -> None:
    """`base` + phần sửa `everything` -> file phiên bản 4 do `bookfile.repack` ghi (Kotlin phải mở và kiểm được)."""
    from abook.webui import bookfile

    with tempfile.TemporaryDirectory() as raw:
        copy = Path(raw) / "base"
        shutil.copytree(BASE, copy)
        shutil.copy2(FIXTURES / "edits" / "everything.json", copy / "edits.json")
        (copy / "edits").mkdir()
        shutil.copy2(FIXTURES / "edits" / "everything.cover.jpg", copy / "edits" / "cover.jpg")
        target.parent.mkdir(parents=True, exist_ok=True)
        bookfile.repack(copy, target)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    generate(rebuild_base="--rebuild-base" in sys.argv)
    print("generated", FIXTURES)
