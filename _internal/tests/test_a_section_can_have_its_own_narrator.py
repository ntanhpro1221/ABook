"""Người kể theo ĐOẠN (narrator_sections.py + webui/narrator_cards.py) - 07-10.

Bộ phát hiện D chạy trên vài chương gold thật (Corpus, chỉ đọc; bỏ qua nếu máy không có). Dây chuyền: người kể của đoạn đã
nhận vào prompt của lô chạm đoạn ấy và vào khoá LÔ - không vào khoá cấp cuốn, và sách không có đoạn nào được nhận thì prompt,
khoá cuốn, khoá lô y hệt hôm nay. Đọc lại ở mỗi lô (resume thấy đúng giá trị đã lưu).
"""
from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from abook import narrator_sections
from abook.analysis import (
    OllamaBookAnalyzer,
    _analysis_context_hash,
    _analysis_group_fingerprint,
    _analysis_policy_fingerprint,
    _original_neighbor_context,
)
from abook.character_registry import resolve_first_person_labels
from abook.config import build_settings
from abook.io_utils import decode_text_bytes
from abook.text_processing import segment_chapter_text
from test_analysis_required import FakeDB

CORPUS = Path("D:/Novels/ABook/Corpus")


# ---- bộ phát hiện trên chương gold thật --------------------------------------------------------------------------------
@pytest.mark.parametrize(("book", "chapter", "narrator", "expected"), [
    ("Shimotsuki wa Mob ga Suki", "195", "NAKAYAMA KOUTAROU", [(0, 57)]),  # cả chương do người khác kể (r1 = 0, r3 = 12,3)
    ("Shimotsuki wa Mob ga Suki", "029", "NAKAYAMA KOUTAROU", []),  # chương do chính người kể kể: không báo
    ("Me ke", "031", "ABIGAIL", [(0, 78)]),  # đoạn 1 (r1 0,8, r3 2,3) báo; đoạn 2 (r1 32,8) không
    ("The Villain Wants to Live", "22", "DECULEIN", [(0, 57), (117, 283)]),  # 4/5 đoạn báo, hai khoảng liền nhau gộp (bộ chia câu ở cây này ra thêm 1 câu so với cây của đáp án: 0-56, 116-282)
])
def test_the_detector_finds_the_sections_measured_on_gold_chapters(book: str, chapter: str, narrator: str, expected: list) -> None:
    source = CORPUS / book / f"{chapter}.txt"
    if not source.is_file():
        pytest.skip("Corpus không có trên máy này")
    raw = decode_text_bytes(source.read_bytes())
    rows = segment_chapter_text(1, raw, max_chars=340)
    found = narrator_sections.detect(raw, rows, narrator)
    assert [(item["from_seq"], item["to_seq"]) for item in found] == expected


# ---- dây chuyền: prompt + khoá --------------------------------------------------------------------------------------------
def _settings(identity: str = "KAKERU SORANO") -> dict[str, Any]:
    settings = build_settings()
    if identity:
        settings["voices"]["first_person_identity"] = identity
    return settings


def _analyzer(tmp_path: Path, settings: dict[str, Any] | None = None) -> OllamaBookAnalyzer:
    db = FakeDB()
    db.path = tmp_path / "project.sqlite3"
    db.chapters = [{"id": 1, "chapter_index": 10, "title": "Chương 10"}, {"id": 2, "chapter_index": 11, "title": "Chương 11"}]
    db.rows = [
        {"id": index, "stable_id": f"s{index}", "chapter_id": 1 if index < 8 else 2, "seq": index if index < 8 else index - 8,
         "text": f"Câu số {index}.", "kind_hint": "narration", "status": "pending", "speaker": None, "paragraph_index": index}
        for index in range(12)
    ]
    return OllamaBookAnalyzer(settings or _settings(), db, lambda _message: None)


