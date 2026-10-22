"""Soát a83 B8: sửa một câu "lời kể -> lời thoại + người nói" ghi hai mục (lines + speakers) cùng mốc; với người dùng là MỘT thay đổi - nút đếm 1, hộp
có 1 mục, "Bỏ" mục ấy bỏ cả hai."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook import listener_overrides as lo
from abook.webui import store
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
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()

    def post(endpoint: str, body: dict) -> tuple[int, dict]:
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(paths.root)}/{endpoint}", headers={"X-Ebook-Token": "t"}, body=body)
        return status, json.loads(data)

    try:
        yield paths, post
    finally:
        server.stop()


def test_one_sentence_edit_with_a_speaker_counts_once(studio) -> None:
    paths, _post = studio
    lo.request_line(paths.root, "c1s0", "sha-c1s0", kind="dialogue", emotion="sad", speaker="LUCIEN", now=10.0)
    assert store.pending_changes(paths.root, 0.0) == 1
    details = store.pending_details(paths.root, 0.0)
    assert [item["kind"] for item in details["items"]] == ["line"]
    assert "lời của" in details["items"][0]["label"]


def test_withdrawing_that_item_withdraws_both(studio) -> None:
    paths, post = studio
    lo.request_line(paths.root, "c1s0", "sha-c1s0", kind="dialogue", emotion="sad", speaker="LUCIEN", now=10.0)
    item = store.pending_details(paths.root, 0.0)["items"][0]
    status, _answer = post("pending-changes/withdraw", {"section": item["section"], "key": item["key"], "requestedAt": item["requestedAt"]})
    assert status == 200
    data = lo.read_overrides(paths.root)
    assert not data.get("lines") and not data.get("speakers")


def test_an_older_separate_speaker_decision_is_not_swallowed(studio) -> None:
    paths, _post = studio
    lo.request_speaker(paths.root, "c1s2", "sha-c1s2", "NATASHA", now=5.0)
    lo.request_line(paths.root, "c1s2", "sha-c1s2", emotion="sad", now=10.0)
    assert store.pending_changes(paths.root, 0.0) == 2, "người nói đặt riêng ở lần bấm khác vẫn là một thay đổi riêng"


def test_a_speaker_decision_before_casting_gets_the_true_reason(studio) -> None:
    """Soát a83 B9: giữa pha phân tích (chưa phân vai) lời từ chối là "chưa phân vai xong", không phải "người này chưa nói câu nào"."""
    from abook.database import ProjectDB
    from abook.models import ProjectPaths
    from abook.webui.server import NOT_CAST_YET

    paths, post = studio
    db = ProjectDB(ProjectPaths.build(paths.root).db)
    with db.connect() as conn:  # trạng thái trước phân vai: nhãn người nói có, chưa gán nhân vật / giọng
        conn.execute("UPDATE segments SET voice_profile_id=NULL, canonical_character_id=NULL, status='analyzed'")
        conn.execute("DELETE FROM voice_profiles")
        conn.execute("DELETE FROM characters")
        conn.execute("UPDATE book SET casting_finalized=0")
    status, answer = post("speaker", {"lines": [{"stableId": "c1s2", "textSha256": "sha-c1s2"}], "speaker": "NATASHA"})
    assert status == 400 and answer["error"] == NOT_CAST_YET


def test_a_group_review_that_fails_midway_says_how_many_were_already_written(studio, monkeypatch) -> None:
    """Soát a83 B11 (c): nhóm nhiều câu ghi lần lượt; lỗi giữa chừng không được báo như chưa ghi gì."""
    from abook.webui import reviews as reviews_module

    paths, post = studio
    real = reviews_module.Reviews.set
    calls = {"n": 0}

    def flaky(self, project, stable_id, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise ValueError("Bản thu đã đổi")
        return real(self, project, stable_id, *args, **kwargs)

    monkeypatch.setattr(reviews_module.Reviews, "set", flaky)
    lines = [{"stableId": "c1s1"}, {"stableId": "c1s2"}, {"stableId": "c1s3"}]
    status, answer = post("review", {"verdict": "ok", "chapterId": 1, "lines": lines})
    assert status == 409 and "1 câu trước đó" in answer["error"]
