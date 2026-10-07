"""Chỗ chung cho các session giả của test phân tích: nhận lời gọi mồi `_prime_fresh_slot`.

Trước mỗi lần gọi model thật, `OllamaBookAnalyzer._ollama_stream` gửi một POST /api/generate KHÔNG stream, 1 token, với
prompt "1" ở chế độ raw (xem docstring `_prime_fresh_slot`). Session giả của test phải trả lời nó như một response OK
và KHÔNG tính nó vào số request / nội dung request thật mà test đang kiểm - nên mỗi session giả hỏi `is_fresh_slot_prime`
rồi gọi `prime_response`.
"""
from __future__ import annotations

from typing import Any

FRESH_SLOT_PROMPT = "1"


def is_fresh_slot_prime(body: Any) -> bool:
    """Body json của lời gọi mồi (không phải request phân tích thật)."""
    return isinstance(body, dict) and body.get("raw") is True and body.get("prompt") == FRESH_SLOT_PROMPT


class PrimeResponse:
    """Response giả của lời gọi mồi: chỉ `raise_for_status` được dùng."""

    def raise_for_status(self) -> None:
        return None
