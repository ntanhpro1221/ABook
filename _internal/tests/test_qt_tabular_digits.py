"""Luật R2 (soát thiết kế 10-11, DESIGN.md 5.5) cho Qt: chữ số đều độ rộng (`tnum`) chỉ cho số đổi tại chỗ và cột số của bảng.

Gắn `tnum` vào chữ chạy làm "1" hở hai bên ("1 0 phút", "còn 2 9 phút", "4/1 0 chương"). Số đổi tại chỗ đi qua ClockLabel.qml; mọi chỗ
khác phải nằm trong danh sách có tên dưới đây VÀ dòng ấy mang chú thích `// tnum-ok: <lý do>`.
"""
from __future__ import annotations

import re
from pathlib import Path

QML = Path(__file__).resolve().parents[1] / "desktop_qt" / "qml"

CLOCK = "ClockLabel.qml"
# File: lý do. Mỗi dòng tnum trong các file này còn phải tự ghi `// tnum-ok:`.
ALLOWED = {
    "ImportChapters.qml": "cột số thứ tự và số chữ của bảng chương nhập",
    "NewChapters.qml": "cột số thứ tự và số chữ / ký tự của bảng tệp",
    "StudioChapterRow.qml": "cột số chương, độ dài, đã xong của bảng chương Studio",
    "ProjectRow.qml": "cột 'cập nhật' của bảng dự án",
    "ProjectScreen.qml": "cột giờ của nhật ký việc",
}
# Chỗ bật chế độ tabular của VoiceNote: chỉ cho chữ có phần trăm tự đổi.
TABULAR_USERS = {"VoiceModule.qml": "phần trăm tải giọng đổi tại chỗ"}

TNUM = re.compile(r'"tnum"')
TABULAR = re.compile(r"\btabular\s*:\s*true\b")


def code(line: str) -> str:
    return line.split("//", 1)[0]


def offenders(name: str, text: str) -> list[str]:
    if name == CLOCK:
        return []
    found = []
    for number, line in enumerate(text.split("\n"), 1):
        if TNUM.search(code(line)) and not (name in ALLOWED and "// tnum-ok:" in line):
            found.append(f"{name}:{number}: {line.strip()[:100]}")
        if TABULAR.search(code(line)) and name not in TABULAR_USERS:
            found.append(f"{name}:{number}: tabular: true ngoài danh sách - {line.strip()[:80]}")
    return found


def test_tnum_only_in_clock_label_and_named_table_cells():
    found = [o for path in sorted(QML.rglob("*.qml")) for o in offenders(path.relative_to(QML).as_posix(), path.read_text(encoding="utf-8"))]
    assert found == [], "tnum ngoài ClockLabel và cột số có tên (số trong câu phải là số tỉ lệ):\n" + "\n".join(found)


def test_named_exceptions_still_use_tnum():
    for name in [*ALLOWED, CLOCK]:
        text = (QML / name).read_text(encoding="utf-8")
        assert TNUM.search(text), f"{name} không còn tnum: bỏ khỏi ALLOWED"
    for name in TABULAR_USERS:
        assert TABULAR.search((QML / name).read_text(encoding="utf-8")), f"{name} không còn tabular: true"


def test_rule_sees_tnum_and_nothing_else():
    assert offenders("BookPage.qml", 'Text {\n    font.features: { "tnum": 1 }\n}') == ['BookPage.qml:2: font.features: { "tnum": 1 }']
    assert offenders("NewChapters.qml", 'font.features: { "tnum": 1 }') != []           # có tên nhưng thiếu chú thích
    assert offenders("NewChapters.qml", 'font.features: { "tnum": 1 }   // tnum-ok: cột số') == []
    assert offenders("BookPage.qml", '// tnum chỉ ở ClockLabel\nText { text: "tnumber" }') == []
    assert offenders(CLOCK, 'font.features: {"tnum": 1}') == []
    assert offenders("SleepWindow.qml", "Select { tabular: true }") != []
