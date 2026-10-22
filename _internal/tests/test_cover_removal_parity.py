import json
from pathlib import Path

import pytest

from abook.webui import book_edits

CASES = json.loads((Path(__file__).parent / "fixtures/book_edits/cover_removal.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_remove_cover_without_a_fake_change(tmp_path, case):
    (tmp_path / "book.json").write_text('{"title":"Sách","chapters":[]}', encoding="utf-8")
    if case["base"]:
        (tmp_path / "cover.jpg").write_bytes(b"base")
    if case["edited"]:
        (tmp_path / "edits").mkdir()
        (tmp_path / "edits/cover.jpg").write_bytes(b"edited")
        (tmp_path / "edits.json").write_text(json.dumps({"format": "abook-edits", "version": 1,
            "cover": {"color": "#112233", "width": 1, "height": 1, "version": 1}}), encoding="utf-8")
    book_edits.remove_cover(tmp_path)
    edits = book_edits.load(tmp_path)
    assert ("cover" in edits) == case["hasCoverKey"]
    if case["hasCoverKey"]:
        assert edits["cover"] is None
    assert not (tmp_path / "edits/cover.jpg").exists()
