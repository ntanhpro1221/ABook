"""Tab Nhân vật của phần nối tiếp chưa phân tích (soát UX a6 01-10, B2): dàn mang từ phần trước - giọng đã ghim - phải hiện,
không phải "Chưa có dàn". Người đã nói ở phần này thì ở danh sách chính như cũ, không lặp lại."""
from __future__ import annotations

from pathlib import Path

from ebook_reader.webui import store
from tests.test_listener_speakers import _book


def test_pinned_voices_without_lines_are_listed_as_carried(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE characters SET locked_voice_key='v_lucien' WHERE canonical_name='LUCIEN'")
        conn.execute("INSERT INTO characters(canonical_name,display_name,gender,age,personality,importance,mention_count,"
                     "confidence,locked,locked_voice_key,created_at,updated_at)"
                     " VALUES('HEIDI','HEIDI','female','young','','main',0,1,1,'v_natasha',0,0)")
    view = store.cast(paths.root)
    assert [person["name"] for person in view["carried"]] == ["HEIDI"], "Lucien đã nói ở phần này - ở danh sách chính"
    heidi = view["carried"][0]
    assert heidi["displayName"] == "Heidi" and heidi["lines"] == 0 and heidi["voice"]["key"] == "v_natasha"
