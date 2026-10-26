"""docs/UI_PARITY.md (bảng lệch chữ / icon giữa web và native) phải khớp mã nguồn - sinh bằng scripts/ui_parity.py.

Giai đoạn này chỉ kiểm file sinh ra còn mới; BẢN THÂN chỗ lệch (chữ khác nhau, icon khác nhau) được báo cáo trong file chứ không làm test hỏng.
"""
import importlib.util
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ui_parity.py"


def _tool():
    spec = importlib.util.spec_from_file_location("ui_parity", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ui_parity"] = module  # @dataclass tra cứu module của lớp qua sys.modules
    spec.loader.exec_module(module)
    return module


def test_ui_parity_doc_is_up_to_date():
    tool = _tool()
    assert tool.main(["--check"]) == 0, "docs/UI_PARITY.md lệch mã nguồn: chạy scripts/ui_parity.py"


def test_ui_parity_doc_uses_lf_and_keeps_markers():
    tool = _tool()
    raw = tool.DOC.read_bytes()
    assert b"\r" not in raw
    text = raw.decode("utf-8")
    assert text.count(tool.BEGIN) == 1 and text.count(tool.END) == 1


def test_ui_parity_is_deterministic_and_fast():
    tool = _tool()
    start = time.monotonic()
    first = tool.render_body()
    assert time.monotonic() - start < 30
    assert first == tool.render_body()


def test_ui_parity_extracts_both_sides_and_pairs_icons():
    tool = _tool()
    web, native = tool.web_scan(), tool.native_scan()
    assert len(web.items) > 500 and len(native.items) > 200
    # Menu sách native: nhãn "Sửa thông tin" đi với icon bút chì lucide; web cùng việc cùng icon.
    assert any(p.label == "Sửa thông tin" and p.icon == "pencil" for p in native.pairs)
    assert any(p.label == "Sửa thông tin" and p.icon == "pencil" for p in web.pairs)
    assert tool.lucide_name("MoreHorizontal") == "ellipsis"
