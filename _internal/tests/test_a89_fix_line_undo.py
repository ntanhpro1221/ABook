"""a89 V7: sửa cách đọc một câu (POST /line) có Hoàn tác như người nói / cách đọc / giọng; T2: rút yêu cầu khi sách đang chạy."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook import listener_overrides as lo
from abook.webui.library import Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.server import App, Server
from tests.test_listener_speakers import _book
from tests.test_webui_listen_and_sync import FakeRunner, _request


@pytest.fixture
def studio(tmp_path: Path):
    paths, _db = _book(tmp_path)
    (paths.root / "book_settings.json").write_text("{}", encoding="utf-8")
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    runner = FakeRunner()
    app = App(preferences=preferences, runner=runner, token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()

    def post(endpoint: str, body: dict) -> tuple[int, dict]:
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(paths.root)}/{endpoint}", headers={"X-Ebook-Token": "t"}, body=body)
        return status, json.loads(data)

    try:
        yield paths, post, app
    finally:
        server.stop()


def _segment(paths, stable_id: str):
    from abook.webui import store
    from contextlib import closing

    with closing(store.connect(paths.root)) as connection:
        return connection.execute("SELECT kind, text_sha256 FROM segments WHERE stable_id=?", (stable_id,)).fetchone()


def test_a_line_fix_can_be_withdrawn_by_the_mark_it_returned(studio) -> None:
    paths, post, _app = studio
    sha = str(_segment(paths, "c1s1")["text_sha256"])
    status, answer = post("line", {"stableId": "c1s1", "textSha256": sha, "emotion": "sad"})
    assert status == 200, answer
    assert answer["requestedAt"] > 0
    assert lo.read_overrides(paths.root)["lines"]["c1s1"]["emotion"] == "sad"
    status, undone = post("line", {"stableId": "c1s1", "withdraw": True, "requestedAt": answer["requestedAt"]})
    assert status == 200 and undone["undone"] == 1, undone
    assert not lo.read_overrides(paths.root).get("lines")


def test_a_line_fix_replaced_by_a_later_one_cannot_be_withdrawn_by_the_old_mark(studio) -> None:
    paths, post, _app = studio
    sha = str(_segment(paths, "c1s1")["text_sha256"])
    _s, first = post("line", {"stableId": "c1s1", "textSha256": sha, "emotion": "sad"})
    _s, second = post("line", {"stableId": "c1s1", "textSha256": sha, "emotion": "angry"})
    status, answer = post("line", {"stableId": "c1s1", "withdraw": True, "requestedAt": first["requestedAt"]})
    assert status == 409, answer
    status, _answer = post("line", {"stableId": "c1s1", "withdraw": True, "requestedAt": second["requestedAt"]})
    assert status == 200
    assert not lo.read_overrides(paths.root).get("lines"), "cách đọc câu không giữ yêu cầu cũ (listener_overrides.request_line không ghi `replaced`)"


def test_a_line_fix_the_pipeline_already_took_cannot_be_withdrawn_quietly(studio) -> None:
    from abook.database import ProjectDB
    from abook.models import ProjectPaths
    from abook.webui import store

    paths, post, _app = studio
    sha = str(_segment(paths, "c1s1")["text_sha256"])
    _s, answer = post("line", {"stableId": "c1s1", "textSha256": sha, "emotion": "sad"})
    entry = lo.read_overrides(paths.root)["lines"]["c1s1"]
    db = ProjectDB(ProjectPaths.build(paths.root).db)
    with db.connect() as conn:  # dây chuyền đã áp: câu mang cảm xúc mới + biên nhận khớp
        conn.execute("UPDATE segments SET emotion='sad' WHERE stable_id='c1s1'")
    stamp = store.receipt_stamp(entry)
    db.record_listener_receipt("lines", "c1s1", stamp[0], stamp[1])
    status, refused = post("line", {"stableId": "c1s1", "withdraw": True, "requestedAt": answer["requestedAt"]})
    assert status == 409 and "không hoàn tác được" in refused["error"], refused
    assert lo.read_overrides(paths.root)["lines"]["c1s1"]["emotion"] == "sad", "yêu cầu đã áp được giữ nguyên"


def test_the_apply_box_may_drop_a_pending_change_while_the_book_runs(studio) -> None:
    """T2: như Hoàn tác trên thông báo - rút lúc sách chạy được khi dây chuyền chưa áp; đã áp thì nói thật."""
    paths, post, app = studio
    sha = str(_segment(paths, "c1s1")["text_sha256"])
    _s, answer = post("line", {"stableId": "c1s1", "textSha256": sha, "emotion": "sad"})
    app.runner.running = lambda _path: True  # type: ignore[method-assign]
    status, done = post("pending-changes/withdraw", {"section": "lines", "key": "c1s1", "requestedAt": answer["requestedAt"]})
    assert status == 200 and done["withdrawn"] == 1, done
    assert not lo.read_overrides(paths.root).get("lines")
