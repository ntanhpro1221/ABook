import pytest

from abook.webui.listening import Listening, merge_states
from abook.webui.reading_anchor import validated


def test_progress_preserves_text_anchor_across_restart_and_sync(tmp_path):
    path = tmp_path / "listening.json"
    anchor = {"segment": 2, "charOffset": 6, "textHash": "fnv1a64:1234567890abcdef"}
    listening = Listening(path)
    state = listening.progress("book", 1, 42.0, 100.0, anchor=anchor)
    assert state["last"]["anchor"] == anchor
    assert Listening(path).get("book")["last"]["anchor"] == anchor
    assert merge_states({}, state)["last"]["anchor"] == anchor
    state = listening.progress("book", 1, 50.0, 100.0)
    assert "anchor" not in state["last"]


@pytest.mark.parametrize("field,value", [("segment", -1), ("segment", True), ("charOffset", 1.5),
                                         ("charOffset", 2**31), ("textHash", "changed")])
def test_invalid_anchor_is_ignored(field, value):
    anchor = {"segment": 1, "charOffset": 6, "textHash": "fnv1a64:bb657205cfbee8a0", field: value}
    assert validated(anchor) is None
