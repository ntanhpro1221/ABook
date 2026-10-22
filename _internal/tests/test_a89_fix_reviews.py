"""a89 V2 + T4 + T8: phán quyết "Cần nghe lại" ghi một lần cho cả nhóm, đọc thì không ghi, trang xem được đệm theo chữ ký."""
import pytest

from abook.webui import reviews


def _two_lines(tmp_path):
    from tests.test_listener_speakers import _book

    paths, db = _book(tmp_path)
    return paths, db


def test_set_many_reads_audio_once_and_writes_once(tmp_path, monkeypatch):
    paths, db = _two_lines(tmp_path)
    saved = reviews.Reviews()
    calls = {"audio": 0, "write": 0}
    audio, write = saved._audio, saved._write
    monkeypatch.setattr(reviews.Reviews, "_audio", staticmethod(lambda root: calls.__setitem__("audio", calls["audio"] + 1) or audio(root)))
    monkeypatch.setattr(saved, "_write", lambda root, entry: calls.__setitem__("write", calls["write"] + 1) or write(root, entry))
    saved.set_many(paths.root, ["c1s1", "c1s2", "c1s3"], "ok", 1)
    assert calls == {"audio": 1, "write": 1}
    stored = saved.get(paths.root)
    assert {key for key, value in stored.items() if value.get("verdict") == "ok"} == {"c1s1", "c1s2", "c1s3"}


def test_set_many_writes_nothing_when_one_line_has_a_newer_take(tmp_path):
    paths, db = _two_lines(tmp_path)
    with db.connect() as connection:
        connection.execute("UPDATE segments SET wav_sha256='new-take' WHERE stable_id='c1s2'")
    saved = reviews.Reviews()
    with pytest.raises(ValueError, match="bản thu"):
        saved.set_many(paths.root, ["c1s1", "c1s2"], "ok", 1, audio_sha256="")
    assert saved.get(paths.root) == {}


def test_set_many_clears_a_verdict_like_set(tmp_path):
    paths, _db = _two_lines(tmp_path)
    saved = reviews.Reviews()
    saved.set_many(paths.root, ["c1s1", "c1s2"], "redo", 1)
    saved.set_many(paths.root, ["c1s1"], None, 1)
    assert set(saved.get(paths.root)) == {"c1s2"}


def test_get_never_writes_even_when_a_verdict_went_stale(tmp_path):
    paths, db = _two_lines(tmp_path)
    with db.connect() as connection:
        connection.execute("UPDATE segments SET wav_sha256='take-one' WHERE stable_id='c1s1'")
    saved = reviews.Reviews()
    saved.set(paths.root, "c1s1", "ok", 1)
    with db.connect() as connection:
        connection.execute("UPDATE segments SET wav_sha256='take-two' WHERE stable_id='c1s1'")
    path = reviews.Reviews.path(paths.root)
    before = path.read_bytes()
    seen = saved.get(paths.root)
    assert seen["c1s1"].get("verdict") is None and seen["c1s1"]["history"][0]["audioSha256"] == "take-one"
    assert path.read_bytes() == before  # chỉ đọc: tệp không đổi (chế độ chỉ đọc cũng gọi get)


def test_review_pages_share_one_scan_until_the_project_or_a_verdict_changes(tmp_path, monkeypatch):
    from abook.webui import listing_cache

    paths, db = _two_lines(tmp_path)
    with db.connect() as connection:
        connection.execute("UPDATE segments SET status='warning', asr_similarity=0.5 WHERE stable_id IN ('c1s1','c1s2')")
    monkeypatch.setattr(listing_cache, "RACY_SECONDS", 0)
    scans = []
    original = reviews.review_items
    monkeypatch.setattr(reviews, "review_items", lambda root: scans.append(1) or original(root))
    first = reviews.review_view(paths.root, {}, include_minor=False, limit=1)
    second = reviews.review_view(paths.root, {}, include_minor=False, limit=1, cursor=first["nextCursor"])
    assert len(scans) == 1 and first["remaining"] == 1 and len(second["items"]) == 1 and second["remaining"] == 0
    reviews.review_view(paths.root, {"c1s1": {"verdict": "ok", "chapterId": 1}}, include_minor=False)
    assert len(scans) == 2  # phán quyết đổi: tính lại
