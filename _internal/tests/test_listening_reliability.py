"""Chỗ nghe chỉ được nhận sau khi ghi bền; cửa sổ cũ không đè phiên mới (a78)."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from abook.webui import listening as module, notices
from abook.webui.listening import Listening
from abook.webui.server import Handler, ApiError
from abook.webui.library import Preferences


def test_progress_unread_is_retryable_and_does_not_change_ram(tmp_path, monkeypatch):
    listening = Listening(tmp_path / "listening.json")
    listening.progress("book", 1, 10, 100)
    before = listening.get("book")
    listening._unread = True

    def held():
        raise notices.Unreadable("đang bị giữ")

    monkeypatch.setattr(listening, "_read", held)
    handler = SimpleNamespace(app=SimpleNamespace(
        listening=listening, _listenable=lambda value: None, sync_remote_state=lambda *a, **k: None),
        _body=lambda: {"chapterId": 1, "seconds": 20, "duration": 100},
        _send_json=lambda *a: pytest.fail("không được ACK khi chưa ghi"))
    with pytest.raises(ApiError) as caught:
        Handler.post_progress(handler, {}, "book")
    assert caught.value.status == 503
    assert "thử lại" in str(caught.value).lower()
    assert listening.get("book") == before
    assert Listening(listening.path).get("book") == before


def test_progress_write_failure_rolls_back_then_retries(tmp_path, monkeypatch):
    listening = Listening(tmp_path / "listening.json")
    listening.progress("book", 1, 10, 100)
    before = listening.get("book")
    with monkeypatch.context() as patch:
        patch.setattr(module, "atomic_write_json", lambda *a, **k: (_ for _ in ()).throw(PermissionError("held")))
        patch.setattr(module, "_append_journal", lambda *a, **k: (_ for _ in ()).throw(PermissionError("held")))  # chỗ nghe thường nối vào nhật ký
        with pytest.raises(OSError):
            listening.progress("book", 1, 20, 100)
    assert listening.get("book") == before
    listening.progress("book", 1, 20, 100)
    assert Listening(listening.path).get("book")["last"]["seconds"] == 20


def test_superseded_playback_and_old_revision_cannot_write(tmp_path):
    listening = Listening(tmp_path / "listening.json")
    listening.begin_progress("book", "tab-a")
    listening.progress("book", 1, 10, 100, session_id="tab-a", revision=1)
    listening.begin_progress("book", "tab-b")
    listening.progress("book", 1, 60, 100, session_id="tab-b", revision=2)
    before = listening.path.read_bytes()
    with pytest.raises(module.StalePlayback):
        listening.begin_progress("book", "tab-a")  # thử lại ACK đăng ký bị mất không giành lại quyền của tab-b
    with pytest.raises(module.StalePlayback):
        listening.progress("book", 1, 20, 100, session_id="tab-a", revision=99)
    with pytest.raises(module.StalePlayback):
        listening.progress("book", 1, 30, 100, session_id="tab-b", revision=1)
    assert listening.path.read_bytes() == before
    # Đọc lại tiến trình vẫn từ chối tab cũ; điện thoại giữ luật timestamp riêng.
    reopened = Listening(listening.path)
    with pytest.raises(module.StalePlayback):
        reopened.progress("book", 1, 20, 100, session_id="tab-a", revision=100)
    reopened.progress("book", 1, 80, 100)
    assert reopened.get("book")["last"]["seconds"] == 80


def test_page_loads_do_not_grow_the_profile_forever(tmp_path):
    listening = Listening(tmp_path / "listening.json")
    for number in range(module.PLAYBACK_SESSIONS_KEPT + 10):
        listening.begin_progress("book", f"load-{number}")
        listening.progress("book", 1, number, 100, session_id=f"load-{number}", revision=1)
    owner = next(iter(listening._data["records"].values()))
    assert len(owner["_playbackSessions"]) == module.PLAYBACK_SESSIONS_KEPT
    with pytest.raises(module.StalePlayback):  # phiên đã bị bỏ khỏi sổ cũng là phiên đã bị thay thế
        listening.progress("book", 1, 5, 100, session_id="load-0", revision=2)


def test_stale_playback_route_returns_409_without_ack(tmp_path):
    listening = Listening(tmp_path / "listening.json")
    listening.begin_progress("book", "new")
    handler = SimpleNamespace(app=SimpleNamespace(
        listening=listening, _listenable=lambda value: None, sync_remote_state=lambda *a, **k: None),
        _body=lambda: {"chapterId": 1, "seconds": 20, "sessionId": "old", "revision": 1},
        _send_json=lambda *a: pytest.fail("phiên cũ không được ACK"))
    with pytest.raises(ApiError) as caught:
        Handler.post_progress(handler, {}, "book")
    assert caught.value.status == 409


def test_default_readaloud_voice_survives_backend_restart(tmp_path):
    path = tmp_path / "preferences.json"
    Preferences(path).update({"readAloudVoice": "edge:vi-VN-NamMinhNeural"})
    assert Preferences(path).get()["readAloudVoice"] == "edge:vi-VN-NamMinhNeural"


def test_loading_an_idle_tab_does_not_take_progress_ownership_until_it_moves(tmp_path):
    listening = Listening(tmp_path / "listening.json")
    listening.begin_progress("book", "playing")
    listening.progress("book", 1, 10, 100, session_id="playing", revision=1)
    listening.begin_progress("book", "idle")
    listening.progress("book", 1, 20, 100, session_id="playing", revision=2)
    listening.progress("book", 1, 40, 100, session_id="idle", revision=1)
    with pytest.raises(module.StalePlayback):
        listening.progress("book", 1, 30, 100, session_id="playing", revision=3)
