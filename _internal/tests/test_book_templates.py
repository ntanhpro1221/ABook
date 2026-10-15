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
    assert cleaned == [{"name": "Tiên hiệp", "narrator": "Đức Trí", "profile": "balanced", "analysisModel": "", "startNow": False, "precastWait": False}]


def test_precast_wait_is_kept_and_defaults_to_off() -> None:
    from abook.webui.library import clean_book_templates

    assert clean_book_templates([_template(precastWait=True)], VOICES)[0]["precastWait"] is True
    assert clean_book_templates([_template()], VOICES)[0]["precastWait"] is False


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
    {"startNow": "yes"}, {"precastWait": "yes"}, {"precastWait": None}, {"analysisModel": 7}, {"analysisModel": "m" * 201},
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


def _op(server, body: dict):
    return _call(server, "POST", "/api/book-templates", body)


def _names(app) -> list[str]:
    return [item["name"] for item in app.preferences.get()["bookTemplates"]]


def test_a_template_is_saved_and_answers_with_the_whole_preferences(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    voice = app.voices()[0]["name"]
    status, data = _op(server, {"op": "save", "template": _template("Light novel", narrator=voice)})
    assert status == 200 and [item["name"] for item in data["bookTemplates"]] == ["Light novel"]
    assert "libraryRoot" in data and data["theme"], "cùng dạng với PUT /api/preferences"
    status, data = _op(server, {"op": "save", "template": _template("Tiên hiệp", narrator="", profile="fast", startNow=True)})
    assert status == 200 and [item["name"] for item in data["bookTemplates"]] == ["Light novel", "Tiên hiệp"]
    assert _names(app) == ["Light novel", "Tiên hiệp"]


def test_saving_a_name_that_exists_asks_unless_replace_and_replaces_in_place(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    for name in ("A", "B", "C"):
        assert _op(server, {"op": "save", "template": _template(name)})[0] == 200
    status, data = _op(server, {"op": "save", "template": _template("b", profile="fast")})
    assert status == 409 and data["error"] == "Đã có mẫu tên “b”"
    assert app.preferences.get()["bookTemplates"][1]["profile"] == "balanced", "409 không đổi gì"
    status, data = _op(server, {"op": "save", "template": _template("b", profile="fast"), "replace": True})
    assert status == 200
    saved = data["bookTemplates"]
    assert [item["name"] for item in saved] == ["A", "b", "C"], "đè tại chỗ, giữ vị trí"
    assert saved[1]["profile"] == "fast"
    assert _op(server, {"op": "save", "template": _template("D"), "replace": True})[0] == 200, "replace mà chưa có thì là thêm"
    assert _names(app) == ["A", "b", "C", "D"]
    assert _op(server, {"op": "save", "template": _template("E"), "replace": "yes"})[0] == 400


def test_a_template_is_renamed_in_place_and_a_clash_or_a_vanished_one_is_refused(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    for name in ("A", "B", "C"):
        _op(server, {"op": "save", "template": _template(name)})
    status, data = _op(server, {"op": "rename", "from": "b", "to": "  Bê  "})
    assert status == 200 and [item["name"] for item in data["bookTemplates"]] == ["A", "Bê", "C"]
    status, data = _op(server, {"op": "rename", "from": "A", "to": "c"})
    assert status == 409 and "Đã có mẫu tên" in data["error"]
    status, data = _op(server, {"op": "rename", "from": "Không có", "to": "X"})
    assert status == 404 and data["error"] == "Không còn mẫu “Không có”"
    assert _op(server, {"op": "rename", "from": "C", "to": "CC"})[0] == 200
    assert _op(server, {"op": "rename", "from": "CC", "to": "cc"})[0] == 200, "đổi hoa thường của chính nó không phải là trùng"
    assert _op(server, {"op": "rename", "from": "A", "to": "   "})[0] == 400
    assert _op(server, {"op": "rename", "from": "A", "to": "x" * 41})[0] == 400
    assert _op(server, {"op": "rename", "from": "A"})[0] == 400
    assert _names(app) == ["A", "Bê", "cc"]


def test_delete_then_restore_puts_the_template_back_where_it_was(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    for name in ("A", "B", "C"):
        _op(server, {"op": "save", "template": _template(name)})
    gone = app.preferences.get()["bookTemplates"][1]
    status, data = _op(server, {"op": "delete", "name": "b"})
    assert status == 200 and [item["name"] for item in data["bookTemplates"]] == ["A", "C"]
    status, data = _op(server, {"op": "delete", "name": "B"})
    assert status == 404 and "Không còn mẫu" in data["error"], "máy khác đã xoá rồi"
    status, data = _op(server, {"op": "restore", "template": gone, "index": 1})
    assert status == 200 and [item["name"] for item in data["bookTemplates"]] == ["A", "B", "C"]
    status, data = _op(server, {"op": "restore", "template": gone, "index": 0})
    assert status == 409, "đã có lại rồi"
    _op(server, {"op": "delete", "name": "B"})
    assert _op(server, {"op": "restore", "template": gone, "index": 99})[0] == 200 and _names(app) == ["A", "C", "B"], "index quá lớn thì xếp cuối"
    _op(server, {"op": "delete", "name": "B"})
    assert _op(server, {"op": "restore", "template": gone, "index": -3})[0] == 200 and _names(app) == ["B", "A", "C"], "index âm thì xếp đầu"
    assert _op(server, {"op": "restore", "template": gone, "index": "1"})[0] == 400
    assert _op(server, {"op": "restore", "template": gone, "index": True})[0] == 400


@pytest.mark.parametrize("body", [
    {}, {"op": "explode"}, {"op": None}, {"op": "save"}, {"op": "save", "template": "x"}, {"op": "save", "template": _template("")},
    {"op": "save", "template": _template("a", profile="ultra")}, {"op": "delete"}, {"op": "delete", "name": 5},
    {"op": "restore", "template": _template("a")}, {"op": "restore", "index": 0},
])
def test_a_bad_operation_is_a_400_and_changes_nothing(studio, body) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _op(server, {"op": "save", "template": _template("Giữ")})
    status, data = _op(server, body)
    assert status == 400 and data["error"]
    assert _names(app) == ["Giữ"]


def test_the_twenty_template_limit_still_holds(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    for index in range(20):
        assert _op(server, {"op": "save", "template": _template(f"Mẫu {index}")})[0] == 200
    status, data = _op(server, {"op": "save", "template": _template("Mẫu thứ 21")})
    assert status == 400 and "20" in data["error"]
    assert len(_names(app)) == 20
    assert _op(server, {"op": "save", "template": _template("mẫu 3", startNow=True), "replace": True})[0] == 200, "đè thì không tăng số mẫu"


def test_put_preferences_no_longer_writes_templates(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _op(server, {"op": "save", "template": _template("Giữ")})
    status, data = _call(server, "PUT", "/api/preferences", {"bookTemplates": [_template("Lạ")], "theme": "dark"})
    assert status == 200 and data["theme"] == "dark"
    assert [item["name"] for item in data["bookTemplates"]] == ["Giữ"]
    assert _names(app) == ["Giữ"]


def test_two_devices_saving_at_once_both_keep_their_template(studio) -> None:  # noqa: F811
    import threading

    _paths, app, server, _runner = studio
    names = [f"Máy {index}" for index in range(12)]
    results: list[int] = []
    barrier = threading.Barrier(len(names))

    def save(name: str) -> None:
        barrier.wait()
        results.append(_op(server, {"op": "save", "template": _template(name)})[0])

    threads = [threading.Thread(target=save, args=(name,)) for name in names]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [200] * len(names)
    assert sorted(_names(app)) == sorted(names), "không ai đè mất mẫu của ai"


def test_preferences_modify_works_on_the_latest_data_and_writes_nothing_on_error(tmp_path) -> None:
    from abook.webui.library import Preferences

    path = tmp_path / "preferences.json"
    first, second = Preferences(path), Preferences(path)
    first.update({"bookTemplates": [{"name": "A", "narrator": "", "profile": "fast", "analysisModel": "", "startNow": True, "precastWait": False}]})
    # `second` đọc từ trước khi `first` ghi: modify phải thấy bản mới nhất, không phải bản cũ trong bộ nhớ.
    updated = second.modify(lambda prefs: {"bookTemplates": [*prefs["bookTemplates"], {**prefs["bookTemplates"][0], "name": "B"}]})
    assert [item["name"] for item in updated["bookTemplates"]] == ["A", "B"]
    assert [item["name"] for item in Preferences(path).get()["bookTemplates"]] == ["A", "B"]

    def broken(_prefs):
        raise RuntimeError("không ghi")

    with pytest.raises(RuntimeError):
        second.modify(broken)
    assert [item["name"] for item in Preferences(path).get()["bookTemplates"]] == ["A", "B"]


def test_a_fresh_install_has_no_templates(tmp_path) -> None:
    from abook.webui.library import Preferences

    assert Preferences(tmp_path / "preferences.json").get()["bookTemplates"] == []


def test_a_removed_voice_falls_back_to_the_suggested_one() -> None:
    # Giọng của mẫu đã bị gỡ khỏi máy: mẫu về "giọng máy đề xuất", không chặn việc lưu cả danh sách (đổi tên mẫu khác).
    from abook.webui.library import clean_book_templates

    for narrator in ("Giọng không có", 3, None):
        assert clean_book_templates([_template(narrator=narrator)], VOICES)[0]["narrator"] == ""
