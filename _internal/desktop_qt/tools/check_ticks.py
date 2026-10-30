"""Máy dò luật chủ sách 30-10 "số tự đổi không chuyển động".

Giá trị tự đổi (thời gian đã nghe / còn lại, đếm ngược hẹn giờ, % tải / nhập / xuất / phân tích, ETA, thời gian đã chạy)
đổi TẠI CHỖ: không trượt, cuộn, mờ chéo, co giãn hay đổi opacity khi giá trị đổi; chữ số đều độ rộng (tnum). Mở / đóng
và thay đổi do người dùng bấm vẫn có chuyển động - máy dò chỉ nhìn chữ dựng từ nguồn tự đổi dưới đây.

Nguồn tự đổi (TICK_SOURCES): Player.clock.*, Player.clockText, formatClock, formatEta, formatPercent, *percent / *Percent(),
packingText, phép "× 100" làm tròn, chữ nối với "%".

Lỗi:
  T1  chữ hiện giá trị tự đổi nằm trên Text không có tnum   -> dùng ClockLabel (Text + font.features tnum)
  T2  phần tử ấy có Behavior on text / opacity / x / y / width / implicitWidth / scale
  T3  phần tử ấy nằm trong Flow / Row / Grid / ListView có move / add / populate / displaced, hay trong cha có
      Behavior on width / implicitWidth / x, mà bề rộng của nó chạy theo chữ  -> giữ chỗ bằng ClockLabel.reserve
      (hay ControlChip.reserve) để bề rộng không đổi theo giá trị
  T4  thành phần nhận chữ tự đổi qua thuộc tính (text: của ControlChip, Button...) mà không có trong STEADY_COMPONENTS
  T5  phần tô của thanh tiến độ (width / x = <cha>.width * giá trị) có Behavior on width / x: tiến độ tự chạy (tải, xuất,
      phân tích, đã nghe) vẽ thẳng theo giá trị như điện thoại native. Thanh người dùng kéo (tua, âm lượng) ghi tick-ok.
Ngoại lệ có chủ đích: dòng có chú thích  // tick-ok: <lý do>.

  python -X utf8 check_ticks.py [thư mục qml]        thoát 1 nếu có vi phạm (build.bat chạy nó như check_text_cut)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_text_cut import strip_noise  # noqa: E402

TICK_SOURCES = [
    r"\bPlayer\.clock\.(position|sleepLeft)\b",
    r"\bclockText\(",
    r"\bformatClock\(",
    r"\bformatEta\(",
    r"\bformatPercent\(",
    r"\b\w*[pP]ercent\(",
    r"\bpackingText\(",
    r"\*\s*100\s*\)",
    r"\+\s*\"%\"",
    r"\}%",
]
TICK = re.compile("|".join(TICK_SOURCES))
# Hàm .js / function của QML trả chữ có nguồn tự đổi (tìm bắc cầu tới điểm dừng): chữ gọi chúng cũng là chữ tự đổi.
TEXT_TYPES = {"Text", "Label", "HintText"}
CLOCK = "ClockLabel"
# Thành phần đã kiểm: nhận chữ tự đổi qua `text` và vẽ nó tại chỗ bằng tnum; `reserve` giữ bề rộng.
STEADY_COMPONENTS = {CLOCK, "ControlChip"}
BAD_BEHAVIORS = {"text", "opacity", "x", "y", "width", "implicitWidth", "scale"}
LAYOUT_BEHAVIORS = {"width", "implicitWidth", "x"}
MOVING_TRANSITIONS = {"move", "add", "populate", "displaced"}
SHOWN_PROPS = ("text", "title", "description", "label", "note", "hint", "detail")
FILL_BEHAVIORS = {"width", "x"}
# "parent.width * root.clamped", "track.width * VoiceLogic.percent(...) / 100": hình chạy theo một giá trị, không phải bố cục
FILL = re.compile(r"\b[\w.]*\bwidth\s*\*|\*\s*[\w.]*\bwidth\b")


class Node:
    def __init__(self, kind: str, name: str, line: int, parent: "Node | None"):
        self.kind, self.name, self.line, self.parent = kind, name, line, parent
        self.props: dict[str, tuple[str, int]] = {}
        self.behaviors: set[str] = set()
        self.transitions: set[str] = set()
        self.children: list[Node] = []


def tree(raw: str) -> Node:
    text = strip_noise(raw)
    text = re.sub(r"^[ \t]*(import|pragma)\b[^\n]*$", lambda m: " " * len(m.group()), text, flags=re.M)
    root = Node("root", "", 0, None)
    stack = [root]
    token_start, i, n = 0, 0, len(text)

    def clause(start: int, end: int) -> None:
        owner = stack[-1]
        if owner.kind not in ("type", "group"):
            return
        body = text[start:end]
        m = re.match(r"^\s*([A-Za-z_][\w.]*)\s*:\s*(.*)$", body, re.S)
        if not m:
            return
        ln = text.count("\n", 0, start + len(body) - len(body.lstrip())) + 1
        target = owner if owner.kind == "type" else owner.parent
        name = m.group(1) if owner.kind == "type" else owner.name + "." + m.group(1)
        target.props[name] = (raw[start + m.start(2):end].strip(), ln)

    while i < n:
        c = text[i]
        if c == "{":
            head = text[token_start:i]
            hm = re.search(r"([A-Za-z_][\w.]*)(\s+on\s+([\w.]+))?\s*$", head)
            before = head[:hm.start()] if hm else head
            ln = text.count("\n", 0, i) + 1
            owner = stack[-1]
            if hm and hm.group(1)[0].isupper():
                node = Node("type", hm.group(1), ln, owner if owner.kind != "group" else owner.parent)
                prop = re.search(r"([A-Za-z_]\w*)\s*:\s*$", before)
                if hm.group(1) == "Behavior" and hm.group(3):
                    node.parent.behaviors.add(hm.group(3))
                if hm.group(1) == "Transition" and prop:
                    node.parent.transitions.add(prop.group(1))
                node.parent.children.append(node)
                stack.append(node)
            elif hm and hm.group(1)[0].islower() and re.search(r":\s*$", before) is None and owner.kind == "type" \
                    and re.match(r"^\s*$", before.rsplit(";", 1)[-1]):
                node = Node("group", hm.group(1), ln, owner)
                stack.append(node)
            else:
                block = Node("js", "", ln, owner)
                prop = re.search(r"([A-Za-z_][\w.]*)\s*:\s*$", head)      # "font.features: {...}", "onClicked: {...}"
                if prop and owner.kind in ("type", "group"):
                    block.name, block.line = prop.group(1), token_start + head.index(prop.group(0))
                stack.append(block)
            token_start = i + 1
        elif c == "}":
            clause(token_start, i)
            if len(stack) > 1:
                block = stack.pop()
                if block.kind == "js" and block.name:
                    owner = block.parent if block.parent.kind == "type" else block.parent.parent
                    name = block.name if block.parent.kind == "type" else block.parent.name + "." + block.name
                    owner.props[name] = (raw[block.line:i + 1].split(":", 1)[1].strip(), text.count(chr(10), 0, block.line) + 1)
        elif c == ";" and stack[-1].kind in ("type", "group"):
            clause(token_start, i)
            token_start = i + 1
        elif c == "\n" and stack[-1].kind in ("type", "group"):
            body = text[token_start:i]
            if body.strip() and body.count("(") == body.count(")") and body.count("[") == body.count("]") \
                    and not body.rstrip().endswith((",", "+", "?", ":", "&&", "||", "=>")):
                nxt = text[i + 1:i + 200].lstrip()
                if not nxt.startswith((".", "?", ":", "+", "&&", "||", ")")):
                    clause(token_start, i)
                    token_start = i + 1
        i += 1
    return root


def walk(node: Node):
    yield node
    for child in node.children:
        yield from walk(child)


def functions(src: str) -> dict[str, str]:
    """Tên hàm -> thân (đếm ngoặc trên bản đã xoá chuỗi / chú thích)."""
    clean = strip_noise(src)
    found: dict[str, str] = {}
    for m in re.finditer(r"\bfunction\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{", clean):
        depth, j = 1, m.end()
        while j < len(clean) and depth:
            depth += {"{": 1, "}": -1}.get(clean[j], 0)
            j += 1
        found[m.group(1)] = src[m.end():j]
    return found


def tick_functions(folder: Path) -> list[str]:
    bodies: dict[str, str] = {}
    for f in sorted(folder.glob("*.js")) + sorted(folder.glob("*.qml")):
        bodies.update(functions(f.read_text(encoding="utf-8")))
    names: set[str] = {name for name, body in bodies.items() if TICK.search(body)}
    while True:
        call = re.compile(r"\b(" + "|".join(sorted(names)) + r")\(") if names else None
        more = {name for name, body in bodies.items() if name not in names and call and call.search(body)}
        if not more:
            return sorted(names)
        names |= more


def has_tnum(node: Node) -> bool:
    value = node.props.get("font.features", ("", 0))[0]
    return "tnum" in value


def scan(path: Path, tick: re.Pattern) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    lines = raw.split("\n")
    errors: list[str] = []
    for node in walk(tree(raw)):
        if node.kind != "type":
            continue
        for prop in sorted(node.behaviors & FILL_BEHAVIORS):
            value, ln = node.props.get(prop, ("", 0))
            if value and FILL.search(value) and "tick-ok" not in lines[ln - 1]:
                errors.append(f"T5 {path.name}:{ln}: {node.name} {{ {prop}: {' '.join(value.split())[:60]} }} - phần tô theo giá trị "
                              f"có Behavior on {prop}; tiến độ tự chạy vẽ thẳng")
        for prop in SHOWN_PROPS:
            value, ln = node.props.get(prop, ("", 0))
            if not value or not tick.search(value):
                continue
            if "tick-ok" in lines[ln - 1]:
                continue
            where = f"{path.name}:{ln}: {node.name} {{ {prop}: {' '.join(value.split())[:60]} }}"
            if node.name in TEXT_TYPES and not has_tnum(node):
                errors.append(f"T1 {where} - chữ số không đều độ rộng; dùng ClockLabel")
            if node.name not in TEXT_TYPES and node.name not in STEADY_COMPONENTS and node.props.get("tabular", ("",))[0] != "true":
                errors.append(f"T4 {where} - {node.name} chưa được kiểm là vẽ giá trị tự đổi tại chỗ")
            moving = node.behaviors & BAD_BEHAVIORS
            if moving:
                errors.append(f"T2 {where} - Behavior on {', '.join(sorted(moving))} làm giá trị chuyển động khi đổi")
            fixed = "reserve" in node.props or "width" in node.props
            parent = node.parent
            while parent is not None and not fixed:
                cause = parent.transitions & MOVING_TRANSITIONS or parent.behaviors & LAYOUT_BEHAVIORS
                if cause:
                    errors.append(f"T3 {where} - bề rộng chạy theo giá trị trong {parent.name} (dòng {parent.line}) có "
                                  f"{', '.join(sorted(cause))} chuyển động; giữ chỗ bằng reserve")
                    break
                if "width" in parent.props:
                    break
                parent = parent.parent
    return errors


def main() -> int:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "qml"
    files = sorted(folder.glob("*.qml"))
    if not files:
        print(f"Máy dò số tự đổi: không thấy file QML nào trong {folder}")
        return 1
    derived = tick_functions(folder)
    tick = re.compile("|".join(TICK_SOURCES + [r"\b(" + "|".join(derived) + r")\("])) if derived else TICK
    errors: list[str] = []
    for f in files:
        errors.extend(scan(f, tick))
    if "--functions" in sys.argv:
        print(chr(10).join(derived))
    if errors:
        print("Máy dò số tự đổi: có giá trị tự đổi chuyển động hay chữ số không đều độ rộng (luật chủ sách 30-10).")
        for e in errors:
            print("  " + e)
        return 1
    print(f"Máy dò số tự đổi: {len(files)} file QML, {len(derived)} hàm dựng chữ tự đổi, mọi giá trị tự đổi đổi tại chỗ.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
