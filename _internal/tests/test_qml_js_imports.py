"""Mỗi `Bí_danh.tên` mà QML / JS của bản Qt đọc từ một file .js đã import phải có thật trong file ấy (soát UI nhạc 01-11).

Loại lỗi: EditBookLogic.js thôi chép các chữ "Nhạc của tôi" (một nguồn: MyMusicText.js) nhưng StudioMusicSwap.qml vẫn gọi
`Book.mineNote` qua bí danh "Book" - QML không báo gì lúc nạp, chỉ ném TypeError khi dòng ấy chạy, dòng phụ của bài rỗng.
qmllint (tools/check_qml_members.py) chỉ biết kiểu C++ / QML, không biết hàm của thư viện .js. Máy dò đọc nguồn: mọi
`import "X.js" as A` / `.import "X.js" as A`, rồi mọi `A.tên` trong file phải là `var` / `function` / `const` / `let`
khai ở đầu dòng của X.js, hay tên của một `.import` lồng trong X.js.
"""
from __future__ import annotations

import re
from pathlib import Path

QML = Path(__file__).resolve().parents[1] / "desktop_qt" / "qml"
IMPORT = re.compile(r'^\s*\.?import\s+"([A-Za-z0-9_]+\.js)"\s+as\s+([A-Za-z_]\w*)', re.M)


def declared(js: Path) -> set[str]:
    text = js.read_text(encoding="utf-8")
    names = set(re.findall(r"^(?:var|let|const|function)\s+([A-Za-z_$][\w$]*)", text, re.M))
    return names | {alias for _, alias in IMPORT.findall(text)}


def missing(root: Path = QML) -> list[str]:
    cache: dict[Path, set[str]] = {}
    found = []
    for path in sorted([*root.glob("*.qml"), *root.glob("*.js")]):
        text = path.read_text(encoding="utf-8")
        for file, alias in IMPORT.findall(text):
            js = path.parent / file
            if not js.exists():
                found.append(f"{path.name}: {file} không có")
                continue
            names = cache.setdefault(js, declared(js))
            for match in re.finditer(r"(?<![\w.$\"/])" + re.escape(alias) + r"\.([A-Za-z_$][\w$]*)", text):
                if match.group(1) not in names:
                    found.append(f"{path.name}:{text.count(chr(10), 0, match.start()) + 1}: {alias}.{match.group(1)} không có trong {file}")
    return found


def test_every_name_read_from_an_imported_js_exists():
    assert missing() == []


def test_the_detector_catches_a_dropped_alias(tmp_path):
    """Kiểm lực: chính lỗi 01-11 (hàm đã dời sang file khác, chỗ gọi cũ còn đó) phải bị bắt."""
    (tmp_path / "Logic.js").write_text('.import "Text.js" as Mine\nvar INTRO = "x"\nfunction swap(a) { return a }\n', encoding="utf-8")
    (tmp_path / "Text.js").write_text("function mineNote(item) { return item }\n", encoding="utf-8")
    (tmp_path / "Row.qml").write_text('import "Logic.js" as Book\nText { text: Book.INTRO + Book.mineNote(x) + Book.Mine.mineNote(x) }\n', encoding="utf-8")
    assert missing(tmp_path) == ["Row.qml:2: Book.mineNote không có trong Logic.js"]
