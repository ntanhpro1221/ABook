"""Danh mục nhạc nền trên mây (webui/music_catalog.py) và chọn nhạc cho từng đoạn (webui/music_select.py)."""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pytest

from abook.webui.music_catalog import CatalogError, MusicCatalog, cell_of, shard_of
from abook.webui.music_select import choose, scene_key

TRACKS = {
    "https://x/calm.mp3": {"valence": 0.3, "arousal": -0.7, "family": "piano", "duration": 180, "source": "incompetech"},
    "https://x/calm2.mp3": {"valence": 0.2, "arousal": -0.5, "family": "eastern", "duration": 200,
                            "source": "incompetech"},
    "https://x/battle.mp3": {"valence": -0.4, "arousal": 0.85, "family": "orchestral", "duration": 150,
                             "source": "incompetech", "title": "Battle", "creator": "Kevin MacLeod"},
    "https://x/sad.mp3": {"valence": -0.7, "arousal": -0.4, "family": "piano", "duration": 240, "source": "incompetech",
                          "emotions": {"sadness": 0.8, "nostalgia": 0.4}, "sd": {"arousal": 0.3}},
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


def _tracks_at(*offsets: tuple[str, dict]) -> list[dict]:
    base = {"duration": 200, "source": "incompetech"}
    return [{"link": f"https://x/{name}.mp3", **base, **fields} for name, fields in offsets]


def _flat_scene(**extra) -> dict:
    return {**_scene(1, 0.0, 0.0), "tension": 0.0, "confidence": 1.0, **extra}


def test_an_energy_mismatch_costs_more_than_an_equal_valence_mismatch_and_tension_sits_between() -> None:
    from abook.webui.music_select import AXIS_WEIGHTS, rank, scene_sigma, z_distance

    assert AXIS_WEIGHTS["arousal"] > AXIS_WEIGHTS["tension"] > AXIS_WEIGHTS["valence"]
    scene = _flat_scene()
    sigma = scene_sigma(scene)
    target = (0.0, 0.0, 0.0)
    energy, tension, valence = (z_distance({"valence": v, "arousal": a, "tension": t}, target, sigma)
                                for v, a, t in ((0.0, 0.4, 0.0), (0.0, 0.0, 0.4), (0.4, 0.0, 0.0)))
    assert energy > tension > valence
    tracks = _tracks_at(("energy", {"valence": 0.0, "arousal": 0.4, "tension": 0.0}),
                        ("valence", {"valence": 0.4, "arousal": 0.0, "tension": 0.0}))
    assert [t["link"] for t in rank(scene, lambda v, a: tracks, book_key="b")] == ["https://x/valence.mp3", "https://x/energy.mp3"]


def test_a_wider_scene_spread_makes_the_same_mismatch_count_less() -> None:
    from abook.webui.music_select import scene_sigma, z_distance

    track = {"valence": 0.0, "arousal": 0.5, "tension": 0.0}
    target = (0.0, 0.0, 0.0)
    tight = z_distance(track, target, scene_sigma(_flat_scene(sd={"valence": 0.05, "arousal": 0.05, "tension": 0.05})))
    loose = z_distance(track, target, scene_sigma(_flat_scene(sd={"valence": 0.4, "arousal": 0.4, "tension": 0.4})))
    assert loose < tight
    wide_track = z_distance({**track, "sd": {"arousal": 0.5}}, target, scene_sigma(_flat_scene()))
    assert wide_track < z_distance(track, target, scene_sigma(_flat_scene())), "bài lẫn lộn hơn cũng khoan dung hơn"


def test_a_scene_without_sd_uses_the_default_and_a_weak_scene_is_given_more_slack() -> None:
    from abook.webui.music_select import SCENE_SD_DEFAULT, UNCERTAIN_SD, scene_sigma

    sure = scene_sigma({"confidence": 1.0})
    assert sure == {axis: pytest.approx(SCENE_SD_DEFAULT) for axis in ("valence", "arousal", "tension")}
    weak = scene_sigma({"confidence": 0.1})
    assert all(weak[axis] > sure[axis] for axis in sure)
    assert weak["arousal"] == pytest.approx((SCENE_SD_DEFAULT ** 2 + (UNCERTAIN_SD * 0.9) ** 2) ** 0.5)


def test_a_track_without_tension_is_scored_on_the_other_two_axes() -> None:
    from abook.webui.music_select import z_distance

    target = (0.0, 0.0, 0.5)
    without = z_distance({"valence": 0.2, "arousal": 0.2}, target)
    assert without == pytest.approx(z_distance({"valence": 0.2, "arousal": 0.2, "tension": 0.5}, target))
    assert z_distance({"valence": 0.2, "arousal": 0.2, "tension": -0.5}, target) > without


def test_the_residual_variance_of_an_imported_track_widens_its_distance_only() -> None:
    from abook.webui.music_select import AXIS_WEIGHTS, SCENE_SD_DEFAULT, TAU, TRACK_SD_DEFAULT, VET_VAR_WEIGHT, z_distance

    target = (0.3, -0.2, 0.1)
    track = {"valence": 0.1, "arousal": 0.0, "tension": 0.4}
    plain = z_distance(track, target)
    assert VET_VAR_WEIGHT == 0.1
    assert z_distance({**track, "vetVar": {}}, target) == plain, "bài danh mục (không có vetVar) y hệt trước"
    var = {"valence": 0.04, "arousal": 0.03, "tension": 0.04}
    denominator = SCENE_SD_DEFAULT ** 2 + TRACK_SD_DEFAULT ** 2 + TAU ** 2
    expected = math.sqrt(sum(AXIS_WEIGHTS[axis] * ((track[axis] - wanted) ** 2 + VET_VAR_WEIGHT * var[axis]) / denominator
                             for axis, wanted in zip(("valence", "arousal", "tension"), target)))
    widened = z_distance({**track, "vetVar": var}, target)
    assert widened > plain and widened == pytest.approx(expected)
    # trục không có trong vetVar thì không cộng gì; bài chưa có tension thì bỏ cả số hạng của trục ấy
    assert z_distance({**track, "vetVar": {"valence": 0.04}}, target) < widened
    assert z_distance({"valence": 0.1, "arousal": 0.0, "vetVar": var}, target) == pytest.approx(
        math.sqrt(sum(AXIS_WEIGHTS[axis] * ((track[axis] - wanted) ** 2 + VET_VAR_WEIGHT * var[axis]) / denominator
                      for axis, wanted in zip(("valence", "arousal"), target))))


def _emotion_scene() -> dict:
    return {**_flat_scene(), "emotions": {"sadness": 0.9, "tenderness": 0.7}}


def _emotions_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Số hạng Lớp 2 đang tắt mặc định (EMOTION_WEIGHT 0 tới khi đường LLM vào) - các test cơ chế bật nó lên."""
    from abook.webui import music_select
    monkeypatch.setattr(music_select, "EMOTION_WEIGHT", 1.0)


def test_emotion_cosine_prefers_the_track_with_the_scenes_blend_and_ignores_missing_data(monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.music_select import emotion_cosine, rank

    _emotions_on(monkeypatch)

    assert emotion_cosine({"sadness": 1.0}, {"sadness": 0.3}) == pytest.approx(1.0), "cosine, không phải độ lớn"
    assert emotion_cosine({"sadness": 1.0}, {"joy": 1.0}) == pytest.approx(0.0)
    assert emotion_cosine({}, {"joy": 1.0}) is None and emotion_cosine(None, {"joy": 1.0}) is None
    assert emotion_cosine({"joy": 1.0}, ["joy"]) is None and emotion_cosine({"joy": 0.0}, {"joy": 1.0}) is None
    same = {"valence": 0.0, "arousal": 0.0, "tension": 0.0}
    tracks = _tracks_at(("joyful", {**same, "emotions": {"joy": 0.9}}),
                        ("blend", {**same, "emotions": {"sadness": 0.6, "tenderness": 0.5}}))
    for order in (tracks, list(reversed(tracks))):
        ranked = rank(_emotion_scene(), lambda v, a, order=order: order, book_key="b")
        assert [t["link"] for t in ranked] == ["https://x/blend.mp3", "https://x/joyful.mp3"]
        assert ranked[1]["score"] - ranked[0]["score"] > 0.4


def test_a_track_or_scene_without_emotions_ranks_by_distance_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.music_select import rank

    _emotions_on(monkeypatch)

    same = {"valence": 0.0, "arousal": 0.0, "tension": 0.0}
    tracks = _tracks_at(("a", {**same}), ("b", {**same, "emotions": {"sadness": 0.9}}))
    ranked = rank(_emotion_scene(), lambda v, a: tracks, book_key="b")
    assert [t["link"] for t in ranked] == ["https://x/b.mp3", "https://x/a.mp3"], "bài có hồ sơ cảm xúc hợp thì lên trước"
    plain = rank(_flat_scene(), lambda v, a: tracks, book_key="b")
    assert abs(plain[0]["score"] - plain[1]["score"]) < 0.01


def test_emotion_cosine_never_rescues_a_track_beyond_the_silence_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import music_select
    from abook.webui.music_select import MAX_Z, rank, scene_sigma, z_distance

    _emotions_on(monkeypatch)
    EMOTION_WEIGHT = music_select.EMOTION_WEIGHT

    scene = {**_flat_scene(arousal=0.5), "emotions": {"sadness": 0.9}}
    scene["arousal"] = 0.5
    track = {"link": "https://x/far.mp3", "valence": 0.0, "arousal": -0.25, "tension": 0.0, "duration": 200,
             "source": "incompetech", "emotions": {"sadness": 0.9}}
    distance = z_distance(track, (0.0, 0.5, 0.0), scene_sigma(scene))
    assert MAX_Z < distance < MAX_Z + EMOTION_WEIGHT, "cosine 1 sẽ kéo bài này xuống dưới ngưỡng nếu được tính"
    assert rank(scene, lambda v, a: [track], book_key="b") == []
    assert rank(scene, lambda v, a: [dict(track, arousal=0.4)], book_key="b"), "bài gần thì có"


def test_the_catalog_hands_emotions_and_sd_through_to_the_ranking(tmp_path: Path) -> None:
    from abook.webui.music_select import rank

    catalog = MusicCatalog(tmp_path / "cache", str(_catalog_dir(tmp_path / "cloud")))
    near_sad = catalog.near(-0.7, -0.4, radius=0)
    sad = next(t for t in near_sad if t["link"] == "https://x/sad.mp3")
    assert sad["emotions"]["sadness"] == 0.8 and sad["sd"]["arousal"] == 0.3
    scene = {**_scene(1, -0.7, -0.4), "emotions": {"sadness": 0.9}}
    ranked = rank(scene, lambda v, a: catalog.near(v, a, radius=1), book_key="b")
    assert ranked[0]["link"] == "https://x/sad.mp3"


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
