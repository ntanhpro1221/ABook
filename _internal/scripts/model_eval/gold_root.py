"""Thư mục đáp án dùng chung cho mọi script đo/dựng dữ liệu.

Bản `gold/` trong repo là bản sao công khai (chỉ nhãn) của nguồn chuẩn riêng; nó có thể đi sau nguồn chuẩn.
Đặt `ABOOK_GOLD_ROOT` để chấm/dựng thẳng từ nguồn chuẩn. Mọi script đọc thư mục đáp án qua hàm này,
không tự ghép `HERE / "gold"`.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_GOLD = Path(__file__).resolve().parent / "gold"


def gold_root() -> Path:
    configured = os.environ.get("ABOOK_GOLD_ROOT", "").strip()
    return Path(configured) if configured else REPO_GOLD
