"""docs/UI_PARITY.md (bảng lệch chữ / icon giữa web và native) phải khớp mã nguồn - sinh bằng scripts/ui_parity.py.

Giai đoạn này chỉ kiểm file sinh ra còn mới; BẢN THÂN chỗ lệch (chữ khác nhau, icon khác nhau) được báo cáo trong file chứ không làm test hỏng.
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

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
        for kind in ("allow", "missing", "deferred", "wording_for_lead"):
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


# --- máy dò phải CẮN: dựng cây nguồn giả (web + Kotlin) trong thư mục tạm, trỏ máy dò vào đó, không đụng file thật -------------------------

WEB_TSX = """export function Screen() {
  return (
    <div>
      <button>{label}</button>
    </div>
  );
}
""".replace("{label}", "%s")
KT_SCREEN = """package vn.abook.player.ui.screens

fun Screen() {
    BasicText("%s")
}
"""


def _synthetic(tool, monkeypatch, tmp_path, web_label, native_label, spec_extra=None, web_extra=None, native_extra=None):
    """Một màn web (desktop/Screen.tsx) và một màn native (screens/Screen.kt) cặp với nhau trong `tmp_path`; trả về (web_scan, native_scan)."""
    web_dir = tmp_path / "ui" / "src" / "desktop"
    kt_dir = tmp_path / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player" / "ui" / "screens"
    web_dir.mkdir(parents=True)
    kt_dir.mkdir(parents=True)
    for d in ("listen", "shared", "studio"):
        (tmp_path / "ui" / "src" / d).mkdir()
    (web_dir / "Screen.tsx").write_bytes((WEB_TSX % web_label + (web_extra or "")).encode("utf-8"))
    (kt_dir / "Screen.kt").write_bytes((KT_SCREEN % native_label + (native_extra or "")).encode("utf-8"))
    spec = {"id": "synthetic", "web": ["desktop/Screen.tsx"], "native": ["screens/Screen.kt"], "sentences": True}
    spec.update(spec_extra or {})
    pairs = tmp_path / "pairs.json"
    pairs.write_bytes(json.dumps({"_doc": "x", "pairs": [spec]}, ensure_ascii=False).encode("utf-8"))
    monkeypatch.setattr(tool, "WEB", tmp_path / "ui" / "src")
    monkeypatch.setattr(tool, "KT", kt_dir.parent)
    monkeypatch.setattr(tool, "KT_CORE", kt_dir.parent.parent)
    monkeypatch.setattr(tool, "PAIRS", pairs)
    monkeypatch.setattr(tool, "rel", lambda path: path.relative_to(tmp_path).as_posix())
    monkeypatch.setattr(tool, "icon_wrappers", lambda: {})
    monkeypatch.setattr(tool, "glyph_icons", lambda: {})
    return tool.web_scan(), tool.native_scan()


def test_detector_bites_a_label_that_differs_between_native_and_desktop(monkeypatch, tmp_path):
    tool = _tool()
    web, native = _synthetic(tool, monkeypatch, tmp_path, "Xoá khỏi thư viện", "Xoá khỏi điện thoại")
    problems = tool.hard_checks(web, native)
    assert any("[synthetic] chỉ có ở web" in p and "Xoá khỏi thư viện" in p for p in problems), problems
    assert any("[synthetic] chỉ có ở native" in p and "Xoá khỏi điện thoại" in p for p in problems), problems


def test_detector_passes_when_both_sides_say_the_same(monkeypatch, tmp_path):
    tool = _tool()
    web, native = _synthetic(tool, monkeypatch, tmp_path, "Thêm sách", "Thêm sách")
    assert tool.hard_checks(web, native) == []


def test_detector_pairs_are_checked_both_ways_unless_only_says_otherwise(monkeypatch, tmp_path):
    tool = _tool()
    web, native = _synthetic(tool, monkeypatch, tmp_path, "Chỉ ở máy tính", "Chỉ ở điện thoại", {"only": "native"})
    problems = tool.hard_checks(web, native)
    assert any("chỉ có ở native" in p for p in problems) and not any("chỉ có ở web" in p for p in problems), problems
    web, native = _synthetic(tool, monkeypatch, tmp_path / "again", "Chỉ ở máy tính", "Chỉ ở điện thoại", {"only": "web"})
    problems = tool.hard_checks(web, native)
    assert any("chỉ có ở web" in p for p in problems) and not any("chỉ có ở native" in p for p in problems), problems


@pytest.mark.parametrize("kind", ["allow", "missing", "wording_for_lead"])
def test_listed_label_is_excused_only_on_its_own_side(kind, monkeypatch, tmp_path):
    tool = _tool()
    entries = [{"side": "native", "label": "Xoá khỏi điện thoại", "reason": "test"}, {"side": "web", "label": "Xoá khỏi thư viện", "reason": "test"}]
    web, native = _synthetic(tool, monkeypatch, tmp_path, "Xoá khỏi thư viện", "Xoá khỏi điện thoại", {kind: entries})
    assert tool.hard_checks(web, native) == []
    diff = tool.pair_diff(web, native, tool.pair_specs()[0])
    counted = {"allow": "allowed", "missing": "missing", "wording_for_lead": "wording"}[kind]
    assert len(diff[counted]) == 2
    # Mục khai nhầm phía không che được nhãn của phía kia.
    wrong = [{"side": "web", "label": "Xoá khỏi điện thoại", "reason": "test"}, {"side": "native", "label": "Xoá khỏi thư viện", "reason": "test"}]
    web, native = _synthetic(tool, monkeypatch, tmp_path / "wrong", "Xoá khỏi thư viện", "Xoá khỏi điện thoại", {kind: wrong})
    assert len(tool.hard_checks(web, native)) == 2


def test_every_native_screen_file_belongs_to_a_checked_pair():
    """Màn native mới phải được ghép với một màn máy tính (hay khai tường minh là bỏ qua): không file nào có chữ mà không ai so."""
    tool = _tool()
    native = tool.native_scan()
    names = sorted({i.file[len(tool.NATIVE_ROOT):] for i in native.items})
    checked: set[str] = set()
    for spec in tool.pair_specs():
        if spec.get("only") != "web":  # `only: web` không đòi nhãn native phải có ở web
            checked |= set(tool.match_files(spec["native"], names))
    skipped = {n for n in names if any(skip.split(":")[0].endswith(n) or n.endswith(skip.split(":")[0]) for skip in tool.COPY_SKIP_NATIVE)}
    skipped |= {"editbook/EditBooks.kt"}  # tên chương giả "Chương N" cho sách chưa đọc được, không phải chữ giao diện
    loose = [n for n in names if n not in checked and n not in skipped]
    assert not loose, "file native có chữ mà không cặp màn nào so với máy tính (thêm vào scripts/ui_parity_pairs.json): " + ", ".join(loose)
