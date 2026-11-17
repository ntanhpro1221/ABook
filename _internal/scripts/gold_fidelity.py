"""Check a recorded book against aligned gold speakers, voices and cast roles.

Usage: python scripts/gold_fidelity.py PROJECT [--gold GOLD_DIRECTORY] [--json REPORT]

This read-only checker catches a canonical person split into two voice owners,
including reversed Japanese name order with inconsistent gender assignment.
Gold NNN.json files map project sequence numbers to kind/speaker records;
cast.json supplies cast, NPC and label-to-person maps. The hand18 layout uses
hand18_gold_replay/. Name matching ignores case, Japanese honorifics, NPC
prefixes and family/given-name order. Identity is learned from gold, never
from the book being checked, which would validate its own mistakes.

Exit 1 blocks book completion on speaker mismatch, multiple voices for one
gold person, voice/gold gender mismatch or an NPC promoted to the main cast.
Unknown gold gender is exempt; children use female voices by casting policy.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from abook.character_registry import (  # noqa: E402
    is_local_speaker, local_speaker_label, preset_fits_person, strip_japanese_honorific,
)
from abook.voice_catalog import VIENEU_PRESETS  # noqa: E402

RESERVED = {"NARRATOR", "UNKNOWN", ""}
NPC_PREFIX = re.compile(r"^\s*npc\s*[*:_-]*\s*", re.IGNORECASE)


def name_key(name: str) -> tuple[str, ...]:
    """Khoá so tên: bỏ tiền tố NPC/NPC_LOCAL, kính ngữ, hoa/thường, gạch dưới; chữ xếp lại (họ-tên đảo vẫn một khoá)."""
    text = local_speaker_label(name) if is_local_speaker(name) else str(name)
    text = unicodedata.normalize("NFC", NPC_PREFIX.sub("", text)).replace("_", " ")
    words = [strip_japanese_honorific(word) for word in text.split()]
    return tuple(sorted(word.casefold() for word in words if word))


class GoldCast:
    """Danh tính trong đáp án: mọi cách gọi -> một người, kèm giới và cờ NPC."""

    def __init__(self, cast: dict[str, Any]):
        self.people: dict[str, dict[str, Any]] = {}
        self.index: dict[tuple[str, ...], str] = {}
        for name, person in cast.get("cast", {}).items():
            self._add(name, str(person.get("gender") or "unknown"), str(person.get("age") or "unknown"), npc=False)
            for alias in person.get("aliases", []):
                self.index.setdefault(name_key(alias), self.canonical(name))
        for name, person in cast.get("npc", {}).items():
            self._add(name, str(person.get("gender") or "unknown"), str(person.get("age") or "unknown"), npc=True)
        for label, target in cast.get("map", {}).items():
            if str(target).upper() in RESERVED:
                continue
            self.index[name_key(label)] = self.resolve(target)

    @staticmethod
    def canonical(name: str) -> str:
        return " ".join(str(name).split()).upper()

    def _add(self, name: str, gender: str, age: str, *, npc: bool) -> None:
        person = self.canonical(name)
        self.people.setdefault(person, {"gender": gender, "age": age, "npc": npc})
        self.index.setdefault(name_key(name), person)

    def resolve(self, label: str) -> str:
        """Người trong đáp án của một nhãn; nhãn lạ thành chính nó (đáp án có thể có NPC một câu không khai trong cast)."""
        if self.canonical(label) in RESERVED:
            return "NARRATOR"
        found = self.index.get(name_key(label))
        if found is not None:
            return found
        person = self.canonical(label)
        self.people.setdefault(person, {"gender": "unknown", "age": "unknown", "npc": bool(NPC_PREFIX.match(str(label)))})
        self.index[name_key(label)] = person
        return person


def _connect(project: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{(project / 'project.sqlite3').as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _gold_chapters(gold: Path) -> list[Path]:
    return sorted(path for path in gold.glob("*.json") if re.fullmatch(r"\d+\.json", path.name))


def check(project: Path, gold: Path | None = None) -> dict[str, Any]:
    project = Path(project)
    gold = Path(gold) if gold else project / "hand18_gold_replay"
    raw_cast = json.loads((gold / "cast.json").read_text(encoding="utf-8-sig"))
    cast = GoldCast(raw_cast)
    first_person = raw_cast.get("narrator", {}) if isinstance(raw_cast.get("narrator"), dict) else {}
    gender_of_preset = {str(preset["name"]): str(preset.get("gender") or "") for preset in VIENEU_PRESETS}
    with _connect(project) as connection:
        chapters = [int(row["id"]) for row in connection.execute("SELECT id FROM chapters ORDER BY chapter_index, id")]
        voices = {int(row["id"]): str(row["preset_name"] or row["voice_key"] or row["id"])
                  for row in connection.execute("SELECT id, preset_name, voice_key FROM voice_profiles")}
        narrator_voices = {int(row["id"]) for row in connection.execute(
            "SELECT id FROM voice_profiles WHERE voice_key = 'narrator'")}
        segments = [dict(row) for row in connection.execute(
            "SELECT chapter_id, seq, kind, speaker, voice_profile_id FROM segments ORDER BY chapter_id, seq")]
    files = _gold_chapters(gold)
    if len(files) != len(chapters):
        raise SystemExit(f"Đáp án có {len(files)} chương, project có {len(chapters)} - không gióng được")
    answer = {chapter: json.loads(path.read_text(encoding="utf-8-sig")) for chapter, path in zip(chapters, files)}
    stem = {chapter: path.stem for chapter, path in zip(chapters, files)}

    mismatches: list[dict[str, Any]] = []
    voices_of: dict[str, Counter[str]] = defaultdict(Counter)
    app_names: dict[str, Counter[str]] = defaultdict(Counter)
    missing = 0
    for row in segments:
        label = answer[row["chapter_id"]].get(str(row["seq"]))
        if label is None:
            missing += 1
            continue
        want = "NARRATOR" if label["kind"] == "narration" else cast.resolve(str(label["speaker"]))
        speaker = str(row["speaker"] or "")
        got = "NARRATOR" if str(row["kind"]) == "narration" else cast.resolve(speaker)
        teller = str(first_person.get(stem[row["chapter_id"]]) or "")
        own_narrator_voice = (row["voice_profile_id"] is not None and int(row["voice_profile_id"]) in narrator_voices
                              and teller not in ("", "-") and cast.resolve(teller) == want == got)
        if want != "NARRATOR":
            app_names[want][speaker] += 1
            # Người kể ngôi thứ nhất của chương ("tôi") nghĩ bằng giọng người kể: một người, không phải tách giọng.
            if row["voice_profile_id"] is not None and not own_narrator_voice:
                voices_of[want][voices.get(int(row["voice_profile_id"]), str(row["voice_profile_id"]))] += 1
        if want != got:
            mismatches.append({"chapter": stem[row["chapter_id"]], "seq": int(row["seq"]), "gold": want,
                               "app": "NARRATOR" if got == "NARRATOR" else speaker, "app_kind": str(row["kind"])})

    splits = {person: dict(found) for person, found in voices_of.items() if len(found) > 1}
    wrong_gender = {}
    for person, found in voices_of.items():
        gender = cast.people.get(person, {}).get("gender", "unknown")
        age = cast.people.get(person, {}).get("age", "unknown")
        if gender not in ("male", "female"):
            continue
        # Trẻ con đọc bằng giọng nữ là luật cấp giọng (`casting_gender`), không phải sai giới.
        bad = {voice: count for voice, count in found.items()
               if gender_of_preset.get(voice) and not preset_fits_person(gender_of_preset[voice], gender, age)}
        if bad:
            wrong_gender[person] = {"gold": gender, "voices": bad}
    npc_main = _npc_in_main_cast(project, cast)
    by_pair = Counter((item["gold"], item["app"]) for item in mismatches)
    report = {
        "project": str(project), "gold": str(gold), "segments": len(segments), "unaligned": missing,
        "speaker_mismatches": len(mismatches),
        "mismatch_pairs": [{"gold": gold_name, "app": app_name, "lines": count}
                           for (gold_name, app_name), count in by_pair.most_common()],
        "voice_splits": splits, "wrong_gender": wrong_gender, "npc_in_main_cast": npc_main,
        "app_names": {person: dict(found) for person, found in app_names.items() if len(found) > 1},
        "mismatches": mismatches,
    }
    report["pass"] = not (mismatches or splits or wrong_gender or npc_main or missing)
    return report


def _npc_in_main_cast(project: Path, cast: GoldCast) -> list[str]:
    """Người đáp án ghi NPC mà tab Nhân vật (cast.json của app, cùng luật cho ba nền) xếp Vai chính TRÁI luật của app.

    Vai do `store.cast_role` quyết - đúng hàm app dùng khi xuất cast.json, với người ấy coi là NPC (nhãn "NPC"): NPC vài câu
    là vai phụ, nhưng NPC nói từ MAIN_ROLE_MAJOR_LINES câu ở từ MAIN_ROLE_MAJOR_CHAPTERS chương là vai chính ở cả app lẫn cổng."""
    try:
        from abook.webui import store
        view = store.cast(project)
        scenes_of, book_scenes, chapters_of = store.speaker_presence(project)
    except Exception as exc:  # noqa: BLE001 - project thiếu phần UI cần thì báo, không đoán
        return [f"(không đọc được dàn nhân vật: {exc})"]
    out = []
    for person in view.get("characters", []):
        name = str(person["name"])
        found = cast.resolve(name)
        if not cast.people.get(found, {}).get("npc"):
            continue
        role = store.cast_role("NPC", None, int(person.get("lines") or 0), scenes_of.get(name, 0), book_scenes,
                               chapters_of.get(name, 0))
        if role != "characters":
            out.append(f"{name} ({found})")
    return out


def summary(report: dict[str, Any]) -> str:
    lines = [f"{'PASS' if report['pass'] else 'FAIL'}  {report['project']}",
             f"  {report['segments']} câu | lệch người {report['speaker_mismatches']} | chưa gióng {report['unaligned']}"
             f" | tách giọng {len(report['voice_splits'])} | sai giới {len(report['wrong_gender'])}"
             f" | NPC thành vai chính {len(report['npc_in_main_cast'])}"]
    for pair in report["mismatch_pairs"][:15]:
        lines.append(f"    lệch: đáp án {pair['gold']} -> sách {pair['app']}: {pair['lines']} câu")
    for person, found in report["voice_splits"].items():
        lines.append(f"    tách giọng: {person}: {found}")
    for person, found in report["wrong_gender"].items():
        lines.append(f"    sai giới: {person} ({found['gold']}): {found['voices']}")
    for name in report["npc_in_main_cast"]:
        lines.append(f"    NPC thành vai chính: {name}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project", type=Path)
    parser.add_argument("--gold", type=Path)
    parser.add_argument("--json", type=Path, help="ghi báo cáo đầy đủ (mọi câu lệch) ra file này")
    args = parser.parse_args(argv)
    report = check(args.project, args.gold)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(summary(report))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
