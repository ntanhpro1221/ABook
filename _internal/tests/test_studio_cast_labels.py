"""Tab Nhân vật và hộp Gộp gọi người nói như người nghe thấy (soát UX a23 B6): nhãn dành riêng của máy ("UNKNOWN") là
"Vai phụ không tên", không phải chữ "Unknown" thô - cùng cách gọi với hộp việc và tab Kịch bản (reviews.speaker_label)."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from abook.webui import store
from tests.test_webui_listen_and_sync import make_project


def test_the_reserved_unknown_speaker_is_shown_as_an_unnamed_extra(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("INSERT INTO characters VALUES (2, 'UNKNOWN', 'Unknown', 'unknown', '', 'minor', 1, '')")
    db.execute("INSERT INTO segments VALUES (6, 1, 4, 2, 0, '“Ai đó?”', 'dialogue', 'UNKNOWN', 2, 'verified', '', '', 1.0, ?)",
               (time.time(),))
    db.commit()
    db.close()
    view = store.cast(project)
    names = [person["displayName"] for person in view["characters"] + view["extras"]]
    assert "Vai phụ không tên" in names and "Unknown" not in names, names


def test_a_person_merged_into_another_shows_the_merge_is_waiting(tmp_path: Path) -> None:
    from abook import aliases

    project = make_project(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("INSERT INTO characters VALUES (2, 'GIAO_SU', 'Giáo sư', 'male', '', 'minor', 1, '')")
    db.execute("INSERT INTO segments VALUES (6, 1, 4, 2, 0, '“Ngồi xuống.”', 'dialogue', 'GIAO_SU', 2, 'verified', '', '', 1.0, ?)",
               (time.time(),))
    db.commit()
    db.close()
    assert all(person.get("mergedInto") is None for person in store.cast(project)["characters"])
    aliases.add(project, "GIAO_SU", "LUCIEN")
    people = {person["name"]: person for person in store.cast(project)["characters"]}
    assert people["GIAO_SU"]["mergedInto"] == "Lucien" and people["LUCIEN"]["mergedInto"] is None
