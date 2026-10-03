"""Bảng thực thể HTML cho bộ đọc thẻ của app Android (`HtmlEntities.kt`), sinh từ `html.entities.html5` của Python.

Bộ nhập sách của máy tính đọc chữ EPUB bằng `html.parser` (gọi `html.unescape`), bản Kotlin (`BookImport.Markup.decode`) là bản chép
của `html.unescape` - nên cần đúng cùng bảng. Sinh lại (chỉ khi Python đổi bảng): runtime/.venv/Scripts/python.exe -m tests.html_entities_kotlin
`test_importers.py` kiểm file đã commit đúng là thứ hàm này sinh ra.
"""
from __future__ import annotations

import html.entities
from pathlib import Path

TARGET = (Path(__file__).resolve().parent.parent / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player"
          / "HtmlEntities.kt")
PER_LINE = 12


def render() -> str:
    entries = [f"{name}={'.'.join(f'{ord(char):x}' for char in value)}" for name, value in sorted(html.entities.html5.items())]
    lines = [" ".join(entries[start:start + PER_LINE]) for start in range(0, len(entries), PER_LINE)]
    body = " +\n".join(f'        "{line} "' for line in lines)
    return (
        "package vn.abook.player\n\n"
        "// SINH TỰ ĐỘNG bởi tests/html_entities_kotlin.py từ `html.entities.html5` của Python - đừng sửa tay.\n\n"
        "/** Mọi thực thể có tên của HTML5 (cả tên cũ không có dấu chấm phẩy), như `html.unescape` của Python dùng: tên -> chữ. */\n"
        "internal object HtmlEntities {\n"
        "    private const val TABLE =\n"
        f"{body}\n\n"
        "    val byName: Map<String, String> by lazy {\n"
        "        TABLE.trim().split(' ').associate { entry ->\n"
        "            val name = entry.substringBefore('=')\n"
        "            name to entry.substringAfter('=').split('.').joinToString(\"\") { String(Character.toChars(it.toInt(16))) }\n"
        "        }\n"
        "    }\n"
        "}\n"
    )


if __name__ == "__main__":
    TARGET.write_bytes(render().encode("utf-8"))
    print(TARGET)
