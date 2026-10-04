"""Bốn hook đo của nhánh dev/breakthrough-eval (ebook_reader/eval_hooks.py): TẮT mặc định, bật bằng biến môi trường.

Không đặt biến nào thì prompt y hệt từng byte; có đặt thì khối chèn đúng vị trí, đúng chữ.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ebook_reader import eval_hooks
from ebook_reader.analysis import OllamaBookAnalyzer, _batch_id, _neighbor_texts, _original_neighbor_context
from ebook_reader.config import build_settings
from test_a_batch_sees_who_spoke_just_before import ChapterDB
from test_analysis_required import FakeSession, analysis_item

HOOK_VARS = (
    "ABOOK_PROMPT_DUMP", "ABOOK_GOLD_PREVIOUS", "ABOOK_ORACLE_DIR", "ABOOK_ORACLE_GOLD_DIR", "ABOOK_ORACLE_KIND",
    "ABOOK_EVAL_SETTINGS",
)
CHAPTER = "Chương 1"  # tên chương của FakeDB


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in HOOK_VARS:
        monkeypatch.delenv(name, raising=False)
    eval_hooks._cache.clear()


def _row(seq: int, kind: str, speaker: str, text: str, status: str = "analyzed") -> dict[str, Any]:
    return {"id": seq + 1, "stable_id": f"c00001_s{seq:07d}_x", "chapter_id": 1, "seq": seq, "paragraph_index": seq,
            "kind": kind, "kind_hint": kind, "speaker": speaker, "text": text, "status": status, "gender": "unknown"}


def _rows() -> list[dict[str, Any]]:
    return [
        _row(0, "narration", "NARRATOR", "Trời mưa."),
        _row(1, "dialogue", "LUCIEN", "“Đi thôi.”"),
        _row(2, "dialogue", "NPC_LOCAL::c00001::r9::bà chủ quán", "“Ừ.”"),
        _row(3, "dialogue", "", "“Đợi đã.”", status="pending"),
        _row(4, "narration", "", "Cô nói.", status="pending"),
    ]


def _analyzer(rows: list[dict[str, Any]], session: FakeSession | None = None) -> OllamaBookAnalyzer:
    analyzer = OllamaBookAnalyzer(build_settings(), ChapterDB(rows), lambda _message: None)
    if session is not None:
        analyzer.session = session
        analyzer._model_digest = "sha256:test-model-digest"
    return analyzer


def _prompt(rows: list[dict[str, Any]] | None = None) -> str:
    rows = rows or _rows()
    group = [row for row in rows if row["status"] == "pending"]
    session = FakeSession({"segments": [analysis_item(_batch_id(index + 1)) for index, _row_ in enumerate(group)]})
    _analyzer(rows, session)._request(group)
    return session.request["json"]["prompt"]


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"))


O1 = [
    {"from_seq": 0, "to_seq": 2, "present": ["Lucien", "Remon (Yakishio)"]},
    {"from_seq": 3, "to_seq": 9, "present": ["Remon (Yakishio)", "Anna"]},
    {"from_seq": 20, "to_seq": 30, "present": ["Người lạ"]},
]
O2 = [
    {"speaker": "Remon (Yakishio)", "listener": "Lucien", "self": "em", "calls": "anh", "note": "thân mật"},
    {"speaker": "Lucien", "listener": "Anna", "self": "-", "calls": "cô"},
    {"speaker": "Anna", "listener": "Lucien", "self": "", "calls": ""},
]


def _oracle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, o2: Any = O2, kind: str | None = None) -> None:
    _write(tmp_path / "truyen" / f"{CHAPTER}.o1.json", O1)
    _write(tmp_path / "truyen" / f"{CHAPTER}.o2.json", o2)
    monkeypatch.setenv("ABOOK_ORACLE_DIR", str(tmp_path))
    monkeypatch.setenv("ABOOK_ORACLE_GOLD_DIR", "truyen")
    if kind:
        monkeypatch.setenv("ABOOK_ORACLE_KIND", kind)


# --- tắt mặc định ------------------------------------------------------------------------------------------


def test_no_variable_means_the_exact_same_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plain = _prompt()
    assert "có mặt" not in plain and "xưng hô" not in plain
    assert plain.index("Nhân vật đã biết") < plain.index("Các đoạn ngay trước") < plain.index("Các đoạn liên tiếp")
    # Đặt biến nhưng không có file (oracle) / không có câu nào trong gold: vẫn từng byte như cũ.
    monkeypatch.setenv("ABOOK_ORACLE_DIR", str(tmp_path))
    monkeypatch.setenv("ABOOK_ORACLE_GOLD_DIR", "khong_co")
    gold = tmp_path / "gold"
    gold.mkdir()
    monkeypatch.setenv("ABOOK_GOLD_PREVIOUS", str(gold))
    monkeypatch.setenv("ABOOK_EVAL_SETTINGS", "{}")
    assert _prompt() == plain


def test_settings_and_neighbours_unchanged_without_the_variable() -> None:
    analyzer = _analyzer(_rows())
    assert analyzer.settings["batch_segments"] == build_settings()["analysis"]["batch_segments"]
    group = [{"stable_id": "a", "text": "x" * 800}, {"stable_id": "b", "text": "y" * 800}]
    previous, following = _neighbor_texts(group, 1, None)
    assert len(previous) == 500 and len(following) == 0
    assert len(_neighbor_texts(group, 0, None)[1]) == 500
    assert eval_hooks.batch_segments_overridden() is False


# --- oracle ------------------------------------------------------------------------------------------------


def test_oracle_blocks_sit_between_the_known_characters_and_the_previous_turns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _oracle(tmp_path, monkeypatch)
    prompt = _prompt()
    block = (
        "Nhân vật có mặt trong cảnh này: Remon (Yakishio), Anna.\n\n"
        "Cách xưng hô giữa các nhân vật:\n"
        '- Remon (Yakishio) nói với Lucien: tự xưng "em", gọi Lucien là "anh" (thân mật)\n'
        '- Lucien nói với Anna: gọi Anna là "cô"\n'
        "- Anna nói với Lucien: không xưng hô\n\n"
    )
    assert block in prompt
    known = prompt.index("Nhân vật đã biết")
    assert known < prompt.index(block) < prompt.index("Các đoạn ngay trước")
    assert prompt.index(block) + len(block) == prompt.index("Các đoạn ngay trước"), "ngay trước _previous_turns"
    assert "Người lạ" not in prompt, "khoảng 20-30 không chạm lô (seq 3, 4)"


def test_oracle_present_is_the_union_of_every_span_touching_the_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _oracle(tmp_path, monkeypatch, kind="o1")
    group = [row for row in _rows() if row["status"] == "pending"]
    assert eval_hooks.oracle_block(group, {1: CHAPTER}) == "Nhân vật có mặt trong cảnh này: Remon (Yakishio), Anna.\n\n"
    group[0]["seq"], group[1]["seq"] = 2, 25  # chạm khoảng 0-2 và 20-30
    assert eval_hooks.oracle_block(group, {1: CHAPTER}) == (
        "Nhân vật có mặt trong cảnh này: Lucien, Remon (Yakishio), Người lạ.\n\n"
    )


def test_oracle_kind_selects_the_block_and_an_empty_o2_inserts_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _oracle(tmp_path, monkeypatch, kind="o2")
    prompt = _prompt()
    assert "Cách xưng hô" in prompt and "có mặt" not in prompt
    _oracle(tmp_path, monkeypatch, o2=[], kind="o1o2")
    prompt = _prompt()
    assert "có mặt" in prompt and "xưng hô" not in prompt


def test_oracle_without_files_for_the_chapter_adds_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plain = _prompt()
    monkeypatch.setenv("ABOOK_ORACLE_DIR", str(tmp_path))
    monkeypatch.setenv("ABOOK_ORACLE_GOLD_DIR", "truyen")
    assert _prompt() == plain


# --- gold previous -----------------------------------------------------------------------------------------


def test_gold_previous_replaces_kind_and_speaker_of_the_turns_before_the_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = _rows()
    model_text = _analyzer(rows)._previous_turns(rows[3:])
    assert "[thoại · LUCIEN]" in model_text and "[kể] Trời mưa." in model_text
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / f"{CHAPTER}.txt").write_bytes(
        (
            "0 N\n"
            "1 D YANAMI,ANNA neutral 0-1 normal normal f\n"
            "2 T NPC*:bà chủ quán neutral 0 normal normal f\n"
        ).encode("utf-8")
    )
    monkeypatch.setenv("ABOOK_GOLD_PREVIOUS", str(gold))
    lines = _analyzer(rows)._previous_turns(rows[3:]).strip().splitlines()[1:]
    assert lines == [
        "- [kể] Trời mưa.",
        "- [thoại · YANAMI] “Đi thôi.”",
        "- [nội tâm · NPC_LOCAL:bà chủ quán] “Ừ.”",
    ]
    # Gold không có câu ấy (seq 1 vắng) thì giữ nhãn của model.
    (gold / f"{CHAPTER}.txt").write_bytes(b"0 N\n2 D LUCIEN neutral 0 normal normal m\n")
    eval_hooks._cache.clear()
    lines = _analyzer(rows)._previous_turns(rows[3:]).strip().splitlines()[1:]
    assert lines[1] == "- [thoại · LUCIEN] “Đi thôi.”" and lines[2] == "- [thoại · LUCIEN] “Ừ.”"


def test_gold_kind_decides_whether_the_block_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [_row(0, "narration", "NARRATOR", "Mưa."), _row(1, "dialogue", "", "“Ồ.”", status="pending")]
    assert _analyzer(rows)._previous_turns(rows[1:]) == ""
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / f"{CHAPTER}.txt").write_bytes("0 D MẸ neutral 0 normal normal f\n".encode("utf-8"))
    monkeypatch.setenv("ABOOK_GOLD_PREVIOUS", str(gold))
    assert "[thoại · MẸ] Mưa." in _analyzer(rows)._previous_turns(rows[1:])


# --- eval settings -----------------------------------------------------------------------------------------


def test_eval_settings_override_analysis_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    base = build_settings()
    monkeypatch.setenv("ABOOK_EVAL_SETTINGS", '{"batch_segments": 3, "batch_chars": 2000, "neighbor_chars": 250}')
    analyzer = OllamaBookAnalyzer(base, ChapterDB(_rows()), lambda _message: None)
    assert analyzer.settings["batch_segments"] == 3 and analyzer.settings["batch_chars"] == 2000
    assert base["analysis"]["batch_segments"] != 3, "không sửa dict gốc"
    assert eval_hooks.batch_segments_overridden() is True
    group = [{"stable_id": "a", "text": "x" * 800}, {"stable_id": "b", "text": "y" * 800}]
    previous, _ = _neighbor_texts(group, 1, None)
    assert len(previous) == 250
    full = [_row(0, "narration", "", "x" * 800), _row(1, "narration", "", "y" * 800)]
    context = _original_neighbor_context(full)
    assert len(context[full[1]["stable_id"]]["previous_text"]) == 250 and len(context[full[0]["stable_id"]]["next_text"]) == 250
    assert len(_neighbor_texts(full, 1, context)[0]) == 250
    wide = _original_neighbor_context(full)
    monkeypatch.setenv("ABOOK_EVAL_SETTINGS", '{"neighbor_chars": 100}')
    assert len(_neighbor_texts(full, 1, wide)[0]) == 100, "chuỗi dựng sẵn dài hơn mức đang đo bị cắt"


def test_neighbor_chars_reach_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [_row(3, "dialogue", "", "a" * 400, status="pending"), _row(4, "dialogue", "", "b" * 400, status="pending")]
    monkeypatch.setenv("ABOOK_EVAL_SETTINGS", '{"neighbor_chars": 120}')
    prompt = _prompt(rows)
    assert '"next_text": "' + "b" * 120 + '"' in prompt
    assert '"previous_text": "' + "a" * 120 + '"' in prompt


# --- dump --------------------------------------------------------------------------------------------------


def test_prompt_dump_records_what_was_sent_and_received(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "dump.jsonl"
    monkeypatch.setenv("ABOOK_PROMPT_DUMP", str(out))
    rows = _rows()
    group = [row for row in rows if row["status"] == "pending"]
    session = FakeSession({"segments": [analysis_item(_batch_id(index + 1)) for index, _row_ in enumerate(group)]})
    _analyzer(rows, session)._request(group)
    _analyzer(rows, session)._request(group)
    raw = out.read_bytes()
    assert b"\r\n" not in raw
    records = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    assert len(records) == 2
    record = records[0]
    sent = session.request["json"]
    assert record["role"] == "generator" and record["chapter"] == CHAPTER and record["attempt"] == 1
    assert record["seqs"] == [3, 4]
    assert record["batch_ids"] == {"S001": group[0]["stable_id"], "S002": group[1]["stable_id"]}
    assert record["system"] == sent["system"] and record["user"] == sent["prompt"]
    assert record["format"] == sent["format"] and record["model"] == sent["model"]
    assert record["options"]["temperature"] == sent["options"]["temperature"]
    assert {"num_ctx", "num_predict", "seed"} <= set(record["options"])
    assert json.loads(record["raw"])["segments"][0]["id"] == "S001", "chuỗi thô, trước khi đổi sang stable_id"


def test_no_dump_file_without_the_variable(tmp_path: Path) -> None:
    _prompt()
    assert list(tmp_path.iterdir()) == []
