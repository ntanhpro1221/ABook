"""Studio đọc chữ bằng cùng bộ chuẩn hoá theo chữ với Nghe ngay (`abook.readaloud.studio_tn`), chữ của bảng phát âm giữ nguyên và mốc anchor dịch đúng."""
from __future__ import annotations

from pathlib import Path

import pytest

from abook.config import build_settings
from abook.database import ProjectDB
from abook.models import ENGLISH_NAME_PRONUNCIATION_SOURCE
from abook.readaloud.studio_tn import studio_tn, studio_tn_tagged
from abook.tts import TTSCoordinator


@pytest.mark.parametrize("text, said", [
    ("Chương IV bắt đầu", "Chương bốn bắt đầu"),
    ("Thế chiến II kết thúc", "Thế chiến hai kết thúc"),
    ("ông X đi qua", "ông X đi qua"),
    ("Anh HP ơi", "Anh hát pê ơi"),
    ("Aaaa! Đau quá", "a… a! Đau quá"),
    ("Ariel-sama đến rồi", "Ariel-xa-ma đến rồi"),
    ("Giá 1,000 người", "Giá 1000 người"),
    ("a ~ b", "a b"),
    ("  Chương IV  ", "  Chương bốn  "),
])
def test_a_word_is_read_as_read_aloud_reads_it(text: str, said: str) -> None:
    assert studio_tn(text, None, True)[0] == said


def test_the_position_table_follows_the_length_change() -> None:
    text = "Anh HP ơi, Chương IV"
    said, where = studio_tn(text, None, True)
    assert said == "Anh hát pê ơi, Chương bốn"
    assert len(where) == len(text) + 1 and where[len(text)] == len(said)
    assert where == sorted(where)  # không đi lùi
    assert said[where[text.index("ơi")]:].startswith("ơi")
    assert said[where[text.index("Chương")]:].startswith("Chương")


def test_a_protected_span_keeps_its_word() -> None:
    assert studio_tn("Anh HP ơi", None, True, [(5, 7)])[0] == "Anh HP ơi"
    assert studio_tn("Chương IV", None, True, [(0, 6)])[0] == "Chương bốn"  # chạm chữ khác thì chữ ấy vẫn đổi


def test_a_vocal_cue_is_left_for_the_vocalization_pass() -> None:
    text, _tags = studio_tn_tagged("[thở dài] Chương IV", [frozenset()] * 19, None, True)
    assert text == "[thở dài] Chương bốn"


def _coordinator(tmp_path: Path) -> tuple[ProjectDB, TTSCoordinator]:
    db = ProjectDB(tmp_path / "project.sqlite3")
    return db, TTSCoordinator(build_settings(), db, lambda _message: None)


def _pronounce(db: ProjectDB, surface: str, spoken: str) -> None:
    db.upsert_pronunciation(surface=surface, normalized_surface=surface.casefold(), spoken_form=spoken, confidence=0.95,
                            source=ENGLISH_NAME_PRONUNCIATION_SOURCE, locked=True)


def test_an_anchor_after_a_changed_word_points_at_its_name_in_the_new_string(tmp_path: Path) -> None:
    db, coordinator = _coordinator(tmp_path)
    _pronounce(db, "Michael", "Mai-cồ")
    text, anchors = coordinator.spoken_text_with_anchors({"text": "Chương IV: gặp HP, rồi Michael đã đi."})
    assert text == "Chương bốn: gặp hát pê, rồi Mai-cồ đã đi."
    assert [text[anchor["spoken_start"]:anchor["spoken_end"]] for anchor in anchors] == ["Mai-cồ"]


def test_the_books_pronunciation_table_beats_the_word_rules(tmp_path: Path) -> None:
    db, coordinator = _coordinator(tmp_path)
    _pronounce(db, "HP", "ách pi")
    text, anchors = coordinator.spoken_text_with_anchors({"text": "Chương IV: HP của Michael."})
    assert text == "Chương bốn: ách pi của Michael."
    assert [text[anchor["spoken_start"]:anchor["spoken_end"]] for anchor in anchors] == ["ách pi"]


def test_a_cue_still_becomes_a_breath_and_the_anchor_after_it_holds(tmp_path: Path) -> None:
    db, coordinator = _coordinator(tmp_path)
    _pronounce(db, "Michael", "Mai-cồ")
    text, anchors = coordinator.spoken_text_with_anchors({"text": "[thở dài] Aaaa, Michael đã đi."})
    assert text.startswith("Hầy...")
    assert [text[anchor["spoken_start"]:anchor["spoken_end"]] for anchor in anchors] == ["Mai-cồ"]


def test_the_book_origin_is_guessed_once(tmp_path: Path, monkeypatch) -> None:
    import abook.studio_names as studio_names

    db, coordinator = _coordinator(tmp_path)
    calls: list[int] = []
    monkeypatch.setattr(studio_names, "book_origin_for_project", lambda _db: calls.append(1))
    for _ in range(3):
        coordinator.spoken_text({"text": "Chương IV"})
    assert calls == [1]


def test_a_stretched_sigh_stays_the_studios_hay() -> None:
    text, _tags = studio_tn_tagged("Haizzz, tôi hiểu", [frozenset()] * 16, None, True)
    assert text == "Haizzz, tôi hiểu"  # `normalize_vocalizations_for_tts` đọc "Hầy"; luật theo chữ không đổi nó thành "hai"
