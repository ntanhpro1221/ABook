"""Original fixtures for organization, format and synthesis identity."""
import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from abook import book_volumes as bv, importers
from abook.hako_import import load
from abook.database import ProjectDB
from abook.webui import bookfile, textbook, packages, export


def image(color):
    out = io.BytesIO()
    Image.new('RGB', (80, 100), color).save(out, 'JPEG')
    return out.getvalue()


def imported():
    return importers.ImportedBook('Test book', chapters=[
        importers.Chapter('Chapter 1', 'The red clock stopped.', volume=1),
        importers.Chapter('Chapter 1', 'The blue clock started.', volume=2)],
        volumes=[importers.Volume(1, 1, 'First', image('red'), 'image/jpeg'), importers.Volume(2, 2, 'Second')])


def test_hako_preserves_source_order_duplicate_titles_and_each_volume_cover():
    url = 'https://docln.net/truyen/123-test'
    page = '''<div class="series-name">Original fixture</div>
    <section class="volume-list"><header><span class="sect-title">First</span></header>
    <div style="background-image:url(/red.jpg)"></div><ul class="list-chapters">
    <li><a href="/truyen/123/c20-one" title="Chapter 1">Chapter 1</a></li></ul></section>
    <section class="volume-list"><header><span class="sect-title">Second</span></header>
    <img data-src="/blue.jpg"><ul class="list-chapters">
    <li><a href="/truyen/123/c10-two" title="Chapter 1">Chapter 1</a></li></ul></section>'''
    data = {url: page.encode(), 'https://docln.net/red.jpg': image('red'), 'https://docln.net/blue.jpg': image('blue')}
    data.update({f'https://docln.net/truyen/123/{chapter}': f'<div id="chapter-content"><p>{text}</p></div>'.encode()
                 for chapter, text in [('c20-one', 'Red clock.'), ('c10-two', 'Blue clock.')]})
    book = load(url, data.__getitem__)
    assert [v.title for v in book.volumes] == ['First', 'Second']
    assert [c.volume for c in book.chapters] == [1, 2]
    assert [c.title for c in book.chapters] == ['Chapter 1', 'Chapter 1']
    assert book.volumes[0].cover_bytes != book.volumes[1].cover_bytes
    assert [c.text for c in book.chapters] == ['Red clock.', 'Blue clock.']


def test_nested_roundtrip_checks_covers_and_keeps_global_chapter_identity(tmp_path):
    path = textbook.build(imported(), tmp_path / 'book.abook')
    with zipfile.ZipFile(path) as archive:
        raw = json.loads(archive.read('book.json'))
        assert 'chapters' not in raw
        assert raw['package']['version'] == 6
        assert [v['chapters'][0]['index'] for v in raw['volumes']] == [1, 2]
        assert 'covers/1.jpg' in raw['package']['files']
    with bookfile.BookFile(path) as reader:
        reader.verify()
        assert [c['id'] for c in reader.book['chapters']] == [1, 2]
        assert reader.book['volumes'][1]['cover'] is None


@pytest.mark.parametrize('change', ['duplicate', 'reorder', 'empty', 'cover'])
def test_invalid_tree_is_refused(change):
    book = {'volumes': [{'id': 1, 'number': 1, 'title': 'One', 'chapters': [{'id': 1, 'index': 1}, {'id': 2, 'index': 2}]}]}
    rows = book['volumes'][0]['chapters']
    if change == 'duplicate': rows[1]['id'] = 1
    if change == 'reorder': rows.reverse()
    if change == 'empty': rows.clear()
    if change == 'cover': book['volumes'][0]['cover'] = {'file': '../outside.jpg'}
    with pytest.raises(ValueError): bv.flatten(book)