def _save(tmp_path: Path, *entries: tuple[int, int, int, str, bool]) -> None:
    for chapter_index, first, last, narrator, accepted in entries:
        narrator_sections.decide(tmp_path, chapter_index, first, last, accepted=accepted, narrator=narrator,
                                 source="owner" if narrator else "auto")


def _group(analyzer: OllamaBookAnalyzer, *positions: int) -> list[Any]:
    return [analyzer.db.rows[position] for position in positions]


def test_a_book_with_no_accepted_section_keeps_its_prompt_and_both_fingerprints(tmp_path: Path) -> None:
    analyzer = _analyzer(tmp_path)
    group = _group(analyzer, 2, 3, 4)
    context = _original_neighbor_context(analyzer.db.rows)
    before = (analyzer._narrator_line(group), _analysis_group_fingerprint(group, context),
              _analysis_context_hash(group, context), analyzer.analysis_policy_fingerprint, copy.deepcopy(context))
    analyzer._bind_narrator_sections(group, context)
    assert (analyzer._narrator_line(group), _analysis_group_fingerprint(group, context), _analysis_context_hash(group, context),
            analyzer.analysis_policy_fingerprint, context) == before
    assert "speaker=KAKERU SORANO" in before[0]
    assert analyzer.analysis_policy_fingerprint == _analysis_policy_fingerprint(_settings()["analysis"], None, "KAKERU SORANO")
    # Đã bỏ qua (hay một đoạn chưa nhận) cũng không đổi gì.
    _save(tmp_path, (10, 2, 4, "", False))
    analyzer._bind_narrator_sections(group, context)
    assert (analyzer._narrator_line(group), _analysis_group_fingerprint(group, context)) == before[:2]


def test_an_accepted_section_changes_the_prompt_and_the_key_of_its_batches_only(tmp_path: Path) -> None:
    analyzer = _analyzer(tmp_path)
    context = _original_neighbor_context(analyzer.db.rows)
    inside, outside, across = _group(analyzer, 2, 3, 4), _group(analyzer, 5, 6, 7), _group(analyzer, 1, 2, 3)
    before = {name: _analysis_group_fingerprint(group, context) for name, group in
              {"inside": inside, "outside": outside, "across": across}.items()}
    policy = analyzer.analysis_policy_fingerprint
    _save(tmp_path, (10, 2, 4, "", True))
    for group in (inside, outside, across):
        analyzer._bind_narrator_sections(group, context)
        name = {id(inside): "inside", id(outside): "outside", id(across): "across"}[id(group)]
        changed = _analysis_group_fingerprint(group, context) != before[name]
        assert changed == (name != "outside"), name
    assert analyzer.analysis_policy_fingerprint == policy, "khoá cấp cuốn không đổi: nhận một đoạn không làm hỏng cả cuốn"
    analyzer._bind_narrator_sections(inside, context)
    assert analyzer._narrator_line(inside) == "", "cả lô nằm trong đoạn ngôi ba: không có người kể xưng tôi"
    analyzer._bind_narrator_sections(across, context)
    line = analyzer._narrator_line(across)
    assert line.startswith("Truyện đổi người kể theo đoạn:")
    assert '- đoạn S001 (từ câu 1 của chương "Chương 10"): người kể xưng "tôi" là KAKERU SORANO' in line
    assert '- các đoạn S002 đến S003 (từ câu 2 của chương "Chương 10"): kể ở ngôi thứ ba, không có người kể xưng "tôi"' in line
    analyzer._bind_narrator_sections(outside, context)
    assert analyzer._narrator_line(outside) == analyzer._narrator_line(_group(analyzer, 5)), "lô ngoài đoạn: như hôm nay"


