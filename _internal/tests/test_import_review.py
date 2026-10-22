"""Hồi quy rev_396: dùng cùng đầu vào và lời lỗi với test JVM."""
import io
import hashlib
import json
import time
import zipfile
from xml.etree import ElementTree

import pytest

from abook import importers
from abook.io_utils import decode_text
from tests import import_fixtures as shared


def cases(name):
    return json.loads((shared.FIXTURES / 'expected' / f'{name}.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', cases('zip_stream_cases'), ids=lambda case: case['case'])
def test_zip_counts_actual_bytes_not_declared_size(case, monkeypatch):
    # ZIP metadata is untrusted. Feed the actual stream even though the entry claims one byte.
    with importers._open_zip(shared.FIXTURES / 'epub3.epub', 'EPUB') as book:
        current = [0]
        monkeypatch.setattr(book, 'member', lambda name: zipfile.ZipInfo(name))
        monkeypatch.setattr(book, 'open', lambda *a, **kw: io.BytesIO(b'x' * current[0]))
        with pytest.raises(importers.ImportFailed) as error:
            for index, size in enumerate(case['sizes']):
                current[0] = size
                if case['cover']:
                    opf = ElementTree.fromstring('<package/>')
                    importers._epub_cover(book, opf, {'cover': ('cover.png', 'image/png', 'cover-image')})
                else:
                    importers._read(book, f'part{index}')
        assert str(error.value) == case['error']


@pytest.mark.parametrize('name', ['review_nul', 'review_controls'])
def test_controls_are_removed_before_extract_decode_round_trip(name, tmp_path):
    book = importers.import_text(shared.FIXTURES / f'{name}.epub')
    expected = json.loads((shared.FIXTURES / 'expected' / f'{name}.json').read_text(encoding='utf-8'))
    folder, _ = importers.extract(shared.FIXTURES / f'{name}.epub', tmp_path)
    raw = next(folder.glob('*.txt')).read_bytes()
    text, encoding = decode_text(raw)
    wanted = importers.Chapter(**expected['chapters'][0])
    assert text == book.chapter_source(wanted)
    assert book.to_dict() == expected
    assert encoding.startswith('utf-8')
    assert 'Con đò' in text


def test_form_feed_in_hidden_html_does_not_split_visible_text():
    assert importers._page(b'<p>Before<script>hidden\x0cdata</script>after</p>').lines == ['Beforeafter']


@pytest.mark.parametrize('case', cases('markup_alias_cases'), ids=lambda case: case['case'])
def test_markup_aliases_in_chapters_and_drm(case):
    raw = bytes.fromhex(case['hex'])
    assert importers.markup_text(raw) == case['text']
    assert importers._page(raw).lines == [case['body']]
    assert not importers._looks_encrypted(raw)


@pytest.mark.parametrize('case', cases('markup_utf16_cases'), ids=lambda case: case['case'])
def test_bomless_utf16_in_chapters_and_drm(case):
    raw = bytes.fromhex(case['hex'])
    assert importers.markup_text(raw) == case['text']
    assert importers._page(raw).lines == [case['body']]
    assert not importers._looks_encrypted(raw)


@pytest.mark.parametrize('case', cases('malformed_xml_cases'), ids=lambda case: case['case'])
def test_strict_xml_rejects_malformed_documents(case):
    raw = bytes.fromhex(case['hex'])
    if 'error' in case:
        with pytest.raises(importers.ImportFailed, match=case['error']):
            importers._xml(raw)
    else:
        assert ''.join(importers._xml(raw).itertext()) == case['text']


@pytest.mark.parametrize('part', ['META-INF/container.xml', 'OEBPS/content.opf', 'word/document.xml'])
def test_package_xml_is_strict(part, tmp_path):
    source = 'headings.docx' if part.startswith('word/') else 'epub3.epub'
    path = tmp_path / source
    with zipfile.ZipFile(shared.FIXTURES / source) as archive:
        path.write_bytes(shared._zip([(info.filename, archive.read(info.filename) + b'<extra/>'
                                      if info.filename == part else archive.read(info.filename)) for info in archive.infolist()]))
    with pytest.raises(importers.ImportFailed):
        importers.import_text(path)


def test_5000_parts_merge_within_budget():
    case = json.loads((shared.FIXTURES / 'expected/many_parts.json').read_text(encoding='utf-8'))
    started = time.perf_counter()
    book = importers.import_text(shared.FIXTURES / 'many_parts.epub')
    elapsed = time.perf_counter() - started
    assert len(book.chapters) == 1
    assert book.chapters[0].title == case['title']
    assert len(book.chapters[0].text) == case['length']
    assert hashlib.sha256(book.chapters[0].text.encode()).hexdigest() == case['sha256']
    print(f'5000 parts: {elapsed:.3f}s')
    assert elapsed < case['max_seconds']
