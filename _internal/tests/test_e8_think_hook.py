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
    # /api/chat: system + prompt thành tin nhắn (generate + think + format không nghĩ ở Ollama 0.33.2)
    assert thinking["messages"] == [{"role": "system", "content": plain["system"]}, {"role": "user", "content": plain["prompt"]}]
    rest = lambda r: {k: v for k, v in r.items() if k not in ("think", "options", "system", "prompt", "messages")}  # noqa: E731
    assert rest(thinking) == rest(plain) and result == plain_result


def test_chat_envelope_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    import test_analysis_required as base

    def chat_lines(self, decode_unicode=False):
        yield json.dumps({"message": {"role": "assistant", "content": "", "thinking": "nghĩ đã"}, "done": False})
        yield json.dumps({"message": {"role": "assistant", "content": json.dumps(self.payload, ensure_ascii=False)},
                          "done": True, "done_reason": "stop", "eval_count": 7}, ensure_ascii=False)

    plain_request, plain_result = _call(_names_payload())
    monkeypatch.setattr(base.FakeResponse, "iter_lines", chat_lines)
    monkeypatch.setenv("ABOOK_EVAL_SETTINGS", json.dumps({"think": True}))
    _request, result = _call(_names_payload())
    assert result == plain_result


def test_think_false_or_absent_is_the_plain_request(monkeypatch: pytest.MonkeyPatch) -> None:
    plain, _ = _call(_names_payload())
    monkeypatch.setenv("ABOOK_EVAL_SETTINGS", json.dumps({"think": False}))
    again, _ = _call(_names_payload())
    assert again == plain


def test_think_num_ctx_raises_the_context_only_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    plain, _ = _call(_names_payload())
    monkeypatch.setenv("ABOOK_EVAL_SETTINGS", json.dumps({"think": True}))
    same, _ = _call(_names_payload())
    assert same["options"]["num_ctx"] == plain["options"]["num_ctx"]
    monkeypatch.setenv("ABOOK_EVAL_SETTINGS", json.dumps({"think": True, "think_num_ctx": 65536}))
    wide, _ = _call(_names_payload())
    assert wide["options"]["num_ctx"] == 65536
