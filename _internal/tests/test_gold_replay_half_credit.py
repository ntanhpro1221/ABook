"""Exercise the replay writer without importing app workers or loading models."""
from __future__ import annotations

import ast
import io
import json
import re
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "model_eval" / "gold_replay.py"


def load_replayer():
    # Compile the real replay class and helpers with only their lightweight dependencies.
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
    names = {"Replayer", "_branch_for", "_title"}
    selected = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "__future__"
                or isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    namespace = {"json": json, "re": re, "Counter": Counter, "Path": Path,
                 "GENDER": {"m": "male", "f": "female"},
                 "A": SimpleNamespace(ALLOWED_KINDS={"narration", "dialogue", "thought"},
                                      ALLOWED_EMOTIONS={"neutral"})}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SCRIPT), "exec"), namespace)
    return namespace["Replayer"]


def make_replay(speakers, *, kind="dialogue", book_spelling=False, out=None, missing=False):
    db = SimpleNamespace(
        list_segments=lambda: [{"chapter_id": 1, "seq": 2, "text": "Alpha and Bé."}],
        list_chapters=lambda: [{"id": 1, "title": "synthetic"}],
        list_characters=lambda: [],
    )
    gold = SimpleNamespace(chapter="synthetic", seq=2, kinds={kind}, speakers=tuple(speakers),
                           npc_label="", gender="u", emotions={"neutral"}, emotion_order=("neutral",),
                           intensity=(0, 1), pace_order=("normal",), volume_order=("normal",))
    replay = load_replayer()(db, {} if missing else {("synthetic", 2): gold}, out, "synthetic",
                            book_spelling=book_spelling)
    request = {"system": "Synthetic test", "prompt": 'Các đoạn liên tiếp:\n' + json.dumps(
        [{"id": "s2", "text": "Alpha and Bé."}], ensure_ascii=False),
        "format": {"properties": {"segments": {"items": {"properties": {"id": {}, "kind": {"enum": [kind]}}}}}}}
    return replay, request


def saved_call(replay, request):
    replay.out = io.StringIO()
    response = replay(None, request)
    return response, json.loads(replay.out.getvalue())


def test_saved_target_keeps_half_credit_without_mutating_host_response():
    replay, request = make_replay([("ALPHA", 1.0), ("BÉ", 0.5), ("UNKNOWN", 0.5),
                                   ("NPC*", 0.5), ("BÉ", 0.5), ("ALPHA ALIAS", 1.0)])
    response, saved = saved_call(replay, request)
    assert "speaker_alt" not in response["segments"][0]
    assert saved["response"]["segments"][0]["speaker"] == "ALPHA"
    assert saved["response"]["segments"][0]["speaker_alt"] == [
        {"speaker": "BÉ", "credit": 0.5}, {"speaker": "UNKNOWN", "credit": 0.5},
        {"speaker": "NPC_LOCAL:người lạ", "credit": 0.5}]
    assert saved["format"] == request["format"]
    assert saved["chapters"] == ["synthetic"]


@pytest.mark.parametrize("kind", ["dialogue", "thought", "narration"])
def test_half_credit_survives_all_kinds_and_book_spelling(kind):
    replay, request = make_replay([("ALPHA", 1.0), ("BÉ", 0.5)], kind=kind, book_spelling=True)
    response, saved = saved_call(replay, request)
    assert saved["response"]["segments"][0]["speaker_alt"] == [{"speaker": "Bé", "credit": 0.5}]
    assert response["segments"][0]["speaker"] == ("NARRATOR" if kind == "narration" else "Alpha")


@pytest.mark.parametrize("missing", [False, True])
def test_unambiguous_and_missing_gold_keep_previous_target_shape(missing):
    replay, request = make_replay([("ALPHA", 1.0)], missing=missing)
    response, saved = saved_call(replay, request)
    assert saved["response"] == response
    assert "speaker_alt" not in saved["response"]["segments"][0]


def test_narrator_primary_still_prefers_full_credit_character():
    replay, request = make_replay([("NARRATOR", 1.0), ("ALPHA", 1.0), ("BÉ", 0.5)])
    response, saved = saved_call(replay, request)
    assert response["segments"][0]["speaker"] == "ALPHA"
    assert saved["response"]["segments"][0]["speaker_alt"] == [{"speaker": "BÉ", "credit": 0.5}]


def test_no_output_path_does_not_add_training_fields():
    replay, request = make_replay([("ALPHA", 1.0), ("BÉ", 0.5)])
    assert "speaker_alt" not in replay(None, request)["segments"][0]


def test_critic_output_is_not_annotated_as_a_generator_target():
    replay, request = make_replay([("ALPHA", 1.0), ("BÉ", 0.5)])
    expected = {"verdicts": [{"id": "s2", "speaker": "ALPHA"}]}
    replay.critic = lambda _request: expected
    request["format"] = {"properties": {"verdicts": {}}}
    response, saved = saved_call(replay, request)
    assert response is expected
    assert saved["response"] == expected
    assert saved["type"] == "critic"


def test_replay_file_uses_utf8_and_lf(tmp_path):
    path = tmp_path / "synthetic.jsonl"
    replay, request = make_replay([("ALPHA", 1.0), ("BÉ", 0.5)], out=path)
    replay(None, request)
    replay.out.close()
    raw = path.read_bytes()
    assert b"\r" not in raw
    assert json.loads(raw.decode("utf-8"))["response"]["segments"][0]["speaker_alt"][0]["speaker"] == "BÉ"


def test_all_half_gold_does_not_crash_or_promote_a_half_choice():
    replay, request = make_replay([("ALPHA", 0.5), ("BÉ", 0.5)])
    response, saved = saved_call(replay, request)
    assert response["segments"][0]["speaker"] == "ALPHA"
    target = saved["response"]["segments"][0]
    assert target["speaker_credit"] == 0.5
    assert target["speaker_alt"] == [{"speaker": "ALPHA", "credit": 0.5}, {"speaker": "BÉ", "credit": 0.5}]
    assert "speaker_credit" not in response["segments"][0]
