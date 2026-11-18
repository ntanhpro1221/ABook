"""A book whose casting was decided by an older tree keeps every speaker, voice, preset and seed under this tree.

Lead ruling 18-11 (castfix2): the NPC mark is a role, not part of a name, so casting must match the tree this branch left
(5c008b85a) row for row. `fixtures/locked_cast/base_5c008b85a.json` was produced by THAT tree from the book below (unaccented
"NPC <name>" labels, as in the gold of All you need is kill: "NPC Cha Rita", "NPC Anh trai"); regenerate only with the base
tree: `python -X utf8 tests/test_a_locked_cast_keeps_voices_and_seeds.py <out.json>` run with the base checkout's `_internal`
first on sys.path (the script imports `abook` from wherever it runs).

- casting the same book with this tree gives the same speakers, characters, voice keys, presets and synthesis seeds;
- once casting is locked, the synthesis seed of every line (TTSCoordinator.generation_seed: stable id + voice key) is the base
  one, so audio already recorded keeps its key and nothing is re-recorded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "locked_cast" / "base_5c008b85a.json"

LINES = [
    (1, "narration", "NARRATOR", "", "Sáng hôm ấy trời mưa."),
    (1, "dialogue", "Rita", "female", "“Dậy đi.”"),
    (1, "dialogue", "Keiji", "male", "“Ừ.”"),
    (1, "dialogue", "NPC Cha Rita", "male", "“Con về rồi à.”"),
    (1, "dialogue", "NPC Anh trai", "male", "“Đi thôi.”"),
    (1, "narration", "NARRATOR", "", "Gió thổi mạnh."),
    (2, "dialogue", "Rita", "female", "“Lại nữa.”"),
    (2, "dialogue", "NPC Cha Rita", "male", "“Cẩn thận.”"),
    (2, "dialogue", "NPC Em trai", "male", "“Chờ em với.”"),
    (2, "dialogue", "Keiji", "male", "“Được.”"),
    (2, "narration", "NARRATOR", "", "Họ đi tiếp."),
]


def build(root: Path):
    from abook.config import build_settings
    from abook.database import ProjectDB

    db = ProjectDB(root / "locked.sqlite3")
    db.initialize_book(title="Book", project_root=root, settings={}, settings_hash="settings", input_manifest_hash="manifest")
    for number in (1, 2):
        chapter_id = db.ensure_chapters([{"chapter_index": number, "title": f"00{number}", "input_path": root / f"{number}.txt",
                                          "input_sha256": f"source-{number}", "input_size": 1, "output_mp3": root / f"{number}.mp3"}])[0]
        db.replace_chapter_segments(chapter_id, [
            {"stable_id": f"c{number}s{seq}", "seq": seq, "text": text, "text_sha256": f"text-{number}-{seq}", "kind_hint": kind, "kind": kind,
             "speaker": speaker, "gender": gender or "unknown", "confidence": 0.95, "status": "analyzed"}
            for seq, (_chapter, kind, speaker, gender, text) in enumerate((row for row in LINES if row[0] == number), 1)])
    from abook.character_registry import build_registry_and_cast

    build_registry_and_cast(db, build_settings(), lambda _message: None)
    db.finalize_casting()
    return db


def snapshot(db) -> dict:
    from abook.io_utils import stable_int

    with db.connect() as connection:
        profiles = {int(row["id"]): row for row in connection.execute("SELECT id, voice_key, preset_name, seed FROM voice_profiles")}
        characters = sorted(str(row["canonical_name"]) for row in connection.execute("SELECT canonical_name FROM characters"))
    lines = []
    for row in db.list_segments():
        profile = profiles.get(int(row["voice_profile_id"])) if row["voice_profile_id"] is not None else None
        voice_key = str(profile["voice_key"]) if profile is not None else ""
        lines.append({"line": str(row["stable_id"]), "speaker": str(row["speaker"]), "voiceKey": voice_key,
                      "preset": str(profile["preset_name"]) if profile is not None else "",
                      "profileSeed": int(profile["seed"]) if profile is not None else None,
                      "seed": stable_int(f"segment::{row['stable_id']}::{voice_key}::")})
    return {"lines": lines, "characters": characters}


def test_casting_matches_the_base_tree_row_for_row(tmp_path: Path) -> None:
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert snapshot(build(tmp_path)) == base["snapshot"]
    assert "NPC CHA RITA" not in base["snapshot"]["characters"], "cây gốc bỏ dấu NPC khỏi tên: phép so có nghĩa"


def test_a_locked_book_keeps_the_synthesis_seed_of_every_line(tmp_path: Path) -> None:
    from abook.tts import TTSCoordinator

    db = build(tmp_path)
    assert db.casting_is_finalized()
    coordinator = TTSCoordinator.__new__(TTSCoordinator)  # chỉ phép tính hạt giống, không nạp máy đọc
    coordinator.db = db
    base = {line["line"]: line for line in json.loads(FIXTURE.read_text(encoding="utf-8"))["snapshot"]["lines"]}
    for row in db.list_segments():
        assert coordinator.generation_seed(row) == base[str(row["stable_id"])]["seed"], row["stable_id"]


if __name__ == "__main__":  # chỉ chạy bằng cây gốc để làm fixture (xem docstring)
    import abook
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        data = snapshot(build(Path(folder)))
    tree = Path(abook.__file__).resolve().parents[2]
    commit = subprocess.run(["git", "-C", str(tree), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    Path(sys.argv[1]).write_text(json.dumps({"tree": commit, "snapshot": data}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
