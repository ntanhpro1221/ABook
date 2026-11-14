"""Artwork is optional, but a coverless export must be explicit."""
import subprocess
import sys

import pytest

from abook.webui import bookfile


@pytest.mark.parametrize(('base', 'files', 'edits', 'missing'), [
    (None, {}, None, True),
    ({'file': 'cover.jpg'}, {}, None, True),
    ({'file': 'cover.jpg'}, {'cover.jpg': b'cover'}, None, False),
    (None, {'edits/cover.jpg': b'cover'}, {'cover': {'width': 64}}, False),
    ({'file': 'cover.jpg'}, {'cover.jpg': b'cover'}, {'cover': None}, True),
    (None, {}, {'cover': {'width': 64}}, True),
])
def test_effective_cover_warning(base, files, edits, missing):
    assert bookfile.cover_warnings({'cover': base}, files, edits) == ([bookfile.MISSING_COVER] if missing else [])


def test_coverless_seal_warns_but_remains_readable(tmp_path):
    book = {'title': 'Synthetic', 'chapters': [{'id': 1, 'title': 'One', 'text': 'texts/1.txt', 'state': 'text'}]}
    with pytest.warns(bookfile.MissingCoverWarning, match='Chưa có bìa'):
        target = bookfile.seal(book, {'texts/1.txt': b'Synthetic text.'}, tmp_path / 'book.abook', producer='test', version=5)
    with bookfile.BookFile(target) as opened:
        opened.verify()
        folder = opened.extract(tmp_path / 'library')
    # Exercise the real CLI; stderr must survive even when the caller consumes stdout as a path.
    result = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'abook.webui.bookfile', 'repack', str(folder),
                             '-o', str(tmp_path / 'copy.abook')], capture_output=True, text=True, encoding='utf-8',
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert result.returncode == 0, result.stderr
    assert 'Chưa có bìa' in result.stderr
    assert (tmp_path / 'copy.abook').is_file()
