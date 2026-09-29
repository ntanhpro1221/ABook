"""Thẻ "Ai nói câu này?" theo XƯNG HÔ (webui/address_cues.py) - 2026-09-29.

Nhầm người kể "tôi" là lỗi lớn nhất của mọi model trên bộ LN. Mỗi nhân vật có cặp xưng/gọi riêng; câu dính người kể mà xưng
hô hợp người khác hơn thì hỏi người nghe. Đo trên bộ LN: câu bị hỏi sai thật 85-95%.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ebook_reader.webui.address_cues import address_doubts, tokens
from ebook_reader.webui.work_items import work_items

TOMOBE = [
    "“Tôi hiểu rồi, thưa tiểu thư. Tôi sẽ đi ngay.”",
    "“Tôi xin lỗi, tôi về muộn.”",
    "“Tiểu thư, tôi mang trà tới rồi.”",
    "“Tôi không sao đâu. Tôi chỉ hơi mệt thôi.”",
    "“Tôi sẽ canh cửa, tiểu thư cứ ngủ đi. Tôi ở ngay đây.”",
]
HINA = [
    "“Ngươi lại đi đâu thế? Ta chờ mãi.”",
    "“Ta không cần ngươi lo.”",
    "“Ngươi nghĩ ta là ai chứ?”",
    "“Lại đây, ta có chuyện muốn nói với ngươi.”",
]
# Máy gán nhầm cho người kể: xưng "ta", gọi "ngươi" - đúng kiểu của Hina.
WRONG = "“Ngươi về trễ hơn ta nghĩ đấy. Ta cứ tưởng ngươi về sớm cơ.”"


def make_book(root: Path, narrator: str) -> Path:
    project = root / "sach"
    project.mkdir()
    voices = {"first_person_identity": narrator} if narrator else {}
    (project / "book_settings.json").write_text(json.dumps({"voices": voices}), encoding="utf-8")
    db = sqlite3.connect(project / "project.sqlite3")
    db.executescript(
        """
        CREATE TABLE chapters (id INTEGER PRIMARY KEY, chapter_index INTEGER, title TEXT);
        CREATE TABLE segments (id INTEGER PRIMARY KEY, stable_id TEXT, chapter_id INTEGER, seq INTEGER, text TEXT,
                               kind TEXT, speaker TEXT, voice_profile_id INTEGER, canonical_character_id INTEGER,
                               status TEXT, asr_text TEXT, asr_similarity REAL, warning_code TEXT, wav_path TEXT,
                               text_sha256 TEXT, gender TEXT);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, canonical_name TEXT, display_name TEXT, gender TEXT,
                                 locked INTEGER, age TEXT);
        """
    )
    db.execute("INSERT INTO chapters VALUES (1, 1, '141')")
    db.executemany("INSERT INTO characters (id, canonical_name, display_name, gender, locked) VALUES (?,?,?,?,?)",
                   [(1, "TOMOBE", "Tomobe", "male", 0), (2, "HINA", "Hina", "female", 0)])
    lines = [(text, "TOMOBE") for text in TOMOBE] + [(text, "HINA") for text in HINA] + [(WRONG, "TOMOBE")]
    db.executemany(
        "INSERT INTO segments (stable_id, chapter_id, seq, text, kind, speaker, status, text_sha256)"
        " VALUES (?, 1, ?, ?, 'dialogue', ?, 'verified', ?)",
        [(f"s{seq}", seq, text, speaker, f"sha{seq}") for seq, (text, speaker) in enumerate(lines)],
    )
    db.commit()
    db.close()
    return project


def test_pronouns_are_counted_without_third_person_or_look_alikes() -> None:
    assert tokens("Ngươi nghĩ ta là ai?") == {"ngươi": 1, "ta": 1}
    assert tokens("Cô ấy nói cô độc lắm, anh ta biết.") == {}, "ngôi ba và 'cô độc' không phải xưng hô"
    assert tokens("Chúng ta đi thôi, mọi người.") == {"chúng ta": 1}


def test_a_line_given_to_the_narrator_that_talks_like_someone_else_is_asked_about(tmp_path: Path) -> None:
    view = work_items(make_book(tmp_path, "Tomobe"))
    cards = [item for item in view["items"] if item["kind"] == "speaker"]

    assert len(cards) == 1, "chỉ câu xưng hô lạc"
    card = cards[0]
    assert card["examples"][0]["text"] == WRONG
    assert card["choices"][0]["value"] == "HINA", "người xưng hô giống nhất đứng đầu"
    assert "“ngươi”" in card["problem"] and "“ta”" in card["problem"]


def test_a_third_person_book_gets_no_pronoun_cards(tmp_path: Path) -> None:
    """Truyện ngôi ba kiểu Trung ai cũng "ta/ngươi" - hỏi theo xưng hô ở đó toàn hỏi nhầm (Tam quốc, Throne 29-09)."""
    view = work_items(make_book(tmp_path, ""))

    assert not [item for item in view["items"] if item["kind"] == "speaker"]


def test_only_lines_that_involve_the_narrator_are_asked_about(tmp_path: Path) -> None:
    rows = [{"chapter_id": 1, "speaker": speaker, "text": text}
            for text, speaker in [(t, "TOMOBE") for t in TOMOBE] + [(t, "HINA") for t in HINA] + [(WRONG, "TOMOBE")]]
    assert [best for _row, best, _cue in address_doubts(rows, lambda _chapter: "Tomobe")] == ["HINA"]
    assert address_doubts(rows, lambda _chapter: "Sumire") == [], "người kể là người khác: câu này không dính người kể"
    assert address_doubts(rows, lambda _chapter: "") == [], "chương kể ngôi ba"
