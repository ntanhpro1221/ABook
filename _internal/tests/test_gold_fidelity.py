"""Gold fidelity rejects speaker drift, split voices, gender errors and main NPCs.

Cover the regression where reversed name order split one woman into two
people and assigned a male voice to the second owner. All fixtures are synthetic.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from abook.config import build_settings, settings_hash
from abook.database import ProjectDB
from abook.io_utils import sha256_file
from abook.models import ProjectPaths

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gold_fidelity.py"
_spec = importlib.util.spec_from_file_location("gold_fidelity", SCRIPT)
gold_fidelity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gold_fidelity)

# (loại, người nói đáp án, người nói trong sổ, giọng)
LINES = [
    ("narration", "NARRATOR", "NARRATOR", "narrator"),
    ("dialogue", "AYA HAJIKANO", "HAJIKANO AYA", "Ngọc Linh"),
    ("dialogue", "YUI HAJIKANO", "Yui Hajikano", "Trúc Ly"),
    ("dialogue", "AYA HAJIKANO", "HAJIKANO AYA", "Ngọc Linh"),
    ("dialogue", "NPC bác bảo vệ", "Npc Bác Bảo Vệ", "Xuân Vĩnh"),
    ("dialogue", "AYA HAJIKANO", "Aya-san", "Ngọc Linh"),
]
CAST = {
    "cast": {"AYA HAJIKANO": {"gender": "female", "age": "young", "aliases": ["Aya"]},
             "YUI HAJIKANO": {"gender": "female", "age": "teen", "aliases": ["Yui"]}},
    "npc": {"NPC BÁC BẢO VỆ": {"gender": "male", "age": "elderly"}},
    "map": {},
    "narrator": {"000": "-"},
}


def _book(tmp_path: Path, lines: list[tuple[str, str, str, str]], mapping: dict[str, str] | None = None) -> tuple[Path, Path]:
    paths = ProjectPaths.build(tmp_path / "project")
    settings = build_settings()
    db = ProjectDB(paths.db)
    db.initialize_book(title="T", project_root=paths.root, settings=settings, settings_hash=settings_hash(settings),
                       input_manifest_hash="manifest")
    source = paths.root / "sources" / "000.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("\n".join(f"Câu {index}." for index in range(len(lines))), encoding="utf-8")
    chapter = db.ensure_chapters([{"chapter_index": 1, "title": "000", "input_path": source, "input_sha256": sha256_file(source),
                                   "input_size": source.stat().st_size, "output_mp3": paths.chapters / "000.mp3"}])[0]
    db.replace_chapter_segments(chapter, [
        {"stable_id": f"s{seq}", "seq": seq, "text": f"Câu {seq}.", "text_sha256": f"sha-{seq}", "kind_hint": kind}
        for seq, (kind, _gold, _app, _voice) in enumerate(lines)])
    voices = {}
    for _kind, _gold, _app, voice in lines:
        if voice not in voices:
            voices[voice] = db.upsert_voice_profile({"voice_key": voice if voice == "narrator" else f"vieneu/{voice}",
                                                     "engine": "vieneu", "preset_name": None if voice == "narrator" else voice})
    with db.connect() as conn:
        for seq, (kind, _gold, app, voice) in enumerate(lines):
            conn.execute("UPDATE segments SET kind=?, speaker=?, voice_profile_id=?, status='verified' WHERE stable_id=?",
                         (kind, app, voices[voice], f"s{seq}"))
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / "cast.json").write_text(json.dumps({**CAST, "map": mapping or {}}, ensure_ascii=False), encoding="utf-8")
    (gold / "000.json").write_text(json.dumps({str(seq): {"kind": kind, "speaker": speaker}
                                               for seq, (kind, speaker, _app, _voice) in enumerate(lines)},
                                              ensure_ascii=False), encoding="utf-8")
    return paths.root, gold


def test_a_book_faithful_to_its_gold_passes(tmp_path: Path) -> None:
    project, gold = _book(tmp_path, LINES)
    report = gold_fidelity.check(project, gold)
    assert report["speaker_mismatches"] == 0, report["mismatches"]
    assert not report["voice_splits"] and not report["wrong_gender"], report
    assert report["npc_in_main_cast"] == [], "NPC hai câu một cảnh: vai phụ"
    assert report["pass"], gold_fidelity.summary(report)


def test_one_person_split_in_two_with_a_male_voice_fails(tmp_path: Path) -> None:
    lines = [*LINES, ("dialogue", "AYA HAJIKANO", "Aya", "Xuân Vĩnh"), ("dialogue", "AYA HAJIKANO", "Kenta", "Ngọc Linh")]
    project, gold = _book(tmp_path, lines)
    report = gold_fidelity.check(project, gold)
    assert not report["pass"]
    assert report["voice_splits"]["AYA HAJIKANO"] == {"Ngọc Linh": 4, "Xuân Vĩnh": 1}
    assert report["wrong_gender"]["AYA HAJIKANO"]["voices"] == {"Xuân Vĩnh": 1}
    assert [(item["gold"], item["app"]) for item in report["mismatches"]] == [("AYA HAJIKANO", "Kenta")], \
        "'Aya' là bí danh trong đáp án: cùng người, chỉ giọng là sai"


def test_the_names_key_ignores_order_case_and_honorifics_but_keeps_the_npc_mark() -> None:
    key = gold_fidelity.name_key
    assert key("HAJIKANO AYA") == key("Aya Hajikano") == key("Aya-san Hajikano")
    assert key("NPC bác bảo vệ") == key("Npc: Bác Bảo Vệ") == key("NPC_LOCAL::c00001::bác bảo vệ")
    assert key("NPC bác bảo vệ") != key("Bác Bảo Vệ"), "NPC X và X là hai người"
    assert key("Yui Hajikano") != key("Aya Hajikano")


def test_the_cli_exits_one_on_fail(tmp_path: Path) -> None:
    lines = [*LINES, ("dialogue", "YUI HAJIKANO", "HAJIKANO AYA", "Ngọc Linh")]
    project, gold = _book(tmp_path, lines)
    out = tmp_path / "report.json"
    assert gold_fidelity.main([str(project), "--gold", str(gold), "--json", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["speaker_mismatches"] == 1


def _set_record(project: Path, canonical: str, display: str, importance: str, mentions: int) -> None:
    with ProjectDB(ProjectPaths.build(project).db).connect() as conn:
        conn.execute("INSERT INTO characters(canonical_name,display_name,gender,age,personality,importance,"
                     "mention_count,confidence,locked,created_at,updated_at) VALUES(?,?,'male','elderly','',?,?,1,0,0,0)",
                     (canonical, display, importance, mentions))


def test_a_gold_npc_whose_prefix_was_dropped_upstream_is_a_speaker_mismatch(tmp_path: Path) -> None:
    """Bộ tiêm cũ bỏ tiền tố "NPC ": sách ghi một người có tên khác hẳn người đáp án - bắt được, không chấp nhận tay."""
    lines = [*LINES[:4], ("dialogue", "NPC bác bảo vệ", "Bác Bảo Vệ", "Xuân Vĩnh"), LINES[5]]
    project, gold = _book(tmp_path, lines)
    report = gold_fidelity.check(project, gold)
    assert [(item["gold"], item["app"]) for item in report["mismatches"]] == [("NPC BÁC BẢO VỆ", "Bác Bảo Vệ")]
    assert not report["pass"]


def test_a_gold_npc_promoted_to_the_main_cast_fails(tmp_path: Path) -> None:
    """Đáp án tự gọi nhãn trần là NPC (map) nhưng sổ của app xếp người ấy vai chính: cast.json sai, cổng chặn."""
    lines = [*LINES[:4], *[("dialogue", "NPC bác bảo vệ", "Bác Bảo Vệ", "Xuân Vĩnh")] * 3, LINES[5]]
    project, gold = _book(tmp_path, lines, mapping={"BÁC BẢO VỆ": "NPC BÁC BẢO VỆ"})
    _set_record(project, "BÁC BẢO VỆ", "Bác Bảo Vệ", "main", 40)
    report = gold_fidelity.check(project, gold)
    assert report["speaker_mismatches"] == 0, report["mismatches"]
    assert report["npc_in_main_cast"] == ["Bác Bảo Vệ (NPC BÁC BẢO VỆ)"], report["npc_in_main_cast"]
    assert not report["pass"]
