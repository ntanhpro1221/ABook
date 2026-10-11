"""Mở file dự án của CÙNG dự án đã có ở máy này (soát UX a25 T5): sửa trong xưởng của file - yêu cầu chờ dây chuyền
(`overrides.json`) và phán quyết "Cần nghe lại" (`reviews.json`) - được GỘP (webui/workshop_merge.py), không bị bỏ im lặng.

Luật gộp đáp chung với app Android (WorkshopMergeTest.kt) bằng tests/fixtures/book_edits/workshop_merge/<ca>.json:
{now, local, incoming, merged, report} - {tên file: nội dung} của máy này, của file, kết quả, và {merged, kept}."""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from abook import listener_overrides
from abook.webui import projectfile, store, workshop_merge
from abook.webui.library import book_id
from abook.webui.reviews import Reviews
from tests.test_project_file import _app, _project

CASES = Path(__file__).parent / "fixtures" / "book_edits" / "workshop_merge"


@pytest.mark.parametrize("case", sorted(path.stem for path in CASES.glob("*.json")))
def test_the_shared_merge_cases(case: str) -> None:
    data = json.loads((CASES / f"{case}.json").read_text(encoding="utf-8"))
    merged, report = workshop_merge.merge_files(data["local"], data["incoming"], data["now"])
    assert report == data["report"]
    assert merged == data["merged"]


def test_opening_the_file_of_a_project_edited_on_another_machine_merges_its_edits(tmp_path: Path) -> None:
    project = _project(tmp_path)
    with sqlite3.connect(project / store.DB_NAME) as db:
        db.execute("ALTER TABLE segments ADD COLUMN stable_id TEXT")
        db.execute("UPDATE segments SET stable_id = 's' || id")
    app = _app(tmp_path, project.parent)
    reviews = Reviews()
    # Máy kia: cùng dự án (chép nguyên), sửa thêm cách đọc Heidi, một phán quyết "Cần thu lại", và một cách đọc Rhine CŨ hơn máy này.
    other = tmp_path / "may_kia" / project.name
    shutil.copytree(project, other)
    listener_overrides.request_pronunciation(other, "Heidi", "Hai-đi", now=200.0)
    listener_overrides.request_pronunciation(other, "Rhine", "Rai-nơ", now=100.0)
    reviews.set(other, "s3", "redo", 1)
    packed = projectfile.pack(other, tmp_path / "may_kia.abookproj")
    # Máy này: Rhine sửa SAU, rồi đã chạy (lần chạy cuối mới hơn mọi sửa của máy kia).
    listener_overrides.request_pronunciation(project, "Rhine", "Rai", now=300.0)

    opened = app.open_book_file(str(packed))

    assert opened == {"id": book_id(project), "how": "project", "workshop": {"merged": 2, "kept": 1}}
    pronunciations = listener_overrides.read_overrides(project)["pronunciations"]
    assert pronunciations["heidi"]["spoken_form"] == "Hai-đi" and pronunciations["rhine"]["spoken_form"] == "Rai"
    assert app.reviews.get(project)["s3"]["verdict"] == "redo"
    labels = [item["label"] for item in store.pending_details(project, 1000.0)["items"]]
    assert labels == ["“Heidi” đọc là “Hai-đi”"], "sửa vừa gộp là sửa mới với máy này, dù mốc gốc cũ hơn lần chạy cuối"

    again = app.open_book_file(str(packed))
    assert again == {"id": book_id(project), "how": "project", "workshop": {"merged": 0, "kept": 1}},         "mở lại cùng file: không còn gì mới để lấy, Rhine vẫn giữ bản của máy này"


def test_cards_decided_on_another_machine_come_along_too(tmp_path: Path) -> None:
    """Thẻ đã quyết ghi ở file riêng (một người hai tên, người nói câu 『』, người kể theo đoạn) gộp cùng luật, ghi bằng đường ghi
    của chính file ấy - dây chuyền đọc lại được như khi người dùng bấm ở máy này."""
    from abook import aliases, bracket_rule, narrator_sections

    mine, theirs = tmp_path / "may_nay", tmp_path / "may_kia"
    mine.mkdir()
    theirs.mkdir()
    aliases.add(mine, "Toko", "Tooko", now=100.0)
    aliases.add(theirs, "toko", "Tomoko", now=200.0)
    bracket_rule.save(mine, "NARRATOR", now=300.0)
    bracket_rule.save(theirs, "HEIDI", now=250.0)
    narrator_sections.decide(mine, 3, 10, 20, accepted=False, now=110.0)
    narrator_sections.decide(theirs, 3, 10, 20, accepted=True, narrator="Rhine", source="owner", now=120.0)

    report = workshop_merge.merge_workshop(mine, lambda name: (theirs / name).read_bytes() if (theirs / name).is_file() else None,
                                           Reviews(), 3000.0)

    assert report == {"merged": 2, "kept": 1}
    assert aliases.load(mine) == {aliases.key("Toko"): "Tomoko"}
    assert bracket_rule.load(mine) == "NARRATOR", "quy ước 『』 của máy này mới hơn"
    assert narrator_sections.load(mine) == {3: [{"from_seq": 10, "to_seq": 20, "narrator": "Rhine", "source": "owner",
                                                 "accepted": True, "dismissed": False, "at": 120.0}]}
