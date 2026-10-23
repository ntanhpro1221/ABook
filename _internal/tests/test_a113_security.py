"""Hồi quy a113: probe1–5 trở thành kiểm tra đường nhập/ghi và socket thật."""
import hashlib
import json
import os
import socket
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from abook import importers
from abook.webui import actions, book_edits, covers, package_share, txt_split
from abook.webui import cast
from tests.test_a109_security import _book_with_cover_colour, _junction


@pytest.mark.parametrize('color, expected', [('url(https://tracker.invalid/x)', ''), (' #AABBCC ', '#aabbcc')])
def test_shared_imported_cover_is_clean_on_both_outputs(tmp_path, color, expected):
    folder = _book_with_cover_colour(tmp_path, color)
    manifest = package_share.manifest(folder, 'b')
    entry = package_share.library_entry(folder, 'b', {})
    assert manifest['cover'].get('color', '') == expected
    assert entry['cover']['color'] == expected


@pytest.mark.parametrize('bad', ['abc', '12', 1.5, True, -1, 0, 20001, [1], {'a': 1}, None])
def test_foreign_dimensions_are_filtered_at_storage_and_view(tmp_path, bad):
    assert covers.stored_meta({'width': bad, 'height': 20000}) == {'height': 20000}
    folder = _book_with_cover_colour(tmp_path, '#112233', width=bad)
    assert book_edits.cover_view(folder, 'b')['width'] == 0
    # Cả metadata cũ trên đĩa cũng phải qua cổng lọc.
    (folder / covers.META_FILE).write_text(json.dumps({'width': bad, 'height': 20000}), encoding='utf-8')
    view = covers.cover_view(folder, 'b')
    assert view['width'] == 0 and view['height'] == 20000


@pytest.mark.parametrize('raw', [[], 'abc', None, 7])
def test_old_cover_metadata_with_the_wrong_shape_still_shows_the_book(tmp_path, raw):
    (tmp_path / covers.COVER_FILE).write_bytes(b'jpeg')
    (tmp_path / covers.META_FILE).write_text(json.dumps(raw), encoding='utf-8')
    assert covers.cover_view(tmp_path, 'b')['width'] == 0


def test_split_refuses_a_digest_junction_before_writing(tmp_path):
    root = tmp_path / 'library' / actions.UPLOAD_FOLDER
    root.mkdir(parents=True)
    source = root / 'whole.txt'
    raw = 'Chương 1\nMột hai ba.\n\nChương 2\nBốn năm sáu.\n'.encode()
    source.write_bytes(raw)
    outside = tmp_path / 'outside'
    outside.mkdir()
    _junction(root / hashlib.sha256(raw + b'+keep-preamble-v2').hexdigest()[:8], outside)
    with pytest.raises(actions.UploadEscape):
        txt_split.split(source, root)
    assert list(outside.iterdir()) == []


def test_extract_refuses_a_target_junction_before_reusing_or_publishing(tmp_path):
    source = Path(__file__).parent / 'fixtures' / 'import' / 'epub3.epub'
    root = tmp_path / 'library' / actions.UPLOAD_FOLDER / actions.UPLOAD_EPUB_FOLDER
    root.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = outside / 'private.txt'
    sentinel.write_bytes(b'private')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:8]
    _junction(root / f'{source.stem} - {digest}', outside)
    with pytest.raises(actions.UploadEscape):
        importers.extract(source, root)
    assert sentinel.read_bytes() == b'private'
    assert [p.name for p in outside.iterdir()] == ['private.txt']


def test_upload_never_follows_an_existing_part_symlink(tmp_path):
    library = tmp_path / 'library'
    folder = library / actions.UPLOAD_FOLDER / 'book'
    folder.mkdir(parents=True)
    outside = tmp_path / 'private.txt'
    outside.write_bytes(b'private')
    try:
        os.symlink(outside, folder / '.001.txt.part')
    except OSError as error:
        if getattr(error, 'winerror', None) != 1314:
            raise
        # Windows không cấp quyền symlink: hardlink thật cũng tái hiện ghi đè byte ngoài qua .part có sẵn.
        os.link(outside, folder / '.001.txt.part')
    with pytest.raises((actions.UploadEscape, FileExistsError)):
        actions.upload_source(library, 'book', '001.txt', b'injected')
    assert outside.read_bytes() == b'private'
    assert not (folder / '001.txt').exists()


def test_upload_scan_refuses_a_stat_error_instead_of_skipping_the_rest(tmp_path, monkeypatch):
    root = tmp_path / 'library' / actions.UPLOAD_FOLDER
    root.mkdir(parents=True)
    class Entries:
        def __enter__(self):
            return iter([SimpleNamespace(is_symlink=lambda: False, stat=lambda **kw: (_ for _ in ()).throw(PermissionError('stat denied')))])
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(actions.os, 'scandir', lambda path: Entries())
    with pytest.raises(actions.UploadEscape):
        actions.check_upload_folder(root, root)


def test_upload_scan_refuses_a_scandir_error(tmp_path, monkeypatch):
    monkeypatch.setattr(actions.os, 'scandir', lambda path: (_ for _ in ()).throw(PermissionError('scan denied')))
    with pytest.raises(actions.UploadEscape):
        actions.check_upload_folder(tmp_path, tmp_path)


def test_cast_allows_at_least_several_minutes_without_write_progress():
    assert cast.STREAM_TIMEOUT >= 300


def test_cast_partial_send_progress_renews_the_idle_timeout():
    class SlowSocket:
        def __init__(self):
            self.timeouts, self.sent = [], bytearray()
        def settimeout(self, timeout):
            self.timeouts.append(timeout)
        def send(self, data):
            self.sent.extend(data[:2])
            return min(2, len(data))
    connection = SlowSocket()
    writer = cast._ProgressWriter(connection, 0.2)
    assert writer.write(b'abcdef') == 6
    assert connection.sent == b'abcdef'
    assert connection.timeouts == [0.2, 0.2, 0.2]


@pytest.mark.parametrize('pause, idle, complete', [(0.4, 1.5, True), (0.8, 0.2, False)])
def test_cast_paused_receiver_and_stalled_receiver_release_slots(tmp_path, monkeypatch, pause, idle, complete):
    monkeypatch.setattr(cast, 'STREAM_TIMEOUT', idle)
    audio = tmp_path / 'a.mp3'
    audio.write_bytes(b'ID3' + b'x' * (6 * 1024 * 1024))
    media = cast.CastMedia('127.0.0.1')
    client = socket.socket()
    try:
        url = media.share(audio, '127.0.0.1')
        server = media._server
        client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        client.settimeout(4)
        client.connect(('127.0.0.1', server.server_port))
        client.sendall(f'GET {urlsplit(url).path} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'.encode())
        first = client.recv(4096)
        time.sleep(pause)
        received = bytearray(first)
        while chunk := client.recv(1 << 20):
            received.extend(chunk)
        body = received.split(b'\r\n\r\n', 1)[1]
        assert (len(body) == audio.stat().st_size) is complete
        deadline = time.monotonic() + 2
        while server.budget._held and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not server.budget._held
    finally:
        client.close()
        media.close()
