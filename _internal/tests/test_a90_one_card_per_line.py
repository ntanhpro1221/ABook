"""a90 T1: một câu chỉ một thẻ - tín hiệu logprob gom vào thẻ "gọi tên chính mình" đã có, và không tốn suất ngân sách logprob."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from test_work_items import lp, make_book, write_logprobs

from abook.webui.work_items import work_items


def _cards_per_line(view: dict) -> Counter:
    return Counter(line["stableId"] for item in view["items"] if item["kind"] in ("speaker", "vocative")
                   for line in item.get("lines", []))


def test_a_vocative_line_that_is_also_unsure_gets_one_card_carrying_both_reasons(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    # "b" (“Heidi, ...” gán Heidi) là câu model kém chắc nhất; "c" kém chắc nhì.
    write_logprobs(project, [lp("b", "HEIDI", 0.3), lp("c", "LUCIEN", 0.5), lp("d", "ÁO CHOÀNG ĐEN", 0.99),
                             lp("e", "ÁO CHOÀNG ĐEN", 0.99), lp("f", "RHINE", 0.99),
                             lp("g", "NPC_LOCAL::c00001::r1::người gác", 0.99)])
    view = work_items(project)
    assert max(_cards_per_line(view).values()) == 1, "không câu nào có hai thẻ"
    (vocative,) = [item for item in view["items"] if item["kind"] == "vocative"]
    assert vocative["lines"][0]["stableId"] == "b"
    assert "30%" in vocative["problem"], "lý do bổ sung: model chỉ chắc ~30% người nói"
    # Suất logprob (6 câu x 20% = 1) không bị "b" ăn: "c" vẫn được hỏi.
    assert [item["key"] for item in view["items"] if item["kind"] == "speaker"] == ["speaker:c"]
    assert view["counts"]["vocative"] == 1


def test_a_vocative_line_the_model_is_sure_about_keeps_its_plain_problem(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    write_logprobs(project, [lp("b", "HEIDI", 0.99), lp("c", "LUCIEN", 0.5)])
    (vocative,) = [item for item in work_items(project)["items"] if item["kind"] == "vocative"]
    assert "%" not in vocative["problem"]
