from pathlib import Path

from abook.webui import reviews


def _items(count):
    return [{"stableId": f"s{i}", "segmentId": i, "chapterId": 1, "kind": "failed",
             "similarity": None, "pendingSpoken": None} for i in range(count)]


def test_review_pages_filter_before_limiting_and_reach_beyond_600(monkeypatch):
    monkeypatch.setattr(reviews, "review_items", lambda _: _items(605))
    verdicts = {f"s{i}": {"verdict": "ok", "chapterId": 1} for i in range(600)}
    page = reviews.review_view(Path("unused"), verdicts, include_minor=False, filter="todo", limit=3)
    assert [i["stableId"] for i in page["items"]] == ["s600", "s601", "s602"]
    assert page["remaining"] == 2
    last = reviews.review_view(Path("unused"), verdicts, include_minor=False, filter="todo", limit=3,
                               cursor=page["nextCursor"])
    assert [i["stableId"] for i in last["items"]] == ["s603", "s604"]
    assert last["remaining"] == 0 and last["nextCursor"] is None
    done = reviews.review_view(Path("unused"), verdicts, include_minor=False, filter="done", limit=600)
    assert len(done["items"]) == 600


def test_review_cursor_still_advances_when_previous_page_is_handled(monkeypatch):
    monkeypatch.setattr(reviews, "review_items", lambda _: _items(605))
    page = reviews.review_view(Path("unused"), {}, include_minor=False, filter="todo", limit=600)
    verdicts = {i["stableId"]: {"verdict": "ok", "chapterId": 1} for i in page["items"]}
    following = reviews.review_view(Path("unused"), verdicts, include_minor=False, filter="todo",
                                    cursor=page["nextCursor"])
    assert len(following["items"]) == 5


def test_changed_audio_archives_verdict_and_is_unheard_after_reopen(tmp_path):
    from tests.test_listener_speakers import _book

    paths, db = _book(tmp_path)
    with db.connect() as connection:
        connection.execute("UPDATE segments SET status='warning', asr_similarity=0.5, wav_sha256='take-one' WHERE stable_id='c1s1'")
    saved = reviews.Reviews()
    saved.set(paths.root, "c1s1", "redo", 1)
    assert saved.get(paths.root)["c1s1"]["verdict"] == "redo"
    with db.connect() as connection:
        connection.execute("UPDATE segments SET wav_sha256='take-two' WHERE stable_id='c1s1'")
    reopened = reviews.Reviews().get(paths.root)
    view = reviews.review_view(paths.root, reopened, include_minor=False, filter="todo")
    assert view["pending"] == 1 and view["items"][0]["verdict"] is None
    assert view["redoChapters"] == []
    assert reopened["c1s1"]["history"][0]["audioSha256"] == "take-one"
    saved.set(paths.root, "c1s1", "ok", 1)
    assert len(saved.get(paths.root)["c1s1"]["history"]) == 1
    assert saved.get(paths.root)["c1s1"]["audioSha256"] == "take-two"


def test_verdict_from_a_stale_review_page_cannot_approve_a_new_take(tmp_path):
    import pytest
    from tests.test_listener_speakers import _book

    paths, db = _book(tmp_path)
    with db.connect() as connection:
        connection.execute("UPDATE segments SET wav_sha256='new-take' WHERE stable_id='c1s1'")
    saved = reviews.Reviews()
    with pytest.raises(ValueError, match="bản thu"):
        saved.set(paths.root, "c1s1", "ok", 1, audio_sha256="old-take")
    assert saved.get(paths.root) == {}