def test_a_section_can_name_another_narrator_and_is_read_again_at_every_batch(tmp_path: Path) -> None:
    analyzer = _analyzer(tmp_path)
    context = _original_neighbor_context(analyzer.db.rows)
    group = _group(analyzer, 2, 3)
    _save(tmp_path, (10, 2, 4, "YUUKO HAYASE", True))
    analyzer._bind_narrator_sections(group, context)
    assert "speaker=YUUKO HAYASE" in analyzer._narrator_line(group) and "KAKERU" not in analyzer._narrator_line(group)
    first_key = _analysis_group_fingerprint(group, context)
    _save(tmp_path, (10, 2, 4, "USHIO NARUMI", True))  # người dùng đổi ý giữa hai lô
    analyzer._bind_narrator_sections(group, context)
    assert "speaker=USHIO NARUMI" in analyzer._narrator_line(group)
    assert _analysis_group_fingerprint(group, context) != first_key
    assert narrator_sections.forget(tmp_path, 10, 2, 4)
    analyzer._bind_narrator_sections(group, context)
    assert "speaker=KAKERU SORANO" in analyzer._narrator_line(group), "bỏ quyết định: về người kể của cuốn"
    assert "narrator_section" not in context[group[0]["stable_id"]]


def test_a_book_without_a_first_person_narrator_ignores_the_file(tmp_path: Path) -> None:
    analyzer = _analyzer(tmp_path, _settings(identity=""))
    context = _original_neighbor_context(analyzer.db.rows)
    group = _group(analyzer, 2, 3)
    before = (analyzer._narrator_line(group), _analysis_group_fingerprint(group, context))
    _save(tmp_path, (10, 2, 4, "YUUKO HAYASE", True))
    analyzer._bind_narrator_sections(group, context)
    assert before == (analyzer._narrator_line(group), _analysis_group_fingerprint(group, context)) and before[0] == ""


def test_a_damaged_or_odd_file_means_no_decision(tmp_path: Path) -> None:
    (tmp_path / narrator_sections.FILE_NAME).write_text("{không phải json", encoding="utf-8")
    assert narrator_sections.load(tmp_path) == {}
    (tmp_path / narrator_sections.FILE_NAME).write_text(json.dumps({"sections": {"10": [{"from_seq": 5, "to_seq": 2},
                                                                                       {"from_seq": "x"}, 7], "z": []}}), encoding="utf-8")
    assert narrator_sections.load(tmp_path) == {}
    assert narrator_sections.narrator_at({}, 10, 3) is None


# ---- sau phân tích: nhãn "tôi" theo người kể của đoạn ---------------------------------------------------------------------
class _Db:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.chapters = [{"id": 1, "chapter_index": 10}]
        self.rows = [{"chapter_id": 1, "seq": seq, "speaker": "Tôi"} for seq in range(6)]

    def list_chapters(self) -> list[dict[str, Any]]:
        return self.chapters

    def list_segments(self) -> list[dict[str, Any]]:
        return list(self.rows)

    def rewrite_speaker(self, old: str, new: str, *, chapter_ids: list[int] | None = None, only_ranges=None, except_ranges=None) -> int:
        moved = 0
        for row in self.rows:
            span = (row["chapter_id"], row["seq"])
            if row["speaker"] != old or (chapter_ids is not None and row["chapter_id"] not in chapter_ids):
                continue
            if only_ranges is not None and not any(c == span[0] and a <= span[1] <= b for c, a, b in only_ranges):
                continue
            if any(c == span[0] and a <= span[1] <= b for c, a, b in except_ranges or ()):
                continue
            row["speaker"] = new
            moved += 1
        return moved

    def event(self, *_args: Any) -> None:
        pass


def test_pronoun_labels_follow_the_narrator_of_their_section(tmp_path: Path) -> None:
    db = _Db(tmp_path / "project.sqlite3")
    _save(tmp_path, (10, 1, 2, "", True), (10, 4, 5, "YUUKO HAYASE", True), (10, 3, 3, "", False))
    resolve_first_person_labels(db, _settings(), lambda _m: None)
    assert [row["speaker"] for row in db.rows] == [
        "KAKERU SORANO", "Tôi", "Tôi", "KAKERU SORANO", "YUUKO HAYASE", "YUUKO HAYASE"]  # ngôi ba để nguyên; chưa nhận = theo cuốn


