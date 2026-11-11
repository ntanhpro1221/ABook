"""Luật design_lint trên CÂY UI xuất cạnh ảnh (bước 2, soát thiết kế 10-11).

Cây do bộ chụp ghi (đơn vị dp, Qt px logic = dp):
  Android  mobile/android/app/build/design_lint/<tên ảnh>.tree.json (vn.abook.player.ui.snapshot.UiTreeCapture)
  Qt       desktop_qt/build/d2shots/<tên ảnh>.tree.json            (desktop_qt/tests/uitree.h, qtUiTree.save)
Mỗi nút: id, parent, bounds [l, t, r, b], visible (phần còn thấy sau clip), role, text, font_size, font_weight,
line_count, color, selected, clickable.

  R1  nhóm chọn-một mang đúng một trong ba vai: tab / choice (2-5 ô, một hàng) / list (mỗi dòng một mục)
  R3  khe dọc giữa hai khối liền nhau trong một cột thuộc thang {0,4,8,12,16,24,32,48,64} ± 0,5 dp
  R8  hộp chữ bị cắt (visible thấp hơn bounds) hay hai hộp chữ chồng nhau
  R9  cặp màn parity (design_lint_parity.json): cùng nhãn thì cùng vai/kiểu, số dòng, token màu; cao lệch > 4 dp là đỏ
  R11 cỡ chữ thuộc thang {12,14,16,18,20,24,32}, không dưới 12; tên hàng trong một danh sách cùng kiểu
  R14 nhãn nút / tab / mục menu 1-4 chữ (bỏ số và đơn vị)
"""
from __future__ import annotations

import json
import hashlib
import math
from functools import lru_cache
from pathlib import Path
import re
import numpy as np
from PIL import Image

import design_lint as dl

PARITY = Path(__file__).with_name("design_lint_parity.json")
FONT_SCALE = (12, 14, 16, 18, 20, 24, 32)
CONTROL_ROLES = {"button", "tab", "menuitem", "dropdownlist", "checkbox", "switch", "radiobutton", "choice", "listitem"}
# R14 xét nhãn của điều khiển; hàng danh sách mang dữ liệu (tên sách, tên chương), không phải nhãn.
LABEL_ROLES = CONTROL_ROLES - {"checkbox", "switch", "listitem"}
UNIT = re.compile(r"^(?:[\d.,:/%×x+−-]+|db|hz|khz|mb|gb|kb|ms|s|phút|giây|giờ|%|×)$", re.I)


def tree_path(shot: dl.Shot) -> Path:
    return shot.path.with_name(shot.path.stem + ".tree.json")


