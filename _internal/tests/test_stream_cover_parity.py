import json
from pathlib import Path

import pytest

from abook.webui import remote_books

CASES = json.loads((Path(__file__).parent / "fixtures/listening_records/stream_covers.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_refresh_replaces_only_a_changed_or_missing_cover(tmp_path, monkeypatch, case):
    old = {"title": "Sách", "chaptersAvailable": 2, "cover": case["old"]}
    fresh = {**old, "cover": case["new"]}
    (tmp_path / "book.json").write_text(json.dumps(old), encoding="utf-8")
    cover = tmp_path / "cover.jpg"
    if case["exists"]:
        cover.write_bytes(b"old")
    asked = []
    def request(_base, _method, path, _token, **_kwargs):
        asked.append(path)
        return json.dumps(fresh).encode() if path.endswith("manifest") else b"new"
    monkeypatch.setattr(remote_books, "_request", request)
    monkeypatch.setattr(remote_books, "_base", lambda _entry: "http://fake")
    remote_books._refresh_book({"token": "t"}, "peer", tmp_path, "b", built=tmp_path)
    assert any(path.endswith("cover.jpg") for path in asked) == case["fetch"]
    if case["fetch"]:
        assert cover.read_bytes() == b"new"
