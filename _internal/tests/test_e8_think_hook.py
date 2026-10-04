"""E8 (nhánh dev, chỉ để đo): ABOOK_EVAL_SETTINGS {"think": true} cho lượt sinh gửi think=true + ngân sách nghĩ; tắt thì y hệt."""
from __future__ import annotations

import json

import pytest

from test_b8_split_and_pointer_modes import _call, _clean_env, _names_payload  # noqa: F401  (fixture autouse)


def test_think_on_only_adds_think_and_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    plain, plain_result = _call(_names_payload())
    assert plain["think"] is False
    monkeypatch.setenv("ABOOK_EVAL_SETTINGS", json.dumps({"think": True, "think_extra_tokens": 512}))
    thinking, result = _call(_names_payload())
    assert thinking["think"] is True
    assert thinking["options"]["num_predict"] == plain["options"]["num_predict"] + 512
    rest = lambda r: {k: v for k, v in r.items() if k not in ("think", "options")}  # noqa: E731
    assert rest(thinking) == rest(plain) and result == plain_result


def test_think_false_or_absent_is_the_plain_request(monkeypatch: pytest.MonkeyPatch) -> None:
    plain, _ = _call(_names_payload())
    monkeypatch.setenv("ABOOK_EVAL_SETTINGS", json.dumps({"think": False}))
    again, _ = _call(_names_payload())
    assert again == plain
