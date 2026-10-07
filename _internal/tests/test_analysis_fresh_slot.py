"""Mồi slot sạch (`OllamaBookAnalyzer._prime_fresh_slot`): trước mỗi lần hỏi model thật có đúng một request 1 token, system
khác; câu trả lời lấy lại từ sổ không hỏi model nên không mồi; lỗi kết nối ở lúc mồi được thử lại như lỗi của request thật.
Lý do và số đo nằm trong docstring của hàm ấy. Không gọi Ollama thật."""
from __future__ import annotations

import json
from typing import Any

import pytest
import requests

from abook.analysis import OLLAMA_TRANSPORT_RECONNECT_ATTEMPTS, OllamaBookAnalyzer
from abook.config import build_settings
from test_analysis_required import FakeDB, FakeResponse
from tests.fresh_slot_fakes import FRESH_SLOT_SYSTEM, PrimeResponse, is_fresh_slot_prime

PAYLOAD = {"segments": [{"id": "S001"}]}
REAL_SYSTEM = "Bạn là bộ phân tích."


def _request() -> dict[str, Any]:
    return {
        "model": "qwen3:8b",
        "system": REAL_SYSTEM,
        "prompt": "Đoạn cần phân tích.",
        "options": {"num_ctx": 16384, "num_predict": 512, "seed": 7},
    }


class LedgerDB(FakeDB):
    """FakeDB có sổ phản hồi: `stored` là bản ghi trả cho `analysis_response`, `recorded` là những gì đã ghi."""

    def __init__(self, stored: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.stored = stored
        self.recorded: list[dict[str, Any]] = []

    def analysis_response(self, request_hash: str) -> dict[str, Any] | None:
        return self.stored

    def record_analysis_response(self, **kwargs: Any) -> None:
        self.recorded.append(kwargs)


class RecordingSession:
    """Ghi MỌI lời gọi post theo thứ tự (kể cả mồi). `faults` = số lần đầu tiên gọi mồi bị rớt kết nối;
    `real_faults` = số lần đầu tiên gọi thật bị rớt kết nối."""

    def __init__(self, *, prime_faults: int = 0, real_faults: int = 0) -> None:
        self.calls: list[dict[str, Any]] = []
        self.prime_faults = prime_faults
        self.real_faults = real_faults

    def post(self, _url: str, **kwargs: Any) -> Any:
        body = kwargs["json"]
        prime = is_fresh_slot_prime(body)
        self.calls.append({"prime": prime, "json": body, "stream": kwargs.get("stream", False)})
        if prime:
            if self.prime_faults > 0:
                self.prime_faults -= 1
                raise requests.exceptions.ConnectionError("rớt lúc mồi")
            return PrimeResponse()
        if self.real_faults > 0:
            self.real_faults -= 1
            raise requests.exceptions.ConnectionError("rớt lúc hỏi thật")
        return FakeResponse(PAYLOAD)

    @property
    def primes(self) -> list[dict[str, Any]]:
        return [call for call in self.calls if call["prime"]]

    @property
    def reals(self) -> list[dict[str, Any]]:
        return [call for call in self.calls if not call["prime"]]


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("abook.analysis.time.sleep", lambda _seconds: None)


def _analyzer(session: RecordingSession, db: FakeDB | None = None) -> OllamaBookAnalyzer:
    analyzer = OllamaBookAnalyzer(build_settings(), db or LedgerDB(), lambda _message: None)
    analyzer.session = session
    return analyzer


def test_every_real_model_call_is_preceded_by_exactly_one_prime() -> None:
    session = RecordingSession()
    request = _request()

    assert _analyzer(session)._stream_json_response(request) == PAYLOAD

    assert [call["prime"] for call in session.calls] == [True, False]
    prime, real = session.calls[0]["json"], session.calls[1]["json"]
    assert prime["model"] == real["model"] == "qwen3:8b"
    assert prime["options"]["num_ctx"] == real["options"]["num_ctx"] == 16384
    assert prime["options"]["num_predict"] == 1
    assert prime["system"] == FRESH_SLOT_SYSTEM and prime["system"] != real["system"]
    assert real["system"] == REAL_SYSTEM and real["options"]["num_predict"] == 512
    # mồi không stream (nhận một JSON rồi thôi), request thật thì stream
    assert prime["stream"] is False and session.calls[0]["stream"] is False
    assert session.calls[1]["stream"] is True


def test_the_prime_leaves_out_num_ctx_when_the_request_has_none() -> None:
    session = RecordingSession()
    request = _request()
    del request["options"]["num_ctx"]

    _analyzer(session)._stream_json_response(request)

    assert "num_ctx" not in session.primes[0]["json"]["options"]
    assert session.primes[0]["json"]["options"]["num_predict"] == 1


def test_two_real_calls_get_one_prime_each_just_before_them() -> None:
    session = RecordingSession()
    analyzer = _analyzer(session)

    analyzer._stream_json_response(_request())
    second = _request()
    second["prompt"] = "Đoạn khác."
    analyzer._stream_json_response(second)

    assert [call["prime"] for call in session.calls] == [True, False, True, False]


def test_an_answer_replayed_from_the_ledger_sends_no_prime() -> None:
    stored = {
        "raw_response": json.dumps(PAYLOAD),
        "done_reason": "stop",
        "eval_tokens": 12,
        "usage_json": None,
    }
    session = RecordingSession()

    assert _analyzer(session, LedgerDB(stored))._stream_json_response(_request()) == PAYLOAD

    assert session.calls == []


def test_a_live_answer_is_recorded_and_the_prime_is_not() -> None:
    db = LedgerDB()
    session = RecordingSession()

    _analyzer(session, db)._stream_json_response(_request())

    assert len(db.recorded) == 1
    assert db.recorded[0]["raw_response"] == json.dumps(PAYLOAD, ensure_ascii=False)
    assert db.recorded[0]["model_name"] == "qwen3:8b"


def test_a_connection_lost_while_priming_is_retried_like_a_lost_real_request() -> None:
    session = RecordingSession(prime_faults=1)

    assert _analyzer(session)._stream_json_response(_request()) == PAYLOAD

    assert [call["prime"] for call in session.calls] == [True, True, False]


def test_priming_stops_retrying_after_the_bounded_reconnect_budget() -> None:
    session = RecordingSession(prime_faults=99)

    with pytest.raises(requests.exceptions.ConnectionError):
        _analyzer(session)._stream_json_response(_request())

    assert len(session.primes) == OLLAMA_TRANSPORT_RECONNECT_ATTEMPTS + 1
    assert session.reals == []


def test_a_lost_real_request_is_primed_again_before_each_retry() -> None:
    """Lần thử lại phải mồi lại: slot có thể đã bị request dở dang làm bẩn."""
    session = RecordingSession(real_faults=1)

    assert _analyzer(session)._stream_json_response(_request()) == PAYLOAD

    assert [call["prime"] for call in session.calls] == [True, False, True, False]
