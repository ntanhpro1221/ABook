"""Untrusted peer data: tests use fakes and never probe a supplied network path."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from abook.webui import packages
from abook.webui import peer_paths, remote_books


@pytest.mark.parametrize("relative", [
    r"\\peer.invalid\share\chapter.mp3", r"C:\chapter.mp3", r"\\?\C:\chapter.mp3",
    "/chapter.mp3", "../sibling/chapter.mp3", "chapters/../chapter.mp3", "chapters/CON.mp3",
    "chapters/a.mp3:stream", "chapters/a. /x", "chapters//a.mp3", "chapters/./a.mp3",
    "chapters/CON .mp3", "chapters/CONIN$", "chapters/CONOUT$",
])
def test_package_rejects_unsafe_names_before_any_locator_io(tmp_path, monkeypatch, relative):
    locator = Mock()
    locator.root = tmp_path
    locator.probe.return_value = (tmp_path / "dummy", False)
    factory = Mock(return_value=locator)
    monkeypatch.setattr(packages, "_locator", factory)
    assert packages._inside(tmp_path, relative) is None
    factory.assert_not_called()


def test_remote_manifest_is_checked_before_creating_book_directory(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(remote_books, "_request", lambda *a, **k: json.dumps({
        "title": "Book", "chapters": [{"file": r"\\peer.invalid\share\a.mp3", "available": True}],
    }).encode())
    with pytest.raises(remote_books.RemoteError):
        remote_books._refresh_book({"host": "127.0.0.1", "port": 1, "token": "t"}, "peer", tmp_path / "new", "book")
    assert not (tmp_path / "new").exists()


def test_normal_package_names_work(tmp_path):
    target = tmp_path / "chapters" / "1.mp3"
    target.parent.mkdir()
    target.write_bytes(b"audio")
    assert packages._inside(tmp_path, "chapters/1.mp3") == target.resolve()


def test_download_stops_before_writing_beyond_promised_size(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from io import BytesIO
    class Response(BytesIO):
        status = 200
        length = None
        def getheader(self, name, default=None):
            return default
    response = Response(b"x" * 1536)
    @contextmanager
    def opened(*args, **kwargs):
        yield response, "pin"
    monkeypatch.setattr(remote_books, "_entry_of", lambda book: ({"token": "t", "host": "127.0.0.1", "port": 1}, "book"))
    monkeypatch.setattr(remote_books, "_open", opened)
    target = tmp_path / "chapter.mp3"
    target.write_bytes(b"old")
    written = []
    with pytest.raises(remote_books.RemoteError):
        remote_books._save(tmp_path, "chapter.mp3", {}, size=1024, progress=written.append)
    assert sum(written) <= 1024, "detected overflow only after writing it"
    assert target.read_bytes() == b"old"
    assert not list(tmp_path.glob("*.part*"))


@pytest.mark.parametrize("announced", [None, 16 * 1024 * 1024 + 1])
def test_response_read_has_a_real_byte_budget(announced):
    from io import BytesIO
    response = BytesIO(b" " * (16 * 1024 * 1024 + 1))
    response.length = announced
    response.getheader = lambda name, default=None: default
    with pytest.raises(remote_books.RemoteError):
        remote_books._read(response)
    assert response.tell() <= 16 * 1024 * 1024 + 1


@pytest.mark.parametrize("project", [False, True])
def test_oversized_archive_mime_is_refused_without_reading_it(tmp_path, monkeypatch, project):
    import zipfile
    from abook.webui import bookfile, projectfile
    archive = tmp_path / "book.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("mimetype", b"x" * 1024)
    read = []
    original = zipfile.ZipFile.read
    def traced(self, name, *args, **kwargs):
        read.append(name)
        return original(self, name, *args, **kwargs)
    monkeypatch.setattr(zipfile.ZipFile, "read", traced)
    with pytest.raises((bookfile.BookFileError, projectfile.ProjectFileError)):
        (projectfile.ProjectFile if project else bookfile.BookFile)(archive)
    assert "mimetype" not in read


@pytest.mark.parametrize("kind", ["json", "cover", "error"])
@pytest.mark.parametrize("announced", [False, True])
def test_all_response_types_stop_at_their_budget(kind, announced):
    from abook.webui import peer_limits
    cap = {"json": peer_limits.JSON_BYTES, "cover": peer_limits.COVER_BYTES, "error": peer_limits.ERROR_BYTES}[kind]
    class Endless:
        length = None
        read_bytes = 0
        def getheader(self, name, default=None):
            return str(cap + 1) if announced else default
        def read(self, size=-1):
            assert size > 0
            self.read_bytes += size
            return b"x" * size
    source = Endless()
    with pytest.raises(remote_books.RemoteError):
        remote_books._read(source, limit=cap)
    assert source.read_bytes <= (0 if announced else cap + 1)


def test_json_shape_and_depth_are_bounded_but_brackets_in_strings_are_not_nesting():
    from abook.webui.peer_limits import check_json
    check_json(b'{"text":"[[[\\\"}}}"}')
    check_json(b'{"ok":true}')
    for data in (b"[]", b'"string"', b"{" + b'"x":[' * 70 + b"0" + b"]" * 70 + b"}"):
        with pytest.raises(ValueError):
            check_json(data)
