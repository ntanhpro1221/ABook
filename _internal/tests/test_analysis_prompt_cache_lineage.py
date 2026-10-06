"""Optional prompt-cache prime before each analysis request (resume_determinism/AUDIT.md 5.3).

llama-server reuses the longest prefix it still holds, so a warm request and the first
request after a load start evaluating at different positions and get different floats. With
`prompt_cache_lineage` on, the request's system prompt goes out with a one-character prompt
just before it, so the request always reuses exactly that shared prefix. Off by default until the GPU A/B decides.
"""
from __future__ import annotations

from typing import Any

import requests

from abook.analysis import OllamaBookAnalyzer


class _Session:
    def __init__(self, fail: bool = False) -> None:
        self.posts: list[dict[str, Any]] = []
        self.fail = fail

    def post(self, url: str, json: dict[str, Any], **_kwargs: Any) -> Any:
        self.posts.append(json)
        if self.fail:
            raise requests.ConnectionError("down")

        class _Ok:
            @staticmethod
            def raise_for_status() -> None:
                return None

        return _Ok()


class _Db:
    events: list[str] = []

    @staticmethod
    def analysis_response(_hash: str) -> None:
        return None

    @staticmethod
    def record_analysis_response(**_kwargs: Any) -> None:
        return None

    def event(self, _level: str, code: str, *_args: Any, **_kwargs: Any) -> None:
        self.events.append(code)


def _analyzer(settings: dict[str, Any], session: _Session) -> tuple[OllamaBookAnalyzer, list[str]]:
    analyzer = OllamaBookAnalyzer.__new__(OllamaBookAnalyzer)
    analyzer.settings = settings
    analyzer.session = session
    analyzer.base_url = "http://127.0.0.1:1"
    analyzer.model = "m"
    analyzer.db = _Db()
    analyzer._model_digest = "d"
    logs: list[str] = []
    analyzer.log = logs.append
    order: list[str] = []

    def stream(body: dict[str, Any], **_kwargs: Any) -> tuple[str, str, int, dict[str, int]]:
        order.append("request:" + body["prompt"])
        return "{}", "stop", 1, {"prompt_eval_count": 1}

    analyzer._ollama_stream = stream
    analyzer._decoded_analysis_response = lambda _request, raw, **_kwargs: {"raw": raw}
    session_post = session.post

    def post(url: str, json: dict[str, Any], **kwargs: Any) -> Any:
        order.append("prime:" + json["prompt"])
        return session_post(url, json, **kwargs)

    session.post = post  # type: ignore[method-assign]
    return analyzer, order


REQUEST = {
    "model": "m",
    "system": "SYSTEM",
    "prompt": "batch 1",
    "format": {"type": "object"},
    "keep_alive": "30m",
    "options": {"temperature": 0.1, "seed": 42, "num_ctx": 8192, "num_predict": 900},
}


def test_the_prime_goes_out_just_before_the_request() -> None:
    session = _Session()
    analyzer, order = _analyzer({"prompt_cache_lineage": True}, session)
    analyzer._stream_json_response(dict(REQUEST), stop_checked=True)
    assert order == ["prime:.", "request:batch 1"]
    prime = session.posts[0]
    assert prime["system"] == "SYSTEM" and prime["prompt"] == "." and prime["format"] == {"type": "object"}
    assert prime["options"] == {"temperature": 0.1, "seed": 42, "num_ctx": 8192, "num_predict": 1}
    assert prime["think"] is False and prime["stream"] is False and prime["keep_alive"] == "30m"


def test_off_by_default_and_a_failed_prime_does_not_stop_the_request() -> None:
    analyzer, order = _analyzer({}, _Session())
    analyzer._stream_json_response(dict(REQUEST), stop_checked=True)
    assert order == ["request:batch 1"]
    analyzer, order = _analyzer({"prompt_cache_lineage": True}, _Session(fail=True))
    assert analyzer._stream_json_response(dict(REQUEST), stop_checked=True) == {"raw": "{}"}
    assert order == ["prime:.", "request:batch 1"]