def test_organization_reopens_atomically_and_never_changes_segments_or_seed(tmp_path):
    from abook.text_processing import load_and_segment_chapter, build_chapter_manifest
    from abook.tts import TTSCoordinator
    root = tmp_path / 'book'
    sources = root / 'sources'
    sources.mkdir(parents=True)
    files = []
    for index, text in enumerate(['Bàn giấy đã khô.\n\n“Đi tiếp nhé!”', 'Cửa sổ vừa mở.\n\n“Được, tôi đi.”'], 1):
        file = sources / f'{index}.txt'
        file.write_text(text, encoding='utf-8')
        files.append(file)
    db = ProjectDB(root / 'project.sqlite3')
    db.ensure_chapters(build_chapter_manifest(files, root / 'output'))
    chapters = [dict(c) for c in db.list_chapters()]
    before = [load_and_segment_chapter(c, 240, project_root=root) for c in chapters]
    for chapter, rows in zip(chapters, before):
        db.replace_chapter_segments(chapter['id'], rows)
    with db.connect() as conn:
        segments = [dict(row) for row in conn.execute('SELECT * FROM segments ORDER BY id')]
    adapter = object.__new__(TTSCoordinator)
    adapter._voice_profile_for_row = lambda row: {"voice_key": "locked-narrator"}
    before_seeds = [adapter.generation_seed(row, salt) for row in segments for salt in ("primary", "asr_clarity_repair_1")]
    # Use the actual generation-seed method with the same locked base seed.
    ids = [c['id'] for c in chapters]
    bv.organize(root, [{'id': 1, 'number': 1, 'title': 'First', 'chapters': ids[:1]},
                       {'id': 2, 'number': 2, 'title': 'Second', 'chapters': ids[1:]}])
    reopened = ProjectDB(root / 'project.sqlite3')
    assert [load_and_segment_chapter(dict(c), 240, project_root=root) for c in reopened.list_chapters()] == before
    with reopened.connect() as conn:
        after = [dict(row) for row in conn.execute('SELECT * FROM segments ORDER BY id')]
        assert after == segments
        assert [adapter.generation_seed(row, salt) for row in after for salt in ("primary", "asr_clarity_repair_1")] == before_seeds
    with pytest.raises(ValueError):
        bv.organize(root, [{'id': 1, 'number': 1, 'title': 'Invalid', 'chapters': ids[::-1]}])
    assert [v['title'] for v in bv.project(root, [{'id': i} for i in ids])] == ['First', 'Second']


def _hako_site():
    url = 'https://docln.net/truyen/77-fixture'
    page = '''<div class="series-name">Fixture series</div>
    <section class="volume-list"><span class="sect-title">Tap mot</span><img src="/v1.jpg">
    <a href="/truyen/77/c1-a" title="Mo dau">Mo dau</a><a href="/truyen/77/c2-b" title="Chuong 1">Chuong 1</a></section>
    <section class="volume-list"><span class="sect-title">Tap hai</span>
    <a href="/truyen/77/c3-c" title="Chuong 1">Chuong 1</a></section>'''
    data = {url: page.encode(), 'https://docln.net/v1.jpg': image('green')}
    for name, text in [('c1-a', 'Gio thoi qua san.'), ('c2-b', 'Mua roi tren mai.'), ('c3-c', 'Nang len o doi.')]:
        data[f'https://docln.net/truyen/77/{name}'] = f'<div id="chapter-content"><p>{text}</p></div>'.encode()
    return url, data


def test_a_pasted_hako_address_becomes_one_book_with_its_volumes_and_volume_covers(tmp_path, monkeypatch):
    from abook import hako_import
    from abook.webui import actions
    url, data = _hako_site()
    asked = []
    monkeypatch.setattr(hako_import, 'fetch', lambda link: asked.append(link) or data[link])
    scan = actions.scan_inputs([url], epub_root=tmp_path / 'sources')
    files = [row['path'] for row in scan['files']]
    assert len(files) == 3 and not scan['errors'], scan['errors']
    fetched = len(asked)
    actions.scan_inputs([url], epub_root=tmp_path / 'sources')
    assert len(asked) == fetched, 'quét lại dùng thư mục đã tách, không tải lại'
    root = actions.create_book(tmp_path / 'library', files, 'Fixture series', 'fast', '')
    chapters = [dict(c) for c in ProjectDB(root / 'project.sqlite3').list_chapters()]
    volumes = bv.project(root, chapters)
    assert [(v['number'], v['title']) for v in volumes] == [(1, 'Tap mot'), (2, 'Tap hai')]
    assert [c['volumeId'] for c in chapters] == [1, 1, 2]
    assert volumes[0]['cover']['file'] == 'covers/1.jpg' and volumes[1]['cover'] is None
    assert (root / 'covers' / '1.jpg').is_file()
    bv.save_cover(root, 2, image('blue'))
    assert bv.project(root, chapters)[1]['cover']['file'] == 'covers/2.jpg'
    bv.save_cover(root, 1, None)
    assert bv.project(root, chapters)[0]['cover'] is None, "gỡ bìa quyển thì dùng lại bìa sách"


