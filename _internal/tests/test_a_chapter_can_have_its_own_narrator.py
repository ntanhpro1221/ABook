"""Người kể "tôi" theo từng chương (`voices.first_person_chapters`) - 29-09.

Light novel hay có chương đổi góc kể: Love Unseen kể bằng "tôi" của Kakeru, nhưng "Chương 11: Yuuko Hayase" và
"Chương 12: Ushio Narumi" kể bằng "tôi" của chính người trong tên chương; Yamiyo đổi người kể theo chương. Một người kể
cho cả cuốn thì prompt nói SAI người ở đúng những chương ấy - và dòng "người kể xưng 'tôi' là X" là dòng đưa model từ
34,0% lên 89,4% người nói ở chương ngôi thứ nhất (YMP 248). Cuốn không đặt người kể theo chương phải thấy đúng prompt và
đúng dấu vân tay sổ ứng viên như trước, để sách đã phân tích resume y hệt.
"""
from __future__ import annotations

from typing import Any

from ebook_reader.analysis import OllamaBookAnalyzer, _analysis_policy_fingerprint, first_person_chapters
from ebook_reader.character_registry import resolve_first_person_labels
from ebook_reader.config import build_settings
from test_analysis_required import FakeDB


def _settings(identity: str = "KAKERU SORANO", chapters: dict[Any, str] | None = None) -> dict[str, Any]:
    settings = build_settings()
    settings["voices"]["first_person_identity"] = identity
    if chapters is not None:
        settings["voices"]["first_person_chapters"] = chapters
    return settings


def _analyzer(settings: dict[str, Any]) -> OllamaBookAnalyzer:
    db = FakeDB()
    db.chapters = [{"id": 1, "chapter_index": 10, "title": "Chương 10: Hai nụ pháo đỏ"},
                   {"id": 2, "chapter_index": 11, "title": "Chương 11: Yuuko Hayase"},
                   {"id": 3, "chapter_index": 12, "title": "Chương 12: Ushio Narumi"}]
    return OllamaBookAnalyzer(settings, db, lambda _message: None)


def _rows(*chapters: int) -> list[dict[str, Any]]:
    return [{"chapter_id": chapter, "stable_id": f"s{index}", "text": "."} for index, chapter in enumerate(chapters)]


def test_the_setting_reads_chapter_indexes_and_drops_pronouns() -> None:
    assert first_person_chapters(_settings(chapters={"11": "YUUKO HAYASE", 12: "USHIO NARUMI", "x": "A",
                                                     "13": "tôi", "14": ""})) == {
        11: "YUUKO HAYASE", 12: "USHIO NARUMI", 14: ""}, "khoá không phải số và đại từ bỏ; rỗng = ngôi thứ ba"
    assert first_person_chapters(_settings()) == {}


def test_a_book_without_chapter_narrators_keeps_its_prompt_and_its_ledger() -> None:
    plain = _analyzer(_settings())
    assert plain._narrator_line(_rows(2)) == plain._narrator_line() and "KAKERU SORANO" in plain._narrator_line()
    base = _analysis_policy_fingerprint(build_settings()["analysis"], None, "KAKERU SORANO")
    assert plain.analysis_policy_fingerprint == _analysis_policy_fingerprint(build_settings()["analysis"], None,
                                                                            "KAKERU SORANO", {})
    assert base == plain.analysis_policy_fingerprint
    pov = _analyzer(_settings(chapters={"11": "YUUKO HAYASE"}))
    assert pov.analysis_policy_fingerprint != base, "ứng viên sinh dưới người kể khác không được dùng lại"
    assert pov.analysis_policy_fingerprint != _analyzer(_settings(chapters={"11": "USHIO NARUMI"})).analysis_policy_fingerprint


def test_each_chapter_names_its_own_narrator() -> None:
    analyzer = _analyzer(_settings(chapters={"11": "YUUKO HAYASE", "12": ""}))
    line = analyzer._narrator_line(_rows(2, 2))
    assert "speaker=YUUKO HAYASE" in line and "KAKERU" not in line, "chương của Hayase: tôi là Hayase"
    assert "speaker=KAKERU SORANO" in analyzer._narrator_line(_rows(1)), "chương không đặt: người kể cả cuốn"
    assert analyzer._narrator_line(_rows(3)) == "", "chương đặt rỗng: kể ngôi thứ ba, prompt như cuốn ngôi ba"


