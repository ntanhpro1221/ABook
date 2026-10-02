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
    # gainDb tính ở máy chủ: danh mục thử chưa có lufs -> trung vị -16,6; levelDb mặc định -20 -> -23,4 dB.
    assert all(cue["gainDb"] == -20.39 for cue in cues["cues"]) and cues["levelDb"] == -20.0
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


def test_editing_one_scene_keeps_the_scenes_of_the_plan_and_only_rechoosing_resplits(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _status, view = _call(server, "GET", f"/api/books/{book}/music")
    first = view["plan"]["scenes"][0]
    # Plan dựng bởi bộ chia đoạn cũ: các đoạn khác những gì `book_scenes` cho ra bây giờ.
    plan_file = paths.root / "music_plan.json"
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    plan["scenes"][0]["end"] = first["end"] + 1.25
    plan["scenes"][0]["legacy"] = "old-splitter"
    plan_file.write_bytes(json.dumps(plan).encode("utf-8"))
    status, changed = _call(server, "PUT", f"/api/books/{book}/music", {"pins": {first["key"]: "https://x/sad.mp3"}})
    assert status == 200
    kept = changed["plan"]["scenes"][0]
    assert kept["end"] == first["end"] + 1.25 and kept["legacy"] == "old-splitter" and kept["key"] == first["key"]
    assert kept["link"] == "https://x/sad.mp3" and kept["pinned"] is True
    assert len(changed["plan"]["scenes"]) == len(plan["scenes"])
    # "Chọn lại nhạc" mới chia lại đoạn.
    status, rebuilt = _call(server, "POST", f"/api/books/{book}/music/rebuild", {})
    assert status == 200 and rebuilt["plan"]["scenes"][0]["end"] == first["end"]
    assert "legacy" not in rebuilt["plan"]["scenes"][0]


def _calm_plan(paths, view: dict, count: int = 8) -> None:
    """Ép plan về `count` đoạn cùng không khí êm (hai bài "calm" cùng hợp): phạt "vừa dùng" lan dọc cuốn."""
    plan_file = paths.root / "music_plan.json"
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    base = plan["scenes"][0]
    plan["scenes"] = [dict(base, firstSegment=100 + i, lastSegment=100 + i, start=i * 20.0, end=i * 20.0 + 20.0,
                           valence=0.3, arousal=-0.6, confidence=0.9, tension=0.0) for i in range(count)]
    plan_file.write_bytes(json.dumps(plan).encode("utf-8"))


def _links(view: dict) -> list:
    return [scene["link"] for scene in view["plan"]["scenes"]]


def test_pinning_one_scene_keeps_the_track_of_every_other_scene(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    _view = json.loads((paths.root / "music_plan.json").read_text(encoding="utf-8"))
    _calm_plan(paths, _view)
    # Đổi phong cách là chọn lại tất cả: dựng nền để so.
    _status, base = _call(server, "PUT", f"/api/books/{book}/music", {"family": "piano"})
    _status, base = _call(server, "PUT", f"/api/books/{book}/music", {"family": ""})
    before = _links(base)
    assert len(before) == 8 and len(set(before)) > 1
    first = base["plan"]["scenes"][0]["key"]
    status, pinned = _call(server, "PUT", f"/api/books/{book}/music", {"pins": {first: "https://x/sad.mp3"}})
    assert status == 200
    after = _links(pinned)
    assert after[0] == "https://x/sad.mp3" and after[1:] == before[1:]
    assert [s["pinned"] for s in pinned["plan"]["scenes"]] == [True] + [False] * 7
    # Không giữ bài thì cùng thao tác này làm các đoạn sau đổi theo (đây là cái đã sửa): chọn lại tất cả với cùng ghim.
    _status, base = _call(server, "PUT", f"/api/books/{book}/music", {"pins": {first: None}})
    assert _links(base)[1:] == before[1:]
    status, cascaded = _call(server, "PUT", f"/api/books/{book}/music", {"genre": "", "pins": {first: "https://x/sad.mp3"}})
    assert status == 200 and _links(cascaded)[1:] != before[1:]
    # Bỏ ghim, im lặng / có nhạc lại, mức nhạc, bật/tắt: cũng không đổi bài của đoạn khác.
    _status, base = _call(server, "PUT", f"/api/books/{book}/music", {"genre": "", "pins": {first: None}})
    before = _links(base)
    for body in ({"silence": {first: True}}, {"levelDb": -24}, {"enabled": False}, {"enabled": True}):
        _status, now = _call(server, "PUT", f"/api/books/{book}/music", body)
        assert _links(now)[1:] == before[1:], body
    _status, now = _call(server, "PUT", f"/api/books/{book}/music", {"silence": {first: False}})
    assert _links(now)[1:] == before[1:] and now["plan"]["scenes"][0]["link"]


def test_banning_a_track_rechooses_only_the_scenes_that_used_it_and_drops_pins_to_it(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    _calm_plan(paths, {})
    _status, base = _call(server, "PUT", f"/api/books/{book}/music", {"family": ""})
    before = _links(base)
    victim = before[0]
    # Ghim bài này vào đoạn cuối nữa: bỏ bài thì ghim ấy cũng phải gỡ.
    last = base["plan"]["scenes"][-1]["key"]
    _status, base = _call(server, "PUT", f"/api/books/{book}/music", {"pins": {last: victim}})
    before = _links(base)
    status, banned = _call(server, "PUT", f"/api/books/{book}/music", {"ban": [victim]})
    assert status == 200
    after = _links(banned)
    for was, now in zip(before, after):
        assert now != victim and now is not None
        if was != victim:
            assert now == was
    assert banned["overrides"]["pins"] == {} and banned["plan"]["scenes"][-1]["pinned"] is False
    assert victim in banned["overrides"]["banned"]
    # Dùng lại bài: không đoạn nào đổi (chỉ các lần "Chọn lại nhạc" mới đưa nó về).
    _status, back = _call(server, "PUT", f"/api/books/{book}/music", {"unban": [victim]})
    assert _links(back) == after


def test_the_view_names_the_banned_tracks_and_survives_a_missing_catalog(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    link = "https://x/battle.mp3"
    status, view = _call(server, "PUT", f"/api/books/{book}/music", {"ban": [link]})
    assert status == 200 and link in view["overrides"]["banned"]
    assert view["bannedTracks"] == {link: {"title": "Battle", "creator": "Kevin MacLeod"}}
    # Mất danh mục (mất mạng, chưa có bản đệm): vẫn xem được, chỉ không có tên - giao diện lùi về tên file.
    app._music_catalog = music_catalog.MusicCatalog(tmp_path / "empty_cache", str(tmp_path / "khong_co"))
    status, offline = _call(server, "GET", f"/api/books/{book}/music")
    assert status == 200 and offline["bannedTracks"] == {}


def test_the_cue_gain_follows_the_users_level_and_the_track_loudness(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    _call(server, "PUT", f"/api/books/{book}/music", {"levelDb": -14})
    plan = json.loads((paths.root / "music_plan.json").read_text(encoding="utf-8"))
    chapter = plan["scenes"][0]["chapterId"]
    link = next(scene["link"] for scene in plan["scenes"] if scene["chapterId"] == chapter and scene["link"])
    plan["tracks"][link].update(lufs=-30.0, speechBand=0.7)  # như danh mục mới: -20 - 14 + 30 - 3,2
    (paths.root / "music_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    status, cues = _call(server, "GET", f"/api/books/{book}/music/chapters/{chapter}")
    assert status == 200 and cues["levelDb"] == -14.0
    assert next(cue for cue in cues["cues"] if cue["link"] == link)["gainDb"] == -4.19


def test_a_track_whose_source_fails_comes_from_its_archive_mirror_only_if_it_matches(studio, tmp_path: Path,  # noqa: F811
                                                                                 monkeypatch) -> None:
    """Nguồn gốc trước; hỏng thì bản sao archive.org trong `mirrors` của danh mục - bản sao sai `sha1` thì bỏ."""
    import hashlib
    import io
    import urllib.error
    import urllib.request

    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    good, bad = b"ID3" + b"\1" * 100, b"ID3" + b"\2" * 100
    mirrors = ["https://archive.org/download/abook-music-x/wrong.mp3", "https://archive.org/download/abook-music-x/a.mp3"]
    info = {"mirrors": mirrors, "sha1": hashlib.sha1(good).hexdigest()}
    monkeypatch.setattr(app.music_catalog(), "lookup", lambda links: {link: info for link in links})
    calls = []

    def open_(request, timeout=0):
        calls.append(request.full_url)
        if request.full_url.startswith("https://x/"):
            raise urllib.error.HTTPError(request.full_url, 404, "gone", {}, None)
        return io.BytesIO(bad if request.full_url.endswith("wrong.mp3") else good)

    monkeypatch.setattr(urllib.request, "urlopen", open_)
    path = app.music_track_file("https://x/gone.mp3")
    assert path.read_bytes() == good and calls == ["https://x/gone.mp3", *mirrors]
    assert not list(path.parent.glob("*.part")), "không để lại file tạm"
    calls.clear()
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout=0: calls.append(request.full_url) or
                        io.BytesIO(good))
    app.music_track_file("https://x/live.mp3")
    assert calls == ["https://x/live.mp3"], "nguồn gốc còn sống thì không đụng bản sao"


def test_a_mirror_without_the_originals_sha1_is_never_used(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    """Danh mục chưa có `sha1` của bài (chưa kiểm bản sao) thì nguồn gốc hỏng là hỏng - không tải bản không kiểm được."""
    import pytest
    import urllib.error
    import urllib.request

    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    info = {"mirrors": ["https://archive.org/download/abook-music-x/a.mp3"]}
    monkeypatch.setattr(app.music_catalog(), "lookup", lambda links: {link: info for link in links})
    calls = []

    def open_(request, timeout=0):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 404, "gone", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", open_)
    with pytest.raises(Exception):
        app.music_track_file("https://x/gone.mp3")
    assert calls == ["https://x/gone.mp3"]
