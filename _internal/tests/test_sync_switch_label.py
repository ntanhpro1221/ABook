"""Tên công tắc kết nối qua Wi-Fi: lời báo lỗi của máy chủ nhắc đúng chuỗi mà giao diện ghi ở Cài đặt (một nguồn, không hai chuỗi lệch)."""
import re
from pathlib import Path

from abook.webui import remote_books

SWITCH_TS = Path(__file__).resolve().parents[1] / "ui" / "src" / "shared" / "syncSwitch.ts"


def test_unreachable_message_names_the_switch_the_settings_page_shows():
    match = re.search(r'SYNC_SWITCH_LABEL\s*=\s*"([^"]+)"', SWITCH_TS.read_text(encoding="utf-8"))
    assert match, "ui/src/shared/syncSwitch.ts không còn SYNC_SWITCH_LABEL"
    assert remote_books.SYNC_SWITCH == match.group(1)
    assert f"“{match.group(1)}”" in remote_books.UNREACHABLE
