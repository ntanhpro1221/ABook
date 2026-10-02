"""Thẻ "Ai nói câu này?" theo XƯNG HÔ (webui/address_cues.py) - 2026-09-29.

Nhầm người kể "tôi" là lỗi lớn nhất của mọi model trên bộ LN. Mỗi nhân vật có cặp xưng/gọi riêng; câu dính người kể mà xưng
hô hợp người khác hơn thì hỏi người nghe. Đo trên bộ LN: câu bị hỏi sai thật 85-95%.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from abook.webui.address_cues import address_doubts, tokens
from abook.webui.work_items import work_items

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


# ---- "Hai người chung một tên" (address_cues.split_doubts) ---------------------------------------------------------------
# Nageki 62 (29-09): 8B-v5 gán 21/25 câu của một bà thầy bói vô danh cho LUCIA. Bà nói "ta… cậu" với Krai; Lucia gọi Krai
# "anh", gọi bà "bà" - hai kiểu không bao giờ đi chung câu, và Lucia ở các chương khác cũng "anh… em".
LUCIA_ELSEWHERE = [
    "“Anh ơi, em đói rồi.”",
    "“Em đi với anh nhé?”",
    "“Anh lại quên mất em rồi.”",
    "“Em không giận anh đâu.”",
]
LUCIA_HERE = ["“Anh đừng tin bà ấy!”", "“Bà nói gì với anh vậy?”", "“Bà thôi đi, anh em về thôi.”"]
FORTUNE_TELLER = [
    "“Ô hô, số mệnh của cậu thật lạ. Ta chưa từng thấy.”",
    "“Cậu sẽ gặp tận số, ta nói thật.”",
    "“Nghe ta nói hết đã, cậu trai.”",
    "“Ta không lấy tiền của cậu đâu.”",
]


def split_rows(narrated: bool = True) -> tuple[list[dict], callable]:
    rows = [{"chapter_id": 1, "speaker": "LUCIA", "text": text, "kind": "dialogue"} for text in LUCIA_ELSEWHERE]
    rows += [{"chapter_id": 2, "speaker": "LUCIA", "text": text, "kind": "dialogue"} for text in LUCIA_HERE + FORTUNE_TELLER]
    return rows, (lambda _chapter: "Krai") if narrated else (lambda _chapter: "")


def test_one_name_speaking_two_ways_to_the_narrator_is_two_people() -> None:
    from abook.webui.address_cues import split_doubts

    rows, narrator_of = split_rows()
    found = split_doubts(rows, narrator_of, lambda speaker: speaker != "NARRATOR")
    assert len(found) == 1
    label, odd, odd_words, usual_words, usual_count = found[0]
    assert label == "LUCIA"
    assert [row["text"] for row in odd] == FORTUNE_TELLER, "nhóm lệch khỏi cách Lucia nói ở chương khác là người lạ"
    assert "ta" in odd_words and "cậu" in odd_words and "anh" in usual_words and usual_count == 3


def test_no_split_card_in_a_third_person_chapter_or_without_the_other_chapters() -> None:
    """Ngôi ba: một người đổi xưng hô theo vai vế (Chu Du "ta… ngươi" với tướng dưới, "tôi… ngài" với chúa). Không có câu
    ở chương khác thì không biết nhóm nào là người thật - không hỏi."""
    from abook.webui.address_cues import split_doubts

    rows, narrator_of = split_rows(narrated=False)
    assert split_doubts(rows, narrator_of, lambda speaker: True) == []
    here_only = [row for row in split_rows()[0] if row["chapter_id"] == 2]
    assert split_doubts(here_only, lambda _chapter: "Krai", lambda speaker: True) == []


def test_calling_mother_and_friend_differently_is_one_person() -> None:
    """Kakeru gọi mẹ "con", gọi bạn "cậu… mình": một người, hai người nghe - không tự xưng nào mâu thuẫn."""
    from abook.webui.address_cues import split_doubts

    friends = ["“Cậu đi đâu thế, mình chờ mãi.”", "“Mình với cậu đi ăn nhé.”", "“Cậu biết mình mà.”"]
    mother = ["“Con về rồi đây.”", "“Con không sao đâu.”"]
    rows = [{"chapter_id": 1, "speaker": "KAKERU", "text": text, "kind": "dialogue"} for text in friends + mother]
    rows += [{"chapter_id": 2, "speaker": "KAKERU", "text": text, "kind": "dialogue"} for text in friends * 3]
    assert split_doubts(rows, lambda _chapter: "Kakeru", lambda speaker: True) == []


def test_saying_we_is_not_a_second_self() -> None:
    """01-10, Nageki 79: Franz hét "tôi… cậu" với Krai và hai lần nói "chúng ta" - một người. Tự xưng số nhiều không phải
    cách tự xưng của người khác."""
    from abook.webui.address_cues import split_doubts

    shouting = ["“Tôi nói rồi, tôi không phải bạn cậu!”", "“Cậu nghĩ tôi cần cậu trấn an chắc?”", "“Cậu mưu tính gì, tôi hỏi!”"]
    we = ["“Chúng ta đi thôi.”", "“Chúng ta không còn thời gian.”"]
    rows = [{"chapter_id": 1, "speaker": "FRANZ", "text": text, "kind": "dialogue"} for text in shouting * 3]
    rows += [{"chapter_id": 2, "speaker": "FRANZ", "text": text, "kind": "dialogue"} for text in shouting + we]
    assert split_doubts(rows, lambda _chapter: "Krai", lambda speaker: True) == []


def test_the_inbox_asks_once_for_the_whole_odd_group(tmp_path: Path) -> None:
    project = tmp_path / "sach"
    project.mkdir()
    (project / "book_settings.json").write_text(json.dumps({"voices": {"first_person_identity": "Krai"}}), encoding="utf-8")
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
    db.executemany("INSERT INTO chapters VALUES (?, ?, ?)", [(1, 1, '61'), (2, 2, '62')])
    db.execute("INSERT INTO characters (id, canonical_name, display_name, gender, locked) VALUES (1, 'LUCIA', 'Lucia', 'female', 0)")
    rows, _ = split_rows()
    db.executemany(
        "INSERT INTO segments (stable_id, chapter_id, seq, text, kind, speaker, status, text_sha256, canonical_character_id)"
        " VALUES (?, ?, ?, ?, 'dialogue', 'LUCIA', 'verified', ?, 1)",
        [(f"s{seq}", row["chapter_id"], seq, row["text"], f"sha{seq}") for seq, row in enumerate(rows)],
    )
    db.commit()
    db.close()

    cards = [item for item in work_items(project)["items"] if item["key"].startswith("split:")]
    assert len(cards) == 1
    card = cards[0]
    assert [line["stableId"] for line in card["lines"]] == [f"s{seq}" for seq in range(7, 11)]
    assert card["choices"][0]["value"] == "UNNAMED", "người lạ trước tiên là vai phụ không tên"
    assert card["affected"] == 4 and "“cậu”" in card["problem"] and "Lucia" in card["title"]


def test_the_narrators_own_label_is_left_to_the_line_by_line_card() -> None:
    """Hai giọng dưới nhãn NGƯỜI KỂ: thẻ xưng hô từng câu lo (address_doubts); hồ sơ người kể ở chương khác nhiễm lời người
    khác mà model gộp vào, nên chọn nhóm lạ theo nó dễ ngược (HDST 130, 29-09)."""
    from abook.webui.address_cues import split_doubts

    rows, _ = split_rows()
    as_narrator = [{**row, "speaker": "KRAI"} for row in rows]
    assert split_doubts(as_narrator, lambda _chapter: "Krai", lambda speaker: True) == []
