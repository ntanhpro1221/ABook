"""Tải sẵn nhạc nền (soát UX a23 B12): không tải khi nhạc tắt; "Đổi bài" chỉ tải bài mới; báo MB đã tải / tổng và huỷ được;
bài quá lớn (MUSIC_TRACK_MAX_MB) coi như không dùng được ở máy này - rãnh nhạc chọn bài khác thay vì tải nó."""
from __future__ import annotations

import io
import json
import threading
from pathlib import Path

from abook.webui.library import book_id
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_music_api import CALM, CALM2, _forced_plan, _with_catalog

MB = 1024 * 1024


class _Response(io.BytesIO):
    """Trả lời HTTP giả: nội dung + Content-Length (có thể nói dối cỡ để thử bài quá lớn)."""

    def __init__(self, data: bytes, length: int | None = None) -> None:
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data) if length is None else length)}


def _fake_network(monkeypatch, gate: threading.Event | None = None, lengths: dict[str, int] | None = None) -> list[str]:
    import urllib.request

    calls: list[str] = []

    def open_(request, timeout=0):
        calls.append(request.full_url)
        if gate is not None:
            gate.wait(10)
        return _Response(b"ID3" + b"\0" * 100, (lengths or {}).get(request.full_url))

    monkeypatch.setattr(urllib.request, "urlopen", open_)
    return calls


def _settle() -> None:
    for thread in threading.enumerate():
        if thread.name == "music-warm":
            thread.join(10)


def _built_without_warming(app, server, book: str) -> None:
    """Dựng rãnh nhạc lần đầu mà không tải gì (bộ đệm rỗng), để test thấy đúng lượt tải của thao tác kế."""
    app._warm_music = lambda *args, **kwargs: None
    try:
        _call(server, "GET", f"/api/books/{book}/music")
    finally:
        del app._warm_music


def test_turning_music_off_downloads_nothing(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    calls = _fake_network(monkeypatch)
    _built_without_warming(app, server, book)
    _forced_plan(paths, CALM, count=2)
    status, _view = _call(server, "PUT", f"/api/books/{book}/music", {"enabled": False})
    _settle()
    assert status == 200 and calls == [], "tắt nhạc mà vẫn tải bài"
    _call(server, "PUT", f"/api/books/{book}/music", {"enabled": True})
    _settle()
    assert calls, "bật lại thì tải bài của rãnh nhạc"


def test_changing_one_scenes_track_downloads_only_the_new_track(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    calls = _fake_network(monkeypatch)
    _built_without_warming(app, server, book)
    plan = _forced_plan(paths, CALM, count=3)
    status, changed = _call(server, "PUT", f"/api/books/{book}/music", {"pins": {plan["scenes"][0]["key"]: CALM2}})
    _settle()
    assert status == 200 and changed["plan"]["scenes"][0]["link"] == CALM2
    assert calls == [CALM2], "Đổi bài một đoạn mà tải lại bài của mọi đoạn khác"


def test_a_track_too_big_for_this_machine_is_never_downloaded_and_another_one_plays(studio, tmp_path: Path,  # noqa: F811
                                                                                  monkeypatch) -> None:
    from abook.webui import music_plan
    from abook.webui.server import MUSIC_TRACK_MAX_MB

    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    catalog = app.music_catalog()
    real_lookup = catalog.lookup
    monkeypatch.setattr(catalog, "lookup", lambda links: {link: dict(info, bytes=(MUSIC_TRACK_MAX_MB + 1) * MB)
                                                          if link == CALM else info for link, info in real_lookup(links).items()})
    calls = _fake_network(monkeypatch)
    _built_without_warming(app, server, book)
    _forced_plan(paths, CALM, count=3)
    app._warm_run(music_plan.read_plan(paths.root), book)
    assert CALM not in calls, "bài quá lớn vẫn bị tải"
    assert [scene["link"] for scene in music_plan.read_plan(paths.root)["scenes"]] == [CALM2] * 3
    assert app.music_track_available(CALM) is False


def test_a_track_whose_server_says_it_is_too_big_is_dropped_without_saving_it(studio, tmp_path: Path,  # noqa: F811
                                                                           monkeypatch) -> None:
    from abook.webui.server import MUSIC_TRACK_MAX_MB

    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    _fake_network(monkeypatch, lengths={CALM: (MUSIC_TRACK_MAX_MB + 1) * MB})
    assert app.music_track_for_export(CALM) is None
    assert app.music_track_cached(CALM) is None and not list((app.music_dir / "files").glob("*.part"))
    assert app.music_track_available(CALM) is False and app.music_track_available(CALM2) is True


def test_the_music_tab_shows_download_progress_and_can_cancel_it(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    gate = threading.Event()
    calls = _fake_network(monkeypatch, gate=gate)
    _built_without_warming(app, server, book)
    plan = _forced_plan(paths, CALM, count=2)
    plan["scenes"][1]["link"] = CALM2
    (paths.root / "music_plan.json").write_bytes(json.dumps(plan).encode("utf-8"))
    app._warm_music(plan, book)
    for _ in range(200):
        if calls:
            break
        threading.Event().wait(0.01)
    _status, view = _call(server, "GET", f"/api/books/{book}/music")
    assert view["download"]["active"] is True and view["download"]["total"] == 2 and view["download"]["done"] == 0
    status, _ = _call(server, "POST", f"/api/books/{book}/music/download/cancel")
    assert status == 200
    gate.set()
    _settle()
    assert len(calls) == 1, "huỷ rồi mà vẫn tải bài kế"
    _status, view = _call(server, "GET", f"/api/books/{book}/music")
    assert view["download"]["active"] is False
    assert [scene["link"] for scene in view["plan"]["scenes"]] == [CALM, CALM2], "huỷ tải không phải bài hỏng: giữ rãnh nhạc"
