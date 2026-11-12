"""Kho nhạc (màn "Nhạc"): lọc / tìm theo bảng ca chung, chi tiết bài, "Vì sao bài này", lưu (ghim) + tải + bỏ lưu, "Nhạc trong sách"."""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from urllib.parse import quote

import pytest

from abook.webui import export_jobs, music_cache, music_library, music_select
from abook.webui.library import book_id
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.async_wait import wait_until
from tests.test_music_api import _with_catalog

CASES = json.loads((Path(__file__).parent / "fixtures" / "music_library" / "cases.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _no_background_warming(monkeypatch):
    from abook.webui.server import App

    monkeypatch.setattr(App, "_warm_music", lambda self, *args, **kwargs: None)


@pytest.mark.parametrize("case", CASES["cases"], ids=[case["name"] for case in CASES["cases"]])
def test_the_shared_filter_table(case) -> None:
    """Cùng bảng với MusicLibraryCasesTest (Android) và test_musiclibrary.cpp (Qt): một luật lọc / tìm / xếp cho ba nền tảng."""
    assert music_library.select(CASES["tracks"], case["filter"], CASES["playlists"], CASES["downloaded"]) == case["expect"]


def test_search_folds_vietnamese_marks_and_case() -> None:
    assert music_library.fold("  Đêm   TRĂNG  ") == "dem trang"
    assert music_library.fold("Ánh Sáng Ủa Ỡ") == "anh sang ua o"


def test_why_shows_the_three_closest_emotions_next_to_the_scene() -> None:
    scene = {"sadness": 0.8, "nostalgia": 0.6, "joy": 0.0, "tenderness": 0.3}
    track = {"sadness": 0.9, "nostalgia": 0.2, "joy": 0.9, "tenderness": 0.7}
    reason = music_library.why(scene, track, music_select.emotion_cosine)
    assert [item["id"] for item in reason["matches"]] == ["sadness", "tenderness", "nostalgia"]
    assert reason["matches"][0] == {"id": "sadness", "scene": 0.8, "track": 0.9}
    assert reason["fit"] == round(music_select.emotion_cosine(scene, track), 3)
    assert music_library.why(None, track, music_select.emotion_cosine) is None  # sách chọn theo danh sách phát: ẩn khối
    assert music_library.why({}, track, music_select.emotion_cosine) is None


def test_book_tracks_merge_repeats_and_count_scenes() -> None:
    scenes = [{"key": "1:1", "link": "https://a"}, {"key": "1:2", "link": "https://b"}, {"key": "2:1", "link": "https://a"},
              {"key": "2:2", "link": None}]
    assert music_library.book_tracks(scenes) == [{"link": "https://a", "scenes": 2, "scene": "1:1"},
                                                 {"link": "https://b", "scenes": 1, "scene": "1:2"}]


def test_the_detail_lists_all_emotions_high_to_low_and_its_playlists() -> None:
    info = {"title": "T", "creator": "C", "bpm": 100, "emotions": {"joy": 0.2, "power": 0.9, "fear": 0.5}, "license": "by"}
    out = music_library.detail("https://a", info, [{"id": "p", "name": "P", "tracks": ["https://a"]}, {"id": "q", "name": "Q", "tracks": []}])
    assert [item["id"] for item in out["emotions"]] == ["power", "fear", "joy"]
    assert out["playlists"] == [{"id": "p", "name": "P"}] and out["license"] == "by"


def _cache_file(app, link: str) -> Path:
    return app.music_dir / "files" / (hashlib.sha1(link.encode("utf-8")).hexdigest() + ".mp3")


def _fake_fetch(app, gate: threading.Event | None = None):
    def fetch(link: str, *, progress=None, cancel=None) -> Path:
        if progress is not None:
            progress(10, 100)
        if gate is not None:
            wait_until(lambda: gate.is_set() or (cancel is not None and cancel.is_set()), timeout=10.0)
            if not gate.is_set():
                raise export_jobs.Cancelled()
        target = _cache_file(app, link)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"ID3" + link.encode("utf-8"))
        return target
    return fetch


def _wait(condition, seconds: float = 5.0) -> None:
    assert wait_until(condition, timeout=seconds), "hết giờ chờ"


def test_the_library_lists_filters_and_labels_the_catalogue(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    status, listing = _call(server, "GET", "/api/music/library")
    assert status == 200 and listing["error"] == "" and listing["count"] == len(listing["tracks"]) > 0
    titles = [music_library.fold(item.get("title", "")) for item in listing["tracks"]]
    assert titles == sorted(titles)
    assert all(item["saved"] is False and item["downloaded"] is False for item in listing["tracks"])
    first = listing["tracks"][0]
    status, found = _call(server, "GET", "/api/music/library?q=" + quote("macleod"))
    assert status == 200 and [item["link"] for item in found["tracks"]] == ["https://x/battle.mp3"]
    status, found = _call(server, "GET", "/api/music/library?length=short")
    assert status == 200 and [item["link"] for item in found["tracks"]] == ["https://x/short.mp3"]
    status, meta = _call(server, "GET", "/api/music/library/meta")
    assert status == 200 and meta["error"] == ""
    status, track = _call(server, "GET", "/api/music/library/track?link=" + quote(first["link"], safe=""))
    assert status == 200 and track["link"] == first["link"] and isinstance(track["emotions"], list)
    status, _missing = _call(server, "GET", "/api/music/library/track?link=" + quote("https://khong/co.mp3", safe=""))
    assert status == 404


def test_saving_downloads_pins_and_unsaving_removes_the_copy(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    app.music_downloads = music_library.Downloads(_fake_fetch(app), export_jobs.Cancelled)
    _status, listing = _call(server, "GET", "/api/music/library")
    link = listing["tracks"][0]["link"]
    status, _state = _call(server, "POST", "/api/music/library/save", {"links": [link, "https://ngoai/danh-muc.mp3"]})
    assert status == 200
    _wait(lambda: not app.music_downloads.busy())
    assert _cache_file(app, link).is_file() and app.music_saved.links() == [link]
    # Bài đã lưu là bài ghim: bộ dọn bộ đệm quá trần không xoá.
    assert _cache_file(app, link).name in app._music_pinned_names()
    _status, saved = _call(server, "GET", "/api/music/library?downloaded=1")
    assert [item["link"] for item in saved["tracks"]] == [link] and saved["tracks"][0]["saved"] is True
    assert saved["saved"]["count"] == 1
    status, _state = _call(server, "POST", "/api/music/library/unsave", {"links": [link]})
    assert status == 200 and not _cache_file(app, link).exists() and app.music_saved.links() == []
    status, error = _call(server, "POST", "/api/music/library/save", {"links": "x"})
    assert status == 400


def test_a_saved_track_survives_a_cache_prune(tmp_path: Path) -> None:
    files = tmp_path / "files"
    files.mkdir()
    link = "https://x/kept.mp3"
    kept = files / (hashlib.sha1(link.encode("utf-8")).hexdigest() + ".mp3")
    other = files / (hashlib.sha1(b"https://x/other.mp3").hexdigest() + ".mp3")
    for path in (kept, other):
        path.write_bytes(b"x" * 1000)
    old = 1_600_000_000  # một mốc cố định xa trong quá khứ: tệp "cũ" với mọi ngưỡng tỉa
    import os

    for path in (kept, other):
        os.utime(path, (old, old))
    cache = music_cache.MusicCache(files, tmp_path / "owned.json", cap_bytes=500)
    cache.prune(lambda: {kept.name})
    assert kept.exists() and not other.exists()


@pytest.mark.parametrize("first_operation", ["add", "remove"])
def test_saved_track_mutations_share_the_read_modify_write_lock(tmp_path: Path, first_operation: str) -> None:
    from concurrent.futures import ThreadPoolExecutor

    saved = music_library.SavedTracks(tmp_path / "saved.json")
    saved.add(["https://x/old"])
    iterating, release, second_attempt = threading.Event(), threading.Event(), threading.Event()
    lock = threading.Lock()

    class ObservedLock:
        def __enter__(self):
            if threading.current_thread().name.endswith("_1"):
                second_attempt.set()
            lock.acquire()

        def __exit__(self, *_args):
            lock.release()

    saved._lock = ObservedLock()

    def first_links():
        iterating.set()
        assert release.wait(5), "test did not release the first mutation"
        yield "https://x/a" if first_operation == "add" else "https://x/old"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(getattr(saved, first_operation), first_links())
        try:
            assert iterating.wait(5)
            second = pool.submit(saved.add, ["https://x/b"])
            assert second_attempt.wait(5)
            # The first writer still owns its read/modify/write transaction.
            assert lock.locked() and not second.done()
        finally:
            release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    expected = ["https://x/old", "https://x/a", "https://x/b"] if first_operation == "add" else ["https://x/b"]
    assert saved.links() == expected
    assert music_library.SavedTracks(saved.path).links() == expected


def test_a_download_can_be_cancelled_and_failures_are_reported(tmp_path: Path) -> None:
    gate = threading.Event()

    class App:
        music_dir = tmp_path

    downloads = music_library.Downloads(_fake_fetch(App, gate), export_jobs.Cancelled)
    downloads.enqueue(["https://x/a", "https://x/b"])
    _wait(lambda: "https://x/a" in downloads.state()["active"] and downloads.state()["active"]["https://x/a"]["done"] == 10)
    assert downloads.state()["active"]["https://x/a"] == {"done": 10, "total": 100}
    downloads.cancel(["https://x/a", "https://x/b"])
    _wait(lambda: not downloads.busy())
    assert downloads.state() == {"active": {}, "failed": {}}

    def broken(link: str, **_kwargs) -> Path:
        raise OSError("mất mạng")

    failing = music_library.Downloads(broken, export_jobs.Cancelled)
    failing.enqueue(["https://x/c"])
    _wait(lambda: not failing.busy())
    assert failing.state()["failed"] == {"https://x/c": "mất mạng"}
    failing.enqueue(["https://x/c"])  # bấm lại: thử lại, lỗi cũ được xoá trước
    _wait(lambda: not failing.busy())
    assert list(failing.state()["failed"]) == ["https://x/c"]


def test_the_book_page_lists_the_music_the_book_uses(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    plan = json.loads((paths.root / "music_plan.json").read_text(encoding="utf-8"))
    links = [scene["link"] for scene in plan["scenes"] if scene.get("link")]
    status, data = _call(server, "GET", f"/api/books/{book}/music/library")
    assert status == 200
    assert [item["link"] for item in data["tracks"]] == list(dict.fromkeys(links))
    assert sum(item["scenes"] for item in data["tracks"]) == len(links)
    assert data["missingBytes"] == sum(item.get("bytes", 0) for item in data["tracks"])
    # Chi tiết mở từ "Nhạc trong sách": có "Vì sao bài này" khi đoạn có cảm xúc máy đọc được.
    first = data["tracks"][0]
    scene = next(item for item in plan["scenes"] if item.get("key") == first["scene"])
    status, track = _call(server, "GET", "/api/music/library/track?link=" + quote(first["link"], safe="")
                          + f"&book={book}&scene=" + quote(first["scene"], safe=""))
    assert status == 200
    assert ("why" in track) == (music_library.why(scene.get("emotions"), track and app.music_catalog().lookup([first["link"]])[first["link"]].get("emotions"),
                                                  music_select.emotion_cosine) is not None)