def test_a_batch_across_two_narrators_names_both_by_chapter_title() -> None:
    line = _analyzer(_settings(chapters={"11": "YUUKO HAYASE", "12": ""}))._narrator_line(_rows(1, 2, 3))
    assert 'chương "Chương 10: Hai nụ pháo đỏ": người kể xưng "tôi" là KAKERU SORANO' in line
    assert 'chương "Chương 11: Yuuko Hayase": người kể xưng "tôi" là YUUKO HAYASE' in line
    assert 'chương "Chương 12: Ushio Narumi": kể ở ngôi thứ ba' in line
    assert line.index("Chương 10") < line.index("Chương 11") < line.index("Chương 12")


class _Db:
    """Hai chương, nhãn "tôi" ở cả hai - đúng dạng ProjectDB cho resolve_first_person_labels."""

    def __init__(self) -> None:
        self.chapters = [{"id": 1, "chapter_index": 10}, {"id": 2, "chapter_index": 11}, {"id": 3, "chapter_index": 12}]
        self.rows = [{"chapter_id": 1, "speaker": "Tôi"}, {"chapter_id": 2, "speaker": "Tôi"},
                     {"chapter_id": 2, "speaker": "ME"}, {"chapter_id": 3, "speaker": "tôi"},
                     {"chapter_id": 2, "speaker": "KOHARU"}]
        self.events: list[tuple[str, str, str, dict]] = []

    def list_chapters(self) -> list[dict[str, Any]]:
        return self.chapters

    def list_segments(self) -> list[dict[str, Any]]:
        return list(self.rows)

    def rewrite_speaker(self, old_name: str, canonical_name: str, *, chapter_ids: list[int] | None = None) -> int:
        moved = [row for row in self.rows if row["speaker"] == old_name
                 and (chapter_ids is None or row["chapter_id"] in chapter_ids)]
        for row in moved:
            row["speaker"] = canonical_name
        return len(moved)

    def event(self, level: str, code: str, message: str, payload: dict) -> None:
        self.events.append((level, code, message, payload))


def test_pronoun_labels_go_to_the_narrator_of_their_own_chapter() -> None:
    db = _Db()
    moved = resolve_first_person_labels(db, _settings(chapters={"11": "YUUKO HAYASE", "12": ""}), lambda _m: None)
    assert moved == 3
    assert [row["speaker"] for row in db.rows] == ["KAKERU SORANO", "YUUKO HAYASE", "YUUKO HAYASE", "tôi", "KOHARU"], \
        "chương 10 về người kể cả cuốn, chương 11 về Hayase, chương 12 (ngôi ba) để nguyên"
    assert db.events and db.events[0][1] == "FIRST_PERSON_LABELS_RESOLVED"


def test_a_real_database_runs_the_chapter_scoped_rewrite(tmp_path) -> None:
    from ebook_reader.database import ProjectDB

    db = ProjectDB(tmp_path / "project.sqlite3")
    assert db.rewrite_speaker("Tôi", "YUUKO HAYASE", chapter_ids=[]) == 0
    assert db.rewrite_speaker("Tôi", "YUUKO HAYASE", chapter_ids=[1, 2]) == 0, "câu SQL theo chương chạy được"
    assert db.rewrite_speaker("Tôi", "YUUKO HAYASE") == 0


def test_the_command_line_takes_chapter_narrators_and_refuses_what_cannot_work() -> None:
    import argparse

    import pytest

    from ebook_reader.cli import CliUsageError, _settings_from_args
    from ebook_reader.config import validate_settings

    def _args(**overrides: Any) -> argparse.Namespace:
        base: dict[str, Any] = {"settings_file": None, "profile": "high_quality", "first_person": "KAKERU SORANO",
                                "first_person_chapter": None}
        base.update(overrides)
        return argparse.Namespace(**base)

    assert "first_person_chapters" not in _settings_from_args(_args())["voices"], "chỉ ghi khi được nói ra"
    chosen = _settings_from_args(_args(first_person_chapter=["11=YUUKO HAYASE", " 12 = USHIO NARUMI ", "13="]))
    assert chosen["voices"]["first_person_chapters"] == {"11": "YUUKO HAYASE", "12": "USHIO NARUMI", "13": ""}
    validate_settings(chosen)
    for bad in (["11"], ["x=A"], ["11=tôi"]):
        with pytest.raises(CliUsageError):
            _settings_from_args(_args(first_person_chapter=bad))
    with pytest.raises(CliUsageError):
        _settings_from_args(_args(first_person="", first_person_chapter=["11=A"], settings_file="s.json"))
    broken = _settings(chapters={"một": "A"})
    with pytest.raises(ValueError, match="first_person_chapters"):
        validate_settings(broken)