def test_without_sections_the_registry_makes_the_same_calls_as_before(tmp_path: Path) -> None:
    db = _Db(tmp_path / "project.sqlite3")
    resolve_first_person_labels(db, _settings(), lambda _m: None)
    assert {row["speaker"] for row in db.rows} == {"KAKERU SORANO"}


def test_the_real_database_runs_range_scoped_rewrites(tmp_path: Path) -> None:
    from abook.database import ProjectDB

    db = ProjectDB(tmp_path / "project.sqlite3")
    assert db.rewrite_speaker("Tôi", "X", only_ranges=[]) == 0
    assert db.rewrite_speaker("Tôi", "X", only_ranges=[(1, 2, 4), (2, 0, 1)]) == 0
    assert db.rewrite_speaker("Tôi", "X", chapter_ids=[1], except_ranges=[(1, 2, 4)]) == 0


# ---- thẻ trong hộp "Việc cần duyệt" ----------------------------------------------------------------------------------------
FIRST = "Tôi bước vào lớp. Tôi nhìn quanh và thấy cả phòng yên tĩnh, tôi ngồi xuống chỗ quen thuộc, tôi mở sách ra đọc."
THIRD = ("Kakeru bước vào lớp. Kakeru nhìn quanh và thấy cả phòng yên tĩnh, Kakeru ngồi xuống chỗ quen thuộc, "
         "Kakeru mở sách ra đọc.")


def _book(root: Path, identity: str = "Kakeru") -> tuple[Path, list[dict[str, Any]]]:
    project = root / "sach"
    project.mkdir()
    source = root / "001.txt"
    text = f"Chương 1\n\n{FIRST}\n\n***\n\n{THIRD}\n\n***\n\n{FIRST}\n"
    source.write_bytes(text.encode("utf-8"))
    settings = {"voices": {"first_person_identity": identity} if identity else {}, "tts": {"max_segment_chars": 340}}
    (project / "book_settings.json").write_text(json.dumps(settings), encoding="utf-8")
    rows = segment_chapter_text(1, text, max_chars=340)
    db = sqlite3.connect(project / "project.sqlite3")
    db.executescript(
        """
        CREATE TABLE chapters (id INTEGER PRIMARY KEY, chapter_index INTEGER, title TEXT, input_path TEXT);
        CREATE TABLE segments (id INTEGER PRIMARY KEY, stable_id TEXT, chapter_id INTEGER, seq INTEGER, text TEXT,
                               kind TEXT, kind_hint TEXT, speaker TEXT, voice_profile_id INTEGER, canonical_character_id INTEGER,
                               status TEXT, asr_text TEXT, asr_similarity REAL, warning_code TEXT, wav_path TEXT,
                               text_sha256 TEXT, gender TEXT);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, canonical_name TEXT, display_name TEXT, gender TEXT,
                                 locked INTEGER, age TEXT);
        CREATE TABLE pronunciations (surface TEXT, spoken_form TEXT, confidence REAL, locked INTEGER);
        """
    )
    db.execute("INSERT INTO chapters VALUES (1, 1, '001', ?)", (str(source),))
    db.executemany(
        "INSERT INTO segments (id, stable_id, chapter_id, seq, text, kind, kind_hint, speaker, status, text_sha256)"
        " VALUES (?,?,1,?,?,?,?,?,'pending',?)",
        [(index + 1, row["stable_id"], row["seq"], row["text"], row["kind"], row["kind_hint"], "NARRATOR", row["text_sha256"])
         for index, row in enumerate(rows)])
    db.commit()
    db.close()
    return project, rows


