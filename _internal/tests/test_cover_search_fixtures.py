"""Bộ ví dụ "Tìm bìa trên mạng" dùng chung với app Android (tests/fixtures/cover_search/): file đã commit phải đúng là thứ bản
Python sinh ra bây giờ - nếu không, test JVM của CoverSearch.kt đang so với một đáp án cũ."""
from __future__ import annotations

from tests import cover_search_fixtures as shared


def test_the_shared_cover_search_cases_are_what_python_answers_today() -> None:
    assert shared.FILE.read_bytes() == shared.dumps(shared.build()), \
        "chạy lại: runtime/.venv/Scripts/python.exe -m tests.cover_search_fixtures (chỉ khi cố ý đổi hành vi)"


def test_the_cases_cover_every_way_a_search_can_go() -> None:
    cases = {case["name"]: case for case in shared.build()["search"]}
    assert cases["mixed"]["expected"]["failed"] == []
    assert {item["provider"] for item in cases["mixed"]["expected"]["results"]} == {"iTunes", "Open Library", "Google Books"}
    assert cases["google_down"]["expected"]["failed"] == ["google_books"]
    assert cases["itunes_ebook_down"]["expected"]["failed"] == ["itunes"], "một nửa iTunes hỏng là cả iTunes hỏng"
    assert cases["all_down"]["expected"]["failed"] == ["itunes", "open_library", "google_books"]
    assert len(cases["thirty_cap"]["expected"]["results"]) == 30
    assert cases["too_short"]["requested"] == [] and cases["empty"]["requested"] == []
    assert len(cases["long_query"]["expected"]["query"]) == 120
    assert all(item["url"].startswith("https://") for item in cases["mixed"]["expected"]["results"])
