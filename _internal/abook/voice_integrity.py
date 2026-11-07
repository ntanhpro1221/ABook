"""Read-only voice checks before exporting a project's recorded chapters.

Checks attribution/casting separately from the voice recorded in signal provenance.
No model, audio regeneration, database initialization, or schema changes are used.
An optional acoustic probe receives each row and its expected profile; it must return
checksum-bound evidence with status pass/review/fail (never a guessed speaker name).
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from . import teller_voice
from .database import thought_reads_as_narrator

AcousticProbe = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


class VoiceIntegrityError(ValueError):
    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        examples = "; ".join(f"{i['stable_id']}: {i['code']}" for i in report['issues'][:8])
        super().__init__(f"Giọng đọc chưa khớp ({len(report['issues'])} lỗi): {examples}. Kiểm tra người nói/giọng và thu lại trước khi xuất.")


def _signal_voices(signal: dict[str, Any], location: str = 'signal') -> list[tuple[str, Any]]:
    result = [(location, signal.get('voice_profile_id'))]
    for key in ('split_parts', 'parts'):
        parts = signal.get(key) or []
        if not isinstance(parts, list):
            raise ValueError('split provenance must be a list')
        for index, part in enumerate(parts):
            if not isinstance(part, dict):
                raise ValueError('split provenance must contain objects')
            result.extend(_signal_voices(part, f'{location}.{key}[{index}]'))
    return result


def audit(project_root: Path | str, *, chapter_ids: set[int] | None = None,
          acoustic_probe: AcousticProbe | None = None) -> dict[str, Any]:
    from .voice_catalog import engine_voice, preset_by_name
    from .webui import store

    root = Path(project_root)
    issues: list[dict[str, Any]] = []
    identities = []
    checked = 0
    with closing(store.connect(root)) as conn:
        book = conn.execute('SELECT settings_json FROM book WHERE id=1').fetchone()
        settings = json.loads(book['settings_json'])
        tellers = teller_voice.tellers_of(root, settings, conn)
        record = teller_voice.read(root)
        chosen = teller_voice._narrator_chosen(conn, root)
        profiles = {int(r['id']): dict(r) for r in conn.execute('SELECT * FROM voice_profiles')}
        characters = {int(r['id']): dict(r) for r in conn.execute('SELECT * FROM characters')}
        base = next((r for r in profiles.values() if r['voice_key'] == 'narrator'), None)
        all_rows = [dict(r) for r in conn.execute('SELECT * FROM segments ORDER BY chapter_id,seq')]
        own: dict[int, Counter[int]] = {}
        for row in all_rows:
            if row['speaker'].upper() != 'NARRATOR' and row['voice_profile_id'] is not None:
                own.setdefault(row['canonical_character_id'], Counter())[int(row['voice_profile_id'])] += 1
        targets = {}

        def voice_gender(profile: dict[str, Any] | None) -> str:
            if profile is None:
                return ''
            name = str(profile['preset_name'])
            voice = engine_voice(name, profile['engine'])
            if voice is not None:
                return str(voice['gender'])
            try:
                return str(preset_by_name(name)['gender'])
            except ValueError:
                return ''

        for row in all_rows:
            if chapter_ids is not None and int(row['chapter_id']) not in chapter_ids:
                continue
            # Text-only chapters have no voice to certify. A packaged recorded chapter
            # checks every row, including a pending retake whose old MP3 still exists.
            if chapter_ids is None and not row['wav_sha256']:
                continue
            checked += 1
            actual = profiles.get(row['voice_profile_id'])
            character = characters.get(row['canonical_character_id'])
            narrator_owned = row['speaker'].upper() == 'NARRATOR' or thought_reads_as_narrator(
                row['kind'], row['speaker'], row['voice_profile_id'])
            expected = base if narrator_owned else actual
            if character and not narrator_owned:
                locked = character['locked_voice_key']
                if locked:
                    expected = next((p for p in profiles.values() if p['voice_key'] == locked), None)
                elif row['canonical_character_id'] in own:
                    expected = profiles[own[row['canonical_character_id']].most_common(1)[0][0]]
            name = tellers.row_narrator(row)
            if name not in targets:
                targets[name] = teller_voice._teller_target(conn, name, int(base['id'])) if name and base else None
            target = targets[name]
            # A named listener speaker choice is already represented by the row's
            # owner. A text-edit wish cannot exempt an incorrect narrator voice.
            if target and not chosen:
                base_gender = voice_gender(base)
                selected = teller_voice.chapter_voice_selected(
                    tellers, row, record['mode'], base_gender, teller_voice.teller_gender(conn, name))
                if narrator_owned and selected:
                    expected = profiles.get(target[1])

            def issue(code: str, **evidence: Any) -> None:
                issues.append(dict(code=code, chapter=int(row['chapter_id']), stable_id=row['stable_id'],
                                   voice_current=actual['preset_name'] if actual else None,
                                   voice_correct=expected['preset_name'] if expected else None, **evidence))

            if expected is None or actual is None:
                issue('VOICE_PROFILE_MISSING')
            elif int(actual['id']) != int(expected['id']):
                issue('VOICE_OWNER_MISMATCH', expected_profile_id=expected['id'], actual_profile_id=actual['id'])
            actual_gender = voice_gender(actual)
            if actual is not None and not actual_gender:
                issue('VOICE_PROFILE_UNKNOWN')
            gender = character['gender'] if character and not narrator_owned else ''
            if not gender and not narrator_owned and row['kind'] in ('dialogue', 'thought'):
                gender = row['gender']
            if actual_gender and gender in ('male', 'female') and actual_gender != gender:
                issue('VOICE_GENDER_MISMATCH', speaker_gender=gender, preset_gender=actual_gender)
            if narrator_owned and row['kind'] == 'dialogue' and row['gender'] in ('male', 'female'):
                expected_gender = voice_gender(expected)
                if expected_gender and expected_gender != row['gender']:
                    issue('SPEAKER_GENDER_CONFLICT', speaker_gender=row['gender'],
                          expected_gender=expected_gender, needs_speaker_review=True)
            try:
                signal = json.loads(row['signal_json'] or '{}')
                if not isinstance(signal, dict):
                    raise ValueError('signal must be an object')
                provenance = _signal_voices(signal)
            except (ValueError, TypeError):
                provenance = [('signal', None)]
            for location, profile_id in provenance:
                if profile_id != row['voice_profile_id'] or profile_id is None:
                    issue('RECORDED_VOICE_MISMATCH', location=location, recorded_profile_id=profile_id,
                          row_profile_id=row['voice_profile_id'])
            if not row['wav_sha256']:
                issue('RECORDING_VOICE_UNPROVEN')
            if acoustic_probe is not None and expected is not None:
                evidence = acoustic_probe(row, expected)
                if (evidence.get('wav_sha256') != row['wav_sha256']
                    or evidence.get('expected_profile_id') != expected['id']
                    or evidence.get('status') not in ('pass', 'review', 'fail')):
                    issue('ACOUSTIC_EVIDENCE_INVALID')
                elif evidence['status'] != 'pass':
                    issue('ACOUSTIC_VOICE_REVIEW', acoustic=evidence)
            identities.append([row['stable_id'], row['voice_profile_id'], row['wav_sha256'],
                               row['speaker'], row['canonical_character_id'], row['signal_json']])
    return dict(version=1, checked=checked, status='fail' if issues else 'pass', issues=issues,
                source_sha256=hashlib.sha256(json.dumps(identities, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest())


def require(project_root: Path | str, *, chapter_ids: set[int],
            acoustic_probe: AcousticProbe | None = None) -> dict[str, Any]:
    report = audit(project_root, chapter_ids=chapter_ids, acoustic_probe=acoustic_probe)
    if report['issues']:
        raise VoiceIntegrityError(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Read-only pre-export voice audit')
    parser.add_argument('project', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = audit(args.project)
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8', newline='\n')
    else:
        print(text, end='')
    return int(report['status'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
