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
