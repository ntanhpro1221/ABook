"""Soát a83 B5: bỏ một thay đổi chờ áp khi sách đang chạy. Chạy thường: máy có thể đang áp chính yêu cầu ấy -> từ chối và nói đúng cách làm.
Tạm dừng ĐÃ tới checkpoint (sổ ghi "paused"): dây chuyền đứng yên, rút được an toàn."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.listener_overrides import read_overrides
from abook.webui.library import Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.server import App, Server
from tests.test_listener_speakers import _book
from tests.test_webui_listen_and_sync import FakeRunner, _request

LINE = {"stableId": "c1s2", "textSha256": "sha-c1s2"}


@pytest.fixture
def studio(tmp_path: Path):
    paths, db = _book(tmp_path)
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
        yield paths, db, runner, post
    finally:
        server.stop()


def _decide(post, paths) -> dict:
    _status, made = post("speaker", {"lines": [LINE], "speaker": "NATASHA"})
    return {"section": "speakers", "key": "c1s2", "requestedAt": made["requestedAt"]}


def test_running_book_refuses_and_says_how_to_withdraw_truthfully(studio) -> None:
    paths, _db, runner, post = studio
    body = _decide(post, paths)
    runner.start(paths.root)
    status, answer = post("pending-changes/withdraw", body)
    assert status == 409
    assert "Tạm dừng hẳn" not in answer["error"], "Tạm dừng không mở khoá nếu chưa tới checkpoint - lời hướng dẫn không được nói sai"
    assert "Đã tạm dừng" in answer["error"] and "Bạn" in answer["error"]
    assert "c1s2" in read_overrides(paths.root)["speakers"]


def test_paused_but_not_yet_at_the_checkpoint_still_refuses(studio) -> None:
    paths, _db, runner, post = studio
    body = _decide(post, paths)
    runner.start(paths.root)
    runner.pause(paths.root, True)  # đã bấm, dây chuyền còn làm nốt việc dở: sổ chưa ghi "paused"
    status, _answer = post("pending-changes/withdraw", body)
    assert status == 409


def test_paused_at_the_checkpoint_can_withdraw(studio) -> None:
    paths, db, runner, post = studio
    body = _decide(post, paths)
    runner.start(paths.root)
    runner.pause(paths.root, True)
    db.update_book(status="paused", stage="paused")  # đúng cái Pipeline._wait_pause_or_stop ghi khi tới checkpoint
    status, answer = post("pending-changes/withdraw", body)
    assert status == 200, answer
    assert "c1s2" not in read_overrides(paths.root).get("speakers", {})
