"""Ngắt nối tiếp (Corpus research/music/PLAN_sadwithin.md): mảnh `length` lệch V xa đầu cảnh đang chạy thì thành đầu cảnh mới."""
from abook.webui import music_scenes as S


def scene(cid, first, valence, reason="length"):
    return {"chapterId": cid, "firstSegment": first, "lastSegment": first + 9, "reason": reason, "valence": valence,
            "start": float(first), "end": float(first + 10)}


def reasons(scenes):
    return [s["reason"] for s in scenes]


def test_off_by_default_returns_the_same_scenes():
    sc = [scene(1, 0, 0.5, "chapter_start"), scene(1, 10, -0.5), scene(1, 20, -0.5)]
    assert S.MOOD_BREAK_THETA is None
    assert S.break_continuation(sc) == sc


def test_a_jump_without_hysteresis_breaks_and_moves_the_reference():
    sc = [scene(1, 0, 0.4, "chapter_start"), scene(1, 10, 0.3), scene(1, 20, 0.1), scene(1, 30, 0.0)]
    out = S.break_continuation(sc, theta=0.2, hysteresis=False)
    # 0.3 lệch 0.1 < 0.2: nối tiếp; 0.1 lệch 0.3: ngắt, mốc mới 0.1; 0.0 lệch 0.1: nối tiếp.
    assert reasons(out) == ["chapter_start", "length", S.MOOD_BREAK_REASON, "length"]


def test_hysteresis_ignores_a_single_outlier():
    sc = [scene(1, 0, 0.4, "chapter_start"), scene(1, 10, -0.2), scene(1, 20, 0.4), scene(1, 30, 0.35)]
    assert reasons(S.break_continuation(sc, theta=0.2, hysteresis=True)) == ["chapter_start", "length", "length", "length"]


def test_hysteresis_breaks_when_the_next_fragment_also_moved_the_same_way():
    sc = [scene(1, 0, 0.4, "chapter_start"), scene(1, 10, -0.2), scene(1, 20, -0.3), scene(1, 30, -0.25)]
    out = S.break_continuation(sc, theta=0.2, hysteresis=True)
    assert reasons(out) == ["chapter_start", S.MOOD_BREAK_REASON, "length", "length"]


def test_hysteresis_needs_a_next_length_fragment():
    sc = [scene(1, 0, 0.4, "chapter_start"), scene(1, 10, -0.4), scene(1, 20, -0.4, "time_jump")]
    assert reasons(S.break_continuation(sc, theta=0.2, hysteresis=True)) == ["chapter_start", "length", "time_jump"]


def test_the_reference_resets_at_every_real_boundary_and_chapter():
    sc = [scene(1, 0, 0.5, "chapter_start"), scene(1, 10, 0.5), scene(2, 0, -0.5, "chapter_start"), scene(2, 10, -0.5),
          scene(2, 20, 0.0, "separator"), scene(2, 30, 0.05)]
    assert reasons(S.break_continuation(sc, theta=0.2, hysteresis=False)) == reasons(sc)


def test_does_not_modify_its_input():
    sc = [scene(1, 0, 0.4, "chapter_start"), scene(1, 10, -0.4), scene(1, 20, -0.4)]
    before = [dict(s) for s in sc]
    S.break_continuation(sc, theta=0.2, hysteresis=True)
    assert sc == before


def test_chapter_scenes_runs_its_scenes_through_the_break(monkeypatch):
    seen = []
    monkeypatch.setattr(S, "break_continuation", lambda scenes: seen.append(len(scenes)) or scenes)
    segs = [{"id": i, "kind": "narration", "text": "Câu chuyện tiếp tục một cách bình thường.", "emotion": "neutral"} for i in range(30)]
    S.chapter_scenes({"chapterId": 1, "segments": segs})
    assert seen and seen[0] >= 1
