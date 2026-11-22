"""A book whose casting was decided by an older tree keeps every speaker, voice, preset and seed under this tree.

Lead ruling 18-11 (castfix2): the NPC mark is a role, not part of a name, so casting must match the tree this branch left
(5c008b85a) row for row. `fixtures/locked_cast/base_5c008b85a.json` was produced by THAT tree from the book below (unaccented
"NPC <name>" labels, as in the gold of All you need is kill: "NPC Cha Rita", "NPC Anh trai"); regenerate only with the base
tree: `python -X utf8 tests/test_a_locked_cast_keeps_voices_and_seeds.py <out.json>` run with the base checkout's `_internal`
first on sys.path (the script imports `abook` from wherever it runs).

- casting the same book keeps speakers, characters and voice-sharing groups, with keys and seeds from the current registry;
- once casting is locked, the synthesis seed of every line (TTSCoordinator.generation_seed: stable id + voice key) is the base
  one, so audio already recorded keeps its key and nothing is re-recorded. The compressed SQLite fixture exercises the
  actual pipeline resume branch with trusted gold labels and a voice/gender carried from the previous part.
"""
from __future__ import annotations

import json
import gzip
import hashlib
import shutil
import sys
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "locked_cast" / "base_5c008b85a.json"
LOCKED = FIXTURE.parent / "base_locked_5c008b85a"

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


def build(root: Path, *, authoritative: bool = False, previous=None, finalize: bool = True):
    from abook.config import build_settings
    from abook.database import ProjectDB

    db = ProjectDB(root / "locked.sqlite3")
    db.initialize_book(title="Book", project_root=root, settings={}, settings_hash="settings", input_manifest_hash="manifest")
    for number in (1, 2):
        chapter_id = db.ensure_chapters([{"chapter_index": number, "title": f"00{number}", "input_path": root / f"{number}.txt",
                                          "input_sha256": f"source-{number}", "input_size": 1, "output_mp3": root / f"{number}.mp3"}])[0]
        db.replace_chapter_segments(chapter_id, [
            {"stable_id": f"c{number}s{seq}", "seq": seq, "text": text, "text_sha256": f"text-{number}-{seq}", "kind_hint": kind, "kind": kind,
             "speaker": speaker, "gender": ("unknown" if previous is not None and speaker == "Rita" else gender or "unknown"),
             "confidence": 0.95, "status": "analyzed"}
            for seq, (_chapter, kind, speaker, gender, text) in enumerate((row for row in LINES if row[0] == number), 1)])
    from abook.character_registry import build_registry_and_cast

    if previous is not None:
        from abook.continuation import seed_casting

        with previous.connect() as connection:
            seed_casting(connection, db, " ".join(row[-1] for row in LINES) + " Rita Keiji Cha Rita Anh trai Em trai", {})
    if authoritative:
        from abook.speaker_labels import install

        labels = {f"c{number}s{seq}": {"kind": kind, "speaker": speaker}
                  for number in (1, 2)
                  for seq, (_chapter, kind, speaker, _gender, _text) in enumerate((row for row in LINES if row[0] == number), 1)}
        install(db, labels, {})
    build_registry_and_cast(db, build_settings(), lambda _message: None)
    if finalize:
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


def previous_part(root: Path):
    """Choose a different valid female preset so that ignoring a carried voice cannot pass by chance."""
    from abook.character_registry import character_preset_allowed, voice_profile_spec
    from abook.voice_catalog import VIENEU_PRESETS

    db = build(root)
    rita = next(row for row in db.list_characters() if row["canonical_name"] == "RITA")
    current = next(line["preset"] for line in snapshot(db)["lines"] if line["speaker"] == "Rita")
    selected = next(preset for preset in VIENEU_PRESETS if preset["gender"] == "female"
                    and preset["name"] != current and character_preset_allowed(preset["name"], {"Đức Trí"}))
    spec = voice_profile_spec(selected)
    profile = db.upsert_voice_profile(spec)
    db.set_voice_for_character_segments(int(rita["id"]), profile)
    db.set_locked_character_voice("RITA", spec["voice_key"])
    return db


def test_casting_matches_the_base_tree_row_for_row(tmp_path: Path) -> None:
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    current = snapshot(build(tmp_path))

    def partition(data: dict) -> dict:
        # Compare who shares a voice, independent of registry versions or the catalog's preset ordering.
        groups: dict[str, str] = {}
        return {"characters": data["characters"], "lines": [
            {"line": line["line"], "speaker": line["speaker"],
             "voiceGroup": groups.setdefault(line["voiceKey"], line["line"])} for line in data["lines"]]}

    assert partition(current) == partition(base["snapshot"])
    from abook.io_utils import stable_int
    from abook.voice_balance import engine_version, voice_key

    for line in current["lines"]:
        key = "narrator" if line["speaker"] == "NARRATOR" else voice_key("vieneu", engine_version("vieneu"), line["preset"])
        assert line["voiceKey"] == key
        assert line["profileSeed"] == stable_int(f"voice::{key}")
        assert line["seed"] == stable_int(f"segment::{line['line']}::{key}::")
    assert "NPC CHA RITA" not in base["snapshot"]["characters"], "cây gốc bỏ dấu NPC khỏi tên: phép so có nghĩa"


