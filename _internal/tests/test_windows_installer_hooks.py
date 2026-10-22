"""Hook NSIS của bộ cài Windows (shell/src-tauri/windows/hooks.nsh) - soát a73, F2.

Cài cho người dùng hiện tại, mẫu NSIS của Tauri đặt $INSTDIR = %LOCALAPPDATA%\\ABook: cũng là cha của Studio và dữ liệu
người dùng. Chạy tay bộ cài bản mới thì nó gọi bộ gỡ ("gỡ trước khi cài") - bộ gỡ dừng tiến trình dưới cả $INSTDIR là giết
worker Studio đang làm sách giữa chừng. Không chạy được NSIS trong bài thử nên đọc chính file hook."""
from __future__ import annotations

import re
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "shell" / "src-tauri" / "windows" / "hooks.nsh"


def _macro(name: str) -> str:
    text = HOOKS.read_text(encoding="utf-8")
    match = re.search(rf"^!macro {name}\n(.*?)^!macroend", text, re.S | re.M)
    assert match, name
    return match.group(1)


def _stopped(body: str) -> list[str]:
    return re.findall(r'^\s*!insertmacro ABOOK_STOP_PROCESSES_UNDER "([^"]+)"', body, re.M)


def test_the_uninstaller_run_by_a_new_setup_only_stops_the_apps_own_programs() -> None:
    folders = _stopped(_macro("NSIS_HOOK_PREUNINSTALL"))
    assert folders == ["$INSTDIR\\resources"], "không dừng Studio hay gì khác dưới %LOCALAPPDATA%\\ABook"


def test_a_real_uninstall_still_stops_studio_before_removing_it() -> None:
    body = _macro("NSIS_HOOK_POSTUNINSTALL")
    folders = _stopped(body)
    assert "$LOCALAPPDATA\\ABook\\Studio" in folders and "$LOCALAPPDATA\\ABook" in folders
    # Xoá qua ABOOK_REMOVE_SAFE (kiểm vị trí thư viện trước mỗi RMDir /r - soát a85 lỗi 4), không RMDir /r trần.
    assert "RMDir /r" not in body
    assert body.index('ABOOK_STOP_PROCESSES_UNDER "$LOCALAPPDATA\\ABook\\Studio"') < body.index('ABOOK_REMOVE_SAFE "$LOCALAPPDATA\\ABook\\Studio"')
    assert body.index('ABOOK_STOP_PROCESSES_UNDER "$LOCALAPPDATA\\ABook"') < body.index('ABOOK_REMOVE_SAFE "$LOCALAPPDATA\\ABook"\n')
