r"""Ký tự vô hình (định dạng Cf, ngắt dòng U+2028/U+2029, điều khiển, khoảng trắng lạ) viết thô trong mã thì người đọc không thấy và công cụ dễ
làm mất: một byte backspace từng nằm thay cho `\b` trong regex WinError 5 của export.py (fix174d). Viết chúng bằng mã thoát (\u + 4 số hex).

NBSP (U+00A0) được phép: nó là chữ hiện (khoảng giữa số và đơn vị, " · ") trong chuỗi giao diện. Script PowerShell giữ BOM đầu file
(Windows PowerShell 5.1 cần nó để đọc UTF-8)."""
from __future__ import annotations

import subprocess
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = (".py", ".kt", ".kts", ".ts", ".tsx", ".js", ".mjs", ".qml", ".cpp", ".h", ".java", ".bat", ".css", ".html")


def _hidden(char: str) -> bool:
    if char in "\t\r\n \xa0":
        return False
    return unicodedata.category(char) in ("Cf", "Zl", "Zp", "Cc", "Zs")


def test_code_writes_invisible_characters_as_escapes() -> None:
    names = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8").split("\0")
    found = []
    for name in names:
        if not name.endswith(CODE):
            continue
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.split("\n"), 1):
            hidden = sorted({f"U+{ord(c):04X}" for c in line if _hidden(c)})
            if hidden:
                found.append(f"{name}:{number} {' '.join(hidden)}")
    assert not found, "\n".join(found)