def test_same_text_split_or_not_gives_identical_segments(tmp_path):
    from abook.text_processing import load_and_segment_chapter
    from abook.webui import actions
    sources = tmp_path / 'src'
    sources.mkdir()
    for index, text in enumerate(['Một.\n\n“Hai!”', 'Ba bốn.', 'Năm sáu bảy.'], 1):
        (sources / f'{index:03d}.txt').write_text(text, encoding='utf-8')
    paths = [str(p) for p in sorted(sources.glob('*.txt'))]
    plain = actions.create_book(tmp_path / 'a', paths, 'X', 'fast', '')
    split = actions.create_book(tmp_path / 'b', paths, 'X', 'fast', '')
    db = ProjectDB(split / 'project.sqlite3')
    ids = [c['id'] for c in db.list_chapters()]
    bv.organize(split, [{'id': 1, 'number': 1, 'title': 'A', 'chapters': ids[:1]}, {'id': 2, 'number': 2, 'title': 'B', 'chapters': ids[1:]}])
    rows = lambda root: [(c['id'], c['chapter_index'], c['input_sha256'], load_and_segment_chapter(dict(c), 240, project_root=root))
                         for c in ProjectDB(root / 'project.sqlite3').list_chapters()]
    assert rows(plain) == rows(split)


def test_a_single_plain_volume_keeps_the_flat_format_and_the_lowest_version(tmp_path):
    book = importers.ImportedBook('One volume', chapters=[importers.Chapter('A', 'Mot.'), importers.Chapter('B', 'Hai.')])
    path = textbook.build(book, tmp_path / 'one.abook')
    with zipfile.ZipFile(path) as archive:
        raw = json.loads(archive.read('book.json'))
    assert 'volumes' not in raw and [c['id'] for c in raw['chapters']] == [1, 2]
    assert all('volumeId' not in c for c in raw['chapters'])
    assert raw['package']['version'] == 5, 'chương chỉ-chữ: phiên bản thấp nhất đủ chứa, không phải 6'
    with bookfile.BookFile(path) as reader:
        assert [v['id'] for v in bv.volumes_of(reader.book)] == [1]


def test_a_tree_in_an_older_version_is_refused(tmp_path):
    path = textbook.build(imported(), tmp_path / 'book.abook')
    older = tmp_path / 'older.abook'
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(older, 'w') as sink:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == 'book.json':
                book = json.loads(data)
                book['package']['version'] = 5
                data = json.dumps(book).encode()
            sink.writestr(info, data)
    with pytest.raises(bookfile.BookFileError, match='lạ'):
        bookfile.BookFile(older)


def test_txt_chapters_opened_by_a_volume_heading_start_a_new_volume_without_touching_the_text(tmp_path):
    folder = tmp_path / 'truyen'
    folder.mkdir()
    texts = ['Tập 1\n\nChương 1\n\nMây trôi.', 'Chương 2\n\nGió nổi.', 'Tập 2: Biển\n\nChương 1\n\nSóng vỗ.']
    for index, text in enumerate(texts, 1):
        (folder / f'{index:03d}.txt').write_text(text, encoding='utf-8')
    book = importers.import_text(folder)
    assert [(v.id, v.title) for v in book.volumes] == [(1, 'Tập 1'), (2, 'Tập 2: Biển')]
    assert [c.volume for c in book.chapters] == [1, 1, 2]
    assert [c.text for c in book.chapters] == [importers.import_text(folder).chapters[i].text for i in range(3)]
    assert 'Tập 2: Biển' in book.chapters[2].text, 'dòng tên quyển vẫn nằm trong chữ chương'
