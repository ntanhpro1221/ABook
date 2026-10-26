"""Reproducible width review, isolated profile and copied fixture; never the owner's library."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.parse
import time
import statistics

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'build' / 'qtwide'
FIXTURE = OUT / 'fixture'
SOURCE = Path('D:/Novels/native_desk_proto/deskqt_fixture_a200')


def audit_shots2():
    """Validate the real PNG size and make 2x inspection crops of row ends/left edges."""
    from PIL import Image
    shots = OUT / 'shots2'
    zooms = OUT / 'zooms2'
    zooms.mkdir(exist_ok=True)
    manifest = {}
    sizes = {1024: (1024, 700), 1440: (1440, 900), 1920: (1920, 1080), 2560: (2560, 1440)}
    for path in sorted(shots.glob('*.png')):
        im = Image.open(path)
        manifest[path.name] = list(im.size)
        suffix = path.stem.split('_')[-1]
        if suffix.isdigit() and im.size != sizes[int(suffix)]:
            raise RuntimeError(f'{path.name}: expected {sizes[int(suffix)]}, got {im.size}')
    for theme in ('dark', 'light'):
        for width, left, right, bottom in [(1440, 272, 1400, 473), (1920, 396, 1756, 544), (2560, 716, 2076, 688)]:
            im = Image.open(shots / f'{theme}_book_{width}.png')
            # Disjoint strips show the common cover/title edge without a tall crop.
            canvas = Image.new('RGB', (276, 212), im.getpixel((left - 6, 120)))
            canvas.paste(im.crop((left - 6, 124, left + 180, 210)), (0, 0))
            canvas.paste(im.crop((left - 6, bottom - 22, left + 270, bottom + 100)), (0, 90))
            canvas.resize((552, 424)).save(zooms / f'{theme}_book_{width}_left_2x.png')
            im.crop((right - 170, 154, right + 8, 282)).resize((356, 256)).save(zooms / f'{theme}_book_{width}_ends_2x.png')
        im = Image.open(shots / f'{theme}_book_hover_1920.png')
        im.crop((798, 154, 1758, 282)).resize((1920, 256)).save(zooms / f'{theme}_current_hover_2x.png')
    (OUT / 'shots2_dimensions.json').write_bytes((json.dumps(manifest, indent=2) + '\n').encode())
    print(f'Validated {len(manifest)} shots; 2x crops in {zooms}', flush=True)


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    if not FIXTURE.exists():
        shutil.copytree(SOURCE, FIXTURE)
    if sys.argv[1] not in ('shots', 'shots2'):
        # Undo the extra chapter rows used by visual review before a new RAM run.
        for source in (SOURCE / 'library').rglob('book.json'):
            if json.loads(source.read_bytes()).get('title') == 'Chuyện Thử Nghe':
                shutil.copy2(source, FIXTURE / source.relative_to(SOURCE))
    prefs = json.loads((FIXTURE / 'prefs.json').read_bytes())
    prefs['libraryRoot'] = prefs['libraryRootSeen'] = str(FIXTURE / 'library')
    (FIXTURE / 'prefs.json').write_bytes((json.dumps(prefs) + '\n').encode())
    # Make benchmark/shot settings independent of the real desktop_qt.ini as well.
    local = OUT / 'profile'
    (local / 'ABook').mkdir(parents=True, exist_ok=True)
    return local


def main():
    if sys.argv[1] == 'audit2':
        audit_shots2()
        return 0
    local = prepare()
    os.environ['LOCALAPPDATA'] = str(local)
    # Book ids include their library path: a copied fixture has new ids.
    env = dict(os.environ, ABOOK_PREFERENCES=str(FIXTURE / 'prefs.json'))
    p = subprocess.Popen(['D:/Novels/ABook/_internal/runtime/.venv/Scripts/pythonw.exe', '-X', 'utf8', '-m', 'abook.webui.host', '--version', 'fixture'],
                         cwd=str(HERE.parent), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        while True:
            line = p.stdout.readline()
            if not line:
                raise RuntimeError(p.stderr.read().decode('utf-8'))
            ready = json.loads(line).get('ready')
            if ready:
                break
        u = urllib.parse.urlsplit(ready)
        token = urllib.parse.parse_qs(u.query)['t'][0]
        req = urllib.request.Request(f'{u.scheme}://{u.netloc}/api/listen/library', headers={'X-Ebook-Token': token})
        books = json.load(urllib.request.urlopen(req))
        (OUT / 'library.json').write_bytes(json.dumps(books, ensure_ascii=False, indent=2).encode())
        ids = {k: next(b['id'] for b in books if b['title'] == title)
               for k, title in [('a', 'Chuyện Thử Nghe'), ('b', 'Sách Không Mốc'), ('c', 'Giọng Cũ')]}
        (FIXTURE / 'audio_books.json').write_bytes(json.dumps(ids).encode())
    finally:
        p.stdin.write(b'{"quit":true}\n')
        p.stdin.flush()
        p.wait(10)
    if sys.argv[1] == 'measure':
        name = sys.argv[2]
        (local / 'ABook' / 'desktop_qt.ini').write_bytes(b'[General]\nthemeMode=dark\nsidebarExpanded=1\n')
        return subprocess.call([sys.executable, '-X', 'utf8', str(HERE / 'tools/measure.py'),
                                '--fixture', str(FIXTURE), '--scenario', 'player', '--runs', '3',
                                '--attempts', '4', '--topmost', '--allow-low-refresh', '--out', str(OUT / (name + '.json'))])
    if sys.argv[1] == 'idle':
        # Use measure.py's private-byte sampler on the Book page itself as well.
        import measure
        import shot
        name = sys.argv[2]
        exe = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else HERE / 'dist/ABookDesk.exe'
        env.update(ABOOK_HOST_PYTHON='D:/Novels/ABook/_internal/runtime/.venv/Scripts/pythonw.exe',
                   ABOOK_HOST_APP=str(HERE.parent), ABOOK_MUTE='1', QT_SCREEN_SCALE_FACTORS='1',
                   QT_ENABLE_HIGHDPI_SCALING='0', QT_SCALE_FACTOR='1',
                   PATH='D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64/bin;' + env['PATH'])
        samples = []
        for i in range(3):
            (FIXTURE / 'listening.json').write_bytes((FIXTURE / 'listening.clean.json').read_bytes())
            (local / 'ABook/desktop_qt.ini').write_bytes(b'[General]\nthemeMode=dark\nsidebarExpanded=1\n')
            app = subprocess.Popen([str(exe)], env=env, cwd=str(exe.parent))
            h = None
            handle = None
            try:
                for _ in range(100):
                    h = shot.find_window(app.pid)
                    if h: break
                    time.sleep(.1)
                if h is None: raise RuntimeError('no window')
                shot.u.SetWindowPos(h, __import__('ctypes').c_void_p(-1), 20, 20, 1920, 1080, 0x10)
                client, outer = shot.wt.RECT(), shot.wt.RECT()
                shot.u.GetClientRect(h, __import__('ctypes').byref(client))
                shot.u.GetWindowRect(h, __import__('ctypes').byref(outer))
                shot.u.SetWindowPos(h, 0, 0, 0, 1920 + outer.right - outer.left - client.right,
                                   1080 + outer.bottom - outer.top - client.bottom, 0x16)
                time.sleep(4)
                # Selection works independently of DPI and the grid's column count.
                for key in ['home', 'right', 'right', 'enter']:
                    shot.key(h, key)
                time.sleep(3)
                shot.grab(h).save(OUT / f'{name}_book_idle_{i}.png')
                handle = measure.k32.OpenProcess(0x0410, False, app.pid)
                readings = []
                for _ in range(12):
                    readings.append(measure.private_mb(handle))
                    time.sleep(.25)
                samples.append(statistics.median(readings))
            finally:
                if handle: measure.k32.CloseHandle(handle)
                if h: shot.u.PostMessageW(h, 0x10, 0, 0)
                app.wait(10)
        result = {'scenario': 'book_page_idle', 'window': [1920, 1080], 'scale': 1,
                  'private_mb': samples, 'median_mb': statistics.median(samples)}
        (OUT / f'{name}_book_idle.json').write_bytes((json.dumps(result, indent=2) + '\n').encode())
        print(json.dumps(result, indent=2), flush=True)
    if sys.argv[1] in ('shots', 'shots2'):
        review2 = sys.argv[1] == 'shots2'
        shot_out = OUT / ('shots2' if review2 else 'shots')
        sizes = [(1024, 700), (1440, 900), (1920, 1080)]
        book_sizes = sizes + ([(2560, 1440)] if review2 else [])
        # Repeat the first fixture chapter as visible sample rows, only in our copy.
        for path in (FIXTURE / 'library').rglob('book.json'):
            book = json.loads(path.read_bytes())
            if book.get('title') != 'Chuyện Thử Nghe':
                continue
            book['chapters'] = book['chapters'][:4]
            for i in range(5, 25):
                chapter = dict(book['chapters'][0], id=i, index=i, title=f'Chương {i}',
                               subtitle=f'Con đường bên sông · Phần {i}', fullTitle=f'Chương {i} · Con đường bên sông')
                book['chapters'].append(chapter)
            book['chaptersTotal'] = book['chaptersAvailable'] = 24
            path.write_bytes(json.dumps(book, ensure_ascii=False).encode())
        for theme in ['dark', 'light']:
            (FIXTURE / 'listening.json').write_bytes((FIXTURE / 'listening.clean.json').read_bytes())
            (local / 'ABook/desktop_qt.ini').write_bytes(f'[General]\nthemeMode={theme}\nsidebarExpanded=1\n'.encode())
            steps = []
            for width, height in book_sizes:
                steps += [f'client={width},{height}', 'wait=1', f'shot={theme}_library_{width}']
            # Editing the synthetic book makes it the first item (updatedAt sort).
            steps += ['client=1024,700', 'wait=.5', 'click=340,260', 'wait=1']
            for width, height in book_sizes:
                steps += [f'client={width},{height}']
                if width == 1440:
                    steps += ['wait=.06', f'shot={theme}_book_transition']
                steps += ['wait=.6', f'shot={theme}_book_{width}']
            steps += ['scroll=1500,400,-1800', 'wait=.5', f'shot={theme}_book_scrolled',
                      'scroll=1500,400,4800', 'wait=.5']
            steps += ['client=1024,700', 'wait=.6', 'click=440,192', 'wait=1', 'key=space',
                      'wait=.5', f'shot={theme}_book_bar_1024']
            if review2:
                steps += ['click=500,610', 'wait=.5', 'client=1920,1080', 'wait=.6',
                          f'shot={theme}_book_current_1920', 'hover=1690,230', 'wait=.1', 'hover=1700,242', 'wait=.3',
                          f'shot={theme}_book_hover_1920', 'unhover', 'client=1024,700', 'wait=.6']
            steps += ['click=400,660', 'wait=1']
            for width, height in [(1024, 700), (1440, 900), (1920, 1080)]:
                steps += [f'client={width},{height}', 'wait=1', f'shot={theme}_now_{width}']
            steps += ['click=28,20', 'wait=.7', f'shot={theme}_now_collapsed', 'key=esc', 'wait=.7',
                      f'shot={theme}_book_collapsed', 'click=28,20', 'wait=.5', 'click=70,1044', 'wait=.6']
            for width, height in [(1024, 700), (1440, 900), (1920, 1080)]:
                steps += [f'client={width},{height}', 'wait=.6', f'shot={theme}_settings_{width}']
            steps += ['click=70,112', 'wait=.6', f'shot={theme}_studio_1920']
            cmd = [sys.executable, '-X', 'utf8', str(HERE / 'tools/shot.py'), str(HERE / 'dist/ABookDesk.exe'), str(shot_out)]
            for key, value in dict(ABOOK_PREFERENCES=str(FIXTURE / 'prefs.json'),
                                  ABOOK_HOST_PYTHON='D:/Novels/ABook/_internal/runtime/.venv/Scripts/pythonw.exe',
                                  ABOOK_HOST_APP=str(HERE.parent), LOCALAPPDATA=str(local),
                                  ABOOK_MUTE='1', QT_ENABLE_HIGHDPI_SCALING='0').items():
                cmd += ['--env', f'{key}={value}']
            result = subprocess.call(cmd + ['wait=3'] + steps)
            if result:
                return result
        if review2:
            audit_shots2()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
