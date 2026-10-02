"""API nhạc nền của máy chủ giao diện: xem / sửa rãnh nhạc của cuốn, mốc nhạc từng chương cho trình phát, file nhạc."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import pytest

from abook.webui import music_catalog
from abook.webui.library import book_id
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_music_catalog_and_select import _catalog_dir


@pytest.fixture(autouse=True)
def _no_background_warming(monkeypatch):
    """Luồng tải sẵn chạm mạng thật và dựng lại plan giữa chừng: test gọi `_warm_run` trực tiếp khi cần."""
    from abook.webui.server import App

    monkeypatch.setattr(App, "_warm_music", lambda self, plan, value=None: None)


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


CALM, CALM2 = "https://x/calm.mp3", "https://x/calm2.mp3"


def _forced_plan(paths, link: str, count: int = 3, only_listed: bool = False) -> dict:
    """Ép plan về `count` đoạn êm cùng dùng `link` (hai bài "calm" của danh mục thử cùng hợp). `only_listed`: plan["tracks"]
    chỉ liệt kê `link` như plan thật (chỉ bài của các đoạn)."""
    plan_file = paths.root / "music_plan.json"
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    base = plan["scenes"][0]
    plan["scenes"] = [dict(base, firstSegment=100 + i, lastSegment=100 + i, start=i * 20.0, end=i * 20.0 + 20.0,
                           key=f"{base['chapterId']}:{100 + i}", link=link, pinned=False, valence=0.3, arousal=-0.6,
                           confidence=0.9, tension=0.0) for i in range(count)]
    if only_listed:
        plan["tracks"] = {link: plan["tracks"].get(link) or {"title": "Calm", "creator": "A"}}
    plan_file.write_bytes(json.dumps(plan).encode("utf-8"))
    return plan


def _cache(app, link: str) -> Path:
    cached = app.music_dir / "files" / (hashlib.sha1(link.encode("utf-8")).hexdigest() + ".mp3")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(b"ID3" + b"\0" * 100)
    return cached


def test_a_network_failure_puts_the_machine_offline_but_an_http_error_marks_the_track(studio, tmp_path: Path,  # noqa: F811
                                                                                   monkeypatch) -> None:
    import io
    import socket
    import urllib.error
    import urllib.request

    from abook.webui.server import ApiError, App

    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    clock = {"now": 1_000_000.0}
    app._music_clock = lambda: clock["now"]
    registry = app.music_dir / "unavailable.json"

    def no_network(request, timeout=0):
        raise urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed"))

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    with pytest.raises(ApiError):
        app.music_track_file(CALM)
    assert not registry.exists(), "mất mạng không phải lỗi của bài"
    assert app.music_track_available(CALM) is False and app.music_track_available(CALM2) is False
    clock["now"] += 301
    assert app.music_track_available(CALM) is True, "hết 5 phút thì thử lại"

    def gone(request, timeout=0):
        raise urllib.error.HTTPError(request.full_url, 404, "gone", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", gone)
    with pytest.raises(ApiError):
        app.music_track_file(CALM)
    assert json.loads(registry.read_text(encoding="utf-8")) == {CALM: clock["now"]}
    assert app.music_track_available(CALM) is False and app.music_track_available(CALM2) is True
    assert app._music_offline_until < clock["now"], "lỗi HTTP không làm cả máy offline"
    marked_at = clock["now"]
    clock["now"] += 24 * 3600 - 1
    assert app.music_track_available(CALM) is False
    clock["now"] += 2
    assert app.music_track_available(CALM) is True, "dấu hỏng hết hạn sau 24 giờ"
    assert App._read_unavailable(app) == {CALM: marked_at}, "sổ nằm trong file: mở lại app vẫn còn"

    # Tải thành công thì xoá dấu.
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout=0: io.BytesIO(b"ID3" + b"\0" * 100))
    app.music_track_file(CALM)
    assert json.loads(registry.read_text(encoding="utf-8")) == {}


def test_a_mirror_that_differs_from_the_original_is_not_a_network_failure(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    import io
    import socket
    import urllib.error
    import urllib.request

    from abook.webui.server import ApiError

    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    info = {"mirrors": ["https://archive.org/download/abook-music-x/a.mp3"], "sha1": hashlib.sha1(b"ID3good").hexdigest()}
    monkeypatch.setattr(app.music_catalog(), "lookup", lambda links: {link: info for link in links})

    def open_(request, timeout=0):
        if request.full_url.startswith("https://x/"):
            raise urllib.error.URLError(socket.timeout("timed out"))
        return io.BytesIO(b"ID3bad")

    monkeypatch.setattr(urllib.request, "urlopen", open_)
    with pytest.raises(ApiError):
        app.music_track_file(CALM)
    assert CALM in json.loads((app.music_dir / "unavailable.json").read_text(encoding="utf-8"))
    assert app._music_offline_until == 0.0


def test_a_cached_track_is_available_even_when_the_machine_is_offline(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    app._music_offline_until = app._music_clock() + 300
    app._music_mark(CALM, True)
    assert app.music_track_available(CALM) is False and app.music_track_available(CALM2) is False
    _cache(app, CALM)
    assert app.music_track_available(CALM) is True, "đã có trong bộ đệm thì không phụ thuộc mạng"


def test_the_player_gets_the_next_best_track_when_the_chosen_one_is_unavailable_and_silence_only_without_one(  # noqa: F811
        studio, tmp_path: Path) -> None:
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    plan = _forced_plan(paths, CALM)
    url = f"/api/books/{book}/music/chapters/{plan['scenes'][0]['chapterId']}"
    _status, cues = _call(server, "GET", url)
    assert [cue["link"] for cue in cues["cues"]] == [CALM]
    app._music_mark(CALM, True)
    status, cues = _call(server, "GET", url)
    assert status == 200 and [cue["link"] for cue in cues["cues"]] == [CALM2]
    assert cues["cues"][0]["src"] == "/api/music/track?link=" + quote(CALM2, safe="") and "gainDb" in cues["cues"][0]
    assert json.loads((paths.root / "music_plan.json").read_text(encoding="utf-8"))["scenes"][0]["link"] == CALM
    app._music_mark(CALM2, True)
    _status, cues = _call(server, "GET", url)
    assert cues["cues"] == []


def test_offline_the_player_only_gets_tracks_already_in_the_cache(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    plan = _forced_plan(paths, CALM)
    app._music_offline_until = app._music_clock() + 300
    url = f"/api/books/{book}/music/chapters/{plan['scenes'][0]['chapterId']}"
    assert _call(server, "GET", url)[1]["cues"] == []
    _cache(app, CALM2)
    assert [cue["link"] for cue in _call(server, "GET", url)[1]["cues"]] == [CALM2]


def test_warming_rebuilds_the_plan_around_a_track_that_cannot_be_fetched(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    import io
    import urllib.error
    import urllib.request

    from abook.webui import music_plan

    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    _forced_plan(paths, CALM, count=3)
    calls = []

    def open_(request, timeout=0):
        calls.append(request.full_url)
        if request.full_url == CALM:
            raise urllib.error.HTTPError(request.full_url, 404, "gone", {}, None)
        return io.BytesIO(b"ID3" + b"\0" * 100)

    monkeypatch.setattr(urllib.request, "urlopen", open_)
    app._warm_run(music_plan.read_plan(paths.root), book)
    rebuilt = music_plan.read_plan(paths.root)
    assert [scene["link"] for scene in rebuilt["scenes"]] == [CALM2] * 3 and list(rebuilt["tracks"]) == [CALM2]
    assert calls == [CALM, CALM2] and app.music_track_cached(CALM2) is not None


def test_warming_offline_keeps_only_cached_tracks_and_stops(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    import socket
    import urllib.error
    import urllib.request

    from abook.webui import music_plan

    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    _forced_plan(paths, CALM, count=2)
    calls = []

    def no_network(request, timeout=0):
        calls.append(request.full_url)
        raise urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed"))

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    app._warm_run(music_plan.read_plan(paths.root), book)
    assert [scene["link"] for scene in music_plan.read_plan(paths.root)["scenes"]] == [None, None]
    assert calls == [CALM], "hỏng vì mạng một lần là đủ biết offline, không chờ từng bài"
    assert not (app.music_dir / "unavailable.json").exists()
    # Một bài đã có trong bộ đệm thì dùng được: lần dựng sau (vẫn offline) chọn nó thay vì im lặng.
    _cache(app, CALM2)
    _forced_plan(paths, CALM, count=2)
    app._warm_run(music_plan.read_plan(paths.root), book)
    assert [scene["link"] for scene in music_plan.read_plan(paths.root)["scenes"]] == [CALM2, CALM2]


def _phone_side(app, paths, tmp_path: Path):
    """Điện thoại nghe cuốn của máy này: (gói nhạc trong manifest, SyncApp phục vụ file) - cùng nguồn `music_sync_source`."""
    from abook.webui.library import Library, Preferences
    from abook.webui.listening import Listening
    from abook.webui.sync import Devices, SyncApp

    from abook.webui import music_plan

    source = app.music_sync_source()
    packed = music_plan.package(paths.root, [1], source)
    sync = SyncApp(Library(Preferences(tmp_path / "prefs2.json")), Listening(tmp_path / "listening2.json"),
                   Devices(tmp_path / "devices2.json"), "may", music_track=source)
    return (packed[0] if packed else None), sync


def test_the_phone_gets_the_substitute_track_and_the_file_of_it_when_the_chosen_one_is_unavailable(  # noqa: F811
        studio, tmp_path: Path, monkeypatch) -> None:
    from abook.webui import music_plan
    from tests.test_music_catalog_and_select import TRACKS

    for key, value in (("title", "Calm Two"), ("creator", "B"), ("attribution", "Calm Two by B"), ("lufs", -20.0)):
        monkeypatch.setitem(TRACKS[CALM2], key, value)  # ghi công + độ to của bài thay thế đi theo gói
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    plan = _forced_plan(paths, CALM, only_listed=True)
    chapter = plan["scenes"][0]["chapterId"]
    # Chưa hỏng: gói giữ bài đã chọn, bài kia (dù có trong bộ đệm) không được phục vụ.
    _cache(app, CALM), _cache(app, CALM2)
    music, sync = _phone_side(app, paths, tmp_path)
    assert [t["link"] for t in music["tracks"].values()] == [CALM] and list(music["chapters"]) == [str(chapter)]
    assert isinstance(sync.resolve_file(paths.root, music_plan.track_name(CALM)), Path)
    assert sync.resolve_file(paths.root, music_plan.track_name(CALM2)) is None
    # Bài đã chọn hỏng (và hết trong bộ đệm): gói mang bài thay thế kèm thông tin, file của nó được phục vụ.
    _cache(app, CALM).unlink()
    app._music_mark(CALM, True)
    music, sync = _phone_side(app, paths, tmp_path)
    name = music_plan.track_name(CALM2)
    assert list(music["tracks"]) == [name] and music["tracks"][name]["link"] == CALM2
    assert music["tracks"][name]["title"] == "Calm Two" and music["tracks"][name]["attribution"] == "Calm Two by B"
    assert music["tracks"][name]["lufs"] == -20.0
    assert [cue["track"] for cue in music["chapters"][str(chapter)]] == [name]
    found = sync.resolve_file(paths.root, name)
    assert isinstance(found, Path) and found.read_bytes().startswith(b"ID3")
    assert sync.resolve_file(paths.root, music_plan.track_name(CALM)) is None
    # Link tuỳ ý (kể cả bài có trong danh mục và đã đệm nhưng không được thay cho đoạn nào của cuốn) vẫn không được phục vụ.
    other = "https://x/short.mp3"
    _cache(app, other)
    assert sync.resolve_file(paths.root, music_plan.track_name(other)) is None
    assert sync.resolve_file(paths.root, music_plan.track_name("https://ke-la.example/x.mp3")) is None


def test_the_phone_package_has_no_music_when_the_chosen_track_is_unavailable_and_nothing_replaces_it(  # noqa: F811
        studio, tmp_path: Path) -> None:
    from abook.webui import music_plan

    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    _call(server, "GET", f"/api/books/{book_id(paths.root)}/music")
    _forced_plan(paths, CALM, only_listed=True)
    app._music_mark(CALM, True)
    app._music_mark(CALM2, True)
    music, sync = _phone_side(app, paths, tmp_path)
    assert music is None, "không bài nào dùng được: mốc bỏ đi, im lặng"
    assert sync.resolve_file(paths.root, music_plan.track_name(CALM2)) is None
    # Bài mới chọn mà chưa tải xong (chưa hỏng): chờ đợt tải sẵn, không thay vội bằng bài khác.
    app._music_mark(CALM, False)
    _cache(app, CALM2)
    app._music_mark(CALM2, False)
    music, sync = _phone_side(app, paths, tmp_path)
    assert music is None and sync.resolve_file(paths.root, music_plan.track_name(CALM2)) is None


def test_change_track_does_not_offer_tracks_this_machine_cannot_get(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    book = book_id(paths.root)
    _call(server, "GET", f"/api/books/{book}/music")
    plan = _forced_plan(paths, CALM)
    url = f"/api/books/{book}/music/scenes/{quote(plan['scenes'][0]['key'], safe='')}/alternatives"
    _status, data = _call(server, "GET", url)
    assert CALM2 in [item["link"] for item in data["alternatives"]]
    app._music_mark(CALM2, True)
    status, data = _call(server, "GET", url)
    assert status == 200 and CALM2 not in [item["link"] for item in data["alternatives"]]
    _cache(app, CALM2)  # đã có trong bộ đệm thì dùng được dù có dấu hỏng
    _status, data = _call(server, "GET", url)
    assert CALM2 in [item["link"] for item in data["alternatives"]]
