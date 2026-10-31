"""Danh sách "việc nặng" (hạn 100 s không byte nào về thay vì 30 s) giống từng chữ ở web, Qt và điện thoại, và mỗi mục là một đường có thật của máy chủ.

Máy chủ làm xong cả việc rồi mới trả lời (quét nguồn, tách chương, tạo sách...), nên hạn 30 s chung sẽ cắt nhầm rồi gửi lại việc ấy.
Một bản thiếu mục là bản đó cắt nhầm; một mục không còn là đường của máy chủ là danh sách đã cũ.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from abook.webui import server

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "ui" / "src" / "shared" / "hostWait.ts"
QT = ROOT / "desktop_qt" / "src" / "hostwait.h"
PHONE = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player" / "net" / "HostWait.kt"


def long_work(path: Path) -> list[str]:
    """Các chuỗi trong khối `LONG_WORK` / `kLongWork` của một file, theo thứ tự."""
    text = path.read_text(encoding="utf-8")
    found = re.search(r"(?:LONG_WORK|kLongWork)\b[^\[({]*[\[({](.*?)[\])}]", text, re.S)
    assert found, f"{path.name}: không thấy danh sách LONG_WORK/kLongWork"
    return re.findall(r'"([^"]+)"', found.group(1))


def test_the_web_list_names_only_real_routes():
    # Đường của máy chủ Studio (server.ROUTES) hay của cổng đồng bộ (sync.py khớp `/sync/v1/books/<mã>/...` bằng một biểu thức).
    sync = re.search(r're\.fullmatch\(r"(/sync/v1/books/[^"]+)"', (ROOT / "abook" / "webui" / "sync.py").read_text(encoding="utf-8"))
    assert sync, "sync.py: không thấy biểu thức đường sách của cổng đồng bộ"
    routes = [pattern for _method, pattern, _handler in server.ROUTES] + [re.compile(sync.group(1))]
    for entry in long_work(WEB):
        sample = entry.replace("*", "abc")
        assert any(pattern.fullmatch(sample) for pattern in routes), f"{entry}: không phải đường của máy chủ"


@pytest.mark.parametrize("other", [QT, PHONE], ids=["qt", "phone"])
def test_every_platform_waits_long_on_the_same_routes(other: Path):
    if not other.exists():
        pytest.skip(f"{other.name} chưa có ở nhánh này")
    assert long_work(other) == long_work(WEB)


def test_the_reader_finds_a_short_list(tmp_path: Path):
    # Phép đọc phải bắt được danh sách thiếu mục, không chỉ danh sách đúng.
    cut = tmp_path / "x.kt"
    cut.write_text('val LONG_WORK = listOf(\n    "/api/readaloud/clip",\n)\n', encoding="utf-8")
    assert long_work(cut) == ["/api/readaloud/clip"]
    assert long_work(cut) != long_work(WEB)
