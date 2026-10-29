"""Bản Qt ghi cỡ file bằng MỘT hàm: desktop_qt/qml/SizeFormat.js (= shared/format.ts formatSize của bản web, hệ 1024).

Trước 29-10 có năm bản tự tính (bốn bản hệ 10, một bản hệ 1024), nên cùng một file hiện "5,0 MB" ở Studio mà "4,8 MB" ở Cài đặt. Máy dò này
chặn bản tự tính mới: hàm cỡ file định nghĩa ngoài SizeFormat.js, hay phép chia cho 1e3 / 1e6 / 1e9 để ra KB / MB / GB.
"""
import re
from pathlib import Path

QML = Path(__file__).resolve().parent.parent / "desktop_qt" / "qml"
SHARED = "SizeFormat.js"
OWN_FORMATTER = re.compile(r"function\s+(formatSize|formatBytes|gigabytes|megabytes)\s*\(")
DECIMAL_UNITS = re.compile(r"/\s*1e[369]\b")


def own_size_formatters(root=QML):
    hits = []
    for path in sorted(list(root.glob("*.js")) + list(root.glob("*.qml"))):
        if path.name == SHARED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if OWN_FORMATTER.search(line) or DECIMAL_UNITS.search(line):
                hits.append(f"{path.name}:{number}: {line.strip()}")
    return hits


def test_one_size_formatter():
    hits = own_size_formatters()
    assert not hits, "dùng SizeFormat.js formatSize thay vì tự tính:\n" + "\n".join(hits)


def test_detector_sees_a_private_formatter(tmp_path):
    (tmp_path / "Old.js").write_text('function formatSize(bytes) { return (bytes / 1e9).toFixed(2) + " GB" }\n', encoding="utf-8")
    (tmp_path / "Inline.qml").write_text('Text { text: (size / 1e6).toFixed(1) + " MB" }\n', encoding="utf-8")
    (tmp_path / SHARED).write_text("function formatSize(bytes) { return bytes / 1e9 }\n", encoding="utf-8")
    assert [h.split(":")[0] for h in own_size_formatters(tmp_path)] == ["Inline.qml", "Old.js"]
