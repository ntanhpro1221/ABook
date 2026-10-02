"""Vòng học (scripts/model_eval/listener_labels.py): mọi quyết định của người nghe thành một tập nhãn, kèm nhãn GỐC của
máy (lấy từ sự kiện áp - sau khi áp, SQLite chỉ còn nhãn mới) và ngữ cảnh để học hay đo."""
from __future__ import annotations

import sys
from pathlib import Path

from abook.config import build_settings
from abook.listener_overrides import request_line, request_pronunciation, request_speaker, request_voice
from tests.test_listener_overrides import _Pipeline
from tests.test_listener_speakers import _book

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "model_eval"))
from listener_labels import labels, main, projects  # noqa: E402


def test_every_listener_decision_becomes_a_label_with_the_machines_original_answer(tmp_path: Path, capsys) -> None:
    paths, db = _book(tmp_path)
    request_speaker(paths.root, "c1s2", "sha-c1s2", "NATASHA", now=1.0)  # sửa: máy gán Lucien
    request_speaker(paths.root, "c1s1", "sha-c1s1", "Lucien", now=1.0)  # xác nhận nhãn máy
    request_speaker(paths.root, "c1s3", "sha-cũ", "Lucien", now=1.0)  # chữ đã đổi: không còn là nhãn của câu nào
    request_line(paths.root, "c1s3", "sha-c1s3", emotion="sad", now=1.0)
    request_voice(paths.root, "Natasha", now=1.0)  # "giữ nguyên"
    request_pronunciation(paths.root, "Natasha", "Na-ta-sa", now=1.0)
    pipeline = _Pipeline(paths, db)
    pipeline.settings = build_settings()
    pipeline._apply_listener_overrides()

    assert [project.resolve() for project in projects([tmp_path])] == [paths.root.resolve()]
    records = list(labels(paths.root))
    speakers = {record["stable_id"]: record for record in records if record["type"] == "speaker"}
    assert set(speakers) == {"c1s1", "c1s2"}
    fixed = speakers["c1s2"]
    assert (fixed["machine"], fixed["listener"], fixed["confirmed"], fixed["applied"]) == ("Lucien", "NATASHA", False, True)
    assert fixed["text"] == "“Cô chắc chứ?”" and [line["stable_id"] for line in fixed["context"]["before"]] == ["c1s0", "c1s1"]
    assert speakers["c1s1"]["confirmed"] is True, "xác nhận nhãn máy đúng cũng là một nhãn"
    (delivery,) = [record for record in records if record["type"] == "delivery"]
    assert delivery["listener"] == {"emotion": "sad"} and delivery["applied"] is True
    assert delivery["machine"]["kind"] == "dialogue"
    (voice,) = [record for record in records if record["type"] == "voice"]
    assert voice["keep"] is True and voice["character"] == "NATASHA"
    (name,) = [record for record in records if record["type"] == "pronunciation"]
    assert (name["surface"], name["listener"]) == ("Natasha", "Na-ta-sa")

    out = tmp_path / "labels.jsonl"
    assert main([str(tmp_path), "--out", str(out)]) == 0
    assert len(out.read_text(encoding="utf-8").splitlines()) == len(records)
    assert "1 câu người nghe xác nhận" in capsys.readouterr().err
