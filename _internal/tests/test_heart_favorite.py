"""Thả tim (yêu thích) cho sách: trạng thái NGƯỜI NGHE trong hồ sơ nghe (không vào file .abook), đi cùng đồng bộ hồ sơ nghe như
`finished` - giá trị + mốc giờ + phiên bản, lần thả mới hơn thắng. Bản Kotlin: HeartFavoriteTest.kt."""
from __future__ import annotations

from pathlib import Path

from abook.webui import server
from abook.webui.listening import Listening, merge_states
from abook.webui.listening_revision import checked_peer
from abook.webui.listening_schema import clean_state
from abook.webui.remote_studio import permitted

BOOK = "0123456789ab"


def test_a_book_is_not_a_favorite_until_the_listener_says_so(tmp_path: Path) -> None:
    store = Listening(tmp_path / "listening.json")
    assert not store.get(BOOK).get("favorite")


def test_toggling_stores_value_stamp_and_revision_and_survives_reopen(tmp_path: Path) -> None:
    store = Listening(tmp_path / "listening.json")
    state = store.set_favorite(BOOK, True)
    assert state["favorite"] is True and state["favoriteAt"] > 0 and state["_fieldRevs"]["favorite"]["counter"] > 0
    first = state["_fieldRevs"]["favorite"]["counter"]
    reopened = Listening(tmp_path / "listening.json")
    assert reopened.get(BOOK)["favorite"] is True
    off = reopened.set_favorite(BOOK, False)
    assert off["favorite"] is False and off["_fieldRevs"]["favorite"]["counter"] > first


def test_the_newer_heart_wins_a_merge_both_ways() -> None:
    older = {"chapters": {}, "favorite": True, "favoriteAt": 10, "_fieldRevs": {"favorite": {"counter": 1, "node": "a"}}}
    newer = {"chapters": {}, "favorite": False, "favoriteAt": 20, "_fieldRevs": {"favorite": {"counter": 2, "node": "b"}}}
    assert merge_states(older, newer)["favorite"] is False
    assert merge_states(newer, older)["favorite"] is False
    assert merge_states({"chapters": {}}, older)["favorite"] is True, "máy chưa thả tim nhận tim của máy kia"


def test_a_heart_without_revision_is_dropped_whole() -> None:
    clean = clean_state({"favorite": True, "favoriteAt": 5, "_fieldRevs": {}})
    assert "favorite" not in clean and "favoriteAt" not in clean
    kept = clean_state({"favorite": True, "favoriteAt": 5, "_fieldRevs": {"favorite": {"counter": 1, "node": "n"}}})
    assert kept["favorite"] is True and kept["favoriteAt"] == 5
    assert checked_peer({}, kept, lambda _text: None)["favorite"] is True


def test_the_api_route_is_open_to_listen_only_devices() -> None:
    assert any(handler is server.Handler.post_favorite for method, pattern, handler in server.ROUTES
               if method == "POST" and pattern.fullmatch(f"/api/listen/books/{BOOK}/favorite"))
    assert permitted("POST", f"/api/listen/books/{BOOK}/favorite", producing=False)
