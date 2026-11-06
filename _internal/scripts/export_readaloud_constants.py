"""Xuất cùng gain ISO của Turbo/Nano vào bảng Python và Kotlin từ bộ câu trung tính."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BEGIN = '# BEGIN ISO_GAIN_DB'
END = '# END ISO_GAIN_DB'


def build(folder: Path) -> dict[str, float]:
    protocol = json.loads((folder / 'protocol.json').read_text(encoding='utf8'))
    if protocol.get('stage') != 'clip_before_playback_gain':
        raise ValueError('Cần đo đúng clip sau bước bù câu ngắn, trước gain lúc phát')
    rows = {r['key']: r for p in (folder / 'keys').glob('*.json')
            for r in [json.loads(p.read_text(encoding='utf8'))]}
    if set(rows) != set(protocol['variants']):
        raise ValueError('Chưa đủ số đo của mọi giọng trong protocol')
    gains = {}
    for key, row in sorted(rows.items()):
        if row['n_takes'] != 80 or row['n_sentences'] != 40 or abs(row['verified_mean_phon'] - 73) > .002:
            raise ValueError(f'Số đo chưa hợp lệ: {key}')
        if row['gain_db'] > 0:
            raise ValueError(f'{key}: gain dương không thể áp ở phần tử audio')
        gains[key] = round(row['gain_db'], 7)
    return gains


def replace_block(text: str, begin: str, end: str, block: str, before: str) -> str:
    if begin in text:
        a = text.index(begin)
        b = text.index(end, a) + len(end)
        return text[:a] + block + text[b:]
    index = text.index(before)
    return text[:index] + block + '\n\n\n' + text[index:]


def export(folder: Path) -> None:
    gains = build(folder)
    py = ROOT / 'abook/readaloud/loudness.py'
    text = py.read_text(encoding='utf8')
    block = BEGIN + '\nISO_GAIN_DB = ' + json.dumps(gains, ensure_ascii=False, indent=4) + '\n' + END
    text = replace_block(text, BEGIN, END, block, 'def gain_db(')
    if 'return ISO_GAIN_DB[voice_id]' not in text:
        text = text.replace('    measured = MEASURED_LUFS.get(voice_id)',
                            '    if voice_id in ISO_GAIN_DB:\n        return ISO_GAIN_DB[voice_id]\n    measured = MEASURED_LUFS.get(voice_id)')
    py.write_text(text, encoding='utf8', newline='\n')
    kt = ROOT / 'mobile/android/app/src/main/java/vn/abook/player/readaloud/VoiceGain.kt'
    text = kt.read_text(encoding='utf8')
    begin, end = '// BEGIN ISO_GAIN_DB', '// END ISO_GAIN_DB'
    entries = '\n'.join(f'        {json.dumps(key,ensure_ascii=False)} to {gain},' for key, gain in gains.items())
    block = begin + '\n    private val isoGain = mapOf(\n' + entries + '\n    )\n    ' + end
    text = replace_block(text, begin, end, block, '    /** LUFS')
    text = re.sub(r'fun db\(voiceId: String\): Double = .*',
                  'fun db(voiceId: String): Double = isoGain[voiceId] ?: (measured[voiceId]?.let { Math.round(minOf(0.0, TARGET_LUFS - it) * 10) / 10.0 } ?: 0.0)', text)
    kt.write_text(text, encoding='utf8', newline='\n')
    print(len(gains), 'ISO playback gains exported identically')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    export(parser.parse_args().folder)
