"""A+ lúc tạo sách (chủ sách 12-10): người dùng không chọn giọng dẫn + có người kể "tôi" -> máy chọn giọng cùng giới và nhớ đó là
lựa chọn của máy (`studio_narrator.json`); người dùng chọn giọng thì không bao giờ bị đè. Giới nói ngay từ đầu được ghim như người nghe ghim."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook import teller_voice
from abook.config import build_settings, settings_hash
from abook.webui import actions

TEXT = "Tôi bước vào lớp học.\n\n“Mai, cậu đến muộn rồi,” Bảo nói.\n\nTôi nhún vai rồi ngồi xuống.\n"


def _source(tmp_path: Path) -> Path:
    folder = tmp_path / "source"
    folder.mkdir(exist_ok=True)
    for index in (1, 2):
        (folder / f"{index:03d}.txt").write_text(TEXT, encoding="utf-8")
    return folder


def _settings(root: Path) -> dict:
    return json.loads((root / "book_settings.json").read_text(encoding="utf-8"))


def _gender(root: Path, name: str) -> tuple[str, int]:
    from abook.database import ProjectDB
    from abook.models import ProjectPaths

    with ProjectDB(ProjectPaths.build(root).db).connect() as conn:
        row = conn.execute("SELECT gender, locked FROM characters WHERE canonical_name=?", (name,)).fetchone()
    return (str(row[0]), int(row[1])) if row else ("", 0)


def test_no_chosen_voice_and_a_known_gender_sets_the_matching_narrator_and_marks_it_the_machines(tmp_path: Path) -> None:
    root = actions.create_book(tmp_path / "lib", [str(_source(tmp_path))], "Thử", "balanced", "", "Mai", first_person_gender="female")

    assert _settings(root)["voices"]["narrator_voice"] == "Ngọc Linh"
    assert teller_voice.read(root)["narratorAuto"] is True
    assert _gender(root, "MAI") == ("female", 1), "giới ghim như người nghe ghim"


def test_a_voice_the_user_chose_is_not_marked_and_not_replaced(tmp_path: Path) -> None:
    root = actions.create_book(tmp_path / "lib", [str(_source(tmp_path))], "Thử", "balanced", "Thái Sơn", "Mai", first_person_gender="female")

    assert _settings(root)["voices"]["narrator_voice"] == "Thái Sơn"
    assert teller_voice.read(root)["narratorAuto"] is False
    assert _gender(root, "MAI") == ("female", 1)


def test_an_unknown_gender_is_marked_for_the_machine_to_decide_after_casting(tmp_path: Path) -> None:
    root = actions.create_book(tmp_path / "lib", [str(_source(tmp_path))], "Thử", "balanced", "", "Mai")

    assert _settings(root)["voices"]["narrator_voice"] == build_settings("balanced")["voices"]["narrator_voice"]
    assert teller_voice.read(root)["narratorAuto"] is True
    assert _gender(root, "MAI") == ("", 0)


def test_a_third_person_book_is_unchanged(tmp_path: Path) -> None:
    root = actions.create_book(tmp_path / "lib", [str(_source(tmp_path))], "Thử", "balanced", "Phạm Tuyên")
    plain = actions.create_book(tmp_path / "lib2", [str(_source(tmp_path))], "Thử", "balanced", "")

    assert not (root / teller_voice.FILE_NAME).exists() and not (plain / teller_voice.FILE_NAME).exists()
    assert _settings(plain)["voices"].get("first_person_identity") is None


def test_the_gender_needs_a_name_and_a_real_gender(tmp_path: Path) -> None:
    source = [str(_source(tmp_path))]
    with pytest.raises(ValueError):
        actions.create_book(tmp_path / "lib", source, "Thử", "balanced", "", "", first_person_gender="female")
    with pytest.raises(ValueError):
        actions.create_book(tmp_path / "lib", source, "Thử", "balanced", "", "Mai", first_person_gender="robot")


def test_the_settings_hash_of_a_book_without_a_teller_does_not_depend_on_the_new_option() -> None:
    assert settings_hash(build_settings("balanced")) == settings_hash(build_settings("balanced", {"voices": {}}))


def _cli_create(tmp_path: Path, capsys, *extra: str) -> Path:
    from abook import cli

    out = tmp_path / f"out{len(list(tmp_path.glob('out*')))}"
    code = cli.main(["create", "--source-dir", str(_source(tmp_path)), "--range", "001..002", "--output-root", str(out), "--title", "T", "--json", *extra])
    assert code == cli.EXIT_OK
    return Path(json.loads(capsys.readouterr().out)["data"]["project_root"])


def test_the_command_line_marks_the_machines_choice_by_the_same_rule(tmp_path: Path, capsys) -> None:
    assert teller_voice.read(_cli_create(tmp_path, capsys, "--first-person", "Mai"))["narratorAuto"] is True
    assert teller_voice.read(_cli_create(tmp_path, capsys, "--first-person", "Mai", "--narrator", "Thái Sơn"))["narratorAuto"] is False
    assert not (_cli_create(tmp_path, capsys) / teller_voice.FILE_NAME).exists()
