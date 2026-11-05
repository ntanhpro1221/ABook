"""Một người phụ không tên = MỘT giọng trong một chương, dù người nói nằm ở nhóm phân tích nào.

Ca thật (Three Days of Happiness, chương 13): "giám sát viên thay thế" nói ở hai nhóm ~5 đoạn liền cảnh; mã cũ băm
đoạn đầu + đoạn cuối của NHÓM vào ID (`NPC_LOCAL::c00013::r<hash>::nhãn`), nên cùng một người thành hai danh tính, hai giọng.
Luật mới: ID = (chương, nhãn đã chuẩn hoá) - `analysis.local_speaker_id`, dùng chung cho phân tích, lượt người nói, sổ nhân vật.
"""
from __future__ import annotations

from pathlib import Path

from abook.analysis import (
    OllamaBookAnalyzer,
    _scope_local_speaker,
    _validate,
    is_local_speaker,
    local_speaker_display,
    local_speaker_id,
    local_speaker_label,
    normalize_local_label,
)
from abook.character_registry import assert_voice_stability, build_registry_and_cast
from abook.config import build_settings
from abook.speaker_pass import db_label
from tests.test_character_casting import _identity_db
from tests.test_listener_speakers import _apply, _book, _segment
from test_analysis_required import FakeDB, _accept_second_pass_director_critic, analysis_item  # noqa: F401 (autouse)


def _rows(chapters: list[int]) -> list[dict]:
    return [
        {
            "id": index,
            "stable_id": f"c{chapter}s{index}",
            "chapter_id": chapter,
            "text": f"Đoạn {index}.",
            "kind_hint": "dialogue",
            "status": "pending",
            "speaker": None,
        }
        for index, chapter in enumerate(chapters, 1)
    ]


def _run_analysis(monkeypatch, chapters: list[int], labels: list[str], batch_segments: int = 2) -> list[str]:
    """Chạy `analyze_all` với model giả trả `NPC_LOCAL:<nhãn>` cho từng đoạn; trả người nói đã lưu theo thứ tự đoạn."""
    db = FakeDB()
    db.rows = _rows(chapters)
    settings = build_settings(overrides={"analysis": {"batch_segments": batch_segments, "batch_chars": 10000}})
    analyzer = OllamaBookAnalyzer(settings, db, lambda _message: None)
    monkeypatch.setattr(analyzer, "ensure_available", lambda: True)
    label_by_id = {row["stable_id"]: label for row, label in zip(db.rows, labels)}

    def request(group, **_kwargs):
        items = []
        for row in group:
            item = analysis_item(str(row["stable_id"]))
            item.update({"kind": "dialogue", "speaker": f"NPC_LOCAL:{label_by_id[row['stable_id']]}", "gender": "male"})
            items.append(item)
        return {"segments": items}

    monkeypatch.setattr(analyzer, "_request", request)
    analyzer.analyze_all(lambda: False)
    saved = {int(segment_id): str(data["speaker"]) for segment_id, data, _threshold in db.updated}
    return [saved[row["id"]] for row in db.rows]


def test_the_label_key_ignores_case_spacing_and_edge_punctuation_but_not_diacritics_or_numbers() -> None:
    assert normalize_local_label("Lính gác") == normalize_local_label("  lính   GÁC. ") == "lính gác"
    assert normalize_local_label("lính gác 1") != normalize_local_label("lính gác 2")
    assert normalize_local_label("má") != normalize_local_label("ma")
    # Tên riêng đứng sau từ đầu giữ chữ hoa: `_honorific_target` nhận ra "tiểu thư Clara" nhờ nó.
    assert normalize_local_label("Tiểu thư Clara") == "tiểu thư Clara"
    assert normalize_local_label("a:b|c") == "a b c"
    assert local_speaker_id(3, "  ") == "UNKNOWN"


def test_two_analysis_groups_in_one_chapter_share_one_identity(monkeypatch) -> None:
    # batch_segments=2 -> 3 nhóm; cùng người nói ở nhóm 1 và 3, nhãn viết hoa/cách khác nhau.
    speakers = _run_analysis(
        monkeypatch, [1] * 6, ["Giám sát viên", "giám sát viên", "áo đỏ", "áo đỏ", "giám sát viên ", "GIÁM SÁT VIÊN."],
    )
    assert speakers[0] == speakers[1] == speakers[4] == speakers[5] == "NPC_LOCAL::c00001::giám sát viên"
    assert speakers[2] == speakers[3] == "NPC_LOCAL::c00001::áo đỏ"
    assert all(is_local_speaker(speaker) for speaker in speakers)
    assert local_speaker_display(speakers[0]) == "NPC giám sát viên"