def load(shot: dl.Shot) -> dict | None:
    path = tree_path(shot)
    if not path.is_file():
        return None
    tree = json.loads(path.read_text(encoding="utf-8"))
    if tree.get("image", shot.path.name) != shot.path.name:
        raise ValueError("tree names a different image")
    if tree.get("image_sha256") and hashlib.sha256(shot.path.read_bytes()).hexdigest() != tree["image_sha256"]:
        raise ValueError("image/tree checksum mismatch; recapture the pair")
    if not all(math.isfinite(tree[k]) and tree[k] > 0 for k in ("width", "height")):
        raise ValueError("invalid viewport")
    nodes = tree["nodes"]
    if not nodes:
        raise ValueError("empty UI tree")
    for i, node in enumerate(nodes):
        if node["id"] != i or not -1 <= node["parent"] < i:
            raise ValueError("node ids must be sequential with parents before children")
        for field in ("bounds", "visible"):
            values = node.get(field, node["bounds"])
            if len(values) != 4 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in values):
                raise ValueError(f"invalid {field}")
            node[field] = list(values)
        node["children"] = []
    for node in nodes:
        if node["parent"] >= 0:
            nodes[node["parent"]]["children"].append(node["id"])
    controls = [n for n in nodes if n.get("role") in CONTROL_ROLES and shown(n)]
    if controls:
        with Image.open(shot.path) as image:
            rgb = np.asarray(image.convert("RGB"))
        sx, sy = rgb.shape[1] / tree["width"], rgb.shape[0] / tree["height"]
        page = np.median(rgb[::max(1, rgb.shape[0] // 32), :max(1, round(sx * 2))], axis=(0, 1))
        accent = dl.token("accent", shot.dark)
        for node in controls:
            x0, y0, x1, y1 = node["visible"]
            crop = rgb[max(0, round(y0 * sy)):max(0, round(y1 * sy)),
                       max(0, round(x0 * sx)):max(0, round(x1 * sx))]
            if not crop.size:
                continue
            sample = crop[::max(1, crop.shape[0] // 16), ::max(1, crop.shape[1] // 32)]
            background = np.median(sample, axis=(0, 1))
            node.setdefault("background_color", "#%02x%02x%02x" % tuple(background.astype(int)))
            bottom = crop[-max(1, round(4 * sy)):].astype(float)
            underline = np.any(np.sum(np.abs(bottom - accent), axis=2) < 24, axis=0).sum() >= 4 * sx
            style = "filled" if dl.delta_e(background, page) >= 3 else "underline" if underline else "plain"
            node.setdefault("control_style", style)
    return tree


def height(node) -> float:
    return node["bounds"][3] - node["bounds"][1]


def width(node) -> float:
    return node["bounds"][2] - node["bounds"][0]


def shown(node) -> bool:
    v = node.get("visible", node["bounds"])
    return v[2] - v[0] > 0.5 and v[3] - v[1] > 0.5


def visible_label(tree: dict, node: dict) -> str:
    """Chữ hiện trên điều khiển: chữ của nó, không có thì chữ đầu tiên ở con cháu."""
    if node.get("text"):
        return node["text"]
    stack = list(node["children"])
    while stack:
        child = tree["nodes"][stack.pop(0)]
        if child.get("text"):
            return child["text"]
        stack[:0] = child["children"]
    return ""


def label(tree: dict, node: dict) -> str:
    """Nhãn để nêu tên / ghép cặp: chữ hiện, không có thì mô tả trợ năng."""
    return visible_label(tree, node) or node.get("description", "")


def words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", text.strip()) if w and not UNIT.match(w.strip("()·,."))]


# ---------------------------------------------------------------- luật

def rule_r1(key: str, tree: dict) -> list[dl.Finding]:
    out = []
    nodes = tree["nodes"]
    for parent in nodes:
        items = [nodes[c] for c in parent["children"] if nodes[c].get("selected") is not None and shown(nodes[c])]
        if len(items) < 2 or not (parent.get("selectable_group") or any(n["selected"] for n in items)):
            continue
        roles = {n.get("role") for n in items}
        tops = sorted({round(n["bounds"][1]) for n in items})
        rows = 1 + sum(1 for a, b in zip(tops, tops[1:]) if b - a > 1)
        one_row = rows == 1
        one_column = rows == len(items)
        selection_count = sum(bool(n["selected"]) for n in items)
        if roles == {"tab"} and one_row and selection_count == 1:
            continue
        if roles <= {"radiobutton", "choice"} and one_row and 2 <= len(items) <= 5 and selection_count == 1:
            continue
        if roles <= {"radiobutton", "listitem"} and one_column and selection_count == 1:
            continue
        shape = "một hàng" if one_row else "một cột" if one_column else f"lưới {rows} hàng"
        names = ", ".join(sorted(str(r) for r in roles))
        out.append(dl.Finding("R1", key, f"nhóm chọn-một {len(items)} mục ({shape}, vai: {names}, chọn {selection_count}) không thuộc tab / choice / list",
                              [round(min(n["bounds"][0] for n in items)), round(min(n["bounds"][1] for n in items)),
                               round(max(n["bounds"][2] for n in items)), round(max(n["bounds"][3] for n in items))]))
    return out


def content_nodes(tree: dict) -> list[dict]:
    """Khối nội dung: nút có chữ, có vai hay bấm được, đang thấy; bỏ khung bao trùm cả màn."""
    nodes = [n for n in tree["nodes"] if shown(n) and (n.get("text") or n.get("role") or n.get("clickable"))]
    area = tree["width"] * tree["height"]
    return [n for n in nodes if width(n) * height(n) < 0.5 * area]


def rule_r3(key: str, tree: dict) -> list[dl.Finding]:
    out = []
    nodes = content_nodes(tree)
    # Bỏ nút nằm trong nút khác cùng tập (chữ trong nút bấm): khe đo giữa các khối ngoài cùng.
    def inside(a, b):
        return (a is not b and a["bounds"][0] >= b["bounds"][0] - 0.5 and a["bounds"][2] <= b["bounds"][2] + 0.5
                and a["bounds"][1] >= b["bounds"][1] - 0.5 and a["bounds"][3] <= b["bounds"][3] + 0.5)
    blocks = [n for n in nodes if not any(inside(n, m) and (width(m) * height(m) > width(n) * height(n) + 0.5
                                                        or m['id'] < n['id']) for m in nodes)]
    seen = set()
    for a in blocks:
        below = [b for b in blocks if b["bounds"][1] >= a["bounds"][3] - 0.5
                 and b["parent"] == a["parent"] and b["id"] != a["id"]
                 and min(a["bounds"][2], b["bounds"][2]) - max(a["bounds"][0], b["bounds"][0]) > 0.5 * min(width(a), width(b))]
        if not below:
            continue
        b = min(below, key=lambda n: n["bounds"][1])
        gap = round(b["bounds"][1] - a["bounds"][3], 2)
        if (a["id"], b["id"]) in seen:
            continue
        seen.add((a["id"], b["id"]))
        if min(abs(gap - s) for s in dl.SPACING_SCALE) > 0.5:
            out.append(dl.Finding("R3", key, f"khe dọc {gap:g} dp giữa '{label(tree, a)[:24]}' và '{label(tree, b)[:24]}'",
                                  [round(a["bounds"][0]), round(a["bounds"][3]), round(a["bounds"][2]), round(b["bounds"][1])]))
    return out


def rule_r8(key: str, tree: dict) -> list[dl.Finding]:
    out = []
    texts = [n for n in tree["nodes"] if n.get("text") and shown(n)]
    for n in texts:
        v, b = n["visible"], n["bounds"]
        lines = [line["bounds"] for line in n.get("lines", [])] or [b]
        cut = any((line[1] < v[1] - 0.5 < line[3] or line[1] < v[3] + 0.5 < line[3])
                  and min(line[3], v[3]) - max(line[1], v[1]) > 0.5 for line in lines)
        if cut:
            out.append(dl.Finding("R8", key, f"chữ '{n['text'][:30]}' bị cắt: thấy {v[3] - v[1]:g}/{b[3] - b[1]:g} dp",
                                  [round(x) for x in v]))
    for i, a in enumerate(texts):
        for c in texts[i + 1:]:
            va, vc = a["visible"], c["visible"]
            w = min(va[2], vc[2]) - max(va[0], vc[0])
            h = min(va[3], vc[3]) - max(va[1], vc[1])
            if w <= 1 or h <= 1:
                continue
            def ancestor(parent, child):
                while child["parent"] >= 0:
                    if child["parent"] == parent["id"]:
                        return True
                    child = tree["nodes"][child["parent"]]
                return False
            if not ancestor(a, c) and not ancestor(c, a):
                out.append(dl.Finding("R8", key, f"hộp chữ chồng nhau: '{a['text'][:20]}' và '{c['text'][:20]}' ({w:g}×{h:g} dp)",
                                      [round(max(va[0], vc[0])), round(max(va[1], vc[1])),
                                       round(min(va[2], vc[2])), round(min(va[3], vc[3]))]))
    return out


def rule_r11(key: str, tree: dict) -> list[dl.Finding]:
    out = []
    nodes = tree["nodes"]
    for n in nodes:
        size = n.get("font_size")
        if size is None or not n.get("text") or not shown(n):
            continue
        if size < 12 or min(abs(size - s) for s in FONT_SCALE) > 0.01:
            out.append(dl.Finding("R11", key, f"cỡ chữ {size:g} ngoài thang ('{n['text'][:24]}')", [round(x) for x in n["bounds"]]))
    # Tên hàng: >= 3 hàng bấm được cùng cha, cao gần nhau -> chữ đầu của mỗi hàng cùng cỡ / đậm / màu.
    for parent in nodes:
        rows = [nodes[c] for c in parent["children"] if nodes[c].get("clickable") and shown(nodes[c])]
        if (len(rows) < 2 or not all(abs(rows[0]["bounds"][0] - r["bounds"][0]) <= 0.5
                                   and abs(width(rows[0]) - width(r)) <= 1
                                   and abs(height(rows[0]) - height(r)) <= 4 for r in rows)
                or any(a["bounds"][3] > b["bounds"][1] + 0.5
                       for a, b in zip(sorted(rows, key=lambda r: r["bounds"][1]), sorted(rows, key=lambda r: r["bounds"][1])[1:]))):
            continue
        styles = {}
        for row in rows:
            first = first_text(tree, row)
            if first is not None and first.get("font_size") is not None:
                styles[row["id"]] = (first.get("font_size"), first.get("font_weight"), first.get("color"))
        if len(styles) >= 2 and len(set(styles.values())) > 1:
            kinds = sorted({f"{s[0]:g}/{s[1]}/{s[2]}" for s in styles.values()})
            out.append(dl.Finding("R11", key, f"tên hàng trong một danh sách khác kiểu: {', '.join(kinds)}",
                                  [round(parent["bounds"][0]), round(parent["bounds"][1]),
                                   round(parent["bounds"][2]), round(parent["bounds"][3])]))
    return out


def first_text(tree: dict, node: dict) -> dict | None:
    if node.get("text") and node.get("font_size") is not None:
        return node
    for child in node["children"]:
        found = first_text(tree, tree["nodes"][child])
        if found is not None:
            return found
    return None


def rule_r14(key: str, tree: dict) -> list[dl.Finding]:
    out = []
    for n in tree["nodes"]:
        if n.get("role") not in LABEL_ROLES or not shown(n):
            continue
        # Nút chỉ có biểu tượng: mô tả trợ năng nên đầy đủ ("Thêm tuỳ chọn cho An"), không đếm chữ; rỗng cả hai là đỏ.
        text = visible_label(tree, n)
        if not text.strip() and n.get("description", "").strip():
            continue
        count = len(words(text))
        if count > 4 or not text.strip():
            out.append(dl.Finding("R14", key, f"nhãn {n['role']} {count} chữ: '{text[:40]}'", [round(x) for x in n["bounds"]]))
    return out


TREE_RULES = (rule_r1, rule_r3, rule_r8, rule_r11, rule_r14)


# ---------------------------------------------------------------- R9 cặp parity

TOKEN_COLOURS = {
    "bg": ("#f5f3ef", "#121110"), "surface": ("#ffffff", "#1c1a17"),
    "focus": ("#a0600c", "#e9a945"), "accent-soft": ("#f7ead5", "#352817"),
    "text": ("#1a1814", "#ece8e1"), "text-2": ("#4f4a43", "#bab3a8"), "text-3": ("#67615a", "#a0998e"),
    "fg-3": ("#8a8478", "#7a746a"), "accent": ("#d4912b", "#e9a945"), "accent-ink": ("#1d1304", "#1b1204"),
    "accent-text": ("#8a5309", "#f0b961"), "danger": ("#b23b33", "#ef7b70"), "success": ("#2a7554", "#5cc596"),
    "warning": ("#905b10", "#e8b64c"),
}


@lru_cache(maxsize=512)
def token_of(colour: str | None, dark: bool) -> str | None:
    if not colour:
        return None
    if len(colour) == 9:
        if colour[1:3] != "ff":
            return colour  # Preserve alpha; do not claim an opaque token.
        colour = "#" + colour[3:]
    best = min(TOKEN_COLOURS, key=lambda name: dl.delta_e(dl.hex_rgb(colour), dl.hex_rgb(TOKEN_COLOURS[name][int(dark)])))
    return best if dl.delta_e(dl.hex_rgb(colour), dl.hex_rgb(TOKEN_COLOURS[best][int(dark)])) < 3 else colour


def describe(tree: dict, dark: bool) -> dict[str, dict]:
    """Mô tả chuẩn hoá của một màn: nhãn -> vai, số dòng, cao, token màu chữ."""
    out = {}
    for n in tree["nodes"]:
        if not shown(n):
            continue
        role = n.get("role")
        if role in CONTROL_ROLES or (n.get("text") and n.get("font_size") is not None):
            text = label(tree, n).strip().casefold()
            if not text or text in out:
                continue
            leaf = first_text(tree, n) or n
            out[text] = {"role": role or "text", "control": n.get("control_style", role or "text"),
                         "lines": leaf.get("line_count"), "height": height(n),
                         "token": token_of(leaf.get("color"), dark), "background": token_of(n.get("background_color"), dark)}
    return out


def load_parity(path: Path = PARITY) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {p["id"] for p in json.loads((dl.ROOT / "scripts/ui_parity_pairs.json").read_text(encoding="utf-8"))["pairs"]}
    for pair in data["pairs"]:
        if pair["pair"] not in known:
            raise ValueError(f"design_lint_parity: cặp '{pair['pair']}' không có trong ui_parity_pairs.json")
    return data["pairs"]


def rule_r9(trees: dict[str, dict], pairs: list[dict]) -> list[dl.Finding]:
    out = []
    for pair in pairs:
        for variant in pair.get("variants", ["_light", "_dark"]):
            sides = {p: f"{p}/{pair[p]}{variant}.png" for p in ("android", "qt", "web") if p in pair}
            present = {p: k for p, k in sides.items() if k in trees}
            if len(present) < 2:
                continue
            dark = "dark" in variant
            described = {p: describe(trees[k], dark) for p, k in present.items()}
            base, *others = list(present)
            for other in others:
                a, b = described[base], described[other]
                for text in sorted(set(a) & set(b)):
                    x, y = a[text], b[text]
                    problems = [f"{field} {x[field]} ≠ {y[field]}" for field in ("role", "control", "lines", "token", "background")
                                if x[field] is not None and y[field] is not None and x[field] != y[field]]
                    if abs(x["height"] - y["height"]) > 4:
                        problems.append(f"cao {x['height']:g} ≠ {y['height']:g} dp")
                    if problems:
                        out.append(dl.Finding("R9", present[other],
                                              f"cặp {pair['pair']} với {present[base]}: '{text[:30]}' " + "; ".join(problems)))
    return out


def lint_one(shot: dl.Shot) -> tuple[dict | None, list[dl.Finding], str | None]:
    """Một ảnh: đọc cây cạnh ảnh rồi chạy các luật một cây (chạy được trong tiến trình con)."""
    try:
        tree = load(shot)
    except Exception as exc:
        return None, [], f"{shot.key}: cây UI hỏng: {exc}"
    if tree is None:
        return None, [], None
    return tree, [f for rule in TREE_RULES for f in rule(shot.key, tree)], None


def lint_shots(shots: list[dl.Shot], measured: dict | None = None, pool=None) -> tuple[list[dl.Finding], int, list[str]]:
    findings, errors, trees = [], [], {}
    if pool is not None and len(shots) > 8:
        results = list(pool.map(lint_one, shots, chunksize=8))
    else:
        results = [lint_one(shot) for shot in shots]
    for shot, (tree, found, error) in zip(shots, results):
        if error:
            errors.append(error)
        if tree is None:
            continue
        trees[shot.key] = tree
        findings += found
        if measured is not None:
            counts = measured.setdefault(shot.platform, {field: 0 for field in
                ("nodes", "roles", "text_nodes", "font_size", "line_count", "color", "background_color", "control_style")})
            for node in tree["nodes"]:
                counts["nodes"] += 1
                counts["roles"] += bool(node.get("role"))
                counts["text_nodes"] += bool(node.get("text"))
                for field in ("font_size", "line_count", "color", "background_color", "control_style"):
                    counts[field] += node.get(field) is not None
    try:
        findings += rule_r9(trees, load_parity())
    except Exception as exc:
        errors.append(f"R9: {exc}")
    return findings, len(trees), errors


def coverage(shots: list[dl.Shot]) -> dict:
    """Missing sidecars are unmeasured, never a green result for tree rules."""
    return {platform: {"images": sum(s.platform == platform for s in shots),
                       "sidecars": sum(s.platform == platform and tree_path(s).is_file() for s in shots)}
            for platform in dl.SCALE}
