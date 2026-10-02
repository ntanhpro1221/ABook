"""Mẫu thiết lập có tên cho sách mới (backlog H4): máy chủ chỉ nhận đúng bốn lựa chọn thường của trình tạo sách + "bắt đầu
ngay", tên không trùng và không quá 20 mẫu - và KHÔNG BAO GIỜ mang theo chuyện sửa chữ truyện (`dropCredits` là đồng ý riêng từng cuốn)."""
from __future__ import annotations

import pytest

from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung

VOICES = {"Đức Trí", "Thục Anh"}


def _template(name: str = "Light novel", **changes):
    return {"name": name, "narrator": "Đức Trí", "profile": "balanced", "analysisModel": "", "startNow": False, **changes}


def test_a_template_is_cleaned_to_its_known_fields() -> None:
    from abook.webui.library import clean_book_templates

    cleaned = clean_book_templates([_template("  Tiên   hiệp ", dropCredits=True, title="x", paths=["a"])], VOICES)
    assert cleaned == [{"name": "Tiên hiệp", "narrator": "Đức Trí", "profile": "balanced", "analysisModel": "", "startNow": False}]


@pytest.mark.parametrize("name", ["", "   ", "x" * 41, None, 5])
def test_a_bad_name_is_refused(name) -> None:
    from abook.webui.library import clean_book_templates

    with pytest.raises(ValueError):
        clean_book_templates([_template(name)], VOICES)


def test_a_name_may_be_forty_characters() -> None:
    from abook.webui.library import clean_book_templates

    assert clean_book_templates([_template("x" * 40)], VOICES)[0]["name"] == "x" * 40


def test_names_are_unique_ignoring_case() -> None:
    from abook.webui.library import clean_book_templates

    with pytest.raises(ValueError):
        clean_book_templates([_template("Tiên hiệp"), _template("TIÊN HIỆP")], VOICES)


def test_at_most_twenty_templates() -> None:
    from abook.webui.library import clean_book_templates

    assert len(clean_book_templates([_template(f"Mẫu {i}") for i in range(20)], VOICES)) == 20
    with pytest.raises(ValueError):
        clean_book_templates([_template(f"Mẫu {i}") for i in range(21)], VOICES)


@pytest.mark.parametrize("changes", [
    {"profile": "ultra"}, {"profile": None},
    {"startNow": "yes"}, {"analysisModel": 7}, {"analysisModel": "m" * 201},
])
def test_an_unknown_choice_is_refused(changes) -> None:
    from abook.webui.library import clean_book_templates

    with pytest.raises(ValueError):
        clean_book_templates([_template(**changes)], VOICES)


def test_not_a_list_or_not_objects_are_refused() -> None:
    from abook.webui.library import clean_book_templates

    for broken in ({}, "x", None, ["x"], [[1]]):
        with pytest.raises(ValueError):
            clean_book_templates(broken, VOICES)


def test_the_default_narrator_may_be_empty() -> None:
    from abook.webui.library import clean_book_templates

    assert clean_book_templates([_template(narrator="")], VOICES)[0]["narrator"] == ""


def test_templates_are_saved_and_a_bad_list_is_a_400_that_keeps_the_old_one(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    voice = app.voices()[0]["name"]
    good = [_template("Light novel", narrator=voice), _template("Tiên hiệp", narrator="", profile="fast", startNow=True)]
    status, data = _call(server, "PUT", "/api/preferences", {"bookTemplates": good})
    assert status == 200 and [item["name"] for item in data["bookTemplates"]] == ["Light novel", "Tiên hiệp"]
    status, data = _call(server, "PUT", "/api/preferences", {"bookTemplates": [_template("a"), _template("A")]})
    assert status == 400 and "mẫu" in data["error"]
    assert [item["name"] for item in app.preferences.get()["bookTemplates"]] == ["Light novel", "Tiên hiệp"]
    status, data = _call(server, "PUT", "/api/preferences", {"bookTemplates": []})
    assert status == 200 and data["bookTemplates"] == []


def test_a_fresh_install_has_no_templates(tmp_path) -> None:
    from abook.webui.library import Preferences

    assert Preferences(tmp_path / "preferences.json").get()["bookTemplates"] == []


def test_a_removed_voice_falls_back_to_the_suggested_one() -> None:
    # Giọng của mẫu đã bị gỡ khỏi máy: mẫu về "giọng máy đề xuất", không chặn việc lưu cả danh sách (đổi tên mẫu khác).
    from abook.webui.library import clean_book_templates

    for narrator in ("Giọng không có", 3, None):
        assert clean_book_templates([_template(narrator=narrator)], VOICES)[0]["narrator"] == ""
