"""Twelve cross-platform UI rules (scripts/ui_parity_rules.py): each holds on the real sources, and each bites a planted violation.

Lead 12-11 (soát đồng nhất ba nền): one task, one word, one token, one shape on web, Qt and Android. The rules compare Qt with
Android directly, read the dictionary's "Thay cho" column, demand every colour token on all three, keep spacing / type / weight on
the scale, give each shared component one radius role, read motion timings from tokens, count hard show/hide (only down), name
every "…" button "Thêm tuỳ chọn…", keep labels at four words, pin same-control pairs to one key and start every row
summary with a capital (L11, 0.4.169) and make every floating layer swallow the taps in its frame (L12, 0.4.174).
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


@pytest.mark.parametrize("rule", ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10", "L11", "L12"])
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
@Composable fun PlayerAlert(text: String) {}
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


def test_l7_confirmed_repairs_cannot_be_hidden_by_a_nearby_animation(planted):
    cfg = planted.config()
    cfg["L7"]["fixed"] = [{"file": "desktop_qt/qml/Lib.qml", "match": "visible: root.ready", "what": "confirmed repair"}]
    planted.CONFIG.write_text(json.dumps(cfg), encoding="utf-8")
    path = planted.ROOT / "desktop_qt/qml/Lib.qml"
    path.write_text('Item {\n    Button { visible: root.ready }\n    Collapse { open: root.other }\n}', encoding="utf-8")
    assert any("confirmed repair" in p for p in planted.l7_instant())


def _categories(planted):
    return {(r["path"].rsplit("/", 1)[-1], r["line"]): r["category"] for r in planted.instant_rows()}


def test_l7_proves_safe_qt_sites_by_structure_not_by_line(planted):
    (planted.ROOT / "desktop_qt/qml/Lib.qml").write_text("""import QtQuick
Item {
    id: root
    readonly property bool wide: width >= 720
    property real shown: 0
    Behavior on shown { NumberAnimation {} }
    Text { id: probe; visible: false }
    Rectangle { visible: opacity > 0; opacity: root.ready ? 1 : 0; Behavior on opacity { NumberAnimation {} } }
    Item { visible: shown > 0 }
    Text { visible: root.wide }
    Item { height: root.grow; visible: root.grow > 0 }
    Rectangle { visible: root.ready }
    Rectangle { Reveal { shown: root.ready } }
}
""", encoding="utf-8")
    got = _categories(planted)
    assert got[("Lib.qml", 7)] == "b-constant" and got[("Lib.qml", 8)] == "b-follows-opacity"
    assert got[("Lib.qml", 9)] == "b-animated-clock" and got[("Lib.qml", 10)] == "b-responsive"
    assert got[("Lib.qml", 11)] == "b-zero-size"
    assert got[("Lib.qml", 12)] == "a-hard"  # a fade elsewhere in the file proves nothing about this row
    assert ("Lib.qml", 13) not in got  # Reveal is the repair, not a site


def test_l7_reveal_inside_a_default_property_holder_must_name_its_target(planted):
    qml = planted.ROOT / "desktop_qt/qml"
    (qml / "Card.qml").write_text("import QtQuick\nItem { default property alias content: body.data; Column { id: body } }\n", encoding="utf-8")
    (qml / "Lib.qml").write_text("import QtQuick\nItem {\n    Card { Reveal { shown: root.a } }\n    Card { id: c; Reveal { target: c; shown: root.a } }\n}\n",
                                 encoding="utf-8")
    problems = [p for p in planted.l7_instant() if "target" in p]
    assert len(problems) == 1 and "Lib.qml:3" in problems[0], problems


def test_l7_proves_safe_web_and_android_sites_by_rule(planted):
    (planted.ROOT / "ui/src/listen/Lib.tsx").write_text("""export function Host() { return null; }
export function Lib({ a, b }: { a: boolean; b: boolean }) {
  const narrow = useMediaQuery("(max-width: 600px)");
  return <div>
    <MotionRegion>{a && <p>x</p>}</MotionRegion>
    <MotionRegion motionKey={b}>{a && <p>y</p>}</MotionRegion>
    {a && <span className="sr-only">z</span>}
    {a && <Host />}
    {narrow && <p>n</p>}
    {b && <p>hard</p>}
    <Reveal when={b}><p>fixed</p></Reveal>
  </div>;
}
""", encoding="utf-8")
    (planted.ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui/Lib.kt").write_text("""package vn.abook.player.ui
