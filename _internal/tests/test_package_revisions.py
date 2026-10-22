import json
from pathlib import Path

import pytest

from abook.webui import audio_revision, bookfile, packages
from abook.webui.fingerprints import Fingerprints

CASES = json.loads((Path(__file__).parent / "fixtures/audio_revisions.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_shared_import_order(case):
    assert audio_revision.import_state(case["local"], case["incoming"], case["localAt"], case["incomingAt"]) == case["status"]


def test_equal_chapter_retake_updates_in_place_and_old_file_asks(tmp_path):
    def packed(name, audio, at):
        book = {"title": "Sách", "chaptersTotal": 2, "chaptersAvailable": 2, "chapters": [
            {"id": i, "file": f"chapters/{i}.mp3", "available": True} for i in (1, 2)]}
        file = bookfile.seal(book, {"chapters/1.mp3": b"same", "chapters/2.mp3": audio}, tmp_path / name, producer="test", version=1)
        # Separate real package snapshots with explicit chronological order.
        from tests.test_bookfile import _rewrite
        def change(name, data):
            if name == "book.json":
                b = json.loads(data)
                b["package"]["createdAt"] = at
                return json.dumps(b).encode()
            return data
        return _rewrite(file, tmp_path / ("dated-" + name), change)

    old = packed("old.abook", b"old", "2026-10-21T00:00:00Z")
    new = packed("new.abook", b"new", "2026-10-22T00:00:00Z")
    library = tmp_path / "library"
    prints = Fingerprints(tmp_path / "prints.json")
    folder, how = packages.import_file(old, library, [], prints)
    assert how == "new"
    (folder / "edits.json").write_text('{"format":"abook-edits","version":1,"title":"Tên bạn đặt"}', encoding="utf-8")
    first_stamp = (folder / "chapters/1.mp3").stat().st_mtime_ns
    from abook.webui.library import book_id
    from abook.webui.listening import Listening
    listening = Listening(tmp_path / "listening.json")
    listening.progress(book_id(folder), 2, 12, 60)
    before = listening.get(book_id(folder))
    again, how = packages.import_file(new, library, [], prints)
    assert (again, how) == (folder, "updated")
    assert (folder / "chapters/2.mp3").read_bytes() == b"new"
    assert (folder / "chapters/1.mp3").stat().st_mtime_ns == first_stamp
    assert json.loads((folder / "edits.json").read_text(encoding="utf-8"))["title"] == "Tên bạn đặt"
    assert listening.get(book_id(folder)) == before
    assert packages.import_file(old, library, [], prints) == (folder, "older")
    assert (folder / "chapters/2.mp3").read_bytes() == b"new"
    assert packages.import_file(old, library, [], prints, allow_older=True) == (folder, "updated")
    assert (folder / "chapters/2.mp3").read_bytes() == b"old"
    assert listening.get(book_id(folder)) == before


def test_all_chapters_can_be_retaken_and_repacking_old_audio_does_not_make_it_new(tmp_path):
    def packed(name, content, revision):
        book = {"title": "Sách", "sourceFingerprint": "same-source", "audioUpdatedAt": revision,
                "chaptersAvailable": 1, "chaptersTotal": 1, "chapters": [{"id": 1, "available": True, "file": "chapters/1.mp3"}]}
        return bookfile.seal(book, {"chapters/1.mp3": content}, tmp_path / name, producer="test", version=1)
    old = packed("old.abook", b"old", "2026-10-21T00:00:00Z")
    new = packed("new.abook", b"new", "2026-10-22T00:00:00Z")
    prints = Fingerprints(tmp_path / "prints.json")
    folder, _ = packages.import_file(old, tmp_path / "library", [], prints)
    assert packages.import_file(new, tmp_path / "library", [], prints) == (folder, "updated")
    with bookfile.BookFile(old) as opened:
        other = opened.extract(tmp_path / "other")
    repacked = bookfile.repack(other, tmp_path / "repacked-old.abook")
    assert packages.import_file(repacked, tmp_path / "library", [], prints) == (folder, "older")
    assert (folder / "chapters/1.mp3").read_bytes() == b"new"
