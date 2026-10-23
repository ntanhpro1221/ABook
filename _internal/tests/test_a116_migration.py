import copy
import json
from pathlib import Path

import pytest

from abook.webui.listening import Listening, default_record_id, merge_states
from abook.webui import listening
from abook.webui.listening_revision import MISSING_REVISION, OLD_PEER, checked_peer, upgrade_local

FIXTURE = Path(__file__).parent / "fixtures/listening_revision/legacy132.json"


@pytest.mark.parametrize("format2", [True, False])
def test_two_132_profiles_upgrade_persist_and_sync(tmp_path, monkeypatch, format2):
    stores = []
    for machine in ("left", "right"):
        folder = tmp_path / machine
        folder.mkdir()
        monkeypatch.setenv("ABOOK_PREFERENCES", str(folder / "preferences.json"))
        path = folder / "listening.json"
        state = json.loads(FIXTURE.read_text("utf-8"))
        record = default_record_id("book")
        raw = {"version": 2, "records": {record: {"name": "Mặc định", "state": state}},
               "links": {"book": {"records": [record], "active": record}}, "deleted": {}} if format2 else {"book": state}
        path.write_text(json.dumps(raw), encoding="utf-8")
        store = Listening(path)
        before = path.read_bytes()
        assert Listening(path).get("book") == store.get("book")
        assert path.read_bytes() == before
        stores.append(store)
    a, b = [store.sync_request("book") for store in stores]
    assert a["last"]["rev"]["node"] != b["last"]["rev"]["node"]
    assert merge_states(a, b) == merge_states(b, a)
    for own, peer in ((stores[0], b), (stores[1], a)):
        reply = own.merge_record("book", peer["record"], peer)
        assert {m["id"] for m in reply["bookmarks"]} == {"kept"}
        assert set(reply["chapters"]) == {"1", "2"}
        assert reply["deleted"] == {"gone": 12}


def test_upgrade_uses_history_then_key_and_preserves_existing_revisions():
    state = json.loads(FIXTURE.read_text("utf-8"))
    assert upgrade_local(state, "test")
    assert state["chapters"]["1"]["rev"]["counter"] == 1
    assert state["chapters"]["2"]["rev"]["counter"] == 2
    assert state["reading"]["rev"]["counter"] == 9
    before = copy.deepcopy(state)
    assert not upgrade_local(state, "other")
    assert state == before


def test_missing_revision_is_data_error_and_explicit_old_capability_is_old_peer():
    with pytest.raises(ValueError, match=MISSING_REVISION):
        checked_peer({}, {"listeningRevision": 1, "rate": 1.5}, lambda _: None)
    with pytest.raises(ValueError, match=OLD_PEER):
        checked_peer({}, {"listeningRevision": 0}, lambda _: None)


def test_failed_migration_keeps_original_and_blocks_sync_until_commit(tmp_path, monkeypatch):
    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "preferences.json"))
    path = tmp_path / "listening.json"
    path.write_text(json.dumps({"book": json.loads(FIXTURE.read_text("utf-8"))}), encoding="utf-8")
    original = path.read_bytes()
    atomic = listening.atomic_write_json
    def blocked(target, *args, **kwargs):
        if target == path:
            raise PermissionError("locked")
        return atomic(target, *args, **kwargs)
    monkeypatch.setattr(listening, "atomic_write_json", blocked)
    store = Listening(path)
    assert store.get("book")["bookmarks"][0]["id"] == "kept"
    with pytest.raises(OSError):
        store.sync_request("book")
    assert path.read_bytes() == original
    monkeypatch.setattr(listening, "atomic_write_json", atomic)
    assert store.sync_request("book")["last"]["rev"]["counter"] > 0
    assert path.read_bytes() != original