@Composable fun Note(text: String) {}
@Composable fun Lib(ready: Boolean) {
    if (ready) Triple(1, 2, 3)
    AnimatedVisibility(ready) {
        if (ready) Note("a")
    }
    if (ready) Note("b") else Note("c")
    if (ready) Note("d")
    Reveal(ready) { Note("e") }
}
""", encoding="utf-8")
    got = _categories(planted)
    assert got[("Lib.tsx", 5)] == "b-parent-motion" and got[("Lib.tsx", 6)] == "a-hard"  # keyed on another value
    assert got[("Lib.tsx", 7)] == "b-not-visible" and got[("Lib.tsx", 8)] == "b-not-visible"
    assert got[("Lib.tsx", 9)] == "b-responsive" and got[("Lib.tsx", 10)] == "a-hard" and ("Lib.tsx", 11) not in got
    assert got[("Lib.kt", 4)] == "b-not-ui" and got[("Lib.kt", 6)] == "b-parent-motion"
    assert got[("Lib.kt", 8)] == "a-swap" and got[("Lib.kt", 9)] == "a-hard" and ("Lib.kt", 10) not in got


def test_l7_retained_presence_and_snapshot_swaps(planted):
    (planted.ROOT / "ui/src/listen/Lib.tsx").write_text("""export function Lib({item}) {
  return <><Presence>{item && <Custom value={item.name} />}</Presence>
    {item && <Custom value={item.name} />}
    <Presence><div>{item && <Custom value={item.name} />}</div></Presence></>;
}
""", encoding="utf-8")
    (planted.ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui/Lib.kt").write_text("""package vn.abook.player.ui
@Composable fun Note(text: String) {}
@Composable fun Lib(value: String?, other: Boolean) {
    SwapContent(value, other, contentKey = { value, other -> value != null && other }) { value, other ->
        if (value != null && other) Note(value)
        if (other) Note("unrelated to this branch key")
    }
    if (value != null) Note(value)
}
""", encoding="utf-8")
    got = _categories(planted)
    assert got[("Lib.tsx", 2)] == "b-retained-presence"
    assert got[("Lib.tsx", 3)] == "a-hard"
    assert got[("Lib.tsx", 4)] == "a-hard"  # an always-present div cannot observe its own conditional descendant
    assert got[("Lib.kt", 5)] == "b-parent-motion"
    assert got[("Lib.kt", 6)] == "a-hard"
    assert got[("Lib.kt", 8)] == "a-hard"


def test_l7_state_icon_and_inline_reveal_own_their_branch(planted):
    """StateIcon is the one in-place icon swap (keyed on its whole state); RevealInline is Reveal's horizontal twin. A branch
    inside either that reads its own value is animated; the same branch outside, or a different condition, still bites."""
    (planted.ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui/Lib.kt").write_text("""package vn.abook.player.ui
@Composable fun Note(text: String) {}
@Composable fun Lib(active: Boolean, busy: Boolean) {
    StateIcon(active) { on ->
        if (on) Note("stop") else Note("play")
    }
    StateIcon(active) { if (it) Note("ring") else Note("glyph") }
    RevealInline(busy) { if (busy) Note("spinner") }
    RevealInline(busy) { if (active) Note("unrelated") }
    if (active) Note("stop") else Note("play")
}
""", encoding="utf-8")
    got = _categories(planted)
    assert got[("Lib.kt", 5)] == "b-parent-motion" and got[("Lib.kt", 7)] == "b-parent-motion"
    assert got[("Lib.kt", 8)] == "b-parent-motion" and got[("Lib.kt", 9)] == "a-hard"
    assert got[("Lib.kt", 10)] == "a-swap"


def test_l7_snapshot_mask_must_erase_the_surface_on_a_real_clock(planted):
    path = planted.ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui/Lib.kt"
    source = """package vn.abook.player.ui
@Composable fun Lib(image: ImageBitmap?) {
    val progress = Animatable(0f)
    LaunchedEffect(Unit) { progress.animateTo(1f, Motion.ThemeReveal) }
    if (image != null) {
        Box(Modifier.drawBehind {
            drawImage(image)
            val far = hypot(size.width, size.height)
            drawCircle(Color.Black, far * progress.value, center, blendMode = BlendMode.Clear)
        })
    }
}
"""
    path.write_text(source, encoding="utf-8")
    assert _categories(planted)[("Lib.kt", 5)] == "b-animated-mask"
    path.write_text(source.replace("animateTo(1f", "animateTo(0f"), encoding="utf-8")
    assert _categories(planted)[("Lib.kt", 5)] == "a-hard"
    path.write_text(source.replace("BlendMode.Clear", "BlendMode.SrcOver"), encoding="utf-8")
    assert _categories(planted)[("Lib.kt", 5)] == "a-hard"


def test_l7_reduced_policy_requires_the_positive_guard(planted):
    path = planted.ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui/Lib.kt"
    path.write_text("""package vn.abook.player.ui
