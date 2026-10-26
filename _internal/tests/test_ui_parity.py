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


def test_ui_parity_hard_rules_pass_with_a_readable_message():
    tool = _tool()
    problems = tool.hard_checks(tool.web_scan(), tool.native_scan())
    assert not problems, "luật cứng chữ / icon / cặp màn:\n" + "\n".join(problems[:40])


def test_pairs_file_is_honest():
    tool = _tool()
    specs = tool.pair_specs()
    assert specs and len({s["id"] for s in specs}) == len(specs)
    web, native = tool.web_scan(), tool.native_scan()
    for spec in specs:
        d = tool.pair_diff(web, native, spec)
        assert d["web_files"] and d["native_files"], f"cặp {spec['id']} không khớp file nào"
        for kind in ("allow", "missing", "deferred"):
            for entry in spec.get(kind, []):
                assert entry["side"] in ("web", "native") and entry.get("reason", "").strip(), f"{spec['id']}.{kind}: thiếu lý do / phía: {entry}"
                assert ("label" in entry) + ("match" in entry) + ("file" in entry) == 1, f"{spec['id']}.{kind}: cần đúng một trong label / match / file: {entry}"


def test_copy_rules_catch_what_they_promise():
    tool = _tool()
    for bad in ("Khóa giọng", "Hòa âm", "Thúy", "Tùy chọn", "Xóa", "Luật Òe"):
        assert tool.NEW_TONE.search(bad), bad
    for good in ("Khoá giọng", "Hoà âm", "Thuý", "Tuỳ chọn", "Xoá", "Quý"):
        assert not tool.NEW_TONE.search(good), good
    for bad in ('"Đang gửi…"', "Lưu thành…", "toast(`Đang mở trên ${name}…`)", '"Đang đọc..."'):
        assert tool.ELLIPSIS_END.search(bad), bad
    for good in ('"…"', '"…hoặc dán đường dẫn"', "`${text.slice(0, 5)}…`", "Vân tay <b>ab</b>"):
        assert not tool.ELLIPSIS_END.search(good), good


def test_icon_table_flags_a_wrong_icon():
    tool = _tool()
    table = dict(tool.icon_table())
    assert table.get("bỏ ghép") == "unplug" and table.get("đọc theo") == "text-align-start"
    assert tool.alias_target("trash-2") == tool.alias_target("trash")
    wrong = tool.Scan()
    wrong.pairs.append(tool.Pair("native", "ui/x.kt", 1, "Bỏ ghép", "x", "call"))
    assert tool.icon_violations(tool.Scan(), wrong)
