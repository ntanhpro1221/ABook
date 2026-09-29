"""Làm tiếp cuốn này: phần kế tiếp của một truyện dài được gieo từ phần trước (ebook_reader/continuation.py).

Ghim các lời hứa người nghe thấy được: cùng một người giữ cùng một giọng qua các phần, cách đọc tên đã chọn không bị hỏi
lại, ghim giới/tuổi của người nghe đi theo, và phần trước chỉ bị đọc chứ không bị ghi.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from ebook_reader import continuation
from ebook_reader.database import LISTENER_PRONUNCIATION_SOURCE, ProjectDB

VOICE_A = "preset_thanh_binh_f100_p-04"
VOICE_B = "preset_ngoc_linh_f107_p+02"
VOICE_C = "preset_thai_son_f100_p+00"
TEXT = {
    "001.txt": "Selene nhìn Marcus. Theosbane im lặng.",
    "002.txt": "Marcus gọi Selene. Arthur Doyle đứng xa.",
    "003.txt": "Selene đi tiếp.",
    "004.txt": "Marcus trở lại.",
    "005.txt": "Hết.",
}


def _source_folder(root: Path) -> Path:
    folder = root / "truyen"
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in TEXT.items():
        (folder / name).write_text(text, encoding="utf-8")
    return folder


def _project(root: Path, files: list[Path], title: str = "Truyện") -> ProjectDB:
    root.mkdir(parents=True, exist_ok=True)
    db = ProjectDB(root / "project.sqlite3")
    db.initialize_book(title=title, project_root=root, settings={}, settings_hash="s", input_manifest_hash=root.name)
    db.ensure_chapters([
        {"chapter_index": index, "title": path.stem, "input_path": path, "input_sha256": path.stem,
         "input_size": 1, "output_mp3": root / f"{path.stem}.mp3"}
        for index, path in enumerate(files, start=1)
    ])
    return db


def _speak(db: ProjectDB, chapter: str, lines: list[tuple[str, str]], status: str = "done") -> None:
    """Chương `chapter` gồm các câu thoại (người nói, voice_key), như sau phân tích + phân vai."""
    with db.connect() as conn:
        chapter_id = int(conn.execute("SELECT id FROM chapters WHERE title=?", (chapter,)).fetchone()[0])
    prefix = f"{db.path.parent.name}_{chapter}"
    db.replace_chapter_segments(chapter_id, [
        {"stable_id": f"{prefix}_{seq}", "seq": seq, "paragraph_index": seq, "text": "…", "text_sha256": f"{prefix}{seq}",
         "kind_hint": "dialogue"}
        for seq in range(len(lines))
    ])
    for seq, (speaker, voice_key) in enumerate(lines):
        character_id = db.upsert_character(canonical_name=speaker, display_name=speaker.title(), gender="female"
                                           if voice_key == VOICE_B else "male", age="adult", personality="",
                                           mentions=0, importance="main", confidence=0.9)
        profile_id = db.upsert_voice_profile({"voice_key": voice_key, "engine": "vieneu", "preset_name": "Đức Trí",
                                              "description": "", "seed": 7, "pitch_semitones": 0, "formant_ratio": 1.0,
                                              "status": "ready"})
        with db.transaction() as conn:
            conn.execute("UPDATE segments SET kind='dialogue', speaker=?, canonical_character_id=?, voice_profile_id=?,"
                         " status=? WHERE stable_id=?", (speaker, character_id, profile_id, status, f"{prefix}_{seq}"))
            conn.execute("UPDATE characters SET mention_count = mention_count + 1 WHERE id=?", (character_id,))


@pytest.fixture()
def book(tmp_path: Path) -> dict[str, Path]:
    folder = _source_folder(tmp_path)
    library = tmp_path / "library"
    first = _project(library / "phan1", [folder / "001.txt", folder / "002.txt"])
    _speak(first, "001", [("SELENE", VOICE_B)] * 3 + [("MARCUS", VOICE_A)] * 2)
    _speak(first, "002", [("MARCUS", VOICE_A), ("SELENE", VOICE_B)])
    first.upsert_pronunciation(surface="Kaizer", normalized_surface="kaizer", spoken_form="Cai-dơ", confidence=0.8,
                               source="english_name_transliteration", locked=True)
    first.set_listener_pronunciation(surface="Theosbane", normalized_surface="theosbane", spoken_form="Thê-ô-ban",
                                     source=LISTENER_PRONUNCIATION_SOURCE)
    first.upsert_pronunciation(surface="Rare", normalized_surface="rare", spoken_form="Ra", confidence=0.3)
    first.lock_character_gender("ARTHUR DOYLE", "male")  # người nghe ghim, nhưng ông không nói câu nào
    first.lock_character_age("MARCUS", "young")
    first.accept_segment_audio(segment_stable_id="phan1_001_0", wav_sha256="ab" * 32, warning_code="LOW_SIMILARITY")
    second = _project(library / "phan2", [folder / "003.txt"])
    return {"folder": folder, "first": first.path.parent, "second": second.path.parent}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_next_part_keeps_every_voice_reading_and_pin(book: dict[str, Path]) -> None:
    first, second = book["first"], book["second"]
    before = _digest(first / "project.sqlite3")

    report = continuation.seed(first, second)

    target = ProjectDB(second / "project.sqlite3")
    assert target.locked_character_voices() == {"SELENE": VOICE_B, "MARCUS": VOICE_A}
    with target.connect() as conn:
        readings = {row["surface"]: (row["spoken_form"], row["source"]) for row in conn.execute(
            "SELECT surface, spoken_form, source FROM pronunciations WHERE locked=1")}
        known = {row["canonical_name"]: int(row["mention_count"]) for row in conn.execute(
            "SELECT canonical_name, mention_count FROM characters")}
        accepted = [tuple(row) for row in conn.execute(
            "SELECT segment_stable_id, warning_code FROM listener_audio_acceptances")]
        ledger = {row[0]: row[1] for row in conn.execute("SELECT canonical_name, dialogue_lines FROM character_exposure")}
    assert readings == {"Kaizer": ("Cai-dơ", "english_name_transliteration"),
                        "Theosbane": ("Thê-ô-ban", LISTENER_PRONUNCIATION_SOURCE)}, "cách đọc chưa khoá không mang"
    assert target.locked_character_genders().get("ARTHUR DOYLE") == "male", "ghim của người im lặng vẫn đi theo"
    assert target.locked_character_ages() == {"MARCUS": "young"}
    assert known["SELENE"] >= 4 and known["MARCUS"] >= 3, "prompt phần sau mở đầu bằng nhân vật đã biết"
    assert accepted == [("phan1_001_0", "LOW_SIMILARITY")]
    assert ledger == {"SELENE": 4, "MARCUS": 3}
    assert report["voices"] == 2 and report["pronunciations"] == 2 and report["part"] == 2
    link = json.loads((second / continuation.LINK_FILE).read_text(encoding="utf-8"))
    assert link["previous"] == "phan1" and link["part"] == 2
    assert _digest(first / "project.sqlite3") == before, "phần trước chỉ được đọc"


def test_a_seed_that_fails_halfway_writes_nothing(book: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Một giao dịch cho cả lượt: hỏng ở bước cuối thì giọng và cách đọc đã "ghi" ở bước trước cũng không còn."""
    def broken(_source: sqlite3.Connection, _target: ProjectDB) -> int:
        raise RuntimeError("hỏng giữa chừng")

    monkeypatch.setattr(continuation, "seed_acceptances", broken)
    with pytest.raises(RuntimeError):
        continuation.seed(book["first"], book["second"])

    target = ProjectDB(book["second"] / "project.sqlite3")
    with target.connect() as conn:
        readings = conn.execute("SELECT COUNT(*) FROM pronunciations").fetchone()[0]
    assert target.locked_character_voices() == {} and readings == 0
    assert not (book["second"] / continuation.LINK_FILE).exists()


