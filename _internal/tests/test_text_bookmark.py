import json
from pathlib import Path
from types import SimpleNamespace

from abook.webui.listening import Listening

MARK = json.loads((Path(__file__).parent / "fixtures/records/text_bookmark.json").read_text(encoding="utf-8"))


def test_text_bookmark_survives_sync_edit_reopen_and_undo(tmp_path):
    desktop = Listening(tmp_path / "desktop.json")
    phone = Listening(tmp_path / "phone.json")
    desktop.merge("b", {"bookmarks": [MARK]})
    assert desktop.get("b")["bookmarks"] == [MARK]
    desktop.update_bookmark("b", MARK["id"], "ghi chú")
    phone.merge("b", desktop.get("b"))
    edited = phone.get("b")["bookmarks"][0]
    assert edited["anchor"] == MARK["anchor"]
    phone.delete_bookmark("b", MARK["id"])
    restored = phone.restore_bookmark("b", edited)
    assert restored["anchor"] == MARK["anchor"]
    desktop.merge("b", phone.get("b"))
    reopened = Listening(tmp_path / "desktop.json").get("b")["bookmarks"][0]
    assert reopened["anchor"] == MARK["anchor"]
    assert (reopened["index"], reopened["quote"]) == (MARK["index"], MARK["quote"])


def test_add_bookmark_accepts_and_validates_anchor(tmp_path):
    listening = Listening(tmp_path / "state.json")
    mark = listening.add_bookmark("b", 1, 6, index=2, quote=MARK["quote"], anchor=MARK["anchor"])
    assert mark["anchor"] == MARK["anchor"]
    invalid = listening.add_bookmark("b", 2, 6, anchor={"segment": -1})
    assert "anchor" not in invalid


def test_bookmark_http_handler_passes_anchor_to_the_store(tmp_path):
    from abook.webui.server import Handler

    listening = Listening(tmp_path / "state.json")
    responses = []
    handler = SimpleNamespace(
        app=SimpleNamespace(listening=listening, _listenable=lambda book: None,
                            sync_remote_state=lambda *args, **kwargs: None),
        _body=lambda: MARK,
        _send_json=lambda status, body: responses.append((status, body)),
    )
    Handler.post_bookmark(handler, {}, "b")
    assert responses[0][0] == 201
    assert responses[0][1]["anchor"] == MARK["anchor"]
