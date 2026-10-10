"""Trình duyệt đóng kết nối giữa chừng (tải lại trang) không được để lại traceback trong nhật ký máy chủ; lỗi khác thì vẫn ghi."""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr

import pytest

from abook.webui.sync import ExclusiveHTTPServer


def reported(error: BaseException) -> str:
    """Những gì `handle_error` in ra khi `error` nổ trong lúc xử lý một kết nối."""
    server = ExclusiveHTTPServer.__new__(ExclusiveHTTPServer)  # không cần mở cổng thật
    out = io.StringIO()
    with redirect_stderr(out):
        try:
            raise error
        except BaseException:
            server.handle_error(object(), ("127.0.0.1", 1))
    return out.getvalue()


@pytest.mark.parametrize("error", [ConnectionAbortedError("đóng"), ConnectionResetError("đứt"), BrokenPipeError("vỡ ống")])
def test_a_closed_connection_is_not_logged(error: BaseException) -> None:
    assert reported(error) == ""


def test_other_errors_are_still_logged() -> None:
    text = reported(ValueError("lỗi thật"))
    assert "ValueError" in text and "lỗi thật" in text
    assert sys.exc_info()[1] is None