def test_the_same_label_in_two_chapters_is_two_people_and_different_labels_are_different(monkeypatch) -> None:
    speakers = _run_analysis(
        monkeypatch, [1, 1, 2, 2, 2, 2],
        ["lính gác 1", "lính gác 2", "lính gác 1", "lính gác 1", "lính gác 2", "lính gác 2"],
    )
    assert speakers[0] == "NPC_LOCAL::c00001::lính gác 1"
    assert speakers[1] == "NPC_LOCAL::c00001::lính gác 2"
    assert speakers[2] == speakers[3] == "NPC_LOCAL::c00002::lính gác 1"
    assert speakers[4] == speakers[5] == "NPC_LOCAL::c00002::lính gác 2"
    assert len(set(speakers)) == 4


def test_the_speaker_pass_and_the_analysis_write_the_same_id() -> None:
    group = [{"id": 1, "stable_id": "c00007_s0", "chapter_id": 7, "text": "“Đứng lại!”", "kind_hint": "dialogue"}]
    item = analysis_item("c00007_s0")
    item.update({"kind": "dialogue", "speaker": "NPC_LOCAL:Lính gác", "gender": "male"})
    from_analysis = _validate(group, {"segments": [item]})["c00007_s0"]["speaker"]

    assert db_label("NPC_LOCAL:lính  gác", 7) == from_analysis == local_speaker_id(7, "lính gác")
    assert db_label("NPC_LOCAL::lính gác", 7) == from_analysis
    assert _scope_local_speaker("NPC_LOCAL:lính gác", {"chapter_id": 7}) == from_analysis
    assert local_speaker_label(from_analysis) == "lính gác"


def test_one_local_identity_is_one_character_with_one_voice(tmp_path: Path, monkeypatch) -> None:
    speakers = _run_analysis(
        monkeypatch, [1] * 6, ["giám sát viên", "áo đỏ", "áo đỏ", "áo đỏ", "Giám sát viên", "giám sát viên"],
    )
    db = _identity_db(tmp_path, [("NARRATOR", "unknown"), *[(speaker, "male") for speaker in speakers]])

    build_registry_and_cast(db, build_settings(), lambda _message: None)
    assert_voice_stability(db)

    by_speaker: dict[str, set[tuple[int, int]]] = {}
    for row in db.list_segments():
        if is_local_speaker(row["speaker"]):
            by_speaker.setdefault(str(row["speaker"]), set()).add((int(row["canonical_character_id"]), int(row["voice_profile_id"])))
    assert set(by_speaker) == {"NPC_LOCAL::c00001::giám sát viên", "NPC_LOCAL::c00001::áo đỏ"}
    assert all(len(pairs) == 1 for pairs in by_speaker.values()), by_speaker


def test_a_studio_edit_onto_a_local_speaker_keeps_its_id(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)
    local = local_speaker_id(1, "lính gác")
    key = local.upper()  # = character_registry.canonical_key
    with db.connect() as conn:
        conn.execute("INSERT INTO characters(canonical_name,display_name,gender,age,personality,importance,mention_count,"
                     "confidence,locked,created_at,updated_at) VALUES(?,?,'male','adult','','minor',1,1,0,0,0)",
                     (key, local_speaker_display(local)))
        conn.execute("UPDATE segments SET speaker=?, canonical_character_id=(SELECT id FROM characters WHERE canonical_name=?),"
                     " voice_profile_id=(SELECT id FROM voice_profiles WHERE voice_key='v_anon_m') WHERE stable_id='c1s4'", (local, key))

    result = _apply(db, "c1s2", local)

    assert result is not None and result["previous_speaker"] == "Lucien"
    assert _segment(db, "c1s2")["speaker"] == local == _segment(db, "c1s4")["speaker"]
    assert _segment(db, "c1s2")["voice_key"] == _segment(db, "c1s4")["voice_key"]
