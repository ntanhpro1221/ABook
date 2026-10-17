"""Tải sẵn bài nhạc kế cho trình phát máy tính (POST /api/music/warm, PLAN_lx F1a): trả ngay, MỘT luồng nền, bỏ trùng, bài đã có thì khỏi
tải, hỏng thì im lặng (mốc ấy tới thì tự tải và tự thử lại như cũ)."""
from __future__ import annotations

import io
import threading
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_music_api import CALM, CALM2, _with_catalog


class _Response(io.BytesIO):
    def __init__(self) -> None:
        super().__init__(b"ID3" + b"\0" * 100)
        self.headers = {"Content-Length": "103"}


class _Network:
    """urlopen giả: ghi các link đã gọi và số lượt tải chạy CÙNG LÚC; `gate` (nếu có) giữ lượt tải lại tới khi mở."""

    def __init__(self, monkeypatch, gate: threading.Event | None = None, fail: bool = False) -> None:
        self.calls: list[str] = []
        self.running = 0
        self.peak = 0
        self.gate = gate
        self.fail = fail
        self.started = threading.Event()
        self._lock = threading.Lock()
        monkeypatch.setattr(urllib.request, "urlopen", self._open)

    def _open(self, request, timeout=0):
        with self._lock:
            self.calls.append(request.full_url)
            self.running += 1
            self.peak = max(self.peak, self.running)
        self.started.set()
        try:
            if self.gate is not None:
                self.gate.wait(10)
            if self.fail:
                raise urllib.error.URLError("không có mạng")
            return _Response()
        finally:
            with self._lock:
                self.running -= 1


def _idle(app) -> None:
    """Chờ luồng tải sẵn làm hết hàng (nó tự thoát khi hàng rỗng)."""
    with app._music_warm_lock:
        thread = app._music_warm_thread
    if thread is not None:
        thread.join(10)
        assert not thread.is_alive()


def _warm(server, link: str):
    return _call(server, "POST", "/api/music/warm?link=" + quote(link, safe=""))


def test_the_request_returns_at_once_and_the_track_arrives_in_the_cache(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    gate = threading.Event()
    network = _Network(monkeypatch, gate)
    status, answer = _warm(server, CALM)  # lượt tải còn bị giữ: yêu cầu mà chặn thì dòng này không bao giờ về
    assert status == 200 and answer == {"queued": True}
    assert network.started.wait(5) and app.music_track_cached(CALM) is None
    gate.set()
    _idle(app)
    assert app.music_track_cached(CALM) is not None
    assert network.calls == [CALM]


def test_a_track_already_in_the_cache_is_not_downloaded_again(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    network = _Network(monkeypatch)
    assert _warm(server, CALM)[1] == {"queued": True}
    _idle(app)
    assert _warm(server, CALM)[1] == {"queued": False}
    _idle(app)
    assert network.calls == [CALM]


def test_duplicates_are_dropped_and_only_one_track_downloads_at_a_time(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    gate = threading.Event()
    network = _Network(monkeypatch, gate)
    assert _warm(server, CALM)[1] == {"queued": True}
    assert network.started.wait(5)
    assert _warm(server, CALM)[1] == {"queued": False}, "bài đang tải được xin lần nữa"
    assert _warm(server, CALM2)[1] == {"queued": True}
    assert _warm(server, CALM2)[1] == {"queued": False}, "bài đang chờ trong hàng được xin lần nữa"
    gate.set()
    _idle(app)
    assert network.calls == [CALM, CALM2] and network.peak == 1, "mỗi bài một lượt tải, lần lượt, không song song"
    assert app.music_track_cached(CALM2) is not None


def test_a_failed_download_is_silent_and_the_worker_carries_on(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    failing = _Network(monkeypatch, fail=True)
    status, answer = _warm(server, CALM)
    assert status == 200 and answer == {"queued": True}
    _idle(app)
    assert failing.calls == [CALM] and app.music_track_cached(CALM) is None
    app._music_hosts.clear()  # mạng về: nguồn không còn bị coi là nghỉ
    app._music_unavailable.clear()
    working = _Network(monkeypatch)
    assert _warm(server, CALM2)[1] == {"queued": True}
    _idle(app)
    assert working.calls == [CALM2] and app.music_track_cached(CALM2) is not None


def test_while_offline_nothing_is_fetched_and_a_link_outside_the_catalog_is_ignored(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    network = _Network(monkeypatch)
    app._music_note("https://x/calm.mp3", failed=True)  # nguồn vừa hỏng vì mạng: khỏi chờ nó
    assert _warm(server, CALM)[1] == {"queued": True}
    _idle(app)
    assert network.calls == []
    app._music_hosts.clear()
    assert _warm(server, "https://x/not-in-the-catalog.mp3")[0] == 200
    _idle(app)
    assert network.calls == [], "link ngoài danh mục không thành chỗ tải hộ"
    assert _warm(server, "http://x/plain.mp3")[0] == 400


def test_a_full_queue_drops_the_oldest_waiting_track(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    from abook.webui.server import MUSIC_WARM_QUEUE

    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    gate = threading.Event()
    network = _Network(monkeypatch, gate)
    assert _warm(server, CALM)[1] == {"queued": True}
    assert network.started.wait(5)
    waiting = [f"https://x/wait{n}.mp3" for n in range(MUSIC_WARM_QUEUE + 1)]
    for link in waiting:
        _warm(server, link)
    with app._music_warm_lock:
        assert list(app._music_warm_queue) == waiting[1:]
    gate.set()
    _idle(app)
