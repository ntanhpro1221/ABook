"""Lượt "người nói từng câu": đề app dựng phải TRÙNG TỪNG BYTE với đề mã đo B41 (LLM_Train/b38) sinh ra.

Fixture (tests/fixtures/speaker_pass, dựng bằng scripts/make_speaker_pass_fixtures.py từ chính mã đo):
- synthetic_a/b: truyện tự viết. Đề đầy đủ với bộ đếm ký tự/3 -> test LUÔN chạy; băm đề với tokenizer thật -> bỏ qua nếu máy
  không có tokenizer.json đúng bản ghim. B ép mọi nhánh cắt khối (bớt câu cuối, cắt xem_truoc, cắt đoạn kể, bỏ khối).
- real.json: chương thật của dự án đo (b9lps1234 + nhãn b41s1234), chỉ băm đề; văn bản và nhãn đọc từ dự án lúc chạy, bỏ qua
  (có lý do) nếu máy không có dự án ấy.

Hai nguồn lệch dễ nhất đã được ghim ở đây: (1) đầu đề hai dòng (tiêu đề chương + người kể ngôi thứ nhất); (2) nhãn trong lịch sử/
sổ nhân vật là nhãn MODEL vừa trả, không phải nhãn của model phân tích.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from pathlib import Path

import pytest

from abook import speaker_pass as sp

FIXTURES = Path(__file__).parent / "fixtures" / "speaker_pass"
EVAL_ROOT = Path(os.environ.get("ABOOK_PQ_EVAL_ROOT") or "D:/Novels/Audiobooks/_model_eval_v2")


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CharCounter:
    kind = "chars/3"

    @staticmethod
    def count(system: str, user: str) -> int:
        return math.ceil(len(sp._template(system, user)) / 3)


def _real_counter():
    path = sp.find_tokenizer(Path(os.environ.get("ABOOK_RUNTIME") or Path(__file__).resolve().parents[1] / "runtime"))
    if path is None:
        pytest.skip("máy không có tokenizer.json của Qwen3-4B-Instruct-2507 đúng bản ghim")
    return sp.TokenCounter(path)


def _expand(text) -> str:
    if isinstance(text, dict):
        unit, count = text["rep"]
        return unit * count
    return text


class Replay:
    """Thay model: trả nhãn đã ghi cho câu đích. Câu đích suy từ thứ tự hỏi (fixture ghi seq từng lần hỏi)."""

    def __init__(self, targets: list[int], labels: dict[int, str]) -> None:
        self.queue = list(targets)
        self.labels = labels
        self.users: list[str] = []

    def __call__(self, user: str) -> tuple[str, int]:
        self.users.append(user)
        return self.labels[self.queue[len(self.users) - 1]], 0


def _synthetic_rows(fixture: dict) -> tuple[list[dict], dict[int, str]]:
    rows, labels = [], {}
    for seq, entry in enumerate(fixture["story"]):
        rows.append({"seq": seq, "text": _expand(entry["text"]), "paragraph_index": seq // 2, "kind": entry["kind"]})
        if "label" in entry:
            labels[seq] = entry["label"]
    return rows, labels


def _run_synthetic(fixture: dict, counter, expected: dict) -> list[str]:
    rows, labels = _synthetic_rows(fixture)
    head = sp.chapter_head(fixture["title"], fixture["narrator"])
    piece = sp.chapter_piece(rows, head)
    replay = Replay(expected["targets"], labels)
    info = sp.run_piece(piece, replay, counter)
    assert json.loads(json.dumps(info)) == expected["info"]
    assert {str(s.seq): s.speaker for s in piece if s.spoken} == expected["final"]
    return replay.users


def test_system_prompt_is_the_measured_one() -> None:
    fixture = _load("synthetic_a.json")
    assert _sha(sp.SYSTEM_PQ) == fixture["system_pq_sha256"]
    assert _sha(sp.SYSTEM_BLOCK) == fixture["system_block_sha256"]
    assert _sha(sp.SYSTEM_PQ) == _load("real.json")["system_pq_sha256"]


@pytest.mark.parametrize("name", ["synthetic_a.json", "synthetic_b.json"])
def test_synthetic_prompts_are_byte_identical_to_the_measurement_code(name: str) -> None:
    fixture = _load(name)
    expected = fixture["chars3"]
    users = _run_synthetic(fixture, CharCounter(), expected)
    assert len(users) == len(expected["users"])
    for index, (got, want) in enumerate(zip(users, expected["users"])):
        assert got == want, f"đề {index} lệch"
    assert [_sha(user) for user in users] == expected["users_sha256"]


@pytest.mark.parametrize("name", ["synthetic_a.json", "synthetic_b.json"])
def test_synthetic_prompts_match_with_the_real_tokenizer(name: str) -> None:
    fixture = _load(name)
    expected = fixture["tokenizer"]
    users = _run_synthetic(fixture, _real_counter(), expected)
    assert [_sha(user) for user in users] == expected["users_sha256"]


def test_synthetic_b_exercises_every_way_a_block_is_cut() -> None:
    info = _load("synthetic_b.json")["chars3"]["info"]
    assert info["blocks_trimmed"] and info["blocks_truncated"] and info["blocks_dropped"]
    # Khối bị bỏ -> UNKNOWN (như lúc đo, không tự đổi luật).
    assert info["unknown_lines"] == info["blocks_dropped"]


def test_the_head_has_two_lines_and_the_narrator_only_in_first_person() -> None:
    fixture = _load("synthetic_a.json")
    rows, labels = _synthetic_rows(fixture)
    first = sp.chapter_piece(rows, sp.chapter_head(fixture["title"], "Minh"))
    third = sp.chapter_piece(rows, sp.chapter_head(fixture["title"], ""))
    assert first[0].head[0] == f"Các chương hiện tại: {fixture['title']}"
    assert first[0].head[1].startswith("Truyện kể ở ngôi thứ nhất") and "speaker=Minh" in first[0].head[1]
    assert third[0].head[1] == ""
    user = sp.render_window(first[0].head, "K", "", [], "pq")
    assert user.startswith(f"Các chương hiện tại: {fixture['title']}\n\nTruyện kể ở ngôi thứ nhất")
    assert sp.render_window(third[0].head, "K", "", [], "pq").startswith(f"Các chương hiện tại: {fixture['title']}\n\nNhân vật")


def test_thoughts_are_asked_and_keep_their_kind() -> None:
    fixture = _load("synthetic_a.json")
    rows, labels = _synthetic_rows(fixture)
    piece = sp.chapter_piece(rows, sp.chapter_head(fixture["title"], "Minh"))
    thoughts = [s for s in piece if s.kind == "thought"]
    assert thoughts and all(s.spoken and s.speaker == "" for s in thoughts)
    users = _run_synthetic(fixture, CharCounter(), fixture["chars3"])
    assert any('"loai": "nội tâm"' in user and '"dich": true' in user for user in users)


def test_the_history_carries_the_model_labels_never_the_analysis_ones() -> None:
    fixture = _load("synthetic_a.json")
    rows, labels = _synthetic_rows(fixture)
    for row in rows:
        row["speaker"] = "NHÃN_MODEL_PHÂN_TÍCH"   # chương trình đọc từ sổ: không được lọt vào đề
    piece = sp.chapter_piece(rows, sp.chapter_head(fixture["title"], "Minh"))
    replay = Replay(fixture["chars3"]["targets"], labels)
    sp.run_piece(piece, replay, CharCounter())
    assert not any("NHÃN_MODEL_PHÂN_TÍCH" in user for user in replay.users)
    later = replay.users[-1]
    assert "- [thoại · " in later and "NPC_LOCAL:" in later and "NPC_LOCAL::" not in later


def _chapter_text_and_labels(entry: dict):
    base = _find_project(entry["root_pattern"], entry["base_tag"], entry["chapter"])
    label = _find_project(entry["root_pattern"], entry["label_tag"], entry["chapter"])
    if base is None or label is None:
        pytest.skip(f"máy không có dự án đo {entry['short']}/{entry['chapter']} (b9lps1234 + b41s1234)")
    con = sqlite3.connect(f"file:{(base / 'project.sqlite3').as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute("select seq, text, paragraph_index, kind from segments order by seq")]
        titles = [str(t) for (t,) in con.execute("select c.title from chapters c where c.id in (select distinct chapter_id from segments) "
                                                  "order by c.chapter_index, c.id")]
    finally:
        con.close()
    con = sqlite3.connect(f"file:{(label / 'project.sqlite3').as_posix()}?mode=ro", uri=True)
    try:
        stored = {int(seq): str(speaker or "") for seq, speaker in con.execute("select seq, speaker from segments")}
    finally:
        con.close()
    labels = {}
    for r in rows:
        if r["kind"] in sp.SPOKEN_KINDS:
            value = stored[int(r["seq"])]
            labels[int(r["seq"])] = "NPC_LOCAL:" + value[len("NPC_LOCAL::"):] if value.startswith("NPC_LOCAL::") else value
    assert len(titles) == 1, "mỗi dự án đo là một chương"
    return rows, titles[0], labels


def _find_project(root_pattern: str, tag: str, chapter: str) -> Path | None:
    root = EVAL_ROOT / root_pattern.replace("{tag}", tag)
    found = sorted(root.glob(f"*/{chapter}/**/project.sqlite3")) if root.is_dir() else []
    return found[0].parent if found else None


@pytest.mark.parametrize("index", range(4))
def test_real_chapters_prompts_are_byte_identical_to_the_measurement(index: int) -> None:
    fixture = _load("real.json")
    entry = fixture["chapters"][index]
    counter = _real_counter()
    rows, title, labels = _chapter_text_and_labels(entry)
    assert _sha("\x00".join(r["text"] for r in rows)) == entry["texts_sha256"], "văn bản dự án đo đã đổi"
    piece = sp.chapter_piece(rows, sp.chapter_head(title, entry["narrator"]))
    assert len(piece) == entry["segments"]
    assert sum(s.spoken for s in piece) == entry["spoken"] and sum(s.kind == "thought" for s in piece) == entry["thoughts"]
    replay = Replay(entry["targets"], labels)
    info = sp.run_piece(piece, replay, counter)
    assert json.loads(json.dumps(info)) == entry["info"]
    assert [_sha(user) for user in replay.users] == entry["users_sha256"]
    final = sorted((s.seq, s.speaker) for s in piece if s.spoken)
    assert _sha(json.dumps([[seq, label] for seq, label in final], ensure_ascii=False)) == entry["final_sha256"]