def test_the_inbox_offers_the_section_and_a_decision_is_stored_beside_the_database(tmp_path: Path) -> None:
    from abook.webui import narrator_cards
    from abook.webui.work_items import work_items

    project, rows = _book(tmp_path)
    cards = [item for item in work_items(project)["items"] if item["kind"] == "narrator"]
    assert len(cards) == 1 and cards[0]["requested"] is None
    middle = [row for row in rows if "Kakeru" in row["text"]]
    section = cards[0]["narratorSection"]
    assert (section["fromSeq"], section["toSeq"]) == (middle[0]["seq"], middle[-1]["seq"]) and section["chapterIndex"] == 1
    assert "không phải Kakeru kể" in cards[0]["title"] and section["appliesNote"] == "", "chưa phân tích: áp ngay"
    narrator_cards.decide(project, {"chapterIndex": 1, "fromSeq": section["fromSeq"], "toSeq": section["toSeq"], "action": "accept"})
    assert narrator_sections.narrator_at(narrator_sections.load(project), 1, middle[0]["seq"]) == ""
    card = [item for item in work_items(project)["items"] if item["kind"] == "narrator"][0]
    assert card["requested"] == "Đổi người kể"
    narrator_cards.decide(project, {"chapterIndex": 1, "fromSeq": section["fromSeq"], "toSeq": section["toSeq"],
                                    "action": "choose", "narrator": "Ushio"})
    assert [item for item in work_items(project)["items"] if item["kind"] == "narrator"][0]["requested"] == "Người kể: Ushio"
    narrator_cards.decide(project, {"chapterIndex": 1, "fromSeq": section["fromSeq"], "toSeq": section["toSeq"], "withdraw": True})
    assert [item for item in work_items(project)["items"] if item["kind"] == "narrator"][0]["requested"] is None


