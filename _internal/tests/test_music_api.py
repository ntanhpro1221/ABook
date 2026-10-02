"""API nhạc nền của máy chủ giao diện: xem / sửa rãnh nhạc của cuốn, mốc nhạc từng chương cho trình phát, file nhạc."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from ebook_reader.webui import music_catalog
from ebook_reader.webui.library import book_id
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_music_catalog_and_select import _catalog_dir


def _with_catalog(app, tmp_path: Path) -> None:
    app._music_catalog = music_catalog.MusicCatalog(tmp_path / "music_cache", str(_catalog_dir(tmp_path / "cloud")))


def test_the_music_track_is_built_on_first_view_and_follows_the_users_choices(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    status, view = _call(server, "GET", f"/api/books/{book}/music")
    assert status == 200 and view["error"] == "" and view["plan"]["enabled"] is True
    assert view["plan"]["scenes"] and view["overrides"]["levelDb"] == -20.0
    key = view["plan"]["scenes"][0]["key"]
    status, changed = _call(server, "PUT", f"/api/books/{book}/music",
                            {"pins": {key: "https://x/sad.mp3"}, "levelDb": -24})
    assert status == 200 and changed["plan"]["scenes"][0]["link"] == "https://x/sad.mp3"
    assert changed["plan"]["levelDb"] == -24.0


def test_the_player_gets_timed_cues_through_this_machine(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    chapter = json.loads((paths.root / "music_plan.json").read_text(encoding="utf-8"))["scenes"][0]["chapterId"]
    status, cues = _call(server, "GET", f"/api/books/{book}/music/chapters/{chapter}")
    assert status == 200 and cues["cues"]
    first = cues["cues"][0]
    assert first["src"] == "/api/music/track?link=" + quote(first["link"], safe="")
    # Ghi công (CC BY) của bài chương này dùng, khoá theo link của mốc - lấy từ plan["tracks"].
    tracks = json.loads((paths.root / "music_plan.json").read_text(encoding="utf-8")).get("tracks") or {}
    for cue in cues["cues"]:
        want = {key: tracks[cue["link"]][key] for key in ("title", "creator", "attribution", "landing")
                if tracks.get(cue["link"], {}).get(key)}
        assert cues["credits"].get(cue["link"], {}) == want


def test_only_catalog_tracks_are_fetched_and_a_cached_file_is_served(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    status, data = _call(server, "GET", "/api/music/track?link=" + quote("https://ke-la.example/x.mp3", safe=""))
    assert status == 404 and "danh mục" in data["error"]
    link = "https://x/calm.mp3"
    cached = app.music_dir / "files" / (hashlib.sha1(link.encode("utf-8")).hexdigest() + ".mp3")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(b"ID3" + b"\0" * 100)
    from tests.test_webui_listen_and_sync import _request

    status, body, _headers = _request(server.port, "GET", "/api/music/track?link=" + quote(link, safe=""),
                                      headers={"X-Ebook-Token": "t"})
    assert status == 200 and body.startswith(b"ID3")


def test_a_scene_offers_other_tracks_best_first_and_choosing_one_pins_it(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _status, view = _call(server, "GET", f"/api/books/{book}/music")
    scene = view["plan"]["scenes"][0]
    current = scene["link"]
    # Ép đoạn về không khí êm (cả hai bài "calm" cùng hợp): bài đang chọn là một trong hai, bài kia là gợi ý.
    plan = json.loads((paths.root / "music_plan.json").read_text(encoding="utf-8"))
    plan["scenes"][0].update(valence=0.25, arousal=-0.65, confidence=0.9, tension=0.0)
    (paths.root / "music_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    url = f"/api/books/{book}/music/scenes/{quote(scene['key'], safe='')}/alternatives"
    status, data = _call(server, "GET", url)
    assert status == 200 and data["key"] == scene["key"]
    items = data["alternatives"]
    assert items and len(items) <= 6
    assert [item["score"] for item in items] == sorted(item["score"] for item in items)
    links = [item["link"] for item in items]
    assert current not in links and len(set(links)) == len(links)
    assert "https://x/short.mp3" not in links  # quá ngắn để lặp - cùng bộ lọc với lúc máy chọn
    assert all(item["title"] is not None and "creator" in item and "attribution" in item for item in items)
    # Bài đã bỏ không được gợi ý nữa.
    _call(server, "PUT", f"/api/books/{book}/music", {"ban": [links[0]]})
    _status, again = _call(server, "GET", url)
    assert links[0] not in [item["link"] for item in again["alternatives"]]
    # Chọn một bài = ghim (đường PUT có sẵn): link của đoạn đổi sang bài ấy.
    _call(server, "PUT", f"/api/books/{book}/music", {"unban": [links[0]]})
    pick = links[0]
    status, changed = _call(server, "PUT", f"/api/books/{book}/music", {"pins": {scene["key"]: pick}})
    assert status == 200
    now = next(s for s in changed["plan"]["scenes"] if s["key"] == scene["key"])
    assert now["link"] == pick and now["pinned"] is True and pick != current


def test_the_alternatives_of_an_unknown_scene_or_without_a_catalog_say_so(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    status, data = _call(server, "GET", f"/api/books/{book}/music/scenes/99%3A99/alternatives")
    assert status == 404 and data["error"]
    app._music_catalog = music_catalog.MusicCatalog(tmp_path / "empty_cache", str(tmp_path / "khong_co"))
    key = json.loads((paths.root / "music_plan.json").read_text(encoding="utf-8"))["scenes"][0]["key"]
    status, data = _call(server, "GET", f"/api/books/{book}/music/scenes/{quote(key, safe='')}/alternatives")
    assert status == 503 and "mạng" in data["error"]


def test_two_requests_for_the_same_track_download_it_once_and_both_get_the_file(studio, tmp_path: Path,  # noqa: F811
                                                                              monkeypatch) -> None:
    """Luồng tải sẵn (sau khi đổi nhạc) và trình phát cùng xin một bài chưa có trong bộ đệm: trên Windows hai luồng ghi
    cùng một file tạm thì một bên hỏng (lỗi 500, đoạn ấy mất nhạc) - nay bên sau chờ bên trước và dùng chung file."""
    import io
    import threading
    import time
    import urllib.request

    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    link = "https://x/calm.mp3"
    calls = []

    def slow_open(request, timeout=0):
        calls.append(request.full_url)
        time.sleep(0.2)
        return io.BytesIO(b"ID3" + b"\0" * 100)

    monkeypatch.setattr(urllib.request, "urlopen", slow_open)
    results, errors = [], []

    def fetch() -> None:
        try:
            results.append(app.music_track_file(link))
        except Exception as exc:  # noqa: BLE001 - kiểm: không bên nào được hỏng
            errors.append(exc)

    threads = [threading.Thread(target=fetch) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors and len(results) == 3 and len(set(results)) == 1 and results[0].read_bytes().startswith(b"ID3")
    assert calls == [link]
    assert not list(results[0].parent.glob("*.part"))
