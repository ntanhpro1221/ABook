"""Tab Nhân vật: "Gộp vào…" (soát UX a6 01-10: máy tách một người thành hai mà Studio chỉ sửa được từng câu). Mọi câu nói của
người này thành câu của người kia trong MỘT lần ghi (một thay đổi trên nút "Áp dụng"), kèm bí danh cấp tên để phần sau của
cuốn tự hiểu; bỏ trong hộp "Áp dụng" là bỏ cả hai."""
from __future__ import annotations

import json
from pathlib import Path

from abook import aliases
from abook.config import build_settings, save_settings
from abook.listener_overrides import read_overrides
from abook.webui import store
from abook.webui.actions import FakeRunner
from abook.webui.library import Preferences, book_id
from abook.webui.server import App, Server
from tests.test_listener_speakers import _book
from tests.test_webui_listen_and_sync import _request


def test_merging_moves_every_line_once_and_drops_as_one(tmp_path: Path) -> None:
    paths, _db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="phien")
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "phien"}
    url = f"/api/books/{book_id(paths.root)}"
    try:
        status, data, _ = _request(server.port, "POST", f"{url}/characters/merge", headers=headers,
                                   body={"from": "LUCIEN", "into": "NATASHA"})
        assert status == 200, data
        assert json.loads(data)["lines"] == 2, "hai câu thoại của Lucien; lời kể nhắc tên Lucien không đụng"
        wishes = read_overrides(paths.root)["speakers"]
        assert sorted(wishes) == ["c1s1", "c1s2"] and {entry["speaker"] for entry in wishes.values()} == {"NATASHA"}
        assert aliases.load(paths.root) == {aliases.key("LUCIEN"): "NATASHA"}, "phần sau của cuốn cũng hiểu"
        assert store.pending_changes(paths.root, 0.0) == 1, "một lần gộp = một thay đổi"
        (item,) = store.pending_details(paths.root, 0.0)["items"]
        assert item["label"] == "2 câu là lời của Natasha" and sorted(item["keys"]) == ["c1s1", "c1s2"]

        status, data, _ = _request(server.port, "POST", f"{url}/pending-changes/withdraw", headers=headers, body={
            "section": item["section"], "key": item["key"], "keys": item["keys"], "requestedAt": item["requestedAt"]})
        assert status == 200, data
        assert not read_overrides(paths.root).get("speakers") and aliases.load(paths.root) == {}

        status, data, _ = _request(server.port, "POST", f"{url}/characters/merge", headers=headers,
                                   body={"from": "Lucien", "into": "LUCIEN"})
        assert status == 400, "cùng một người"
    finally:
        server.stop()
        app.close()
