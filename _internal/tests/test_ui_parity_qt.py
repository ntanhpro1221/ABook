"""docs/UI_PARITY_QT.md (bảng lệch chữ / icon / bo góc giữa web máy tính và bản Qt) phải khớp mã nguồn - sinh bằng scripts/ui_parity_qt.py.

Chữ và icon lệch được báo cáo trong file chứ không làm test hỏng; riêng bo góc là luật cứng như web (radiusRules.test.ts) và điện thoại
(RadiusRulesTest.kt): QML chỉ dùng token của Theme.qml, tròn hay không bo.
"""
import importlib.util
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ui_parity_qt.py"


def _tool():
    spec = importlib.util.spec_from_file_location("ui_parity_qt", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ui_parity_qt"] = module  # @dataclass tra cứu module của lớp qua sys.modules
    spec.loader.exec_module(module)
    return module


def test_ui_parity_qt_doc_is_up_to_date():
    tool = _tool()
    assert tool.main(["--check"]) == 0, "docs/UI_PARITY_QT.md lệch mã nguồn: chạy scripts/ui_parity_qt.py"


def test_ui_parity_qt_doc_uses_lf_and_keeps_markers():
    tool = _tool()
    raw = tool.DOC.read_bytes()
    assert b"\r" not in raw
    text = raw.decode("utf-8")
    assert text.count(tool.BEGIN) == 1 and text.count(tool.END) == 1


def test_ui_parity_qt_is_deterministic_and_fast():
    tool = _tool()
    start = time.monotonic()
    first = tool.render_body()
    assert time.monotonic() - start < 30
    assert first == tool.render_body()


def test_qml_radius_uses_tokens_only():
    tool = _tool()
    assert tool.qt_scan().radii == [], "bo góc QML ngoài Theme.radiusControl / Cover / Sheet, tròn, 0 - xem docs/UI_PARITY_QT.md mục d"


def test_extracts_qt_text_and_pairs_icons():
    tool = _tool()
    qt = tool.qt_scan()
    pairs = {(p.label, p.icon) for p in qt.pairs}
    assert ("Thư viện", "library") in pairs                       # NavItem: text + icon cùng đối tượng
    assert {("Tạm dừng", "pause"), ("Phát", "play")} <= pairs      # PlayButton: hai nhánh `?:` cùng điều kiện, ghép theo thứ tự
    assert ("Thu nhỏ", "chevron-down") in pairs                    # IconButton: tip bỏ phần "(Esc)"
    assert ("Tới câu đang nghe", "locate") in pairs                # Icon cạnh Text trong một Row
    assert ("Về Thư viện", "arrow-left") in pairs                  # ScreenHeader { backLabel } -> IconButton của ScreenHeader
    texts = {i.text for i in qt.items}
    assert {"Chưa có sách", "Hết chương này", "Tốc độ đọc"} <= texts      # "Chưa có sách": EmptyLibrary của desktop/App.tsx
    assert not any(i.file.endswith("BenchScenario.qml") for i in qt.items)
    assert all(not t.startswith("Ctrl+") for t in texts)


def test_web_side_reads_labels_and_back_button():
    tool = _tool()
    web = tool.web_scan()
    assert any(p.label == "Về Thư viện" and p.icon == "arrow-left" for p in web.pairs)
    assert any(i.file.endswith("listen/labels.ts") and i.text == "Tạm dừng" for i in web.items)
    assert any(i.file.endswith("shared/SettingsNav.tsx") and i.text == "Nâng cao" for i in web.items)
    assert any(i.text == "Hẹn giờ đã tắt tiếng lúc" for i in web.items)   # chữ JSX trong JSX của thuộc tính `idle={...}`


def test_tray_and_mini_shared_labels_are_detected():
    tool = _tool()
    texts = {item.text for item in tool.qt_scan().items}
    assert {"Mở ABook", "Mở rộng", "Phát", "Tạm dừng", "Lùi {} giây", "Tới {} giây",
            "Chương trước", "Chương sau", "Cửa sổ mini", "Thoát ABook", "Ghim trên cùng",
            "Thu vào khay khi đóng", "Tự mở cửa sổ mini"} <= texts


def test_detector_catches_each_kind(tmp_path):
    tool = _tool()
    qml = tmp_path / "Probe.qml"
    qml.write_text(
        'import QtQuick\n'
        'Item {\n'
        '    Rectangle { radius: 6 }\n'
        '    Rectangle { radius: Theme.radiusControl - 2 }\n'
        '    Rectangle { radius: height / 2 }\n'
        '    Rectangle { radius: framed ? Theme.radiusSheet : 0 }\n'
        '    Rectangle { radius: big ? Theme.radiusSheet : 5 }\n'
        '    Text { text: "Nghe " + person.name + " nói" }\n'
        '    IconButton { icon: "moon"; tip: "Hẹn giờ  (Ctrl+T)" }\n'
        '    Row {\n'
        '        Icon { name: "check" }\n'
        '        Text { text: qsTr("Đã xong") }\n'
        '    }\n'
        '    property string note: "Hoà giải"\n'
        '    Text { text: state === "busy" ? "Đang mở..." : "Sẵn sàng" }\n'
        '}\n', encoding="utf-8")
    scan = tool.QtScan()
    tool.qml_scan_file(qml, scan)
    assert [r[2] for r in scan.radii] == ["6", "Theme.radiusControl - 2", "big ? Theme.radiusSheet : 5"]
    assert ("Hẹn giờ", "moon") in {(p.label, p.icon) for p in scan.pairs}
    assert ("Đã xong", "check") in {(p.label, p.icon) for p in scan.pairs}
    assert [s[0] for s in scan.spaced] == ["Hẹn giờ  (Ctrl+T)"]
    assert ("Hẹn giờ", "Ctrl+T") in {(s[0], s[1]) for s in scan.shortcuts}
    texts = {i.text for i in scan.items}
    assert {"Hoà giải", "Đang mở...", "Sẵn sàng", "Đã xong", "Nghe {} nói"} <= texts and "busy" not in texts
    assert "Nghe " not in texts and " nói" not in texts
    js = tmp_path / "ProbeLogic.js"
    js.write_text('function label(p) { return "Bỏ gộp " + p.from + " vào " + p.into }\nvar KEY = "cast"\n', encoding="utf-8")
    scan = tool.QtScan()
    tool.js_scan_file(js, scan)
    assert [i.text for i in scan.items] == ["Bỏ gộp {} vào {}"]
    assert tool.template_hit("Lùi 15 giây", ["Lùi {} giây"]) and not tool.template_hit("Lùi 15 giây", ["Tới {} giây"])