@Composable fun ReducedFade(value: Boolean) {}
@Composable fun Lib(ready: Boolean) {
    if (rememberReducedMotion()) { ReducedFade(ready) }
    if (!rememberReducedMotion()) { ReducedFade(ready) }
}
""", encoding="utf-8")
    got = _categories(planted)
    assert got[("Lib.kt", 4)] == "b-motion-policy"
    assert got[("Lib.kt", 5)] == "a-hard"


def test_l8_bites_an_ellipsis_button_with_the_wrong_name(planted):
    problems = planted.l8_ellipsis_names()
    assert any("Lib.qml" in p and "Tuỳ chọn {0}" in p for p in problems), problems


def test_l9_bites_a_five_word_button(planted):
    assert any("Thu vào khay khi đóng cửa sổ" in p for p in planted.l9_label_length())


@pytest.mark.parametrize("source", ['const label = S.s_g;', 'const action = { label: S.s_g };', '<LogBox title={S.s_g} />'])
def test_l9_checks_labels_built_before_the_control(planted, source):
    (planted.ROOT / "ui/src/listen/Lib.tsx").write_text(source, encoding="utf-8")
    assert any("ui/src/listen/Lib.tsx" in p for p in planted.l9_label_length())


def test_l10_bites_one_control_with_two_words(planted):
    problems = planted.l10_control_pairs()
    assert any("[marks]" in p and "chữ khác" in p for p in problems), problems


def test_l5_bites_a_menu_using_the_sheet_radius(planted):
    cfg = planted.config()
    cfg["L5"]["components"] = [{"name": "menu", "role": "cover", "file": "ui/src/listen/Lib.tsx",
                                "require": "rounded-cover", "forbid": ["rounded-sheet"]}]
    planted.CONFIG.write_text(json.dumps(cfg), encoding="utf-8")
    assert planted.l5_radius_roles()


def test_l6_bites_missing_timings_and_a_hard_reduced_fade(planted):
    token = planted.ROOT / "ui_design/tokens.json"
    token.parent.mkdir()
    token.write_text('{"timing": {}}', encoding="utf-8")
    assert any("skeletonPeriodMs" in p for p in planted.l6_motion_tokens())
    token.write_text(json.dumps({"timing": {k: 120 for k in (
        "skeletonLow", "skeletonPeriodMs", "noticeMs", "undoMs", "reducedFadeMs", "indeterminateMs", "spinMs")}}), encoding="utf-8")
    qml = planted.ROOT / "desktop_qt/qml/Lib.qml"
    qml.write_text(qml.read_text(encoding="utf-8") + '\nBehavior on opacity { duration: Theme.reduceMotion ? 0 : 220 }', encoding="utf-8")
    assert any("cắt cứng" in p for p in planted.l6_motion_tokens())


def test_l6_rejects_generated_but_wrong_design_timings(planted):
    token = planted.ROOT / "ui_design/tokens.json"
    token.parent.mkdir()
    token.write_text(json.dumps({"timing": {"skeletonLow": 0.5, "skeletonPeriodMs": 2000, "noticeMs": 5000,
        "undoMs": 28000, "reducedFadeMs": 0, "indeterminateMs": 1400, "spinMs": 1000}}), encoding="utf-8")
    problems = planted.l6_motion_tokens()
    assert all(any(key in p for p in problems) for key in ("skeletonLow", "skeletonPeriodMs", "noticeMs", "reducedFadeMs"))


def test_l9_ignores_input_hints_and_descriptions(planted):
    path = planted.ROOT / "desktop_qt/qml/Lib.qml"
    path.write_text('FormField { placeholder: S.s_g; description: S.s_g }', encoding="utf-8")
    assert not any("Lib.qml" in str(p) for p in planted.long_labels().values())


def test_l10_bites_a_control_with_wrong_geometry(planted):
    cfg = planted.config()
    cfg["L10"]["controls"] = [{"id": "toast-close", "at": {"qt": {
        "file": "desktop_qt/qml/Lib.qml", "require": [r"x: card.width - width - 12"], "forbid": [r"x: -6"]}}}]
    planted.CONFIG.write_text(json.dumps(cfg), encoding="utf-8")
    assert any("toast-close" in p for p in planted.l10_control_pairs())


def test_l11_bites_a_lowercase_row_summary_on_all_three_platforms(planted):
    """0.4.168 Android Settings: "nhạc tự chọn" under "Nghe" while every other row summary starts with a capital."""
    vi = dict(VI, s_low="nhạc tự chọn", s_up="Tự động", s_frag="đã tải ", s_count="{0} bài", s_inner="chưa rõ", s_wrap="Tóm tắt: {0}",
              s_opt="đang tắt trong Cài đặt", s_kept="đọc là “{0}”")
    (planted.ROOT / "ui_strings/vi.json").write_text(json.dumps({"strings": vi}, ensure_ascii=False), encoding="utf-8")
    cfg = planted.config()
    android = "mobile/android/app/src/main/java/vn/abook/player/ui/Lib.kt"
    cfg["L11"] = {"producers": [{"file": "desktop_qt/qml/Lib.qml", "start": r"function summary\(key\)"},
                                {"file": android, "start": r"\bOption\(", "arg": 2}],
                  "allow": [{"file": android, "key": "s_kept", "reason": "continues the title"}]}
    planted.CONFIG.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    (planted.ROOT / "desktop_qt/qml/Lib.qml").write_text(
        'Item {\n    function summary(key) {\n        if (key === "a") return S.s_up\n        return ready ? S.s_low : S.s_count(2)\n    }\n'
        '    Row { hint: S.s_up + n + S.s_frag }\n}\n', encoding="utf-8")
    (planted.ROOT / android).write_text(
        'fun Lib() {\n    Fold(S.s_a, "x", summary = if (on) S.s_wrap(S.s_inner) else S.s_up)\n    ListItem(t, hint = S.s_kept(x))\n'
        '    add(Option(null, S.s_up, if (off) S.s_opt else auto))\n}\n', encoding="utf-8")
    (planted.ROOT / "ui/src/listen/Lib.tsx").write_text('export const rows = [{ label: S.s_up, hint: S.s_frag + "x" }];\n', encoding="utf-8")
    problems = planted.l11_summary_case()
    found = {(p.split()[1].split(":")[0].rsplit("/", 1)[-1], p.split("(")[-1].split(")")[0]) for p in problems}
    # Fragments after `+` and values inside another string's slot do not start the line; the allowed continuation is not reported.
    assert found == {("Lib.qml", "s_low"), ("Lib.kt", "s_opt"), ("Lib.tsx", "s_frag")}, problems
    cfg["L11"]["allow"].append({"file": android, "key": "s_up", "reason": "stale"})
    planted.CONFIG.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    assert any("allow thừa" in p and "s_up" in p for p in planted.l11_summary_case())
    cfg["L11"]["producers"][0]["start"] = r"function gone\("
    planted.CONFIG.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    assert any("không còn" in p and "function gone" in p for p in planted.l11_summary_case())


def test_l12_bites_floating_layers_that_let_a_tap_through(planted):
    """Chủ sách 17-11: thanh "Đang nghe thử" nổi trên Kho nhạc để cú bấm lọt xuống dòng bài - trên cả ba nền, lớp nổi phải nuốt cú bấm."""
    root = planted.ROOT
    android = "mobile/android/app/src/main/java/vn/abook/player/ui/"
    (root / android / "components").mkdir(parents=True, exist_ok=True)
    (root / android / "components/Components.kt").write_text("fun Modifier.floatingLayer(): Modifier = pointerInput(Unit) { detectTapGestures { } }\n", encoding="utf-8")
    (root / "desktop_qt/qml/TapShield.qml").write_text("MouseArea { anchors.fill: parent }\n", encoding="utf-8")
    (root / android / "Bar.kt").write_text(
        "fun Screen() {\n    Box {\n        // a bracket ( in a comment does not move the chain\n"
        "        Bar(ui, Modifier.align(Alignment.BottomCenter))\n"
        "        Bar(ui, Modifier.align(Alignment.BottomCenter).floatingLayer())\n"
        "        Hint(Modifier.align(Alignment.BottomEnd).padding(8.dp).pressable { open() })\n"
        "        Chip(Modifier.align(Alignment.TopEnd))\n    }\n}\n", encoding="utf-8")
    (root / "ui/src/listen/Bar.tsx").write_text(
        'export const A = () => <div className="pointer-events-none sticky bottom-3"><Bar /></div>;\n'
        'export const B = () => <div aria-hidden className="pointer-events-none absolute inset-0 bg-gradient-to-t" />;\n'
        'export const C = () => <div className="pointer-events-none flex gap-2" />;\n', encoding="utf-8")
    (root / "desktop_qt/qml/Shelf.qml").write_text(
        "Item {\n    ListView { anchors.fill: parent }\n"
        "    Rectangle {\n        id: bar\n        y: root.height - height - 8\n        color: \"white\"\n        Text { text: \"x\" }\n    }\n"
        "    Rectangle {\n        id: shielded\n        z: 3\n        TapShield {}\n    }\n"
        "    IconButton {\n        id: fab\n        y: parent.height - height\n    }\n}\n", encoding="utf-8")
    problems = planted.l12_floating_layers()
    text = "\n".join(problems)
    # Soát 17-11: `.padding(8.dp).pressable {}` vẫn để phần đệm cho cú bấm lọt - bộ bắt chạm phải đứng trước padding đầu tiên.
    assert len([p for p in problems if "Bar.kt" in p]) == 2 and "Bar.kt:4:" in text and "Bar.kt:6:" in text, problems
    assert "Bar.kt:5:" not in text, problems
    assert "Bar.tsx:1:" in text and "Bar.tsx:2:" not in text and "Bar.tsx:3:" not in text, problems
    assert "Rectangle#bar" in text and "#shielded" not in text and "#fab" not in text, problems
    # An exception needs the exact site and its own reason; a stale one is reported.
    cfg = planted.config()
    cfg["L12"] = {"allow": [{"platform": "qt", "file": "desktop_qt/qml/Shelf.qml", "what": "Rectangle#bar", "reason": "x"},
                            {"platform": "web", "file": "ui/src/listen/Gone.tsx", "what": "pointer-events-none fixed", "reason": "x"}]}
    planted.CONFIG.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    problems = planted.l12_floating_layers()
    assert not any("Rectangle#bar" in p and "allow" not in p for p in problems), problems
    assert any("allow thừa" in p and "Gone.tsx" in p for p in problems), problems
    (root / android / "components/Components.kt").write_text("fun Modifier.other() = this\n", encoding="utf-8")
    assert any("thiếu Modifier.floatingLayer()" in p for p in planted.l12_floating_layers())


GOOD_INTERACTIVE = ("Item {\n    id: root\n    property bool exclusiveTap: false\n    readonly property bool holdsTap: exclusiveTap || layer.shielded\n"
                    "    QtObject { id: layer; property bool shielded: false\n"
                    "        function scan() { for (let p = root.parent; p; p = p.parent) if (p.children[0] instanceof TapShield) return true; return false } }\n"
                    "    TapHandler { gesturePolicy: root.holdsTap ? TapHandler.ReleaseWithinBounds : TapHandler.DragThreshold }\n}\n")
GOOD_SHIELD = ("Item {\n    anchors.fill: parent\n    TapHandler { acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton; "
               "gesturePolicy: TapHandler.ReleaseWithinBounds }\n    HoverHandler {}\n}\n")


def test_l12_bites_a_button_in_a_shielded_layer_that_does_not_hold_its_tap(planted):
    """Đo 17-11: nút (TapHandler thụ động) trong lớp có TapShield để cú bấm tới cả Interactive nằm dưới lớp (màn Đang nghe trên thư viện). Cách sửa
    chung là Interactive tự giữ riêng cú bấm khi một tổ tiên có TapShield làm con đầu tiên; luật đỏ khi bất kỳ mắt xích nào của cách ấy gãy."""
    root = planted.ROOT
    qml = root / "desktop_qt/qml"
    (qml / "Interactive.qml").write_text(GOOD_INTERACTIVE, encoding="utf-8")
    (qml / "TapShield.qml").write_text(GOOD_SHIELD, encoding="utf-8")
    (qml / "Layer.qml").write_text(
        "Item {\n    Rectangle {\n        id: good\n        HoverHandler {}\n        TapShield {}\n        IconButton {}\n    }\n"
        "    Rectangle {\n        id: late\n        Rectangle { anchors.fill: parent }\n        TapShield {}\n        IconButton {}\n    }\n"
        "    Rectangle {\n        id: bare\n        MouseArea { anchors.fill: parent }\n        IconButton {}\n    }\n"
        "    Rectangle {\n        id: shifted\n        transform: Translate { y: 4 }\n        Behavior on opacity { NumberAnimation {} }\n"
        "        TapShield {}\n    }\n}\n", encoding="utf-8")
    problems = planted.l12_qt_layer_problems()
    text = "\n".join(problems)
    assert "Layer.qml:11:" in text and "con đầu tiên" in text, problems         # khiên đứng sau nền: nút trong lớp không giữ cú bấm
    assert "Layer.qml:16:" in text and "MouseArea" in text, problems            # lớp tự chặn bằng MouseArea trơn
    assert "Layer.qml:5:" not in text and "Layer.qml:22:" not in text, problems  # Handler / giá trị thuộc tính / Behavior không phải con
    assert len(problems) == 2, problems
    # Interactive thôi dò khiên (hay gesturePolicy không theo holdsTap): mọi nút của mọi lớp lại để cú bấm lọt.
    (qml / "Interactive.qml").write_text(GOOD_INTERACTIVE.replace("root.holdsTap ?", "root.exclusiveTap ?"), encoding="utf-8")
    assert any("Interactive.qml" in p for p in planted.l12_qt_layer_problems())
    (qml / "Interactive.qml").write_text(GOOD_INTERACTIVE.replace("instanceof TapShield", "!== null"), encoding="utf-8")
    assert any("Interactive.qml" in p for p in planted.l12_qt_layer_problems())
    # Khiên nuốt nút Back: Back của chuột không còn đóng Đang nghe.
    (qml / "Interactive.qml").write_text(GOOD_INTERACTIVE, encoding="utf-8")
    (qml / "TapShield.qml").write_text("MouseArea {\n    anchors.fill: parent\n    acceptedButtons: Qt.AllButtons\n}\n", encoding="utf-8")
    assert any("TapShield.qml" in p and "Back" in p for p in planted.l12_qt_layer_problems())


def test_l12_bites_the_18_11_review_cases(planted):
    """Soát 18-11 (82cb3968e): L12 báo xanh trong khi (1) floatingLayer chia chạm với anh em - dòng nằm dưới nhận cú bấm trước lớp, (2) danh sách xổ
    của Select (C.Popup) không có khiên, (3) nền bấm-ra-ngoài của Popover / Modal là MouseArea - vừa đóng vừa kích hoạt thứ dưới; cộng các lỗ: một nút
    trong Item nổi được coi là cả Item bắt chạm, MouseArea phủ kín có thêm thuộc tính, lớp nổi không dính đáy trong Box có danh sách cuộn."""
    root = planted.ROOT
    android = "mobile/android/app/src/main/java/vn/abook/player/ui/"
    (root / android / "components").mkdir(parents=True, exist_ok=True)
    good = ("fun Modifier.floatingLayer(scrollThrough: ScrollableState? = null): Modifier =\n"
            "    (if (scrollThrough != null) this.scrollable(scrollThrough, Orientation.Vertical) else this).pointerInput(Unit) { detectTapGestures { } }\n\n")
    (root / android / "components/Components.kt").write_text(good, encoding="utf-8")
    qml = root / "desktop_qt/qml"
    (qml / "Interactive.qml").write_text(GOOD_INTERACTIVE, encoding="utf-8")
    (qml / "TapShield.qml").write_text(GOOD_SHIELD, encoding="utf-8")
    assert not any("Components.kt" in p or "Android:" in p for p in planted.l12_floating_layers())

    # (1) Lớp chia chạm với anh em, và floatingLayer không còn chặn bằng pointerInput.
    (root / android / "components/Components.kt").write_text(
        "fun Modifier.floatingLayer(): Modifier = this then FloatingLayerElement\n\n"
        "private class FloatingLayerNode : Modifier.Node(), PointerInputModifierNode {\n"
        "    override fun sharePointerInputWithSiblings() = true\n}\n", encoding="utf-8")
    text = "\n".join(planted.l12_floating_layers())
    assert "Components.kt:4:" in text and "sharePointerInputWithSiblings" in text, text
    assert "không còn bắt chạm bằng pointerInput" in text, text
    (root / android / "components/Components.kt").write_text(good, encoding="utf-8")

    # Lớp nổi góc / giữa trong Box có danh sách cuộn; nhánh `when` thay danh sách và căn trong Column thì không phải lớp nổi.
    (root / android / "Over.kt").write_text(
        "fun Screen() {\n    Box {\n        LazyColumn(Modifier.fillMaxSize()) { items(rows) { Row(it) } }\n"
        "        Chip(Modifier.align(Alignment.TopEnd))\n"
        "        Chip(Modifier.align(Alignment.TopEnd).floatingLayer())\n    }\n"
        "    Box {\n        when {\n            loading -> Text(Modifier.align(Alignment.Center))\n"
        "            else -> LazyColumn(Modifier.fillMaxSize()) { }\n        }\n    }\n"
        "    Column { Handle(Modifier.align(Alignment.CenterHorizontally)) ; LazyColumn() {} }\n}\n", encoding="utf-8")
    text = "\n".join(planted.l12_floating_layers())
    assert "Over.kt:4:" in text and "Over.kt:5:" not in text and "Over.kt:9:" not in text and "Over.kt:13:" not in text, text
    (root / android / "Over.kt").unlink()

    # (2) Popup không khiên; (3) nền MouseArea đóng lớp; MouseArea phủ kín có thêm thuộc tính; nút trong Item nổi không thay khiên; WindowLayer không khiên.
    (qml / "Pick.qml").write_text(
        "Item {\n    C.Popup {\n        contentItem: ListView { delegate: Interactive {} }\n    }\n"
        "    C.Popup {\n        modal: true; contentItem: Item {\n            TapShield {}\n            ListView {}\n        }\n    }\n"
        "    ShortcutsDialog {}\n}\n", encoding="utf-8")
    (qml / "Pop.qml").write_text(
        "WindowLayer {\n    MouseArea {\n        anchors.fill: parent\n        enabled: root.open\n        onPressed: root.close()\n    }\n"
        "    Rectangle {\n        id: panel\n        z: 2\n        IconButton {}\n    }\n"
        "    Rectangle {\n        MouseArea { anchors.fill: parent; hoverEnabled: true }\n    }\n"
        "    MouseArea { anchors.fill: parent; acceptedButtons: Qt.NoButton; onWheel: wheel => wheel.accepted = true }\n}\n", encoding="utf-8")
    (qml / "Seek.qml").write_text("Item {\n    MouseArea {\n        anchors.fill: parent\n        onPressed: mouse => root.seek(mouse.x)\n    }\n}\n",
                                  encoding="utf-8")
    (qml / "Bar.qml").write_text("Item {\n    Seek {\n        id: seek\n        z: 2\n    }\n}\n", encoding="utf-8")
    problems = planted.l12_floating_layers()
    text = "\n".join(problems)
    assert "Pick.qml:2:" in text and "C.Popup" in text and "Pick.qml:5:" not in text and "Pick.qml:11:" not in text, text
    assert "Pop.qml:2:" in text and "Backdrop" in text, text
    assert "Pop.qml:9:" in text and "Rectangle#panel" in text, text          # một IconButton bên trong không chặn chỗ trống quanh nó
    assert "Pop.qml:13:" in text, text                                        # MouseArea phủ kín chỉ thêm hoverEnabled vẫn là cái chặn trơn
    assert "Pop.qml:15:" not in text, text                                    # chỉ giữ cú lăn (NoButton): không chặn cú bấm
    assert "Pop.qml: lớp WindowLayer không có TapShield" in text, text
    assert "Bar.qml" not in text, text                                        # điều khiển phủ cả khung (thanh tua) tự bắt cú bấm


def test_l12_bites_the_fourth_review_holes(planted):
    """Soát 18-11 lần 4 (5c9d541af): nền bấm-ra-ngoài bằng TapHandler thụ động, lớp đưa lên Overlay (`parent: …overlay`) hay dính đáy bằng neo cạnh
    danh sách, một TapShield ở đâu đó trong tệp được coi là cả kiểu bắt chạm, floatingLayer chỉ còn chữ `pointerInput(`, và web dùng thẳng menu /
    Popover của Radix (không modal: bấm ra ngoài tới thứ nằm dưới)."""
    root = planted.ROOT
    qml = root / "desktop_qt/qml"
    (qml / "Interactive.qml").write_text(GOOD_INTERACTIVE, encoding="utf-8")
    (qml / "TapShield.qml").write_text(GOOD_SHIELD, encoding="utf-8")
    # (a) TapHandler thụ động đóng lớp; Backdrop thật (ReleaseWithinBounds) thì không bị báo.
    (qml / "Scrim.qml").write_text(
        "Item {\n    TapHandler {\n        onTapped: root.close()\n    }\n"
        "    TapHandler {\n        gesturePolicy: TapHandler.ReleaseWithinBounds\n        onPressedChanged: if (pressed) root.dismissed()\n    }\n}\n",
        encoding="utf-8")
    # (c) Kiểu có TapShield trong một bảng con sâu không bắt cả khung; con đầu của gốc / của bảng chính thì có.
    (qml / "Deep.qml").write_text("Item {\n    Rectangle {\n        Column {\n            TapShield {}\n        }\n    }\n}\n", encoding="utf-8")
    (qml / "Pill.qml").write_text("Item {\n    Rectangle {\n        id: pill\n        TapShield {}\n    }\n}\n", encoding="utf-8")
    (qml / "Shade.qml").write_text("Item {\n    Backdrop {}\n    Rectangle {}\n}\n", encoding="utf-8")
    # (b) Overlay và neo đáy cạnh danh sách.
    (qml / "Page.qml").write_text(
        "Item {\n    Deep {\n        z: 2\n    }\n    Pill {\n        z: 2\n    }\n    Shade {\n        z: 2\n    }\n"
        "    Item {\n        id: floating\n        parent: C.Overlay.overlay\n        Text {}\n    }\n"
        "    ListView {\n        anchors.fill: parent\n    }\n"
        "    Row {\n        id: dock\n        anchors.bottom: parent.bottom\n        IconButton {}\n    }\n"
        "    Rectangle {\n        id: fade\n        anchors.bottom: parent.bottom\n        height: 24\n    }\n}\n", encoding="utf-8")
    (qml / "Footer.qml").write_text(
        "Item {\n    ListView {\n        anchors.top: parent.top\n        anchors.bottom: bar.top\n    }\n"
        "    Row {\n        id: bar\n        anchors.bottom: parent.bottom\n        IconButton {}\n    }\n}\n", encoding="utf-8")
    text = "\n".join(planted.l12_floating_layers())
    assert "Scrim.qml:2:" in text and "TapHandler thụ động" in text and "Scrim.qml:5:" not in text, text
    assert "Page.qml:3:" in text and "Deep" in text, text                       # khiên sâu trong bảng con không phủ cả khung
    assert "Page.qml:6:" not in text and "Page.qml:9:" not in text, text        # khiên đầu của bảng chính / Backdrop thì có
    assert "Item#floating" in text, text                                        # lớp đưa lên Overlay
    assert "Row#dock" in text and "Rectangle#fade" not in text, text            # dải nút dính đáy trên danh sách; dải mờ trang trí thì không
    assert "Footer.qml" not in text, text                                       # danh sách dừng trên dải (anchors.bottom: bar.top)
    # (d) floatingLayer phải thật sự bắt cú chạm (detectTapGestures), không chỉ có chữ pointerInput(.
    android = root / "mobile/android/app/src/main/java/vn/abook/player/ui/components"
    android.mkdir(parents=True, exist_ok=True)
    (android / "Components.kt").write_text("fun Modifier.floatingLayer(): Modifier = this.pointerInput(Unit) { }\n\n", encoding="utf-8")
    assert any("detectTapGestures" in p for p in planted.l12_floating_layers())
    (android / "Components.kt").write_text("fun Modifier.floatingLayer(): Modifier = this.pointerInput(Unit) { detectTapGestures { } }\n\n",
                                           encoding="utf-8")
    assert not any("Components.kt" in p or "Android:" in p for p in planted.l12_floating_layers())
    # Web: Radix thẳng thì đỏ; bọc chung phải gắn lớp chặn ngoài.
    shared = root / "ui/src/shared"
    shared.mkdir(parents=True, exist_ok=True)
    wrapper = ("import * as Radix from \"@radix-ui/react-{0}\";\nexport * from \"@radix-ui/react-{0}\";\n"
               "export const Content = forwardRef(function C(props, ref) {{ return <Radix.Content {{...props}} ref={{useOutsideShield(ref)}} />; }});\n")
    (shared / "DropdownMenu.tsx").write_text(wrapper.format("dropdown-menu"), encoding="utf-8")
    (shared / "Popover.tsx").write_text(wrapper.format("popover"), encoding="utf-8")
    (shared / "outsideShield.ts").write_text("Object.assign(cover.style, { position: \"fixed\" });\nwrapper.before(cover);\n", encoding="utf-8")
    (root / "ui/src/listen/Volume.tsx").write_text("import * as Popover from \"@radix-ui/react-popover\";\n", encoding="utf-8")
    text = "\n".join(planted.l12_floating_layers())
    assert "Volume.tsx:1:" in text and "shared/Popover.tsx" in text, text
    assert "DropdownMenu.tsx" not in text and "outsideShield" not in text, text
    (shared / "Popover.tsx").write_text(wrapper.format("popover").replace("useOutsideShield(ref)", "ref"), encoding="utf-8")
    assert any("ui/src/shared/Popover.tsx: Content không gắn lớp chặn ngoài" in p for p in planted.l12_floating_layers())
    # N1: Popup không modal đóng khi nhấn ra ngoài (closePolicy mặc định) để cú nhấn ấy tới trang; N2: Backdrop không giữ con trỏ.
    (qml / "Drop.qml").write_text(
        "Item {\n    C.Popup {\n        contentItem: Item { TapShield {} }\n    }\n"
        "    C.Popup {\n        closePolicy: C.Popup.CloseOnEscape\n        contentItem: Item { TapShield {} }\n    }\n"
        "    C.Popup {\n        modal: true\n        contentItem: Item { TapShield {} }\n    }\n}\n", encoding="utf-8")
    (qml / "Backdrop.qml").write_text("Item {\n    TapHandler { gesturePolicy: TapHandler.ReleaseWithinBounds }\n}\n", encoding="utf-8")
    text = "\n".join(planted.l12_floating_layers())
    assert "Drop.qml:2:" in text and "không modal" in text and "Drop.qml:5:" not in text and "Drop.qml:9:" not in text, text
    assert "Backdrop.qml phải" in text and "HoverHandler" in text, text
    (qml / "Backdrop.qml").write_text("Item {\n    TapHandler { gesturePolicy: TapHandler.ReleaseWithinBounds }\n    HoverHandler {}\n}\n", encoding="utf-8")
    assert not any("Backdrop.qml phải" in p for p in planted.l12_floating_layers())
