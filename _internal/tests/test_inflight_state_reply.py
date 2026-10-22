"""Lời đáp chụp từ trước phải hợp với những thay đổi trong lúc chờ mạng (fixture chung JVM)."""
import json
from pathlib import Path

from abook.webui.listening import Listening


def test_reply_merges_with_changes_since_request(tmp_path):
    spec = json.loads((Path(__file__).parent / "fixtures/listening_records/inflight_reply.json").read_text(encoding="utf-8"))
    listening = Listening(tmp_path / "listening.json")
    listening.merge("b", spec["request"])
    request = listening.get("b")
    listening.merge("b", spec["current"])
    assert request["last"]["seconds"] == 10
    listening.merge("b", spec["reply"])
    assert listening.get("b") == spec["expected"]
