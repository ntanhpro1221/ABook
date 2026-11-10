"""Máy đo thiết kế trên ẢNH ĐÃ VẼ của cả ba nền tảng (việc 10, soát thiết kế 10-11).

Cổng cũ kiểm luật trên mã nguồn và so ảnh hôm nay với ảnh vàng hôm qua; ảnh vàng xấu thì vẫn xanh.
Máy này đo chính điểm ảnh (và cây UI xuất cạnh ảnh, xem design_lint_tree.py):

  R4  công tắc bật = --focus (ΔE < 3); <= 1 nút nền --accent mỗi màn; nút chính cao 44-56 dp
  R5  lưới lựa chọn không có hàng cuối thiếu ô
  R6  <= 3 trục mép trái mỗi vùng; không trộn căn giữa / căn trái trong một vùng
  R7  nhóm trạng thái (np_*, mini_*, book_*): bìa, thanh tiến độ, nút phát, nút chính cùng toạ độ ± 1 dp
  R8  mép sheet / mép vùng cuộn không cắt ngang một dòng chữ
  R10 không dải trống dọc > 40 % màn, không nửa ngang trống > 40 % ở khổ rộng

Ngoại lệ chỉ có dạng "ảnh này, luật này, lý do này" trong design_lint_exceptions.json; không có ngưỡng nới chung.
Chạy từ _internal:
  runtime/.venv/Scripts/python.exe -X utf8 scripts/design_lint.py [--qt DIR] [--web DIR] [--json OUT] [--strict]
Mặc định chỉ BÁO CÁO (exit 0 khi đo được); --strict thoát 1 khi còn ô đỏ.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import sys
import time

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
ANDROID_SHOTS = ROOT / "mobile/android/app/src/test/snapshots"
QT_SHOTS = ROOT / "desktop_qt/build/d2shots"
EXCEPTIONS = Path(__file__).with_name("design_lint_exceptions.json")
GROUPS = Path(__file__).with_name("design_lint_groups.json")

# Điểm ảnh trên một dp: Roborazzi chụp xxhdpi (w360dp = 1080 px); Qt và web chụp px logic.
SCALE = {"android": 3.0, "qt": 1.0, "web": 1.0}
SPACING_SCALE = (0, 4, 8, 12, 16, 24, 32, 48, 64)

# Token DESIGN.md §5.1 (sáng, tối).
TOKENS = {
    "accent": ("#d4912b", "#e9a945"),
    "focus": ("#a0600c", "#e9a945"),
    "switch-off": ("#857e72", "#75706a"),
    "switch-thumb": ("#ffffff", "#1b1204"),
}

# Nút chính: điện thoại 48 (soát 10-11: 44-56), máy tính 40 (DESIGN.md §6 "cao 48 / 40") ± 4.
BUTTON_HEIGHT = {"android": (44, 56), "qt": (36, 44), "web": (36, 44)}

KEYLINE_SLACK_DP = 3
INK = 40            # tổng |Δ| ba kênh so với nền của hàng: điểm có mực
MIN_FULL_SCREEN_DP = 600
RULES = ("R1", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R14")


@dataclass
class Finding:
    rule: str
    image: str          # "<nền tảng>/<tên tệp>"
    detail: str
    box: list[int] = field(default_factory=list)   # x0, y0, x1, y1 (px ảnh) khi có


@dataclass
class Shot:
    platform: str
    path: Path

    @property
    def key(self) -> str:
        return f"{self.platform}/{self.path.name}"

    @property
    def scale(self) -> float:
        return SCALE[self.platform]

    @property
    def dark(self) -> bool:
        return bool(re.search(r"(^|[_-])dark([_-]|\.|$)", self.path.name))


# ---------------------------------------------------------------- màu

def hex_rgb(value: str) -> np.ndarray:
    value = value.lstrip("#")
    return np.array([int(value[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def lab(rgb) -> np.ndarray:
    """sRGB 0-255 -> CIELAB (D65)."""
    c = np.asarray(rgb, dtype=float) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.2126, 0.0193], [0.3576, 0.7152, 0.1192], [0.1805, 0.0722, 0.9505]])
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def delta_e(a, b) -> float:
    return float(np.linalg.norm(lab(a) - lab(b)))


def token(name: str, dark: bool) -> np.ndarray:
    return hex_rgb(TOKENS[name][int(dark)])


# ---------------------------------------------------------------- phân tích ảnh

@dataclass
class Band:
    top: int
    bottom: int                      # bao gồm
    segments: list[tuple[int, int]]  # cụm cột mực [x0, x1] tách bởi khe >= 8 dp

    @property
    def left(self) -> int:
        return self.segments[0][0]

    @property
    def right(self) -> int:
        return self.segments[-1][1]

    @property
    def height(self) -> int:
        return self.bottom - self.top + 1


def runs(mask: np.ndarray, merge: int = 1) -> list[tuple[int, int]]:
    """Các đoạn True liên tiếp [a, b] (bao gồm); hai đoạn cách nhau < merge chỗ trống thì gộp."""
    idx = np.flatnonzero(mask)
    if not len(idx):
        return []
    cuts = np.flatnonzero(np.diff(idx) > merge)
    starts = np.r_[idx[0], idx[cuts + 1]]
    ends = np.r_[idx[cuts], idx[-1]]
    return list(zip(starts.tolist(), ends.tolist()))


class Analysis:
    def __init__(self, shot: Shot, rgb: np.ndarray | None = None):
        self.shot = shot
        if rgb is None:
            with Image.open(shot.path) as im:
                rgb = np.asarray(im.convert("RGB"))
        self.rgb = rgb.astype(np.int16)
        self.h, self.w, _ = self.rgb.shape
        self.s = shot.scale
        # Nền của từng hàng = trung vị hàng: chịu được bìa, sheet, lớp mờ (mỗi hàng một nền).
        self.bg = np.median(self.rgb, axis=1).astype(np.int16)
        d = self.rgb - self.bg[:, None, :]
        np.abs(d, out=d)
        self.diff = d.sum(axis=2, dtype=np.int16)
        self.ink = self.diff > INK
        self._bands = None
        self._labels = None
        self._colour_cache: dict = {}
        self._page_diff = None
        self._surfaces = None
        # Nền màn = nền hàng phổ biến nhất (hàng có bìa / nút tràn ngang không được tính là nền).
        keys, counts = np.unique(self.bg // 4, axis=0, return_counts=True)
        self.page_bg = (keys[counts.argmax()] * 4 + 2).astype(np.int16)
        self.page_rows = np.abs(self.bg - self.page_bg).sum(axis=1) <= 12

    def dp(self, px: float) -> float:
        return px / self.s

    def px(self, dp: float) -> int:
        return int(round(dp * self.s))

    @property
    def full_screen(self) -> bool:
        return self.h / self.s >= MIN_FULL_SCREEN_DP and self.w / self.s >= 300

    def bands(self, x0: int = 0, x1: int | None = None) -> list[Band]:
        if x0 == 0 and x1 is None and self._bands is not None:
            return self._bands
        if x0 == 0 and (x1 is None or x1 >= self.w):
            ink = self.ink
        else:
            # Nền hàng tính riêng trong vùng: mỗi vùng (thanh bên, trình phát, mặt đọc) có nền của nó.
            part = self.rgb[:, x0:x1]
            ink = np.abs(part - np.median(part, axis=1).astype(np.int16)[:, None, :]).sum(axis=2) > INK
        out = []
        for top, bottom in runs(ink.sum(axis=1) > 1, merge=self.px(2)):
            cols = ink[top:bottom + 1].any(axis=0)
            segments = [(a + x0, b + x0) for a, b in runs(cols, merge=self.px(8))]
            out.append(Band(top, bottom, segments))
        if x0 == 0 and x1 is None:
            self._bands = out
        return out

    @property
    def page_diff(self) -> np.ndarray:
        if self._page_diff is None:
            d = self.rgb - self.page_bg
            np.abs(d, out=d)
            self._page_diff = d.sum(axis=2, dtype=np.int16)
        return self._page_diff

    def colour_components(self, colour: np.ndarray, min_alpha: float = 0.3):
        """Thành phần liên thông của điểm mang một màu phủ trên nền màn với độ đục >= min_alpha
        (nút nền hổ phách kể cả khi bị vô hiệu = hổ phách mờ; không tính --accent-soft ~ 0,14-0,2)."""
        key = (tuple(colour.tolist()), min_alpha)
        if key in self._colour_cache:
            return self._colour_cache[key]
        u = (colour - self.page_bg).astype(np.float32)
        mask = np.zeros((self.h, self.w), bool)
        idx = np.flatnonzero(self.page_diff > 16)   # nền màn thì khỏi tính
        v = (self.rgb.reshape(-1, 3)[idx] - self.page_bg).astype(np.float32)
        alpha = (v @ u) / max(float(u @ u), 1.0)
        residual = np.abs(v - alpha[:, None] * u).sum(axis=1)
        mask.flat[idx] = (alpha >= min_alpha) & (alpha <= 1.15) & (residual <= 36)
        if mask.any():
            rows = np.flatnonzero(mask.any(axis=1))
            cols = np.flatnonzero(mask.any(axis=0))
            y0, y1 = max(0, rows[0] - 4), rows[-1] + 5
            x0, x1 = max(0, cols[0] - 4), cols[-1] + 5
            mask[y0:y1, x0:x1] = ndimage.binary_closing(mask[y0:y1, x0:x1], iterations=2)
        labels, _ = ndimage.label(mask)
        result = labels, ndimage.find_objects(labels)
        self._colour_cache[key] = result
        return result

    def surface_components(self):
        """Thành phần khác nền màn (bìa, mặt nổi)."""
        labels, _ = ndimage.label(self.page_diff > INK)
        return labels, ndimage.find_objects(labels)

    def surfaces(self) -> list[tuple[tuple[int, int, int, int], np.ndarray]]:
        """Mặt phẳng một màu đủ lớn (sheet, popover, thẻ, vùng): (x0, y0, x1, y1), màu. Đo ở 1/4 độ phân giải."""
        if self._surfaces is not None:
            return self._surfaces
        k = 4
        small = self.rgb[::k, ::k] // 8
        keys = (small[..., 0].astype(np.int32) << 10) | (small[..., 1].astype(np.int32) << 5) | small[..., 2]
        counts = np.bincount(keys.ravel(), minlength=1 << 15)
        out = []
        for value in np.argsort(counts)[::-1][:5]:
            if counts[value] < 0.02 * keys.size:
                break
            labels, _ = ndimage.label(ndimage.binary_closing(keys == value, iterations=2))
            for index, sl in enumerate(ndimage.find_objects(labels), start=1):
                y0, y1, x0, x1 = sl[0].start * k, sl[0].stop * k, sl[1].start * k, sl[1].stop * k
                if (y1 - y0) < self.px(100) or (x1 - x0) < self.px(100) or (labels[sl] == index).mean() < 0.5:
                    continue
                colour = (np.array([value >> 10, (value >> 5) & 31, value & 31]) * 8 + 4).astype(np.int16)
                out.append(((x0, y0, min(x1, self.w), min(y1, self.h)), colour))
        self._surfaces = out
        return out

    def bands_in(self, box: tuple[int, int, int, int], colour: np.ndarray) -> list[Band]:
        x0, y0, x1, y1 = box
        ink = np.abs(self.rgb[y0:y1, x0:x1] - colour).sum(axis=2) > INK
        out = []
        for top, bottom in runs(ink.sum(axis=1) > 1, merge=self.px(2)):
            cols = ink[top:bottom + 1].any(axis=0)
            out.append(Band(top + y0, bottom + y0, [(a + x0, b + x0) for a, b in runs(cols, merge=self.px(8))]))
        return out

    def components(self):
        if self._labels is None:
            self._labels, _ = ndimage.label(self.ink)
            self._objects = ndimage.find_objects(self._labels)
        return self._labels, self._objects

    def panes(self) -> list[tuple[int, int]]:
        """Khổ rộng: tách cột theo đổi nền dọc (thanh bên) hay vạch chia cao hết màn."""
        if self.w / self.s < 600:
            return [(0, self.w)]
        # Ranh giới vùng = cột mà >= 80 % số hàng đổi màu khi bước qua (thanh bên, vạch chia cao hết màn);
        # popover / bìa chỉ phủ một phần chiều cao nên không tách vùng.
        step = np.abs(self.rgb[:, 2:] - self.rgb[:, :-2]).sum(axis=2) > 20
        change = np.zeros(self.w - 1, bool)
        change[:-1] |= step.mean(axis=0) > 0.8
        divider = self.ink.mean(axis=0) > 0.9
        cuts = sorted(set(np.flatnonzero(change).tolist()) | set(np.flatnonzero(divider).tolist()))
        panes, start = [], 0
        for cut in cuts + [self.w]:
            if cut - start >= self.px(120):
                panes.append((start, cut))
            start = max(start, cut + 1)
        return panes or [(0, self.w)]


# ---------------------------------------------------------------- luật trên ảnh

def rule_r10(a: Analysis) -> list[Finding]:
    """Vùng trống: dải ngang không mực > 40 % chiều cao; khổ rộng: dải dọc trống > 40 % bề ngang."""
    if not a.full_screen:
        return []
    out = []
    empty_rows = runs(~(a.ink.sum(axis=1) > 1) & a.page_rows)
    if empty_rows:
        top, bottom = max(empty_rows, key=lambda r: r[1] - r[0])
        share = (bottom - top + 1) / a.h
        if share > 0.40:
            out.append(Finding("R10", a.shot.key, f"dải trống {share:.0%} chiều cao (y {top}-{bottom})",
                               [0, top, a.w, bottom]))
    if a.w / a.s >= 600:
        empty_cols = runs(~(a.ink.sum(axis=0) > 1))
        if empty_cols:
            left, right = max(empty_cols, key=lambda r: r[1] - r[0])
            share = (right - left + 1) / a.w
            if share > 0.40:
                out.append(Finding("R10", a.shot.key, f"cột trống {share:.0%} bề ngang (x {left}-{right})",
                                   [left, 0, right, a.h]))
    return out


def keylines(a: Analysis, bands: list[Band], x0: int, width: int) -> list[float]:
    """Mép trái của khối chữ (cách đo của scan.py, soát 10-11), gom thành trục.

    Đo mép MỰC chứ không phải mép hộp: chữ cái đầu có lề riêng 1-3 dp, nên hai mép cách nhau <= 3 dp là một trục.
    Bỏ khối chạm mép vùng (<= 1 dp: vạch chia, dải tràn lề), đó không phải chữ.
    """
    edges = sorted({round(a.dp(b.left - x0)) for b in bands
                    if b.height >= a.px(4) and b.right - b.left > a.px(10)
                    and a.px(1) < b.left - x0 < width * 0.4})
    groups: list[list[int]] = []
    for e in edges:
        if groups and e - groups[-1][-1] <= KEYLINE_SLACK_DP:
            groups[-1].append(e)
        else:
            groups.append([e])
    return [g[0] for g in groups]


def inside_filled(a: Analysis, band: Band, x0: int) -> bool:
    """Dải nằm trong một khối tô nền thụt lề (nút, thẻ): nền hàng khác màu ở mép vùng."""
    y = (band.top + band.bottom) // 2
    return bool(np.abs(a.rgb[y, x0 + a.px(2)] - a.bg[y]).sum() > 24)


def rule_r6(a: Analysis) -> list[Finding]:
    if not a.full_screen:
        return []
    out = []
    for x0, x1 in a.panes():
        width = x1 - x0
        bands = a.bands(x0, x1)
        keys = keylines(a, bands, x0, width)
        if len(keys) > 3:
            out.append(Finding("R6", a.shot.key, f"{len(keys)} trục mép trái (dp: {' '.join(map(str, keys))})",
                               [x0, 0, x1, a.h]))
        # Trộn căn: khối một cụm nằm giữa (lệch tâm <= 2 dp, thụt > 16 dp so với lề) cạnh khối căn lề.
        if not keys:
            continue
        margin = x0 + a.px(keys[0])
        # Chỉ khối cao cỡ dòng chữ (<= 48 dp): hộp thoại giữa màn là một mặt nổi, không phải chữ căn giữa.
        centred = [b for b in bands if len(b.segments) == 1 and a.px(4) <= b.height <= a.px(48)
                   and not inside_filled(a, b, x0)
                   and b.left - margin > a.px(16) and abs((b.left - x0) - (x1 - 1 - b.right)) <= a.px(2)
                   and b.right - b.left < width * 0.8]
        # Nút chữ phụ căn giữa ngay dưới nút tô nền tràn ngang (cụm hành động ở đáy) là một khối, không phải trộn căn.
        buttons = [b for b in bands if inside_filled(a, b, x0)]
        centred = [b for b in centred if not any(0 <= b.top - f.bottom <= a.px(64) for f in buttons)]
        flush = [b for b in bands if abs(b.left - margin) <= a.px(1) and b.height >= a.px(4)
                 and b.right - b.left > a.px(10)]
        if centred and len(flush) >= 2:
            b = centred[0]
            out.append(Finding("R6", a.shot.key,
                               f"trộn căn giữa ({len(centred)} khối, đầu tiên y {b.top}) với căn trái ({len(flush)} khối)",
                               [b.left, b.top, b.right, b.bottom]))
    return out


def rule_r5(a: Analysis) -> list[Finding]:
    """Lưới lựa chọn: hàng đủ k >= 3 ô cùng cỡ, rồi ngay sau một hàng 1..k-1 ô cùng cỡ (xét từng vùng)."""
    out, seen = [], set()
    candidates = [(a.bands(x0, x1), x1 - x0) for x0, x1 in a.panes()]
    # Mặt phẳng gần cả màn đã được xét qua vùng (pane); chỉ xét thêm mặt nổi nhỏ hơn (popover, sheet, thẻ).
    candidates += [(a.bands_in(box, colour), box[2] - box[0]) for box, colour in a.surfaces()
                   if (box[2] - box[0]) * (box[3] - box[1]) < 0.6 * a.w * a.h]
    for bands, width in candidates:
        for f in grid_short_rows(a, bands, width):
            if (f.box[1], f.box[3]) not in seen:
                seen.add((f.box[1], f.box[3]))
                out.append(f)
    return out


def grid_short_rows(a: Analysis, bands: list[Band], width: int) -> list[Finding]:
    out = []
    for i in range(len(bands) - 1):
        full, last = bands[i], bands[i + 1]
        k, m = len(full.segments), len(last.segments)
        if k < 3 or not 1 <= m < k:
            continue
        widths = [b - a_ for a_, b in full.segments]
        if min(widths) < a.px(6) or max(widths) > 3 * min(widths) or max(widths) > width / k:
            continue
        centres = [(x0 + x1) / 2 for x0, x1 in full.segments]
        pitch = np.diff(centres)
        if pitch.max() - pitch.min() > a.px(4):
            continue
        # Hàng trên phải là hàng đầy: nếu có hàng trước cùng số ô thì càng chắc; một hàng đầy cũng đủ (3+2, 5+2).
        lw = [b - a_ for a_, b in last.segments]
        if min(lw) < 0.4 * min(widths) or max(lw) > 2.5 * max(widths):
            continue
        if abs(last.height - full.height) > max(a.px(2), 0.25 * full.height):
            continue  # cao khác: hàng nhãn dưới hàng icon, không phải hàng cùng lưới
        gap = last.top - full.bottom
        if gap < a.px(8) or gap > max(2.5 * full.height, a.px(48)):
            continue  # khe < 8 dp: hàng nhãn dưới hàng icon, không phải hàng lưới
        lc = [(x0 + x1) / 2 for x0, x1 in last.segments]
        aligned = all(min(abs(c - d) for d in centres) <= a.px(3) for c in lc)
        same_pitch = m >= 2 and np.all(np.abs(np.diff(lc) - pitch.mean()) <= a.px(4))
        # Hàng cuối căn giữa dưới hàng đầy (popover web 3+2, 5+2): khoảng ô gần bằng bước lưới.
        centred = (m >= 2 and abs(np.mean(lc) - np.mean(centres)) <= a.px(3)
                   and np.all(np.abs(np.diff(lc) - pitch.mean()) <= 0.25 * pitch.mean()))
        if not (aligned or same_pitch or centred):
            continue
        # Hàng "cuối" phải thật là cuối: hàng sau nó (nếu sát) không mang đủ k ô cùng lưới.
        if i + 2 < len(bands) and len(bands[i + 2].segments) == k and bands[i + 2].top - last.bottom <= a.px(48):
            continue
        out.append(Finding("R5", a.shot.key, f"lưới {k} cột, hàng cuối {m} ô (y {last.top})",
                           [full.left, full.top, full.right, last.bottom]))
    return out


def full_bleed(a: Analysis, y: int) -> bool:
    """Hàng y thuộc một mặt phủ hết bề ngang (lớp mờ, mặt sheet): hai mép ảnh cùng màu với nền hàng."""
    if not 0 <= y < a.h:
        return False
    edge = a.px(2)
    return all(np.abs(a.rgb[y, x] - a.bg[y]).sum() <= 24 for x in (edge, a.w - 1 - edge))


def cut_text(a: Analysis, y: int, side: int, reference: float) -> tuple[list, int, float] | None:
    """Mực chạm mép y từ phía side (-1 = trên, +1 = dưới), trông như dòng chữ bị xén."""
    rows = range(y - 1, -1, -1) if side < 0 else range(y, a.h)
    first = next(iter(rows), None)
    if first is None:
        return None
    row = a.ink[first]
    segs = runs(row, merge=a.px(2))
    if len(segs) < 3 or row.mean() > 0.7:
        return None  # vạch chia / viền / ảnh, không phải chữ
    depth = 0
    for r in rows:
        if a.ink[r].sum() <= 1 or depth >= a.px(40):
            break
        depth += 1
    if depth < a.px(2):
        return None   # một chấm, không phải nét chữ bị cắt
    lo, hi = (first - depth + 1, first + 1) if side < 0 else (first, first + depth)
    cut = a.diff[lo:hi][a.ink[lo:hi]]
    strength = np.percentile(cut, 90) / reference if reference else 0
    if strength < 0.35:
        return None   # nằm hẳn trong dải mờ
    return segs, (lo if side < 0 else hi), strength


def rule_r8(a: Analysis) -> list[Finding]:
    """Mép sheet / mặt phủ (nền hàng đổi đột ngột, cả hai phía phủ hết bề ngang) hay đáy màn cắt ngang một dòng chữ."""
    out = []
    bg = a.bg
    jump = np.abs(np.diff(bg, axis=0)).sum(axis=1) > 30
    edges = []
    for y in np.flatnonzero(jump) + 1:
        # Hai mặt phẳng cao >= 24 dp mỗi bên (lớp mờ / mặt sheet); dải mảnh, hàng tô nền không phải mép.
        above = bg[max(0, y - a.px(24)):y]
        below = bg[y:min(a.h, y + a.px(24))]
        if not (len(above) >= a.px(24) and len(below) >= a.px(24)
                and np.ptp(above, axis=0).sum() <= 12 and np.ptp(below, axis=0).sum() <= 12):
            continue
        # Bìa, nút tràn ngang... có lề hai bên: không phải mép sheet. Sheet bo góc: xét sâu 24 dp vào mặt sheet.
        if not (full_bleed(a, y - a.px(3)) or full_bleed(a, y - a.px(24))):
            continue
        if not (full_bleed(a, y + a.px(3)) or full_bleed(a, y + a.px(24))):
            continue
        edges.append(("sheet", int(y)))
    reference = np.percentile(a.diff[a.ink], 90) if a.ink.any() else 0
    found = []
    for kind, y in edges:
        for side in (-1, 1):
            hit = cut_text(a, y, side, reference)
            if hit:
                found.append((kind, y, hit))
    if a.full_screen:
        hit = cut_text(a, a.h, -1, reference)
        if hit:
            found.append(("đáy", a.h, hit))
    # Mảnh dòng còn lại dưới lớp mờ / mép cuộn: dải thấp (<= 6 dp) toàn chấm nhỏ trải rộng = đỉnh hay đáy của
    # một dòng chữ bị xén (np_reading_dark: hàng chấm).
    for b in a.bands():
        if b.height > a.px(6) or b.right - b.left < 0.4 * a.w:
            continue
        dots = runs(a.ink[b.top:b.bottom + 1].any(axis=0), merge=a.px(1))
        widths = [x1 - x0 + 1 for x0, x1 in dots]
        if len(dots) >= 6 and np.median(widths) <= a.px(3) and max(widths) <= a.px(8):
            out.append(Finding("R8", a.shot.key, f"mảnh dòng chữ bị xén y {b.top} ({len(dots)} chấm, cao {a.dp(b.height):.0f} dp)",
                               [b.left, b.top, b.right, b.bottom]))
    for kind, y, (segs, end, strength) in found:
        out.append(Finding("R8", a.shot.key, f"mép {kind} y {y} cắt dòng chữ ({len(segs)} cụm, đậm {strength:.0%})",
                           [segs[0][0], min(y, end), segs[-1][1], max(y, end)]))
    return out


def is_switch(a: Analysis, sl) -> tuple[bool, np.ndarray | None]:
    h = sl[0].stop - sl[0].start
    w = sl[1].stop - sl[1].start
    if not (a.px(18) <= h <= a.px(40) and 1.4 <= w / h <= 2.2):
        return False, None
    labels, _ = a.components()
    box = a.rgb[sl]
    thumb_colour = token("switch-thumb", a.shot.dark)
    bgc = a.bg[sl[0]].mean(axis=0)
    # Rãnh = điểm của thành phần khác hẳn núm và nền.
    for side in (0, 1):
        x0 = 0 if side == 0 else w - h
        sq = box[:, x0:x0 + h].astype(float)
        cy, cx = np.mgrid[0:h, 0:h]
        disk = (cy - h / 2) ** 2 + (cx - h / 2) ** 2 <= (0.28 * h) ** 2
        if not disk.any():
            continue
        thumb = sq[disk]
        if thumb.std(axis=0).max() > 10 or delta_e(thumb.mean(axis=0), thumb_colour) > 12:
            continue
        ring = (cy - h / 2) ** 2 + (cx - h / 2) ** 2 >= (0.5 * h) ** 2
        rest = np.ones((h, w), bool)
        rest[:, x0:x0 + h] = ring
        track = box[rest & (np.abs(box - bgc).sum(axis=2) > INK) &
                    (np.abs(box - thumb_colour).sum(axis=2) > 60)]
        if len(track) < 0.25 * h * w:
            continue
        return True, np.median(track, axis=0)
    return False, None


def accent_buttons(a: Analysis) -> list[tuple[list[int], int]]:
    """Nút nền --accent: khối hổ phách chữ nhật (rộng >= 1,5 cao), đặc >= 70 %, cao >= 28 dp."""
    labels, objects = a.colour_components(token("accent", a.shot.dark))
    out = []
    for index, sl in enumerate(objects, start=1):
        h = sl[0].stop - sl[0].start
        w = sl[1].stop - sl[1].start
        mask = labels[sl] == index
        if h < a.px(28) or w / h < 1.5 or mask.mean() < 0.7:
            continue
        # Một khối liền, mép trái/phải thẳng (vùng bôi chọn chữ nhiều dòng có mép phải răng cưa).
        middle = mask[int(h * 0.2):int(h * 0.8) + 1]
        filled = middle.any(axis=1)
        if not filled.all():
            continue
        lefts = middle.argmax(axis=1)
        rights = w - 1 - middle[:, ::-1].argmax(axis=1)
        if np.ptp(lefts) > a.px(1) or np.ptp(rights) > a.px(1):
            continue
        out.append(([sl[1].start, sl[0].start, sl[1].stop, sl[0].stop], h))
    return out


def rule_r4(a: Analysis) -> list[Finding]:
    out = []
    labels, objects = a.components()
    dark = a.shot.dark
    focus = token("focus", dark)
    off = token("switch-off", dark)
    buttons = []
    for index, sl in enumerate(objects, start=1):
        if sl is None:
            continue
        h = sl[0].stop - sl[0].start
        w = sl[1].stop - sl[1].start
        if h < a.px(18) or w < a.px(28):
            continue
        switch, track = is_switch(a, sl)
        box = [sl[1].start, sl[0].start, sl[1].stop, sl[0].stop]
        if switch:
            if delta_e(track, off) < 6:
                continue
            de = delta_e(track, focus)
            if de >= 3:
                colour = "#%02x%02x%02x" % tuple(int(v) for v in track)
                out.append(Finding("R4", a.shot.key, f"rãnh công tắc bật {colour} ≠ --focus (ΔE {de:.1f})", box))
            continue
    buttons = accent_buttons(a)
    if len(buttons) > 1:
        out.append(Finding("R4", a.shot.key, f"{len(buttons)} nút nền --accent trong một màn",
                           [min(b[0][0] for b in buttons), min(b[0][1] for b in buttons),
                            max(b[0][2] for b in buttons), max(b[0][3] for b in buttons)]))
    low, high = BUTTON_HEIGHT[a.shot.platform]
    for box, h in buttons:
        if not low <= a.dp(h) <= high:
            out.append(Finding("R4", a.shot.key, f"nút chính cao {a.dp(h):.0f} dp (chuẩn {low}-{high})", box))
    return out


# ---------------------------------------------------------------- R7: neo trong nhóm trạng thái

def anchors(a: Analysis) -> dict[str, float]:
    """Toạ độ dọc (dp) của các nút neo tìm được trên ảnh."""
    found: dict[str, float] = {"height": a.dp(a.h)}
    labels, objects = a.surface_components()
    covers = [sl for sl in objects if sl is not None
              and (sl[0].stop - sl[0].start) * (sl[1].stop - sl[1].start) > 0.06 * a.h * a.w
              and 0.6 <= (sl[1].stop - sl[1].start) / (sl[0].stop - sl[0].start) <= 1.7]
    if covers:
        found["cover_top"] = a.dp(max(covers, key=lambda sl: (sl[0].stop - sl[0].start) * (sl[1].stop - sl[1].start))[0].start)
    labels, objects = a.colour_components(token("accent", a.shot.dark))
    circles = []
    for index, sl in enumerate(objects, start=1):
        h = sl[0].stop - sl[0].start
        w = sl[1].stop - sl[1].start
        if h >= a.px(32) and 0.85 <= w / h <= 1.15 and 0.6 <= (labels[sl] == index).mean() <= 0.9:
            circles.append(sl)
    if circles:
        sl = max(circles, key=lambda sl: sl[0].stop - sl[0].start)
        found["play_centre"] = a.dp((sl[0].start + sl[0].stop) / 2)
    buttons = accent_buttons(a)
    if buttons:
        box, h = max(buttons, key=lambda b: (b[0][2] - b[0][0]) * b[1])
        found["button_top"] = a.dp(box[1])
        found["button_height"] = a.dp(h)
    # Thanh tiến độ: dải mảnh (<= 4 dp) có nền hàng khác nền màn, kẹp giữa hai hàng nền màn.
    for top, bottom in runs(~a.page_rows):
        if bottom - top + 1 <= a.px(4) and top > a.h * 0.1 and 0 < top and bottom + 1 < a.h:
            found["track_y"] = a.dp(top)
            break
    return found


def rule_r7(analyses: dict[str, dict[str, float]], groups: dict[str, list[str]]) -> list[Finding]:
    out = []
    for name, members in groups.items():
        present = [m for m in members if m in analyses]
        if len(present) < 2:
            continue
        keys = sorted({k for m in present for k in analyses[m]})
        for key in keys:
            values = {m: analyses[m][key] for m in present if key in analyses[m]}
            if len(values) < 2:
                continue
            # Mốc = giá trị nhiều thành viên chung nhất (± 1 dp); ai lệch hơn 1 dp là đỏ.
            ref = max(values.values(), key=lambda v: (sum(abs(v - u) <= 1 for u in values.values()), -v))
            for member, value in values.items():
                if abs(value - ref) > 1:
                    out.append(Finding("R7", member, f"nhóm {name}: {key} {value:.0f} dp, mốc {ref:.0f} dp"))
    return out


# ---------------------------------------------------------------- chạy

IMAGE_RULES = (rule_r4, rule_r5, rule_r6, rule_r8, rule_r10)


def analyse(shot: Shot, group_members: frozenset[str] = frozenset()) -> tuple[list[Finding], dict | None, str | None]:
    try:
        a = Analysis(shot)
        findings = [f for rule in IMAGE_RULES for f in rule(a)]
        return findings, (anchors(a) if shot.key in group_members else None), None
    except Exception as exc:  # một ảnh hỏng không được làm im cả lượt
        return [], None, f"{shot.key}: {type(exc).__name__}: {exc}"


def collect(android: Path | None, qt: Path | None, web: Path | None) -> list[Shot]:
    shots = []
    for platform, directory in (("android", android), ("qt", qt), ("web", web)):
        if directory and directory.is_dir():
            shots += [Shot(platform, p) for p in sorted(directory.glob("*.png"))]
    return shots


def load_groups(path: Path = GROUPS) -> dict[str, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    groups = {}
    for group in data["groups"]:
        for variant in group.get("variants", [""]):
            groups[group["name"] + (f" [{variant}]" if variant else "")] = [
                f"{group['platform']}/{member}{variant}.png" for member in group["members"]]
    return groups


def load_exceptions(path: Path = EXCEPTIONS) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["exceptions"]:
        if set(entry) != {"image", "rule", "reason"} or not entry["reason"].strip() or entry["rule"] not in RULES:
            raise ValueError(f"ngoại lệ phải có đúng image/rule/reason và luật hợp lệ: {entry}")
        if any(ch in entry["image"] for ch in "*?["):
            raise ValueError(f"ngoại lệ phải nêu tên một ảnh, không dùng mẫu: {entry['image']}")
    return data["exceptions"]


def run(shots: list[Shot], groups: dict[str, list[str]], exceptions: list[dict], workers: int = 4,
        trees: bool = True) -> dict:
    start = time.monotonic()
    members = frozenset(m for ms in groups.values() for m in ms)
    findings: list[Finding] = []
    group_anchors: dict[str, dict] = {}
    errors: list[str] = []
    if workers > 1 and len(shots) > 8:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(analyse, shots, [members] * len(shots), chunksize=8))
    else:
        results = [analyse(shot, members) for shot in shots]
    for shot, (found, anchor, error) in zip(shots, results):
        findings += found
        if anchor is not None:
            group_anchors[shot.key] = anchor
        if error:
            errors.append(error)
    findings += rule_r7(group_anchors, groups)
    tree_count = 0
    if trees:
        import design_lint_tree

        tree_findings, tree_count, tree_errors = design_lint_tree.lint_shots(shots)
        findings += tree_findings
        errors += tree_errors
    waived = {(e["image"], e["rule"]) for e in exceptions}
    kept = [f for f in findings if (f.image, f.rule) not in waived]
    used = {(f.image, f.rule) for f in findings}
    scanned = {s.key for s in shots}
    # Chỉ ảnh đã quét mới nói được ngoại lệ còn cần hay không (chạy thiếu Qt thì ngoại lệ Qt không bị coi là thừa).
    stale = [e for e in exceptions if e["image"] in scanned and (e["image"], e["rule"]) not in used]
    red_images = {rule: sorted({f.image for f in kept if f.rule == rule}) for rule in RULES}
    return {
        "images": len(shots),
        "platforms": {p: sum(s.platform == p for s in shots) for p in SCALE},
        "trees": tree_count,
        "seconds": round(time.monotonic() - start, 2),
        "red_images": {rule: len(v) for rule, v in red_images.items()},
        "findings": [asdict(f) for f in kept],
        "waived": len(findings) - len(kept),
        "stale_exceptions": stale,
        "errors": errors,
        "anchors": group_anchors,
    }


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--android", type=Path, default=ANDROID_SHOTS)
    parser.add_argument("--qt", type=Path, default=QT_SHOTS)
    parser.add_argument("--web", type=Path, default=None)
    parser.add_argument("--json", type=Path, help="ghi báo cáo đầy đủ ra tệp này")
    parser.add_argument("--strict", action="store_true", help="thoát 1 khi còn ô đỏ (chế độ chặn)")
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--only", help="chỉ in phát hiện của các luật này, phân cách dấu phẩy")
    parser.add_argument("--summary", action="store_true", help="dòng cuối là JSON tóm tắt (cho release_gate)")
    args = parser.parse_args(argv)
    shots = collect(args.android, args.qt, args.web)
    report = run(shots, load_groups(), load_exceptions(), args.workers)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    wanted = set(args.only.split(",")) if args.only else set(RULES)
    for f in report["findings"]:
        if f["rule"] in wanted:
            print(f"{f['rule']:<4} {f['image']}: {f['detail']}")
    print(f"\n{report['images']} ảnh {report['platforms']}, {report['trees']} cây UI, {report['seconds']} s, "
          f"{report['waived']} phát hiện được miễn có tên")
    print("ảnh đỏ theo luật: " + ", ".join(f"{r}={n}" for r, n in report["red_images"].items()))
    for e in report["stale_exceptions"]:
        print(f"ngoại lệ thừa (ảnh không còn đỏ): {e['rule']} {e['image']}")
    for e in report["errors"]:
        print(f"LỖI ĐO: {e}")
    red = sum(report["red_images"].values())
    if args.summary:
        print(json.dumps({"images": report["images"], "red_images": report["red_images"], "errors": len(report["errors"]),
                          "stale_exceptions": len(report["stale_exceptions"]), "seconds": report["seconds"]}))
    if not shots or report["errors"]:
        return 2
    return 1 if args.strict and (red or report["stale_exceptions"]) else 0


if __name__ == "__main__":
    sys.exit(main())
