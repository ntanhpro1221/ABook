"""B10 (nhánh dev, chỉ để đo): ABOOK_SCENE_FIRST=1 thêm "scene" đứng đầu schema sinh, prompt không đổi, host bỏ "scene"."""
from __future__ import annotations

import pytest

from ebook_reader import eval_hooks
from test_b8_split_and_pointer_modes import _call, _clean_env, _names_payload  # noqa: F401  (fixture autouse)


@pytest.fixture(autouse=True)
def _no_scene(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABOOK_SCENE_FIRST", raising=False)


def test_scene_first_only_changes_the_schema_and_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    plain_request, plain_result = _call(_names_payload())
    monkeypatch.setenv("ABOOK_SCENE_FIRST", "1")
    payload = {"scene": {"present": ["YANAMI", "LUCIEN"], "pair": ["LUCIEN", "YANAMI"]}, **_names_payload()}
    request, result = _call(payload)
    assert request["prompt"] == plain_request["prompt"] and request["system"] == plain_request["system"]
    assert list(request["format"]["properties"])[0] == "scene"
    assert request["format"]["required"][0] == "scene"
    assert request["format"]["properties"]["scene"] == eval_hooks.SCENE_SCHEMA
    assert {k: v for k, v in request["format"].items() if k not in ("properties", "required")} == \
        {k: v for k, v in plain_request["format"].items() if k not in ("properties", "required")}
    assert result == plain_result


def test_scene_off_and_zero_leave_the_request_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    plain, _ = _call(_names_payload())
    monkeypatch.setenv("ABOOK_SCENE_FIRST", "0")
    again, _ = _call(_names_payload())
    assert again == plain and "scene" not in plain["format"]["properties"]
