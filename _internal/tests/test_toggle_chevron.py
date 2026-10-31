"""Mũi tên phải ở mép phải hàng chỉ dành cho hàng mở trang con (soát UI nhạc 01-11 mục 3, Lead duyệt).

Hàng gập mở tại chỗ (Tìm hiểu thêm, khối gập của Cài đặt, "Đang phát") mà mang ">" ở mép phải thì trông y như hàng đi tới một trang nữa:
người dùng bấm "Phân tích nhạc" chờ sang trang, chỉ thấy một câu trợ giúp mở ra. Hàng ấy mang mũi tên xuống, lật lên khi mở - thành phần
chung lo việc này (web: DisclosureRow `expanded`, Qt: DisclosureRow.qml `expanded`, điện thoại: ChevronIcon `turn`).

Máy dò đọc nguồn ba nền, bắt chỗ tự vẽ lại mũi tên phải rồi xoay nó để làm hàng gập:
  - Qt: khối `Icon { name: "chevron-right" ... }` vừa neo mép phải (`anchors.right`) vừa có `rotation:`;
  - web: `<ChevronRight` trong file có `aria-expanded` (nút gập), hay mang lớp xoay `rotate-90`;
  - điện thoại: `rotate(` quanh `LucidePaths.CHEVRON_RIGHT`.
Mũi tên nhỏ ĐẦU dòng của khối chi tiết (VoiceDetails, StudioMusicDetails...) là kiểu tam giác gập quen thuộc, không đứng ở mép phải, nên không bị bắt.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "desktop_qt" / "qml"
WEB = ROOT / "ui" / "src"
PHONE = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java"


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name


def blocks(text: str, opener: str):
    """Các khối `opener {...}` (ngoặc nhọn cân bằng) của một file QML."""
    for match in re.finditer(opener + r"\s*\{", text):
        i, depth = match.end(), 1
        while depth and i < len(text):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        yield text.count("\n", 0, match.start()) + 1, text[match.start():i]


def qt_trailing_toggle_chevrons(root: Path = QML) -> list[str]:
    found = []
    for path in sorted(root.rglob("*.qml")):
        for line, block in blocks(path.read_text(encoding="utf-8"), r"\bIcon"):
            if re.search(r'\bname\s*:\s*"chevron-right"\s*(;|//|$)', block, re.M) and "anchors.right" in block and re.search(r"\brotation\s*:", block):
                found.append(f"{rel(path)}:{line}")
    return found


def web_toggle_chevrons(root: Path = WEB) -> list[str]:
    found = []
    for path in sorted(root.rglob("*.tsx")):
        if ".test." in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"<ChevronRight\b[^>]*>", text):
            if "aria-expanded" in text or "rotate-90" in match.group(0):
                found.append(f"{rel(path)}:{text.count(chr(10), 0, match.start()) + 1}")
    return found


def phone_turned_right_chevrons(root: Path = PHONE) -> list[str]:
    found = []
    for path in sorted(root.rglob("*.kt")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"rotate\([^{]*\{[^}]*CHEVRON_RIGHT", text):
            found.append(f"{rel(path)}:{text.count(chr(10), 0, match.start()) + 1}")
    return found


def test_no_trailing_right_chevron_turns_into_a_fold_on_any_platform():
    assert qt_trailing_toggle_chevrons() == []
    assert web_toggle_chevrons() == []
    assert phone_turned_right_chevrons() == []


def test_the_shared_rows_pick_the_down_chevron_for_folds():
    qt = (QML / "DisclosureRow.qml").read_text(encoding="utf-8")
    assert 'root.toggles ? "chevron-down" : "chevron-right"' in qt
    assert "property var expanded: undefined" in qt
    web = (WEB / "shared" / "DisclosureRow.tsx").read_text(encoding="utf-8")
    assert "expanded === undefined ? ChevronRight : ChevronDown" in web
    phone = (PHONE / "vn" / "abook" / "player" / "ui" / "components" / "Controls.kt").read_text(encoding="utf-8")
    assert "LucidePaths.CHEVRON_DOWN" in phone


def test_the_detector_catches_the_old_rows(tmp_path):
    """Kiểm lực: chính ba cách vẽ cũ (trước 01-11) phải bị bắt."""
    (tmp_path / "Row.qml").write_text(
        'Interactive {\n    Icon {\n        anchors.right: parent.right\n        name: "chevron-right"\n        rotation: root.open ? 90 : 0\n    }\n}\n',
        encoding="utf-8")
    (tmp_path / "Lead.qml").write_text(
        'Interactive {\n    Icon {\n        name: "chevron-right"\n        rotation: root.open ? 90 : 0\n    }\n}\n', encoding="utf-8")
    assert qt_trailing_toggle_chevrons(tmp_path) == ["Row.qml:2"]  # mũi tên nhỏ đầu dòng (Lead.qml) không bị bắt
    (tmp_path / "Row.tsx").write_text(
        '<button aria-expanded={open}><ChevronRight className={cn("size-4", open && "rotate-90")} /></button>', encoding="utf-8")
    assert web_toggle_chevrons(tmp_path) == ["Row.tsx:1"]
    (tmp_path / "Row.kt").write_text(
        "rotate(90f * turn(), pivot = c) {\n    drawLucide(LucidePaths.CHEVRON_RIGHT, color, unit)\n}\n", encoding="utf-8")
    assert phone_turned_right_chevrons(tmp_path) == ["Row.kt:1"]