def test_a_chapter_already_analysed_says_the_change_waits_for_a_redo(tmp_path: Path) -> None:
    from abook.webui.work_items import work_items

    project, _rows = _book(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE segments SET status='verified'")
    db.commit()
    db.close()
    card = [item for item in work_items(project)["items"] if item["kind"] == "narrator"][0]
    assert card["narratorSection"]["appliesNote"] == "Chương này đã phân tích xong - đổi sẽ áp khi làm lại sách."


def test_a_book_without_a_narrator_gets_no_card_and_a_stale_range_is_refused(tmp_path: Path) -> None:
    from abook.webui import narrator_cards
    from abook.webui.work_items import work_items

    project, _rows = _book(tmp_path, identity="")
    assert not [item for item in work_items(project)["items"] if item["kind"] == "narrator"]
    with pytest.raises(ValueError):
        narrator_cards.decide(project, {"chapterIndex": 1, "fromSeq": 3, "toSeq": 4, "action": "accept"})
    (tmp_path / "again").mkdir()
    other, _rows = _book(tmp_path / "again")
    proposal = narrator_cards.proposals(other)[0]
    with pytest.raises(ValueError, match="đại từ"):
        narrator_cards.decide(other, {"chapterIndex": 1, "fromSeq": proposal["from_seq"], "toSeq": proposal["to_seq"],
                                      "action": "choose", "narrator": "tôi"})


def test_a_one_line_section_says_line_not_a_range_and_suggests_the_names_in_it(tmp_path: Path) -> None:
    """Soát UX a8: "câu 6–6" -> "câu 6"; "Chọn người kể…" gợi sẵn tên riêng có mặt trong đoạn (sổ nhân vật có thể còn trống)."""
    from abook.webui import narrator_cards
    from abook.webui.work_items import work_items

    names = narrator_cards.section_names(
        ["Mai ngồi một mình. Cô gọi Lâm Hạ, rồi Mai thở dài, và Lâm Hạ quay lại.", "Anh nhìn Hạ Vy."], {"Kakeru"})
    assert names == ["Lâm Hạ", "Mai", "Hạ Vy"], names
    assert "Kakeru" not in narrator_cards.section_names(["Rồi Kakeru cười. Sau đó Kakeru đi."], {"Kakeru"})

    project, rows = _book(tmp_path)
    card = [item for item in work_items(project)["items"] if item["kind"] == "narrator"][0]
    section = card["narratorSection"]
    where = f"câu {section['fromSeq']}" if section["fromSeq"] == section["toSeq"] else f"câu {section['fromSeq']}–{section['toSeq']}"
    assert card["title"].endswith(f"{where}: có vẻ không phải Kakeru kể")
    assert "Kakeru" not in [choice["label"] for choice in section["choices"]], "người kể của sách không phải gợi ý"


def test_a_decided_narrator_card_carries_the_withdrawal_of_the_decision(tmp_path: Path) -> None:
    from abook.webui import narrator_cards
    from abook.webui.work_items import work_items

    project, _rows = _book(tmp_path)
    section = narrator_cards.proposals(project)[0]
    narrator_cards.decide(project, {"chapterIndex": 1, "fromSeq": section["from_seq"], "toSeq": section["to_seq"], "action": "accept"})
    card = [item for item in work_items(project)["items"] if item["kind"] == "narrator"][0]
    assert card["undo"] == {"endpoint": "narrator-section", "decisions": [
        {"chapterIndex": 1, "fromSeq": section["from_seq"], "toSeq": section["to_seq"]}]}


def test_a_card_that_only_a_redo_can_apply_goes_last_and_stops_saying_the_machine_keeps_it(tmp_path: Path) -> None:
    """Soát UX a13 #1: đoạn đã phân tích xong thì lựa chọn chỉ áp khi làm lại sách - thẻ không được xếp trên việc áp ngay."""
    from abook.webui import narrator_cards
    from abook.webui.work_items import work_items

    project, _rows = _book(tmp_path)
    card = [item for item in work_items(project)["items"] if item["kind"] == "narrator"][0]
    assert not card["redoOnly"] and "Chưa trả lời thì máy giữ nguyên" in card["problem"], "chưa phân tích: áp ngay, như cũ"
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE segments SET status='verified'")
    # Một thẻ khác, điểm thấp hơn hẳn: một cách đọc tên máy kém chắc.
    db.execute("INSERT INTO pronunciations VALUES ('Zed', 'zét', 0.2, 0)")
    db.execute("UPDATE segments SET text = text || ' Zed.' WHERE seq = 1")
    db.commit()
    db.close()
    items = work_items(project)["items"]
    kinds = [item["kind"] for item in items]
    assert len(kinds) > 1 and kinds[-1] == "narrator" and items[-1]["redoOnly"] and items[-1]["score"] > 0, kinds
    section = items[-1]["narratorSection"]
    narrator_cards.decide(project, {"chapterIndex": 1, "fromSeq": section["fromSeq"], "toSeq": section["toSeq"], "action": "accept"})
    answered = [item for item in work_items(project)["items"] if item["kind"] == "narrator"][0]
    assert answered["requested"] == "Đổi người kể" and answered["redoOnly"]
    assert "Chưa trả lời" not in answered["problem"]


def test_overlapping_name_fragments_keep_the_longest_name_that_does_not_overlap(tmp_path: Path) -> None:
    """Soát UX a13 #11: "Thiên Biến Vạn", "Biến Vạn Hóa", "Hóa Krai Andrey" là mảnh của cùng một cụm tên - gợi ý chỉ giữ không chồng."""
    from abook.webui import narrator_cards

    texts = ["Rồi Thiên Biến Vạn Hóa Krai Andrey bước vào.", "Lúc ấy Thiên Biến Vạn gật đầu.", "Gặp Biến Vạn Hóa, Mai cười."]
    names = narrator_cards.section_names(texts, set())
    assert "Biến Vạn Hóa" not in names and "Thiên Biến Vạn" in names, names
    assert not any(narrator_cards._overlap(a, b) for a in names for b in names if a != b), names
    assert not narrator_cards._overlap("Lâm Hạ", "Hạ Vy"), "chung một chữ vẫn là hai người"
    assert narrator_cards._overlap("Krai", "Krai Andrey")
