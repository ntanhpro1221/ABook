"""Internal marks (QA verdicts, line ids, machine codes, raw local-role labels) never reach text a listener sees.

Owner rule 15-11: a shipped book showed "Cần nghe lại" as the subtitle of six chapters. Every package goes through `seal`,
which refuses listener-visible text carrying such a mark. Data fields (qualityPassed, qualityWarning) stay data.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from abook.webui import bookfile


def _book(**chapter) -> dict:
    return {"title": "Sách thử", "narrator": "Giọng A", "cover": None,
            "chapters": [{"id": 1, "index": 1, "title": "Chương 1", "subtitle": "", "fullTitle": "Chương 1",
                          "file": "chapters/1.mp3", "qualityPassed": False, "qualityWarning": "Cần nghe lại: c00001_s0002",
                          **chapter}]}


def test_clean_listener_text_passes_even_when_quality_data_records_a_warning() -> None:
    cast = {"narrator": {"voice": "Giọng A", "chapterVoices": [{"voice": "Giọng B", "chapters": [{"id": 1, "title": "Chương 1"}]}],
                         "exceptChapters": [{"id": 1, "title": "Chương 1"}]},
            "characters": [{"name": "NPC_LOCAL::c00001::bác gác", "displayName": "Bác gác", "firstChapter": "Chương 1",
                            "gender": "Nam", "age": "Người lớn"}], "extras": [], "carried": []}
    assert bookfile.listener_text_problems(_book(), cast) == []


@pytest.mark.parametrize("field, value", [
    ("subtitle", "Cần nghe lại"),
    ("subtitle", "Lần gặp đầu · Cần nghe lại"),
    ("fullTitle", "Chương 1 · Cần thu lại"),
    ("title", "Chương 1 c00001_s0002"),
    ("subtitle", "TTS_PACE_OUTLIER"),
])
def test_a_mark_in_a_chapter_title_is_found(field: str, value: str) -> None:
    assert bookfile.listener_text_problems(_book(**{field: value}), None) == [f"chapters[1].{field}: {value}"]


def test_a_mark_in_the_cast_is_found() -> None:
    cast = {"narrator": {"voice": "Giọng A", "exceptChapters": [{"id": 1, "title": "Chương 1 · Cần nghe lại"}]},
            "characters": [], "extras": [{"name": "x", "displayName": "NPC_LOCAL::c00001::bác gác"}], "carried": []}
    assert len(bookfile.listener_text_problems(_book(), cast)) == 2


def test_seal_refuses_a_package_whose_listener_text_carries_a_mark(tmp_path: Path) -> None:
    with pytest.raises(bookfile.BookFileError, match="dấu nội bộ"):
        bookfile.seal(_book(subtitle="Cần nghe lại"), {"chapters/1.mp3": b"audio"}, tmp_path / "x.abook",
                      producer="test", version=1)
    assert not (tmp_path / "x.abook").exists()


def test_the_npc_mark_is_identity_in_data_but_never_shown() -> None:
    """"NPC X" stays the key (`name`, used to match lines) but the shown name is "X" (humanize.person_name)."""
    from abook.webui.humanize import person_name

    assert [person_name(name) for name in ("NPC Bà Lão Bán Hoa", "NPC_BÁC_GÁC", "Npc: cô gái")] == ["Bà Lão Bán Hoa", "Bác Gác", "cô gái"]
    cast = {"narrator": {"voice": "Giọng A"}, "characters": [],
            "extras": [{"name": "NPC Bà Lão Bán Hoa", "displayName": "Bà Lão Bán Hoa"}], "carried": []}
    assert bookfile.listener_text_problems(_book(), cast) == []
    cast["extras"][0]["displayName"] = "NPC Bà Lão Bán Hoa"
    assert bookfile.listener_text_problems(_book(), cast) == ["cast.extras.displayName: NPC Bà Lão Bán Hoa"]
    assert bookfile.listener_text_problems({**_book(), "title": "Tôi chuyển sinh thành NPC"}, None) == [], "chữ NPC trong tên sách là chữ thật"


def test_seal_refuses_a_script_line_whose_speaker_shows_a_mark(tmp_path: Path) -> None:
    script = '{"segments": [{"speaker": "Bà Lão"}, {"speaker": "NPC Bà Lão Bán Hoa"}]}'.encode()
    assert bookfile.script_speaker_problems("scripts/1.json", script) == ["scripts/1.json.speaker: NPC Bà Lão Bán Hoa"]
    assert bookfile.script_speaker_problems("scripts/1.json", '{"segments": [{"speaker": "An \\"Cáo\\""}]}'.encode()) == []
    with pytest.raises(bookfile.BookFileError, match="dấu nội bộ"):
        bookfile.seal(_book(), {"chapters/1.mp3": b"audio", "scripts/1.json": script}, tmp_path / "x.abook", producer="test", version=1)
    assert not (tmp_path / "x.abook").exists()
