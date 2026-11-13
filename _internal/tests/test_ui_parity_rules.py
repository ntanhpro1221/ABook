"""Ten cross-platform UI rules (scripts/ui_parity_rules.py): each holds on the real sources, and each bites a planted violation.

Lead 12-11 (soát đồng nhất ba nền): one task, one word, one token, one shape on web, Qt and Android. The rules compare Qt with
Android directly, read the dictionary's "Thay cho" column, demand every colour token on all three, keep spacing / type / weight on
the scale, give each shared component one radius role, read motion timings from tokens, count hard show/hide (only down), name
every "…" button "Thêm tuỳ chọn…", keep labels at four words and pin same-control pairs to one key.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ui_parity_rules.py"


def _tool():
    spec = importlib.util.spec_from_file_location("ui_parity_rules", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ui_parity_rules"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("rule", ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10"])
def test_rule_holds_on_the_sources(rule):
    tool = _tool()
    problems = tool.RULES[rule]()
    assert not problems, f"{rule}:\n" + "\n".join(problems[:60])


def test_every_exception_has_a_reason():
    cfg = _tool().config()
    for rule, block in cfg.items():
        if not isinstance(block, dict):
            continue
        for kind in ("allow", "web_only"):
            for entry in block.get(kind, []):
                assert entry.get("reason", "").strip(), f"{rule}.{kind}: thiếu lý do: {entry}"


# --- planted violations: a tiny source tree in tmp_path ---------------------------------------------------------------------------
VI = {"s_a": "Chưa có sách", "s_b": "Chưa có sách trên máy", "s_c": "Thử giọng", "s_d": "Nghe thử", "s_e": "Tuỳ chọn {0}",
      "s_f": "Thêm tuỳ chọn cho {0}", "s_g": "Thu vào khay khi đóng cửa sổ", "s_h": "Bỏ số gọi", "s_i": "Không đọc số chú thích"}
DOC = """# x
## Từ điển chữ chung

| Việc | Viết | Thay cho | Lý do |
|---|---|---|---|
| Nghe mẫu một giọng | Nghe thử | Thử giọng | x |
| Thêm máy | Ghép thiết bị | x | x |
| Ghép | Thêm máy | Ghép thiết bị | x |

<!-- ui_parity:begin -->
"""
CONFIG = {"L1": {"screens": [{"id": "lib", "qt": ["desktop_qt/qml/Lib.qml"], "android": ["mobile/android/app/src/main/java/vn/abook/player/ui/Lib.kt"]}], "allow": []},
          "L2": {"allow": []}, "L3": {"web_only": [], "allow": []}, "L4": {"allow": [], "remaining": {}}, "L5": {"components": []},
          "L6": {"uses": []}, "L7": {"fixed": [], "remaining": {}}, "L9": {"allow": []},
          "L10": {"controls": [{"id": "marks", "at": {"qt": {"file": "desktop_qt/qml/Lib.qml", "key": "s_i"},
                                                      "android": {"file": "mobile/android/app/src/main/java/vn/abook/player/ui/Lib.kt", "key": "s_h"}}}]}}
QML = """import QtQuick
Item {
    Text { text: S.s_a }
    Text { text: S.s_c; font.pixelSize: 13; font.weight: 600 }
    Rectangle { color: "#2a2723"; visible: root.ready }
    IconButton { icon: "ellipsis"; Accessible.name: S.s_e(root.title) }
    Button { text: S.s_g }
    Text { text: S.s_i; anchors.leftMargin: 6 }
}
"""
KT = """package vn.abook.player.ui
fun Lib() {
    BasicText(S.s_b)
    BasicText(S.s_h, Modifier.padding(top = 2.dp))
    Box(Modifier.background(Color.Black))
    if (ready) PlayerAlert(S.s_d)
}
"""


@pytest.fixture
def planted(tmp_path, monkeypatch):
    tool = _tool()
    files = {
        "ui_strings/vi.json": json.dumps({"strings": VI}, ensure_ascii=False),
        "docs/UI_PARITY.md": DOC,
        "scripts/ui_parity_rules.json": json.dumps(CONFIG, ensure_ascii=False),
        "desktop_qt/qml/Lib.qml": QML,
        "mobile/android/app/src/main/java/vn/abook/player/ui/Lib.kt": KT,
        "ui/src/listen/Lib.tsx": 'export const X = () => <div className="gap-1.5 font-semibold text-[0.8125rem]">{ready && <Alert />}</div>;\n',
    }
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    monkeypatch.setattr(tool, "CONFIG", tmp_path / "scripts/ui_parity_rules.json")
    return tool


def test_l1_bites_qt_and_android_saying_one_thing_two_ways(planted):
    problems = planted.l1_cross_platform()
    assert any("'Chưa có sách'" in p and "'Chưa có sách trên máy'" in p for p in problems), problems


def test_l2_bites_a_retired_word_and_a_self_contradicting_dictionary(planted):
    problems = planted.l2_banned_words()
    assert any("'Thử giọng'" in p and "Lib.qml" in p for p in problems), problems
    assert any("tự mâu thuẫn" in p and "Ghép thiết bị" in p for p in problems), problems


def test_l3_bites_a_hand_written_colour_on_qt_and_android(planted):
    hits = planted.hand_colours()
    assert any("Lib.qml" in p and "#2a2723" in p for p in hits) and any("Lib.kt" in p and "Color.Black" in p for p in hits), hits


def test_l4_counts_off_scale_spacing_type_and_weight_on_all_three(planted):
    hits = {(rule, planted._platform(path), token) for rule, path, _line, token in planted.scale_hits()}
    assert ("type", "qt", "font.pixelSize: 13") in hits and ("weight", "qt", "font.weight: 600") in hits
    assert ("space", "qt", "anchors.leftMargin: 6") in hits and any(r == "space" and p == "android" for r, p, _t in hits)
    assert {("space", "web", "gap-1.5"), ("weight", "web", "font-semibold"), ("type", "web", "text-[0.8125rem]")} <= hits
    problems = planted.l4_scale()
    assert any("chỉ được giảm" in p for p in problems), problems


def test_l7_ratchet_only_goes_down(planted, monkeypatch):
    hits = planted.instant_hits()
    files = {path for path, _i, _l in hits}
    assert {"desktop_qt/qml/Lib.qml", "mobile/android/app/src/main/java/vn/abook/player/ui/Lib.kt", "ui/src/listen/Lib.tsx"} <= files, hits
    assert any("chỉ được giảm" in p for p in planted.l7_instant())
    cfg = planted.config()
    cfg["L7"]["remaining"] = {f: 9 for f in files}
    (planted.ROOT / "scripts/ui_parity_rules.json").write_bytes(json.dumps(cfg, ensure_ascii=False).encode("utf-8"))
    assert all("hạ số" in p for p in planted.l7_instant())  # fixed more than the list says: the list must be lowered too


def test_l8_bites_an_ellipsis_button_with_the_wrong_name(planted):
    problems = planted.l8_ellipsis_names()
    assert any("Lib.qml" in p and "Tuỳ chọn {0}" in p for p in problems), problems


def test_l9_bites_a_five_word_button(planted):
    assert any("Thu vào khay khi đóng cửa sổ" in p for p in planted.l9_label_length())


def test_l10_bites_one_control_with_two_words(planted):
    problems = planted.l10_control_pairs()
    assert any("[marks]" in p and "chữ khác" in p for p in problems), problems
