"""Bộ chấm model phân tích: đọc đáp án chuẩn đúng cú pháp và chấm người nói khắt khe, cảm xúc theo tập."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "model_eval"))

from score_models import GOLD_DIR, load_gold, parse_gold, score_rows, speaker_credit, speaker_key  # noqa: E402

SAMPLE = """# chú thích
0 H
1 N
2 D DOUGLAS happy,neutral 0-2 normal normal m
3 T,N NARRATOR,BELLAK~ afraid 1-2 normal,fast normal u
4 D LUCIEN,NPC*,THẦN HƠI NƯỚC,UNKNOWN~ neutral 0-2 slow,normal normal,loud u
5 D DOUGLAS happy 1-2 normal normal m
"""


def _gold(tmp_path: Path):
    path = tmp_path / "351.txt"
    path.write_text(SAMPLE, encoding="utf-8")
    return {(row.chapter, row.seq): row for row in parse_gold(path)}


def test_the_gold_syntax_is_read_as_written(tmp_path: Path) -> None:
    gold = _gold(tmp_path)
    assert ("351", 0) not in gold, "tiêu đề chương không chấm"
    assert gold[("351", 1)].speakers == (("NARRATOR", 1.0),) and not gold[("351", 1)].spoken
    assert gold[("351", 3)].kinds == {"thought", "narration"}
    assert speaker_credit(gold[("351", 3)], "Bellak") == 0.5
    # tên có dấu cách đọc trọn, và mọi NPC_LOCAL gom về NPC*
    assert speaker_credit(gold[("351", 4)], "thần hơi nước") == 1.0
    assert speaker_credit(gold[("351", 4)], "NPC_LOCAL::c00038::rbb6::lão") == 1.0
    assert speaker_key("NPC_LOCAL::c1::r2::x") == "NPC*"


def test_an_anonymous_speaker_can_say_who_it_is_without_changing_the_score(tmp_path: Path) -> None:
    """`NPC*:<mô tả>` ("mẹ Kakeru"): chấm y như NPC*, mô tả để gold_replay dạy model nhãn riêng cho từng người lạ."""
    path = tmp_path / "07.txt"
    path.write_text("5 D NPC*:mẹ Kakeru,UNKNOWN~ neutral 0 normal normal f\n6 D NPC* neutral 0 normal normal u\n",
                    encoding="utf-8")
    gold = {row.seq: row for row in parse_gold(path)}
    assert gold[5].speakers == (("NPC*", 1.0), ("UNKNOWN", 0.5))
    assert gold[5].npc_label == "mẹ Kakeru" and gold[6].npc_label == ""
    assert speaker_credit(gold[5], "NPC_LOCAL:bà cụ") == 1.0
    assert speaker_credit(gold[5], "Kakeru") == 0.0
    assert speaker_key("NPC*:mẹ Kakeru") == "NPC*"


def test_a_pronoun_label_is_scored_as_the_anonymous_voice_the_listener_hears() -> None:
    """Dây chuyền đẩy tên là đại từ vào nhóm VÔ DANH khi phân vai, nên bộ chấm gom nó về `NPC*` như NPC_LOCAL.

    Ca thật 21-09: phép thử prompt bị trừ oan `407:10-12` gán "MÌNH" - người nghe nghe giọng vô danh, và
    đáp án nhận `NPC*`. Tên thật trùng mặt chữ với một đại từ không có trong truyện này, nên luật an toàn.
    """
    for pronoun in ("MÌNH", "mình", "Tôi", "hắn", "ta", "me"):
        assert speaker_key(pronoun) == "NPC*", pronoun
    # Tên người vẫn so bằng chính nó - kể cả tên CÓ chứa một đại từ bên trong.
    assert speaker_key("LUCIEN") == "LUCIEN"
    assert speaker_key("Minh Quân") == "MINH QUÂN"
    assert speaker_key("MINH") == "MINH", "`minh` không dấu là tên riêng, không nằm trong PRONOUNS"


def test_a_line_given_to_the_narrator_costs_the_speaker_score(tmp_path: Path) -> None:
    gold = _gold(tmp_path)
    base = {"chapter": "351", "gender": "male", "intensity": 1, "pace": "normal", "volume": "normal",
            "status": "analyzed", "text": "x"}
    rows = [
        {**base, "seq": 1, "kind": "narration", "speaker": "NARRATOR", "emotion": "neutral"},
        {**base, "seq": 2, "kind": "dialogue", "speaker": "NARRATOR", "emotion": "happy"},
        {**base, "seq": 3, "kind": "thought", "speaker": "BELLAK", "emotion": "afraid"},
        {**base, "seq": 4, "kind": "dialogue", "speaker": "LUCIEN", "emotion": "angry"},
        {**base, "seq": 5, "kind": "dialogue", "speaker": "Douglas", "emotion": "happy"},
    ]
    result = score_rows(gold, rows)
    # 2: DOUGLAS nói mà gán NARRATOR = 0; 3: BELLAK nửa điểm; 4, 5: đúng
    assert result["counts"]["speaker"] == [2.5, 4]
    assert result["counts"]["emotion"] == [4.0, 5]
    # chỉ chấm giới tính khi đúng người: dòng 2 sai người nên không tính, dòng 5 tính
    assert result["counts"]["gender"] == [1.0, 1]
    assert result["segments_missing"] == 0


def test_the_committed_gold_files_parse() -> None:
    gold = load_gold(GOLD_DIR)
    assert len(gold) >= 399
    assert sum(row.spoken for row in gold.values()) >= 150


def test_build_training_set_drops_batches_with_uncertain_gold(tmp_path: Path, monkeypatch) -> None:
    """Mẻ có câu gold không ai đủ điểm (mọi phương án ~): replay chỉ trả tạm phương án đầu, mẫu ấy không được thành đích học."""
    import json

    import build_training_set

    rows = [{"type": "generator", "gold": "demo", "chapters": ["001"], "system": "s", "prompt": f"p{i}", "format": {},
             "response": {"segments": []}, "uncertain": ids} for i, ids in enumerate(([], ["S002"], []))]
    src = tmp_path / "replay.jsonl"
    src.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["build_training_set.py", str(src), "--out", str(tmp_path / "out")])
    build_training_set.main()
    train = (tmp_path / "out" / "train.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["messages"][1]["content"] for line in train] == ["p0", "p2"]
