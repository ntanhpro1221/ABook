"""Danh mục nhạc nền trên mây (webui/music_catalog.py) và chọn nhạc cho từng đoạn (webui/music_select.py)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from abook.webui.music_catalog import CatalogError, MusicCatalog, cell_of, shard_of
from abook.webui.music_select import choose, scene_key

TRACKS = {
    "https://x/calm.mp3": {"valence": 0.3, "arousal": -0.7, "family": "piano", "duration": 180, "source": "incompetech"},
    "https://x/calm2.mp3": {"valence": 0.2, "arousal": -0.6, "family": "eastern", "duration": 200,
                            "source": "incompetech"},
    "https://x/battle.mp3": {"valence": -0.4, "arousal": 0.85, "family": "orchestral", "duration": 150,
                             "source": "incompetech", "title": "Battle", "creator": "Kevin MacLeod"},
    "https://x/sad.mp3": {"valence": -0.7, "arousal": -0.4, "family": "piano", "duration": 240, "source": "incompetech"},
    "https://x/short.mp3": {"valence": 0.3, "arousal": -0.7, "family": "piano", "duration": 20, "source": "incompetech"},
}


def _catalog_dir(root: Path, revision: str = "r1") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "tracks").mkdir(exist_ok=True)
    (root / "cells").mkdir(exist_ok=True)
    shards: dict[str, dict] = {}
    cells: dict[str, list] = {}
    for link, track in TRACKS.items():
        shards.setdefault(shard_of(link), {})[link] = track
        v, a = cell_of(track["valence"], track["arousal"])
        cells.setdefault(f"{v}_{a}", []).append({"link": link, **track})
    for shard, data in shards.items():
        (root / "tracks" / f"{shard}.json").write_text(json.dumps(data), encoding="utf-8")
    for cell, items in cells.items():
        (root / "cells" / f"{cell}.json").write_text(json.dumps(items), encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({
        "format": "abook-music-catalog", "version": 1, "revision": revision, "grid": 5, "shards": sorted(shards),
        "cells": {cell: len(items) for cell, items in cells.items()}}), encoding="utf-8")
    return root


def test_a_list_of_links_brings_back_exactly_their_data(tmp_path: Path) -> None:
    catalog = MusicCatalog(tmp_path / "cache", str(_catalog_dir(tmp_path / "cloud")))
    found = catalog.lookup(["https://x/battle.mp3", "https://x/sad.mp3", "https://khong/co.mp3"])
    assert set(found) == {"https://x/battle.mp3", "https://x/sad.mp3"}
    assert found["https://x/sad.mp3"]["valence"] == -0.7


def test_the_catalog_keeps_working_offline_from_its_cache(tmp_path: Path) -> None:
    cloud = _catalog_dir(tmp_path / "cloud")
    MusicCatalog(tmp_path / "cache", str(cloud)).lookup(["https://x/calm.mp3"])
    shutil.rmtree(cloud)  # mất mạng / nguồn biến mất
    offline = MusicCatalog(tmp_path / "cache", str(cloud))
    assert "https://x/calm.mp3" in offline.lookup(["https://x/calm.mp3"])


def test_a_first_start_without_network_says_so(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="mạng"):
        MusicCatalog(tmp_path / "cache", str(tmp_path / "khong_co")).manifest()


def test_a_new_catalog_revision_replaces_the_cached_data(tmp_path: Path) -> None:
    cloud = _catalog_dir(tmp_path / "cloud", "r1")
    catalog = MusicCatalog(tmp_path / "cache", str(cloud))
    catalog.lookup(["https://x/calm.mp3"])
    data = json.loads((cloud / "tracks" / f"{shard_of('https://x/calm.mp3')}.json").read_text(encoding="utf-8"))
    data["https://x/calm.mp3"]["valence"] = 0.9
    (cloud / "tracks" / f"{shard_of('https://x/calm.mp3')}.json").write_text(json.dumps(data), encoding="utf-8")
    manifest = json.loads((cloud / "manifest.json").read_text(encoding="utf-8"))
    (cloud / "manifest.json").write_text(json.dumps({**manifest, "revision": "r2"}), encoding="utf-8")
    catalog.manifest(refresh=True)
    assert catalog.lookup(["https://x/calm.mp3"])["https://x/calm.mp3"]["valence"] == 0.9


def _scene(first: int, valence: float, arousal: float, confidence: float = 0.8) -> dict:
    return {"chapterId": 1, "firstSegment": first, "valence": valence, "arousal": arousal, "confidence": confidence}


@pytest.fixture
def near(tmp_path: Path):
    catalog = MusicCatalog(tmp_path / "cache", str(_catalog_dir(tmp_path / "cloud")))
    return lambda v, a: catalog.near(v, a, radius=1)


def test_each_scene_gets_music_of_its_mood(near) -> None:
    plan = choose([_scene(1, 0.3, -0.6), _scene(40, -0.5, 0.8), _scene(80, -0.7, -0.4)], near, book_key="b")
    assert [entry["link"] for entry in plan] == ["https://x/calm.mp3", "https://x/battle.mp3", "https://x/sad.mp3"]


def test_a_scene_with_no_clear_mood_gets_a_quiet_bed(near) -> None:
    [entry] = choose([_scene(1, 0.0, 0.1, confidence=0.05)], near, book_key="b")
    assert entry["link"] in ("https://x/calm.mp3", "https://x/calm2.mp3")


def test_nothing_close_enough_means_silence(near) -> None:
    [entry] = choose([_scene(1, 0.95, 0.95)], near, book_key="b")
    assert entry["link"] is None


def test_the_book_style_and_the_users_choices_are_respected(near) -> None:
    [eastern] = choose([_scene(1, 0.3, -0.6)], near, book_key="b", family="eastern")
    assert eastern["link"] == "https://x/calm2.mp3"
    [pinned] = choose([_scene(1, 0.3, -0.6)], near, book_key="b", pins={scene_key(_scene(1, 0, 0)): "https://x/sad.mp3"})
    assert pinned["link"] == "https://x/sad.mp3" and pinned["pinned"] is True
    [other] = choose([_scene(1, 0.3, -0.6)], near, book_key="b", banned={"https://x/calm.mp3"})
    assert other["link"] == "https://x/calm2.mp3"


def test_short_tracks_are_not_used_and_choices_repeat_exactly(near) -> None:
    scenes = [_scene(i * 40, 0.3, -0.6) for i in range(5)]
    first = choose(scenes, near, book_key="b")
    assert "https://x/short.mp3" not in [entry["link"] for entry in first]
    assert first == choose(scenes, near, book_key="b"), "làm lại ra đúng bài cũ"


def test_a_style_that_does_not_fit_the_books_world_is_never_chosen(near) -> None:
    from abook.webui.music_select import choose as pick

    tracks = [{"link": "https://x/rock.mp3", "valence": 0.3, "arousal": -0.6, "tension": 0.0, "style": "rock",
               "duration": 200, "source": "incompetech"},
              {"link": "https://x/guzheng.mp3", "valence": 0.0, "arousal": -0.2, "tension": 0.0, "style": "eastern_ancient",
               "duration": 200, "source": "incompetech"}]
    xianxia = {"eastern_ancient": 1, "orchestral_epic": 1}
    [entry] = pick([_scene(1, 0.3, -0.6)], lambda v, a: tracks, book_key="b", genre_styles=xianxia)
    assert entry["link"] == "https://x/guzheng.mp3", "rock gần hơn nhưng không hợp truyện tiên hiệp"
    [free] = pick([_scene(1, 0.3, -0.6)], lambda v, a: tracks, book_key="b")
    assert free["link"] == "https://x/rock.mp3", "chưa chọn thể loại thì không lọc"


def test_tension_tells_fear_from_excitement(near) -> None:
    from abook.webui.music_select import choose as pick

    tracks = [{"link": "https://x/thrill.mp3", "valence": -0.3, "arousal": 0.7, "tension": 0.9, "duration": 200,
               "source": "incompetech"},
              {"link": "https://x/party.mp3", "valence": -0.2, "arousal": 0.7, "tension": -0.6, "duration": 200,
               "source": "incompetech"}]
    scene = {**_scene(1, -0.25, 0.7), "tension": 0.8}
    [entry] = pick([scene], lambda v, a: tracks, book_key="b")
    assert entry["link"] == "https://x/thrill.mp3"


def _eight_calm_scenes() -> list[dict]:
    return [_scene(i * 40, 0.3, -0.6) for i in range(8)]


def test_pinning_one_scene_cascades_through_the_recent_penalty_unless_the_others_are_kept(near) -> None:
    scenes = _eight_calm_scenes()
    first = choose(scenes, near, book_key="b")
    pin = {scene_key(scenes[0]): "https://x/sad.mp3"}
    cascaded = choose(scenes, near, book_key="b", pins=pin)
    # Cái cũ: ghim đoạn 0 làm các đoạn sau đổi bài theo (bài ghim chiếm chỗ trong "vừa dùng", bài khác hết bị phạt).
    assert [e["link"] for e in cascaded[1:]] != [e["link"] for e in first[1:]]
    keep = {entry["key"]: entry["link"] for entry in first}
    sticky = choose(scenes, near, book_key="b", pins=pin, keep={k: v for k, v in keep.items() if k not in pin})
    assert sticky[0]["link"] == "https://x/sad.mp3" and sticky[0]["pinned"] is True
    assert [e["link"] for e in sticky[1:]] == [e["link"] for e in first[1:]]
    assert not any(e["pinned"] for e in sticky[1:])


def test_a_kept_track_that_is_now_banned_is_chosen_again_and_the_rest_stay(near) -> None:
    scenes = _eight_calm_scenes()
    first = choose(scenes, near, book_key="b")
    used = {entry["link"] for entry in first}
    victim = first[0]["link"]
    keep = {entry["key"]: entry["link"] for entry in first}
    after = choose(scenes, near, book_key="b", banned={victim}, keep=keep)
    for before, now in zip(first, after):
        if before["link"] == victim:
            assert now["link"] != victim and now["link"] is not None
        else:
            assert now["link"] == before["link"]
    assert victim in used and victim not in {entry["link"] for entry in after}


def test_a_scene_that_was_silent_for_lack_of_a_match_stays_silent_when_kept(near) -> None:
    scene = _scene(1, 0.3, -0.6)
    assert choose([scene], near, book_key="b")[0]["link"] is not None  # không giữ thì đoạn này có nhạc
    [entry] = choose([scene], near, book_key="b", keep={scene_key(scene): None})
    assert entry["link"] is None and entry["pinned"] is False


def test_js_divergence_is_zero_for_equal_symmetric_and_none_without_data() -> None:
    from abook.webui.music_scenes import gems_from_point
    from abook.webui.music_select import js_divergence

    calm, fight = gems_from_point(0.5, -0.8, -0.7), gems_from_point(-0.5, 0.6, 0.9)
    assert js_divergence(calm, calm) == pytest.approx(0.0, abs=1e-9)
    assert js_divergence(calm, fight) == pytest.approx(js_divergence(fight, calm))
    assert js_divergence(calm, fight) > 0.3
    assert js_divergence(calm, None) is None and js_divergence(None, calm) is None
    assert js_divergence(calm, {}) is None and js_divergence(calm, ["wonder"]) is None


def _gems_tracks(gems_a, gems_b) -> list[dict]:
    base = {"valence": -0.5, "arousal": 0.6, "tension": 0.9, "duration": 200, "source": "incompetech"}
    return [{"link": "https://x/a.mp3", **base, "gems": gems_a}, {"link": "https://x/b.mp3", **base, "gems": gems_b}]


def test_rank_prefers_the_track_whose_gems_match_the_scene() -> None:
    from abook.webui.music_scenes import gems_from_point
    from abook.webui.music_select import rank

    scene = {**_scene(1, -0.5, 0.6), "tension": 0.9, "gems": gems_from_point(-0.5, 0.6, 0.9)}
    tracks = _gems_tracks({"peacefulness": 1.0}, gems_from_point(-0.5, 0.6, 0.9))  # b hợp, a lệch hẳn
    ranked = rank(scene, lambda v, a: tracks, book_key="b")
    assert [t["link"] for t in ranked] == ["https://x/b.mp3", "https://x/a.mp3"]
    assert ranked[1]["score"] - ranked[0]["score"] > 1.0
    swapped = rank(scene, lambda v, a: list(reversed(tracks)), book_key="b")
    assert swapped[0]["link"] == "https://x/b.mp3"


def test_gems_never_rescue_a_track_beyond_the_silence_ceiling() -> None:
    from abook.webui.music_scenes import gems_from_point
    from abook.webui.music_select import rank

    scene = {**_scene(1, -0.5, 0.6), "tension": 0.9, "gems": gems_from_point(-0.5, 0.6, 0.9)}
    far = {"link": "https://x/far.mp3", "valence": 0.9, "arousal": -0.9, "tension": -0.7, "duration": 200,
           "source": "incompetech", "gems": gems_from_point(-0.5, 0.6, 0.9)}
    assert rank(scene, lambda v, a: [far], book_key="b") == []


def test_a_track_with_old_shape_gems_still_ranks_without_a_gems_term() -> None:
    from abook.webui.music_scenes import gems_from_point
    from abook.webui.music_select import rank

    scene = {**_scene(1, -0.5, 0.6), "tension": 0.9, "gems": gems_from_point(-0.5, 0.6, 0.9)}
    tracks = _gems_tracks(["wonder", "power"], None)
    ranked = rank(scene, lambda v, a: tracks, book_key="b")
    assert {t["link"] for t in ranked} == {"https://x/a.mp3", "https://x/b.mp3"}
    assert abs(ranked[0]["score"] - ranked[1]["score"]) < 0.01, "cả hai đều không có số hạng GEMS"


def test_a_track_this_machine_cannot_get_is_skipped_and_the_next_best_is_used(near) -> None:
    from abook.webui.music_select import rank

    scene = _scene(1, 0.3, -0.6)
    down = lambda link: link != "https://x/calm.mp3"  # noqa: E731
    assert rank(scene, near, book_key="b")[0]["link"] == "https://x/calm.mp3"
    ranked = rank(scene, near, book_key="b", available=down)
    assert ranked and "https://x/calm.mp3" not in [t["link"] for t in ranked]
    [entry] = choose([scene], near, book_key="b", available=down)
    assert entry["link"] == ranked[0]["link"] == "https://x/calm2.mp3"
    [nothing] = choose([scene], near, book_key="b", available=lambda link: False)
    assert nothing["link"] is None, "không bài nào lấy được thì mới im lặng"


def test_a_pinned_track_that_is_unavailable_falls_back_to_ranking_but_the_pin_stays_the_users(near) -> None:
    scene = _scene(1, 0.3, -0.6)
    pins = {scene_key(scene): "https://x/sad.mp3"}
    [entry] = choose([scene], near, book_key="b", pins=pins, available=lambda link: link != "https://x/sad.mp3")
    assert entry["link"] in ("https://x/calm.mp3", "https://x/calm2.mp3")
    assert entry["pinUnavailable"] is True and entry["pinned"] is False and pins == {scene_key(scene): "https://x/sad.mp3"}
    [back] = choose([scene], near, book_key="b", pins=pins, available=lambda link: True)
    assert back["link"] == "https://x/sad.mp3" and back["pinned"] is True and "pinUnavailable" not in back


def test_a_kept_track_that_is_unavailable_is_chosen_again_and_an_available_one_stays(near) -> None:
    scene = _scene(1, 0.3, -0.6)
    keep = {scene_key(scene): "https://x/calm.mp3"}
    [stays] = choose([scene], near, book_key="b", keep=keep, available=lambda link: True)
    assert stays["link"] == "https://x/calm.mp3"
    [moved] = choose([scene], near, book_key="b", keep=keep, available=lambda link: link != "https://x/calm.mp3")
    assert moved["link"] == "https://x/calm2.mp3"
