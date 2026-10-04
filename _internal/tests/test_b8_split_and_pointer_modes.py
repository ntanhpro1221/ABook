"""B8 (nhánh dev/breakthrough-eval, chỉ để đo): ABOOK_SPEAKER_ONLY / ABOOK_POINTER_MODE / ABOOK_EMOTION_ONLY.

Tắt thì request y hệt; bật thì thân b và d chung, dòng việc ở cuối, schema rút gọn, host điền phần còn lại; con trỏ dựng,
đổi ngược và con trỏ hỏng -> PointerError (ValueError, vòng thử lại xử lý như JSON hỏng).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ebook_reader import eval_hooks, field_mode, pointer_mode
from ebook_reader.analysis import (
    DIRECTOR_CRITIC_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    OllamaBookAnalyzer,
    _batch_id,
    _host_affect_adjudication,
    _semantic_delivery_issues,
)
from ebook_reader.config import build_settings
from test_a_batch_sees_who_spoke_just_before import ChapterDB
from test_analysis_required import FakeSession, analysis_item

VARS = ("ABOOK_POINTER_MODE", "ABOOK_POINTER_GOLD_NAMES", "ABOOK_SPEAKER_ONLY", "ABOOK_EMOTION_ONLY", "ABOOK_EMOTION_GOLD",
        "ABOOK_PROMPT_DUMP", "ABOOK_GOLD_PREVIOUS", "ABOOK_ORACLE_DIR", "ABOOK_EVAL_SETTINGS")
CHAPTER = "Chương 1"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in VARS:
        monkeypatch.delenv(name, raising=False)
    eval_hooks._cache.clear()


def _row(seq: int, kind: str, speaker: str, text: str, status: str = "analyzed") -> dict[str, Any]:
    return {"id": seq + 1, "stable_id": f"c00001_s{seq:07d}_x", "chapter_id": 1, "seq": seq, "paragraph_index": seq,
            "kind": kind, "kind_hint": kind, "speaker": speaker, "text": text, "status": status, "gender": "unknown"}


def _rows() -> list[dict[str, Any]]:
    return [
        _row(0, "narration", "NARRATOR", "Trời mưa. Rồi Yanami bước vào quán."),
        _row(1, "dialogue", "LUCIEN", "“Đi thôi!”"),
        _row(2, "dialogue", "NPC_LOCAL::c00001::r9::bà chủ quán", "“Ừ.”"),
        _row(3, "dialogue", "", "“Đợi đã, Lucien.”", status="pending"),
        _row(4, "dialogue", "", "“Gì nữa?”", status="pending"),
    ]


def _item(batch_id: str, **fields: Any) -> dict[str, Any]:
    return {**analysis_item(batch_id), **fields}


def _call(payload: dict[str, Any], rows: list[dict[str, Any]] | None = None, narrator: str = "") -> tuple[dict, dict]:
    rows = rows or _rows()
    group = [row for row in rows if row["status"] == "pending"]
    settings = build_settings()
    if narrator:
        settings["voices"]["first_person_identity"] = narrator
    analyzer = OllamaBookAnalyzer(settings, ChapterDB(rows), lambda _message: None)
    analyzer.session = FakeSession(payload)
    analyzer._model_digest = "sha256:test-model-digest"
    analyzer._speaker_counts.update({"LUCIEN": 3, "YANAMI": 2})
    result = analyzer._request(group)
    return analyzer.session.request["json"], result


def _names_payload() -> dict[str, Any]:
    return {"segments": [_item("S001", kind="dialogue", speaker="YANAMI"), _item("S002", kind="dialogue", speaker="LUCIEN")]}


# --- tắt = y hệt -------------------------------------------------------------------------------------------


def test_off_and_zero_mean_the_exact_same_request(monkeypatch: pytest.MonkeyPatch) -> None:
    plain, _ = _call(_names_payload())
    assert plain["system"] == SYSTEM_PROMPT
    assert "emotion" in json.dumps(plain["format"]) and "gender" in json.dumps(plain["format"])
    assert "Con trỏ" not in plain["prompt"] and "NHIỆM VỤ" not in plain["prompt"]
    for name in ("ABOOK_POINTER_MODE", "ABOOK_SPEAKER_ONLY", "ABOOK_EMOTION_ONLY"):
        monkeypatch.setenv(name, "0")
    monkeypatch.setenv("ABOOK_POINTER_GOLD_NAMES", "")
    again, _ = _call(_names_payload())
    assert again == plain
    assert field_mode.mode() == "" and pointer_mode.enabled() is False
    assert field_mode.generator_system(SYSTEM_PROMPT, "") == SYSTEM_PROMPT


def test_emotion_only_cannot_be_combined_with_speaker_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABOOK_EMOTION_ONLY", "1")
    monkeypatch.setenv("ABOOK_POINTER_MODE", "1")
    with pytest.raises(ValueError):
        field_mode.mode()


# --- dựng con trỏ ------------------------------------------------------------------------------------------


def test_pointer_context_lists_quotes_nearest_first_and_names_in_the_window() -> None:
    window = [("narration", "NARRATOR", "Trời mưa. Rồi Yanami bước vào quán."), ("dialogue", "LUCIEN", "“Đi thôi!”"),
              ("thought", "NPC_LOCAL::c00001::r9::bà chủ quán", "“Ừ.”")]
    batch = [{"text": "“Đợi đã, Lucien.”", "next_text": ""}, {"text": "“Gì nữa?” Anna hỏi.", "next_text": "Kakeru gật."}]
    context = pointer_mode.build_context(window, batch, ["LUCIEN", "YANAMI", "NARRATOR", "NPC_LOCAL::x"], "KAKERU")
    assert [quote.speaker for quote in context.quotes] == ["NPC_LOCAL:bà chủ quán", "LUCIEN"]
    # tên trong lô trước (theo lần đầu), rồi cửa sổ gần lô trước; chữ viết hoa một mình đầu câu ("Trời", "Kakeru" đầu
    # next_text) bị bỏ, sau dấu đóng ngoặc kép thì không ("” Anna hỏi")
    assert [mention.name for mention in context.names] == ["LUCIEN", "Anna", "YANAMI"]
    text = pointer_mode.block(context)
    assert text.startswith("Con trỏ (@qk = ")
    assert "@narrator = KAKERU" in text.splitlines()[0]
    assert "@q1 NPC_LOCAL:bà chủ quán (nội tâm): “Ừ.”" in text and "@q2 LUCIEN: “Đi thôi!”" in text
    assert "@n1 LUCIEN: " in text and text.endswith("\n\n")


def test_known_name_parts_match_only_capitalised_and_unambiguous() -> None:
    batch = [{"text": "Nukumizu nhìn. Tôi mong Kazuhiko và Sakuko tới.", "next_text": ""}]
    context = pointer_mode.build_context([], batch, ["NUKUMIZU KAZUHIKO", "URAZUMI SAKUKO", "URAZUMI ENMI"])
    names = [mention.name for mention in context.names]
    assert names == ["NUKUMIZU KAZUHIKO", "URAZUMI SAKUKO"]  # "Nukumizu" đầu câu vẫn khớp tên đã biết; "mong" thường thì không


def test_pointer_mode_prompt_system_and_resolution_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABOOK_POINTER_MODE", "1")
    payload = {"segments": [_item("S001", kind="dialogue", speaker="@q1"), _item("S002", kind="dialogue", speaker="@n1")]}
    request, result = _call(payload)
    assert request["system"].endswith(pointer_mode.SYSTEM_RULE)
    assert request["system"].startswith(field_mode.generator_system(SYSTEM_PROMPT, field_mode.SPEAKER))
    prompt = request["prompt"]
    assert prompt.index("Các đoạn ngay trước") < prompt.index("Con trỏ (") < prompt.index("Các đoạn liên tiếp:")
    assert prompt.endswith("NHIỆM VỤ: NGƯỜI NÓI. Mỗi đoạn chỉ trả id, kind, speaker.")
    item_schema = request["format"]["properties"]["segments"]["items"]
    branches = item_schema.get("oneOf", [item_schema])
    assert all(set(branch["properties"]) == {"id", "kind", "speaker"} for branch in branches)
    assert all(branch["properties"]["speaker"] == {"type": "string", "maxLength": 120} for branch in branches)
    speakers = [segment["speaker"] for segment in result["segments"]]
    assert speakers == ["NPC_LOCAL:bà chủ quán", "LUCIEN"]
    assert result["segments"][0]["emotion"] == "neutral" and result["segments"][0]["confidence"] == 0.9


# --- đổi ngược ---------------------------------------------------------------------------------------------


def _context() -> pointer_mode.PointerContext:
    return pointer_mode.PointerContext(
        quotes=[pointer_mode.Quote("dialogue", "LUCIEN", "a"), pointer_mode.Quote("dialogue", "NPC_LOCAL:bà chủ quán", "b")],
        names=[pointer_mode.Mention("YANAMI", "…Yanami…")], narrator="KAKERU", known=["LUCIEN", "YANAMI"])


def test_resolution_of_every_pointer_form() -> None:
    payload = {"segments": [
        {"id": "S001", "kind": "dialogue", "speaker": "@q2"},
        {"id": "S002", "kind": "dialogue", "speaker": "@S001"},
        {"id": "S003", "kind": "thought", "speaker": "@narrator"},
        {"id": "S004", "kind": "dialogue", "speaker": "@n1"},
        {"id": "S005", "kind": "dialogue", "speaker": "@new:lính gác"},
        {"id": "S006", "kind": "dialogue", "speaker": "@new:Hayase"},
        {"id": "S007", "kind": "dialogue", "speaker": "@new:lucien"},
        {"id": "S008", "kind": "thought", "speaker": "NARRATOR"},
        {"id": "S009", "kind": "narration", "speaker": "@q1"},
        {"id": "S010", "kind": "dialogue", "speaker": "@Q1"},
    ]}
    pointer_mode.resolve_payload(payload, _context(), [f"S{index:03d}" for index in range(1, 11)])
    assert [item["speaker"] for item in payload["segments"]] == [
        "NPC_LOCAL:bà chủ quán", "NPC_LOCAL:bà chủ quán", "KAKERU", "YANAMI", "NPC_LOCAL:lính gác", "Hayase", "LUCIEN",
        "NARRATOR", "NARRATOR", "LUCIEN"]


@pytest.mark.parametrize("bad", ["@q3", "@q0", "@n2", "@S002", "@S009", "Lucien", "@new:", "@new:" + "x" * 81, "@x1", ""])
def test_broken_pointers_raise(bad: str) -> None:
    payload = {"segments": [{"id": "S001", "kind": "dialogue", "speaker": "@q1"},
                            {"id": "S002", "kind": "dialogue", "speaker": bad}]}
    with pytest.raises(pointer_mode.PointerError):
        pointer_mode.resolve_payload(payload, _context(), ["S001", "S002"])


def test_narrator_pointer_without_a_first_person_book_is_broken() -> None:
    context = _context()
    context.narrator = ""
    with pytest.raises(pointer_mode.PointerError):
        pointer_mode.resolve_one("@narrator", context, {})


def test_pointer_to_a_narration_segment_of_the_batch_is_broken() -> None:
    payload = {"segments": [{"id": "S001", "kind": "narration", "speaker": "NARRATOR"},
                            {"id": "S002", "kind": "dialogue", "speaker": "@S001"}]}
    with pytest.raises(pointer_mode.PointerError):
        pointer_mode.resolve_payload(payload, _context(), ["S001", "S002"])


def test_broken_pointer_from_the_model_is_a_value_error_like_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABOOK_POINTER_MODE", "1")
    payload = {"segments": [_item("S001", kind="dialogue", speaker="@q7"), _item("S002", kind="dialogue", speaker="@q1")]}
    with pytest.raises(ValueError):  # vòng thử lại bắt `except Exception` -> last_error, thử lại
        _call(payload)


def test_gold_names_replace_the_model_names_of_the_quotes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / f"{CHAPTER}.txt").write_bytes("0 N\n1 D ANNA neutral 0 normal normal f\n2 D NPC* neutral 0 normal normal f\n"
                                          .encode("utf-8"))
    monkeypatch.setenv("ABOOK_POINTER_MODE", "1")
    monkeypatch.setenv("ABOOK_POINTER_GOLD_NAMES", str(gold))
    payload = {"segments": [_item("S001", kind="dialogue", speaker="@q2"), _item("S002", kind="dialogue", speaker="@q1")]}
    request, result = _call(payload)
    assert "@q2 ANNA: “Đi thôi!”" in request["prompt"] and "@q1 NPC_LOCAL:người lạ: “Ừ.”" in request["prompt"]
    assert [segment["speaker"] for segment in result["segments"]] == ["ANNA", "NPC_LOCAL:người lạ"]
    assert "[thoại · LUCIEN]" in request["prompt"], "khối các đoạn ngay trước vẫn theo model (chỉ @q đổi)"


# --- chỉ người nói / chỉ cảm xúc: thân chung ----------------------------------------------------------------


def _emotion_gold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / f"{CHAPTER}.txt").write_bytes("3 D NARRATOR,YANAMI angry 2 fast loud f\n4 D NPC*:bà chủ quán sad 1 slow soft f\n"
                                          .encode("utf-8"))
    monkeypatch.setenv("ABOOK_EMOTION_ONLY", "1")
    monkeypatch.setenv("ABOOK_EMOTION_GOLD", str(gold))


def test_speaker_only_and_emotion_only_share_system_and_body(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABOOK_SPEAKER_ONLY", "1")
    speaker_request, speaker_result = _call(_names_payload())
    monkeypatch.delenv("ABOOK_SPEAKER_ONLY")
    _emotion_gold(tmp_path, monkeypatch)
    emotion_payload = {"segments": [{"id": "S001", "emotion": "angry", "intensity": 2, "pace": "fast", "volume": "loud"},
                                    {"id": "S002", "emotion": "sad", "intensity": 1, "pace": "slow", "volume": "soft"}]}
    emotion_request, emotion_result = _call(emotion_payload)
    assert speaker_request["system"] == emotion_request["system"] != SYSTEM_PROMPT
    body_s, tail_s = speaker_request["prompt"].rsplit("\n\nNHIỆM VỤ:", 1)
    body_e, tail_e = emotion_request["prompt"].rsplit("\n\nNHIỆM VỤ:", 1)
    assert body_s == body_e
    assert tail_e.endswith("- S001: kind=dialogue; speaker=Yanami\n- S002: kind=dialogue; speaker=NPC_LOCAL:bà chủ quán")
    assert "gender" not in json.dumps(speaker_request["format"]) and "emotion" not in json.dumps(speaker_request["format"])
    emotion_items = emotion_request["format"]["properties"]["segments"]["items"]
    for branch in emotion_items.get("oneOf", [emotion_items]):
        assert set(branch["properties"]) == {"id", "emotion", "intensity", "pace", "volume"}
    first_speaker = speaker_result["segments"][0]
    assert (first_speaker["kind"], first_speaker["speaker"]) == ("dialogue", "YANAMI")
    assert {key: first_speaker[key] for key in field_mode.SPEAKER_DEFAULTS} == field_mode.SPEAKER_DEFAULTS
    first = emotion_result["segments"][0]
    assert (first["kind"], first["speaker"], first["gender"], first["emotion"], first["intensity"]) == (
        "dialogue", "Yanami", "female", "angry", 2)


def test_speaker_only_switches_off_the_host_affect_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    group = [_row(0, "dialogue", "", "“Cứu tôi với!” cô hét lên sợ hãi.", status="pending")]
    validated = {group[0]["stable_id"]: {"kind": "dialogue", "speaker": "YANAMI", "emotion": "neutral", "intensity": 0,
                                         "pace": "normal", "volume": "normal"}}
    monkeypatch.setenv("ABOOK_SPEAKER_ONLY", "1")
    assert _host_affect_adjudication(group, validated).issues == ()
    assert _semantic_delivery_issues(group, validated) == ({}, False)


def test_emotion_only_needs_a_gold_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABOOK_EMOTION_ONLY", "1")
    with pytest.raises(RuntimeError):
        _call({"segments": []})


# --- critic ------------------------------------------------------------------------------------------------


def test_critic_prompt_rows_schema_and_fill_follow_the_mode() -> None:
    for mode in (field_mode.SPEAKER, field_mode.EMOTION):
        system = field_mode.critic_system(DIRECTOR_CRITIC_SYSTEM_PROMPT, mode)
        assert system != DIRECTOR_CRITIC_SYSTEM_PROMPT and "sáu" not in system
    rows = [{"batch_signature_count": 2, "candidate": {"emotion": "sad", "intensity": 1, "kind": "dialogue", "pace": "slow",
                                                        "speaker": "Yanami", "volume": "soft"},
             "host_locked_fields": {"kind": "dialogue", "emotion": "sad"}, "id": "S001", "text": "x"}]
    speaker_rows = field_mode.critic_rows(rows, field_mode.SPEAKER)
    assert speaker_rows[0]["candidate"] == {"kind": "dialogue", "speaker": "Yanami"}
    assert speaker_rows[0]["host_locked_fields"] == {"kind": "dialogue"} and "batch_signature_count" not in speaker_rows[0]
    emotion_rows = field_mode.critic_rows(rows, field_mode.EMOTION)
    assert emotion_rows[0]["candidate"] == {"emotion": "sad", "intensity": 1, "pace": "slow", "volume": "soft"}
    assert emotion_rows[0]["given"] == {"kind": "dialogue", "speaker": "Yanami"}
    assert rows[0]["candidate"]["speaker"] == "Yanami", "không đổi dòng gốc (host còn băm nó)"
    payload = {"candidate_hash": "h", "verdicts": [{"id": "S001", "kind": "dialogue", "speaker": "Lucien", "rationale": "abcd",
                                                    "evidence_quote": "x", "critic_confidence": 0.9}]}
    field_mode.fill_critic(payload, rows, field_mode.SPEAKER)
    assert payload["verdicts"][0]["speaker"] == "Lucien" and payload["verdicts"][0]["emotion"] == "sad"