def test_seeding_twice_adds_nothing(book: dict[str, Path]) -> None:
    continuation.seed(book["first"], book["second"])
    again = continuation.seed(book["first"], book["second"])
    assert again["voices"] == 0 and again["pronunciations"] == 0 and again["acceptances"] == 0


def test_one_voice_for_two_people_stays_with_the_one_heard_most(tmp_path: Path) -> None:
    folder = _source_folder(tmp_path)
    first = _project(tmp_path / "library" / "phan1", [folder / "001.txt"])
    _speak(first, "001", [("SELENE", VOICE_A)] * 5 + [("MARCUS", VOICE_A)] * 2 + [("THEOSBANE", VOICE_C)])
    second = _project(tmp_path / "library" / "phan2", [folder / "002.txt"])

    continuation.seed(first.path.parent, second.path.parent)

    assert ProjectDB(second.path).locked_character_voices() == {"SELENE": VOICE_A, "THEOSBANE": VOICE_C}


def test_a_spelling_the_book_never_writes_joins_the_one_it_does(tmp_path: Path) -> None:
    """SELNE (0 lần trong sách) là SELENE viết sai: một người, một giọng - giọng của cách viết đúng."""
    folder = _source_folder(tmp_path)
    first = _project(tmp_path / "library" / "phan1", [folder / "001.txt"])
    _speak(first, "001", [("SELNE", VOICE_C)] * 4 + [("SELENE", VOICE_B)])
    second = _project(tmp_path / "library" / "phan2", [folder / "002.txt"])

    continuation.seed(first.path.parent, second.path.parent)

    assert ProjectDB(second.path).locked_character_voices() == {"SELENE": VOICE_B}


