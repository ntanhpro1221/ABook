"""Đối chiếu meter nhẹ trên gói sách, chỉ lưu số đo, không lưu chữ/audio."""
from __future__ import annotations

import io
import json
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def levels(x, rate):
    n = int(.02 * rate)
    x = x[:len(x) // n * n]
    frames = x.reshape(-1, n)
    energy = np.mean(frames ** 2, axis=1)
    keep = energy > max(1e-12, energy.max() * .001)
    if keep.sum() * .02 < 1:
        return None
    x = frames[keep].reshape(-1)[:8 * rate]
    k = x.copy()
    for filt in pyln.Meter(rate)._filters.values():
        k = filt.apply_filter(k)
    # Đáp ứng A tại các tần số FFT; mức tương đối, không giả làm phon ISO.
    f2 = np.fft.rfftfreq(len(x), 1 / rate) ** 2
    a = 12194.0 ** 2 * f2 ** 2 / np.maximum(
        (f2 + 20.6 ** 2) * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194.0 ** 2), 1e-30)
    ax = np.fft.irfft(np.fft.rfft(x) * a, n=len(x))
    return [float(10*np.log10(max(np.mean(y*y), 1e-15))) for y in (x, k, ax)]


def measure(path):
    started = time.perf_counter()
    voice = defaultdict(list)
    chapter = defaultdict(list)
    with zipfile.ZipFile(path) as z:
        b = json.loads(z.read('book.json'))
        cast = json.loads(z.read('cast.json'))
        def key(v):
            if isinstance(v, str):
                return v
            return str(v.get('preset') or v.get('key') or '') + str(v.get('tone') or '')
        narrator = key(cast['narrator']['voice'])
        mapping = {r['name']: key(r['voice']) for r in cast['characters'] + cast['extras']}
        mapping.update({'NARRATOR': narrator, '': narrator})
        candidates = defaultdict(list)
        chapters = {}
        for ch in b['chapters']:
            chapters[ch['index']] = ch
            for g in json.loads(z.read(ch['script']))['segments']:
                v = mapping.get(g['speaker'], narrator if g['kind'] in ('narration', 'heading') else None)
                if v and g.get('volume', 'normal') == 'normal' and g['end']-g['start'] >= 1.5:
                    candidates[v].append((ch['index'], g['stableId'], g['start'], g['end']))
        picks = set()
        rng = np.random.default_rng(7)
        for v, rows in sorted(candidates.items()):
            if len(rows) >= 12:
                for i in rng.permutation(len(rows))[:60]:
                    picks.add((v, *rows[i]))
        for index, ch in chapters.items():
            items = sorted(p for p in picks if p[1] == index)
            if not items:
                continue
            with z.open(ch['file']) as f:
                data = io.BytesIO(f.read())
            with sf.SoundFile(data) as f:
                rate = f.samplerate
                for v, _, sid, a, e in items:
                    f.seek(int(a*rate))
                    x = f.read(int((e-a)*rate), dtype='float64', always_2d=True).mean(axis=1)
                    q = levels(x, rate)
                    if q is not None:
                        voice[v].append(q)
                        chapter[index].append(q)
            print('chapter', index, 'seconds', round(time.perf_counter()-started, 1), flush=True)
    rows = []
    for i, (v, values) in enumerate(sorted(voice.items())):
        a = np.asarray(values)
        rows.append({'voice': i+1, 'n': len(a), 'means': a.mean(axis=0).tolist(),
                     'ci': np.percentile(a[np.random.default_rng(7).integers(0, len(a), (2000, len(a)))].mean(axis=1), [2.5,97.5], axis=0).tolist()})
    big = [r for r in rows if r['n'] >= 12]
    means = np.array([r['means'] for r in big])
    return {'meters': ['RMS', 'K', 'A'], 'seconds': time.perf_counter()-started,
            'spread': np.ptp(means, axis=0).tolist(), 'voices': rows,
            'chapters': {str(k): {'n':len(v), 'means': np.mean(v,axis=0).tolist()} for k,v in chapter.items()}}


if __name__ == '__main__':
    paths = [
        Path('D:/Novels/Audiobooks/sugaru_v6/abook/Your Story - theo chuong.abook'),
        Path('D:/Novels/LLM_Train/ys_redo/ch1fix/Pain, Pain, Go Away.abook'),
        *sorted(Path('D:/Novels/Audiobooks/sugaru_v6/abook/hoan_chinh/CUOI').glob('*.abook')),
    ]
    out = Path(__file__).resolve().parents[2] / 'chaplevel_meter_comparison.json'
    results = []
    for i, path in enumerate(paths):
        print('package', i, flush=True)
        results.append({'package': i, **measure(path)})
        out.write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8', newline='\n')
        print('RESULT', i, results[-1]['spread'], flush=True)
