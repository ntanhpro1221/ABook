"""Công tắc B qua Studio (webui/teller_mode.py + /api/books/ID/narrator-mode): xem cái giá trước, bật/tắt sau khi người dùng xác nhận.

Sách đã phân vai: áp ngay (chỉ khi KHÔNG chạy); chưa phân vai: chỉ ghi ý muốn, worker áp sau phân vai."""
from __future__ import annotations

import json

import pytest

from abook import teller_voice
from abook.config import save_settings
from tests.test_teller_voice import _book, _speakers
from tests.test_teller_voice_b import _record_everything


@pytest.fixture
def studio(tmp_path):
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server

    paths, db, settings = _book(tmp_path / "lib")
    save_settings(paths.settings, settings)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "lib")})
    runner = FakeRunner()
    app = App(preferences=preferences, runner=runner, token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    try:
        yield paths, db, settings, server, runner
    finally:
        server.stop()


def _call(server, method: str, path: str, body: dict | None = None):
    from tests.test_webui_listen_and_sync import _request

    status, data, _ = _request(server.port, method, path, headers={"X-Ebook-Token": "t"}, body=body)
    return status, json.loads(data or b"{}")


def _url(paths) -> str:
    from abook.webui.library import book_id

    return f"/api/books/{book_id(paths.root)}/narrator-mode"


def test_the_price_is_shown_before_anything_changes(studio) -> None:
    paths, db, _settings, server, _runner = studio
    _record_everything(db)

    status, view = _call(server, "GET", _url(paths))

    assert status == 200 and view["available"] is True and view["mode"] == "narrator" and view["applied"] is False
    assert view["plan"]["direction"] == "on" and view["plan"]["lines"] == 3 and view["plan"]["recorded"] == 3
    assert view["plan"]["seconds"] > 0 and view["plan"]["tellers"] == ["Mai"]
    assert _speakers(db)["c1s0"] == "NARRATOR", "xem giá không đổi gì"


def test_turning_it_on_after_confirming_applies_it_and_turning_it_off_gives_the_book_back(studio) -> None:
    paths, db, _settings, server, _runner = studio
    _record_everything(db)

    status, view = _call(server, "PUT", _url(paths), {"mode": "teller"})

    assert status == 200 and view["mode"] == "teller" and view["applied"] is True and view["plan"]["direction"] == "off"
    assert _speakers(db)["c1s0"] == "MAI"

    status, view = _call(server, "PUT", _url(paths), {"mode": "narrator"})

    assert status == 200 and view["mode"] == "narrator" and view["applied"] is False
    assert _speakers(db)["c1s0"] == "NARRATOR" and _speakers(db)["c1s2"] == "MAI", "nội tâm A+ không tự về giọng dẫn khi đã có bản thu"


def test_a_running_book_is_refused_and_nothing_is_written(studio) -> None:
    paths, db, _settings, server, runner = studio
    runner._running.add(str(paths.root))

    status, body = _call(server, "PUT", _url(paths), {"mode": "teller"})

    assert status == 409 and "Dừng" in json.dumps(body, ensure_ascii=False)
    assert teller_voice.read(paths.root)["mode"] == "narrator" and _speakers(db)["c1s0"] == "NARRATOR"


def test_before_casting_only_the_wish_is_written(studio) -> None:
    paths, db, _settings, server, _runner = studio
    with db.transaction() as conn:
        conn.execute("UPDATE book SET casting_finalized=0")

    status, view = _call(server, "PUT", _url(paths), {"mode": "teller"})

    assert status == 200 and view["castLocked"] is False and view["plan"] is None and view["mode"] == "teller"
    assert _speakers(db)["c1s0"] == "NARRATOR"


def test_a_bad_mode_or_a_third_person_book_is_refused(studio, tmp_path) -> None:
    paths, _db, _settings, server, _runner = studio

    assert _call(server, "PUT", _url(paths), {"mode": "robot"})[0] == 400
    path = paths.settings
    data = json.loads(path.read_bytes())
    data["voices"].pop("first_person_identity")
    path.write_bytes(json.dumps(data).encode("utf-8"))
    status, view = _call(server, "GET", _url(paths))
    assert status == 200 and view["available"] is False
    assert _call(server, "PUT", _url(paths), {"mode": "teller"})[0] == 400


def test_the_phone_may_use_the_same_routes() -> None:
    from abook.webui import remote_studio

    assert remote_studio.permitted("PUT", "/api/books/abc/narrator-mode", producing=True)
    assert remote_studio.permitted("GET", "/api/books/abc/narrator-mode", producing=True)