def test_an_analysed_project_is_not_seeded(book: dict[str, Path]) -> None:
    _speak(ProjectDB(book["second"] / "project.sqlite3"), "003", [("SELENE", VOICE_B)], status="analyzed")
    with pytest.raises(continuation.ContinuationError, match="đã phân tích 1 đoạn"):
        continuation.seed(book["first"], book["second"])
    assert not (book["second"] / continuation.LINK_FILE).exists()


def test_the_chain_knows_its_parts_and_what_comes_next(book: dict[str, Path]) -> None:
    folder = book["folder"]
    assert [path.name for path in continuation.next_chapters(book["first"])] == ["003.txt", "004.txt", "005.txt"]

    continuation.seed(book["first"], book["second"])

    assert continuation.chain_of(book["second"]) == [book["first"].resolve(), book["second"].resolve()]
    assert continuation.part_number(book["second"]) == 2
    assert continuation.next_chapters(book["second"]) == [(folder / "004.txt").resolve(), (folder / "005.txt").resolve()]
    assert continuation.continued_title("Truyện · Phần 2", 3) == "Truyện · Phần 3"
    assert continuation.continued_title("Truyện", 2) == "Truyện · Phần 2"
    assert continuation.continued_title("Truyện (phần 2)", 3) == "Truyện · Phần 3", "hậu tố kiểu cũ"


def test_a_redone_chapter_is_counted_once(book: dict[str, Path]) -> None:
    """Phần sau làm lại chương 002: sổ đếm bản của phần sau, không cộng chồng hai bản."""
    folder = book["folder"]
    third = _project(book["first"].parent / "phan2b", [folder / "002.txt", folder / "003.txt"])
    _speak(third, "002", [("SELENE", VOICE_B)] * 2)
    _speak(third, "003", [("MARCUS", VOICE_A)])
    (third.path.parent / continuation.LINK_FILE).write_text(json.dumps({"previous": "phan1", "part": 2}),
                                                            encoding="utf-8")

    exposure = continuation.book_exposure(continuation.chain_of(third.path.parent))

    # 001 của phần 1 (SELENE 3, MARCUS 2) + 002 của phần 2b (SELENE 2) + 003 (MARCUS 1).
    assert exposure == {"SELENE": (5, 2), "MARCUS": (3, 2)}


def test_the_carried_summary_counts_without_writing(book: dict[str, Path]) -> None:
    before = _digest(book["first"] / "project.sqlite3")
    assert continuation.carried_summary(book["first"]) == {
        "voices": 2, "pronunciations": 2, "listenerReadings": 1, "pins": 2, "aliases": 0,
    }
    assert _digest(book["first"] / "project.sqlite3") == before


def test_a_project_without_the_newer_tables_seeds_what_it_has(tmp_path: Path) -> None:
    """Dự án rất cũ (thiếu bảng) không làm hỏng lượt gieo: có gì mang nấy."""
    old = tmp_path / "library" / "cu"
    old.mkdir(parents=True)
    connection = sqlite3.connect(old / "project.sqlite3")
    connection.execute("CREATE TABLE chapters (id INTEGER PRIMARY KEY, title TEXT, input_path TEXT, chapter_index INT)")
    connection.commit()
    connection.close()
    folder = _source_folder(tmp_path)
    second = _project(tmp_path / "library" / "moi", [folder / "002.txt"])

    report = continuation.seed(old, second.path.parent)

    assert report["voices"] == 0 and report["pronunciations"] == 0 and report["known"] == 0


def test_the_cli_creates_the_next_part_already_seeded(book: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    from ebook_reader import cli

    folder = book["folder"]
    arguments = ["create", "--files", str(folder / "004.txt"), str(folder / "005.txt"), "--output-root",
                 str(book["first"].parent), "--title", "Truyện (phần 2)", "--seed-from", str(book["first"]), "--json"]

    assert cli.main([*arguments, "--dry-run"]) == cli.EXIT_OK
    preview = json.loads(capsys.readouterr().out)["data"]
    assert preview["seed_from"]["carries"]["voices"] == 2

    assert cli.main(arguments) == cli.EXIT_OK
    created = json.loads(capsys.readouterr().out)["data"]
    root = Path(created["project_root"])
    assert created["seeded"]["voices"] == 2 and created["seeded"]["part"] == 2
    assert ProjectDB(root / "project.sqlite3").locked_character_voices() == {"SELENE": VOICE_B, "MARCUS": VOICE_A}
    assert continuation.chain_of(root) == [book["first"].resolve(), root.resolve()]


def test_the_cli_refuses_a_seed_that_is_not_a_project(book: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    from ebook_reader import cli

    code = cli.main(["create", "--files", str(book["folder"] / "004.txt"), "--output-root", str(book["first"].parent),
                     "--seed-from", str(book["folder"]), "--json"])

    assert code == cli.EXIT_USAGE
    assert "not a project" in json.loads(capsys.readouterr().out)["error"]
