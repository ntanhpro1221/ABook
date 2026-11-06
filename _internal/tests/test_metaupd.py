"""Desktop web and Qt both open packaged books through App.open_book_file."""
from __future__ import annotations

import json

import pytest

from abook.webui import book_edits, packages
from tests.a81_files import app_in, build, simple_book


@pytest.mark.parametrize("change", ["cover", "script", "metadata", "cast", "music"])
def test_open_file_updates_the_base_and_keeps_listener_state(tmp_path, change):
    library = tmp_path / "library"
    library.mkdir()
    app = app_in(tmp_path, library)
    book, files = simple_book(1)
    files["scripts/1.json"] = b'{"segments": []}'
    first = app.open_book_file(str(build(tmp_path / "first.abook", files, book)))
    folder, = packages.folders(library)
    identifier = first["id"]
    book_edits.set_title(folder, "Tên của người nghe")
    edits = book_edits.load(folder)
    app.listening.progress(identifier, 1, 23.5, 120.0)
    app.listening.set_rate(identifier, 1.25)
    app.listening.set_chapter_done(identifier, 1, True)
    state = json.loads(json.dumps(app.listening.get(identifier)))
    audio = (folder / "chapters/001.mp3").read_bytes()

    if change == "cover":
        files["cover.jpg"] = b"new cover"
        book["cover"] = {"file": "cover.jpg", "width": 12, "height": 24}
    elif change == "script":
        files["scripts/1.json"] = b'{"segments": [{"text": "new script"}]}'
    elif change == "metadata":
        book.update(title="Tên mới trong file", author="Tác giả", description="Mô tả mới")
    elif change == "cast":
        cast = json.loads(files["cast.json"])
        cast["narrator"]["voice"] = "new voice"
        files["cast.json"] = json.dumps(cast).encode()
    else:
        track = "music/" + "a" * 40 + ".mp3"
        files[track] = b"ID3 music"
        book["music"] = {"tracks": {track: {"file": track}}, "chapters": {"1": [
            {"start": 0.0, "end": 1.0, "track": track}]}}
    incoming = build(tmp_path / "new.abook", files, book)
    updated = app.open_book_file(str(incoming))
    assert updated["how"] == "updated" and updated["id"] == identifier
    assert len(list(packages.folders(library))) == 1
    for name, data in files.items():
        assert (folder / name).read_bytes() == data
    raw = packages.manifest(folder)
    for key in ("title", "author", "description", "cover", "music"):
        assert raw.get(key) == book.get(key)
    assert book_edits.load(folder) == edits
    assert packages.edited_manifest(folder)["title"] == "Tên của người nghe"
    assert app.listening.get(identifier) == state
    assert (folder / "chapters/001.mp3").read_bytes() == audio
    assert app.open_book_file(str(incoming))["how"] == "existing"
    assert app.listening.get(identifier) == state
