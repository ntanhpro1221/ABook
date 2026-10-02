"""Tab Nhân vật của phần nối tiếp chưa phân tích (soát UX a6 01-10, B2): dàn mang từ phần trước - giọng đã ghim - phải hiện,
không phải "Chưa có dàn". Người đã nói ở phần này thì ở danh sách chính như cũ, không lặp lại."""
from __future__ import annotations

import json
from pathlib import Path

from abook import continuation, names
from abook.webui import store
from tests.test_continue_this_book import VOICE_A, VOICE_B, _speak, book  # noqa: F401  (fixture)
from tests.test_listener_speakers import _book


def _continue(root: Path) -> None:
    """Đánh dấu dự án là phần 2 (continues.json) - `store.cast` chỉ liệt kê dàn mang sang ở phần nối tiếp."""
    (root / continuation.LINK_FILE).write_text(json.dumps({"previous": "phan0", "part": 2}), encoding="utf-8")


def test_pinned_voices_without_lines_are_listed_as_carried(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    _continue(paths.root)
    with db.connect() as conn:
        conn.execute("UPDATE characters SET locked_voice_key='v_lucien' WHERE canonical_name='LUCIEN'")
        conn.execute("INSERT INTO characters(canonical_name,display_name,gender,age,personality,importance,mention_count,"
                     "confidence,locked,locked_voice_key,created_at,updated_at)"
                     " VALUES('HEIDI','HEIDI','female','young','','main',0,1,1,'v_natasha',0,0)")
    view = store.cast(paths.root)
    assert [person["name"] for person in view["carried"]] == ["HEIDI"], "Lucien đã nói ở phần này - ở danh sách chính"
    heidi = view["carried"][0]
    assert heidi["displayName"] == "Heidi" and heidi["lines"] == 0 and heidi["voice"]["key"] == "v_natasha"


def test_a_book_that_continues_nothing_lists_no_carried_people(tmp_path: Path) -> None:
    """Ở sách lẻ, người có giọng ghim mà không còn câu (đã gộp đi) không phải "từ phần trước"."""
    paths, db = _book(tmp_path)
    with db.connect() as conn:
        conn.execute("INSERT INTO characters(canonical_name,display_name,gender,age,personality,importance,mention_count,"
                     "confidence,locked,locked_voice_key,created_at,updated_at)"
                     " VALUES('HEIDI','HEIDI','female','young','','main',0,1,1,'v_natasha',0,0)")
    assert store.cast(paths.root)["carried"] == []


def test_a_seeded_part_shows_the_carried_cast_before_any_line_and_then_as_normal(book: dict[str, Path]) -> None:  # noqa: F811
    names.set_name(book["first"], "SELENE", "Selena", "Selene")
    continuation.seed(book["first"], book["second"])

    before = store.cast(book["second"])
    assert before["characters"] == [] and before["extras"] == []
    carried = {person["name"]: person for person in before["carried"]}
    assert set(carried) == {"SELENE", "MARCUS"}
    selene = carried["SELENE"]
    assert (selene["lines"], selene["seconds"]) == (0, 0.0)
    assert selene["displayName"] == "Selena" and selene["originalName"] == "Selene", "tên đã đổi đi theo"
    assert selene["gender"] and selene["voice"] and selene["voice"]["key"] == VOICE_B
    assert carried["MARCUS"]["voice"]["key"] == VOICE_A

    from abook.database import ProjectDB
    _speak(ProjectDB(book["second"] / "project.sqlite3"), "003", [("SELENE", VOICE_B)])
    after = store.cast(book["second"])
    assert [(person["name"], person["lines"], person["displayName"]) for person in after["characters"]]         == [("SELENE", 1, "Selena")] and after["extras"] == []
    assert [person["name"] for person in after["carried"]] == ["MARCUS"], "đã nói ở phần này thì không còn trong 'mang sang'"