def test_a_locked_book_keeps_the_synthesis_seed_of_every_line(tmp_path: Path, monkeypatch) -> None:
    from abook.database import ProjectDB
    from abook.speaker_labels import load
    from abook.tts import TTSCoordinator
    from tests.test_speaker_pass_pipeline import _pipeline, _Stop

    # This SQLite was cast and finalized by 5c008b85a, with trusted labels and a previous-part cast.
    raw = gzip.decompress(LOCKED.with_suffix(".sqlite3.gz").read_bytes())
    expected = json.loads(LOCKED.with_suffix(".json").read_text(encoding="utf-8"))
    assert hashlib.sha256(raw).hexdigest() == expected["sha256"]
    (tmp_path / "locked.sqlite3").write_bytes(raw)
    shutil.copyfile(LOCKED.with_suffix(".speaker_labels.json"), tmp_path / "speaker_labels.json")
    db = ProjectDB(tmp_path / "locked.sqlite3")
    assert db.casting_is_finalized()
    before = snapshot(db)
    assert before == expected["snapshot"]

    def cast_rows():
        with db.connect() as connection:
            return {table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
                    for table in ("segments", "characters", "voice_profiles")}

    rows_before = cast_rows()
    labels = load(db)
    assert labels.labels
    assert all(labels.allows(row, str(row["speaker"])) for row in db.list_segments())
    assert not labels.allows(db.list_segments()[3], "Rita"), "the NPC gold label remains authoritative after reopening"

    # Run the real resume branch with the base DB; only model/TTS boundaries are fakes.
    pipeline = _pipeline(monkeypatch, finalized=True, pending=False)
    pipeline.db = db
    from abook import pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "build_registry_and_cast", lambda *_a, **_kw: pytest.fail("Locked resume must not recast"))
    pipeline._run_speaker_pass = lambda *_a: pytest.fail("Locked resume must not rerun speaker attribution")
    with pytest.raises(_Stop):
        pipeline.run(recovery_already_run=True)
    assert db.casting_is_finalized()
    assert snapshot(ProjectDB(db.path)) == before
    assert cast_rows() == rows_before
    coordinator = TTSCoordinator.__new__(TTSCoordinator)  # chỉ phép tính hạt giống, không nạp máy đọc
    coordinator.db = db
    base = {line["line"]: line for line in expected["snapshot"]["lines"]}
    for row in db.list_segments():
        assert coordinator.generation_seed(row) == base[str(row["stable_id"])]["seed"], row["stable_id"]


def test_gold_labels_and_the_previous_parts_gender_and_voice_survive_casting(tmp_path: Path) -> None:
    from abook.speaker_labels import load
    from abook.io_utils import stable_int

    previous = previous_part(tmp_path / "part1")
    db = build(tmp_path / "part2", authoritative=True, previous=previous)
    prior = {line["speaker"]: line for line in snapshot(previous)["lines"]}
    for line in snapshot(db)["lines"]:
        assert line["voiceKey"] == prior[line["speaker"]]["voiceKey"]
        assert line["profileSeed"] == prior[line["speaker"]]["profileSeed"]
        assert line["seed"] == stable_int(f"segment::{line['line']}::{prior[line['speaker']]['voiceKey']}::")
    rita = next(row for row in db.list_characters() if row["canonical_name"] == "RITA")
    assert rita["gender"] == "female"
    assert not rita["locked"], "known gender came from the previous part, rather than a listener gender pin"
    from abook.character_registry import canonical_key

    assert db.locked_character_voices()[canonical_key("Rita")] == prior["Rita"]["voiceKey"]
    assert all(row["gender"] == "unknown" for row in db.list_segments() if row["speaker"] == "Rita")
    assert all(load(db).allows(row, str(row["speaker"])) for row in db.list_segments())


if __name__ == "__main__":  # chỉ chạy bằng cây gốc để làm fixture (xem docstring)
    import abook
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        if len(sys.argv) > 2 and sys.argv[2] == "--locked":
            source_tree = Path(abook.__file__).resolve().parents[2]
            source_commit = subprocess.run(["git", "-C", str(source_tree), "rev-parse", "HEAD"], capture_output=True,
                                           text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
            archived_base = json.loads((source_tree / "base_source.json").read_text(encoding="utf-8"))["commit"] \
                if (source_tree / "base_source.json").is_file() else ""
            assert (source_commit or archived_base).startswith("5c008b85a"), "Generate locked fixture with the base tree only"
            previous = previous_part(Path(folder) / "previous")
            db = build(Path(folder) / "locked", authoritative=True, previous=previous)
            data = snapshot(db)
            with db.connect() as connection:
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            raw = db.path.read_bytes()
            output = Path(sys.argv[1])
            output.with_suffix(".sqlite3.gz").write_bytes(gzip.compress(raw, mtime=0))
            shutil.copyfile(db.path.parent / "speaker_labels.json", output.with_suffix(".speaker_labels.json"))
            output.with_suffix(".json").write_text(json.dumps({"tree": "5c008b85a", "sha256": hashlib.sha256(raw).hexdigest(),
                "snapshot": data}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            raise SystemExit(0)
        data = snapshot(build(Path(folder)))
    tree = Path(abook.__file__).resolve().parents[2]
    commit = subprocess.run(["git", "-C", str(tree), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    Path(sys.argv[1]).write_text(json.dumps({"tree": commit, "snapshot": data}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
