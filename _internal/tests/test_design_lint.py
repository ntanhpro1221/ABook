"""Kiểm lực hai phía cho design_lint: ảnh tốt phải xanh, ảnh hỏng cố ý phải đỏ (ảnh giả vẽ bằng PIL)."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import design_lint as dl  # noqa: E402

BG = (245, 243, 239)       # --bg sáng
TEXT = (26, 24, 20)        # --text sáng
W, H = 1080, 2340          # Roborazzi xxhdpi: 3 px / dp


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (W, H), BG)
    return im, ImageDraw.Draw(im)


def text(draw: ImageDraw.ImageDraw, x: int, y: int, words: int = 3, height: int = 42) -> int:
    """Một dòng chữ giả: chữ cái là khối 12 px, cách 4 px; từ cách 15 px. Trả về mép phải của mực."""
    right = x
    for _ in range(words):
        for _ in range(4):
            draw.rectangle([x, y, x + 11, y + height - 1], fill=TEXT)
            right = x + 11
            x += 16
        x += 15
    return right


def column(draw, x: int, top: int = 120, rows: int = 14, pitch: int = 150):
    for i in range(rows):
        text(draw, x, top + i * pitch)


def shot(tmp_path: Path, im: Image.Image, name: str = "screen_light.png") -> dl.Shot:
    path = tmp_path / name
    im.save(path)
    return dl.Shot("android", path)


def rules_of(findings) -> set[str]:
    return {f.rule for f in findings}


def analyse(tmp_path, im, name="screen_light.png") -> dl.Analysis:
    return dl.Analysis(shot(tmp_path, im, name))


# ---------------------------------------------------------------- R5 lưới hụt hàng cuối

def grid(draw, items: int, cols: int = 3, top: int = 300, pitch: int = 150):
    for i in range(items):
        row, col = divmod(i, cols)
        words = 1 + (i % 2)                                   # ô chữ ngắn 1-2 từ, căn giữa ô như sheet Tốc độ
        width = 64 * words + 15 * (words - 1) - 4
        text(draw, 180 + col * 360 - width // 2, top + row * pitch, words=words)


def test_r5_full_grid_is_green(tmp_path):
    im, draw = canvas()
    grid(draw, 12)
    assert dl.rule_r5(analyse(tmp_path, im)) == []


def test_r5_short_last_row_is_red(tmp_path):
    im, draw = canvas()
    grid(draw, 11)
    findings = dl.rule_r5(analyse(tmp_path, im))
    assert [f.rule for f in findings] == ["R5"] and "hàng cuối 2 ô" in findings[0].detail


def test_r5_icon_row_with_labels_is_not_a_grid(tmp_path):
    im, draw = canvas()
    for x in (120, 480, 840):                       # hàng icon 3 ô
        draw.rectangle([x, 300, x + 59, 359], fill=TEXT)
    text(draw, 100, 372, words=1, height=30)        # nhãn sát dưới (khe 4 dp), thấp hơn
    text(draw, 460, 372, words=1, height=30)
    assert dl.rule_r5(analyse(tmp_path, im)) == []


# ---------------------------------------------------------------- R6 trục mép trái, trộn căn

def test_r6_margin_and_indent_is_green(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=7)
    column(draw, 168, top=1200, rows=7)             # lề + icon
    assert dl.rule_r6(analyse(tmp_path, im)) == []


def test_r6_many_axes_is_red(tmp_path):
    im, draw = canvas()
    for i, x in enumerate((60, 120, 200, 260, 330)):
        column(draw, x, top=120 + i * 420, rows=2)
    findings = dl.rule_r6(analyse(tmp_path, im))
    assert any("5 trục" in f.detail for f in findings)


def test_r6_centred_block_among_left_blocks_is_red(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=6)
    width = text(ImageDraw.Draw(Image.new("RGB", (W, 50))), 0, 0, words=2) + 1
    text(draw, (W - width) // 2, 1500, words=2)     # một dòng căn giữa giữa màn căn trái
    findings = dl.rule_r6(analyse(tmp_path, im))
    assert any("trộn căn" in f.detail for f in findings)


def test_r6_text_button_under_filled_button_is_one_block(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=6)
    draw.rounded_rectangle([60, 1900, 1020, 2043], 24, fill=(212, 145, 43))
    width = text(ImageDraw.Draw(Image.new("RGB", (W, 50))), 0, 0, words=2) + 1
    text(draw, (W - width) // 2, 1950, words=2)
    text(draw, (W - width) // 2, 2100, words=2)     # nút chữ phụ căn giữa ngay dưới nút chính
    assert not any("trộn căn" in f.detail for f in dl.rule_r6(analyse(tmp_path, im)))


def test_r6_slider_scale_and_spread_bar_are_cells_not_axes(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=6)
    for i, top in enumerate((900, 1200, 1500, 1800)):  # thang số dưới thanh trượt: ô ngắn cách đều, mỗi thang lệch một chút
        for k in range(4):
            draw.rectangle([150 + i * 45 + k * 150, top, 150 + i * 45 + k * 150 + 44, top + 30], fill=TEXT)
    for k in range(4):                               # thanh nút đáy trải hết bề ngang
        draw.rectangle([100 + k * 260, 2200, 100 + k * 260 + 60, 2260], fill=TEXT)
    assert dl.rule_r6(analyse(tmp_path, im)) == []


def test_r6_centred_empty_state_lines_are_not_axes(tmp_path):
    im, draw = canvas()
    draw.rectangle([60, 140, 107, 187], fill=TEXT)   # nút lùi ở lề
    for i, words in enumerate((4, 6, 5, 7)):         # trạng thái trống căn giữa: mỗi dòng dài khác nhau
        width = text(ImageDraw.Draw(Image.new("RGB", (W, 50))), 0, 0, words=words) + 1
        text(draw, (W - width) // 2, 900 + i * 150, words=words)
    assert not any("trục mép trái" in f.detail for f in dl.rule_r6(analyse(tmp_path, im)))


@pytest.mark.parametrize("cover_left, red", [(300, True), (60, False)])
def test_r6_cover_indented_over_flush_title(tmp_path, cover_left, red):
    im, draw = canvas()
    draw.rectangle([cover_left, 300, cover_left + 480, 780], fill=(70, 45, 25))   # bìa
    text(draw, 60, 840, words=4)                                                # tên chương bám lề ngay dưới
    column(draw, 60, top=1000, rows=4)
    findings = [f for f in dl.rule_r6(analyse(tmp_path, im)) if "ảnh mép trái" in f.detail]
    assert bool(findings) is red


def test_r6_value_over_a_centred_scale_is_one_group(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=6)
    width = text(ImageDraw.Draw(Image.new("RGB", (W, 50))), 0, 0, words=1) + 1
    text(draw, (W - width) // 2, 1500, words=1)              # số đọc "1×" căn giữa
    for k in range(5):                                       # thang số căn giữa ngay dưới (khe 30 dp)
        x = 218 + k * 150
        draw.rectangle([x, 1632, x + 44, 1662], fill=TEXT)
    assert not any("trộn căn" in f.detail for f in dl.rule_r6(analyse(tmp_path, im)))


def test_r6_uneven_short_clusters_still_count_as_an_axis(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=4)
    for i, top in enumerate((900, 1200, 1500, 1800)):  # cụm ngắn KHÔNG cách đều: vẫn là chữ thụt, vẫn tính trục
        x = 200 + i * 70
        for dx in (0, 90, 330):
            draw.rectangle([x + dx, top, x + dx + 44, top + 40], fill=TEXT)
    findings = dl.rule_r6(analyse(tmp_path, im))
    assert any("trục mép trái" in f.detail for f in findings)


# ---------------------------------------------------------------- R4 công tắc, nút chính

def switch(draw, track, y=600, thumb=(255, 255, 255), on=True):
    x0, x1 = 860, 1016                              # 52 x 32 dp
    draw.rounded_rectangle([x0, y, x1, y + 95], 48, fill=track)
    cx = x1 - 48 if on else x0 + 48
    draw.ellipse([cx - 36, y + 12, cx + 36, y + 84], fill=thumb)


@pytest.mark.parametrize("track, red", [
    ((160, 96, 12), False),     # --focus
    ((133, 126, 114), False),   # --switch-off
    ((26, 24, 20), True),       # đen (lỗi Android 10-11)
])
def test_r4_switch_track_colour(tmp_path, track, red):
    im, draw = canvas()
    text(draw, 60, 620)
    switch(draw, track, on=track != (133, 126, 114))
    findings = [f for f in dl.rule_r4(analyse(tmp_path, im)) if "công tắc" in f.detail]
    assert bool(findings) is red


def test_r4_dark_theme_uses_dark_focus(tmp_path):
    im = Image.new("RGB", (W, H), (18, 17, 16))
    draw = ImageDraw.Draw(im)
    switch(draw, (233, 169, 69), thumb=(27, 18, 4))
    assert not [f for f in dl.rule_r4(analyse(tmp_path, im, "x_dark.png")) if "công tắc" in f.detail]
    im = Image.new("RGB", (W, H), (18, 17, 16))
    switch(ImageDraw.Draw(im), (236, 232, 225), thumb=(27, 18, 4))
    assert [f for f in dl.rule_r4(analyse(tmp_path, im, "y_dark.png")) if "công tắc" in f.detail]


def button(draw, y, height, fill=(212, 145, 43)):
    draw.rounded_rectangle([60, y, 1020, y + height - 1], 36, fill=fill)
    text(draw, 420, y + height // 2 - 21, words=2)


def test_r4_one_main_button_48dp_is_green(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=5)
    button(draw, 1200, 144)
    assert dl.rule_r4(analyse(tmp_path, im)) == []


def test_r4_tall_main_button_is_red(tmp_path):
    im, draw = canvas()
    button(draw, 1200, 243)                         # 81 dp
    assert any("cao 81 dp" in f.detail for f in dl.rule_r4(analyse(tmp_path, im)))


def test_r4_two_accent_buttons_is_red_even_when_one_is_disabled(tmp_path):
    im, draw = canvas()
    button(draw, 900, 144)
    mixed = tuple(int(0.5 * a + 0.5 * b) for a, b in zip((212, 145, 43), BG))   # nút bị vô hiệu: hổ phách mờ
    button(draw, 1500, 144, fill=mixed)
    assert any("2 nút nền --accent" in f.detail for f in dl.rule_r4(analyse(tmp_path, im)))


def test_r4_accent_soft_chip_is_not_a_button(tmp_path):
    im, draw = canvas()
    button(draw, 900, 144)
    button(draw, 1500, 144, fill=(247, 234, 213))   # --accent-soft
    assert dl.rule_r4(analyse(tmp_path, im)) == []


def scrimmed(colour, dark=False):
    return tuple(int(round(v)) for v in dl.under_scrim(np.array(colour, float), dark))


@pytest.mark.parametrize("track, red", [
    (scrimmed((160, 96, 12)), False),             # --focus dưới màn mờ của sheet đang mở
    (scrimmed((133, 126, 114)), False),           # --switch-off dưới màn mờ
    (scrimmed((26, 24, 20)), True),               # rãnh đen dưới màn mờ vẫn sai
])
def test_r4_switch_under_scrim_compares_scrimmed_token(tmp_path, track, red):
    im = Image.new("RGB", (W, H), scrimmed(BG))
    draw = ImageDraw.Draw(im)
    switch(draw, track, thumb=scrimmed((255, 255, 255)), on=True)
    findings = [f for f in dl.rule_r4(analyse(tmp_path, im)) if "công tắc" in f.detail]
    assert bool(findings) is red


def test_r4_disabled_switch_is_faded_token_not_a_wrong_colour(tmp_path):
    im, draw = canvas()
    faded_off = tuple(int(0.5 * a + 0.5 * b) for a, b in zip((133, 126, 114), BG))
    switch(draw, faded_off, on=False)
    assert not [f for f in dl.rule_r4(analyse(tmp_path, im)) if "công tắc" in f.detail]


def test_r4_skeleton_block_and_square_tile_are_not_switches(tmp_path):
    im, draw = canvas()
    bone = (227, 223, 215)                        # khối xương chờ tải: "núm" cùng màu "rãnh"
    draw.rounded_rectangle([860, 600, 1016, 695], 48, fill=bone)
    draw.rounded_rectangle([60, 900, 252, 995], 24, fill=(23, 60, 54))   # ô bìa 64 x 32 dp góc vuông bo 8
    draw.ellipse([90, 912, 162, 984], fill=(255, 255, 255))
    assert not [f for f in dl.rule_r4(analyse(tmp_path, im)) if "công tắc" in f.detail]


def test_r4_main_button_height_follows_design_per_platform(tmp_path):
    # DESIGN.md §6: nút chính cao 48 (điện thoại) / 40 (máy tính).
    im = Image.new("RGB", (1280, 900), BG)
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([500, 600, 700, 639], 8, fill=(212, 145, 43))      # 40 px = 40 dp trên Qt / web
    path = tmp_path / "desk_light.png"
    im.save(path)
    for platform in ("qt", "web"):
        assert dl.rule_r4(dl.Analysis(dl.Shot(platform, path))) == []
    im, draw = canvas()
    draw.rounded_rectangle([60, 1200, 1020, 1319], 24, fill=(212, 145, 43))  # 40 dp trên điện thoại
    assert any("cao 40 dp" in f.detail for f in dl.rule_r4(analyse(tmp_path, im)))


def test_r4_page_button_under_a_modal_is_not_a_second_main_button(tmp_path):
    im = Image.new("RGB", (1280, 900), BG)
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([1000, 20, 1200, 59], 8, fill=(212, 145, 43))     # nút chính của trang (dưới màn mờ)
    draw.rounded_rectangle([400, 200, 880, 700], 20, fill=(255, 255, 255))   # hộp thoại
    draw.rounded_rectangle([700, 640, 860, 679], 8, fill=(212, 145, 43))     # nút chính của hộp
    path = tmp_path / "dialog_light.png"
    im.save(path)
    shot = dl.Shot("qt", path)
    assert any("2 nút nền --accent" in f.detail for f in dl.rule_r4(dl.Analysis(shot)))   # chưa có cây: đo cả ảnh
    nodes = [{"id": 0, "parent": -1, "bounds": [0, 0, 1280, 900]},
             {"id": 1, "parent": 0, "bounds": [0, 0, 1280, 900], "modal": True, "z": 70},
             {"id": 2, "parent": 1, "bounds": [0, 0, 1280, 900]},                  # màn mờ phủ cả màn
             {"id": 3, "parent": 1, "bounds": [400, 200, 880, 700]}]
    path.with_name("dialog_light.tree.json").write_text(json.dumps({"width": 1280, "height": 900, "nodes": nodes}))
    assert not any("nút nền --accent" in f.detail for f in dl.rule_r4(dl.Analysis(shot)))
    # Hai nút chính TRONG hộp thoại vẫn đỏ.
    draw.rounded_rectangle([420, 640, 580, 679], 8, fill=(212, 145, 43))
    im.save(path)
    assert any("2 nút nền --accent" in f.detail for f in dl.rule_r4(dl.Analysis(shot)))


# ---------------------------------------------------------------- R8 mép sheet cắt chữ

def sheet(draw, top):
    draw.rectangle([0, 0, W, top - 1], fill=(143, 139, 133))       # lớp mờ phủ nền
    draw.rectangle([0, top, W, H], fill=(255, 255, 255))           # mặt sheet tràn ngang


def test_r8_sheet_edge_between_lines_is_green(tmp_path):
    im, draw = canvas()
    sheet(draw, 1200)
    text(draw, 60, 1100)
    text(draw, 60, 1300)
    assert dl.rule_r8(analyse(tmp_path, im)) == []


def test_r8_sheet_edge_through_a_line_is_red(tmp_path):
    im, draw = canvas()
    text(draw, 60, 1170, words=4)                   # dòng chữ phía sau ...
    sheet_top = 1200
    ImageDraw.Draw(im).rectangle([0, sheet_top, W, H], fill=(255, 255, 255))   # ... bị mép sheet xén
    findings = dl.rule_r8(analyse(tmp_path, im))
    assert any("mép sheet" in f.detail for f in findings)


def test_r8_cover_edge_is_not_a_sheet(tmp_path):
    im, draw = canvas()
    draw.rectangle([60, 300, 1020, 1260], fill=(60, 40, 20))       # bìa có lề hai bên
    text(draw, 120, 1218)                                          # chữ trên bìa chạm đáy bìa
    assert not [f for f in dl.rule_r8(analyse(tmp_path, im)) if "mép sheet" in f.detail]


def test_r8_sliver_of_cut_line_is_red(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=8)
    for i in range(12):                                            # chỉ còn đỉnh chữ: hàng chấm 3 dp
        draw.rectangle([60 + i * 70, 1600, 66 + i * 70, 1608], fill=TEXT)
    assert any("mảnh dòng" in f.detail for f in dl.rule_r8(analyse(tmp_path, im)))


# ---------------------------------------------------------------- R10 vùng trống

def test_r10_spread_content_is_green(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=15)
    assert dl.rule_r10(analyse(tmp_path, im)) == []


def test_r10_large_empty_band_is_red(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=4)
    findings = dl.rule_r10(analyse(tmp_path, im))
    assert findings and "dải trống" in findings[0].detail


def test_r10_short_list_tail_is_green_but_sparse_empty_state_is_red(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=7)                                  # danh sách 7 dòng vừa hết mục, đuôi trống tới thanh đáy
    text(draw, 60, 2250, words=4, height=40)                  # thanh điều hướng ghim đáy
    assert dl.rule_r10(analyse(tmp_path, im)) == []
    im, draw = canvas()
    column(draw, 60, rows=3)                                  # màn thưa: tiêu đề + hai dòng dồn góc
    text(draw, 60, 2250, words=4, height=40)
    findings = dl.rule_r10(analyse(tmp_path, im, "sparse_light.png"))
    assert findings and "dải trống" in findings[0].detail


def test_r10_gap_in_the_middle_of_a_list_is_red(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=7, pitch=100)
    column(draw, 60, top=1800, rows=1)                        # khối không ghim đáy: khoảng giữa là lỗ hổng bố cục
    findings = dl.rule_r10(analyse(tmp_path, im))
    assert findings and "dải trống" in findings[0].detail


def test_r10_isolated_fixture_is_not_a_page(tmp_path):
    im, draw = canvas()
    draw.rectangle([60, 2100, 1020, 2300], fill=(230, 226, 220))   # trình phát nhỏ chụp riêng: không tiêu đề góc trên
    text(draw, 100, 2160)
    assert dl.rule_r10(analyse(tmp_path, im)) == []
    im = Image.new("RGB", (W, H), (98, 95, 91))                 # sheet tách riêng trên màn mờ: nền không phải --bg
    ImageDraw.Draw(im).rectangle([0, 1500, W, H], fill=BG)
    text(ImageDraw.Draw(im), 60, 40)
    text(ImageDraw.Draw(im), 60, 1600)
    assert dl.rule_r10(analyse(tmp_path, im, "sheet_light.png")) == []


def test_r10_gutter_inside_full_width_rows_is_green_but_packed_left_is_red(tmp_path):
    def wide(trailing: bool) -> list:
        im = Image.new("RGB", (1440, 900), BG)
        draw = ImageDraw.Draw(im)
        text(draw, 40, 24, words=2, height=32)                    # tiêu đề màn
        for i in range(12):
            y = 100 + i * 64
            text(draw, 40, y, words=3, height=20)                 # tên hàng
            if trailing:
                draw.rounded_rectangle([1360, y - 4, 1400, y + 20], radius=12, fill=TEXT)   # công tắc cuối hàng
        path = tmp_path / f"rows_{trailing}_light.png"
        im.save(path)
        return [f for f in dl.rule_r10(dl.Analysis(dl.Shot("qt", path))) if "cột trống" in f.detail]

    assert wide(trailing=True) == []                              # khe ở trong hàng chạy hết cột
    assert wide(trailing=False)                                   # cùng hàng mà dừng ở 1/4 bề ngang: dồn trái


def test_r10_centred_state_block_is_not_packed_left(tmp_path):
    def state(x: int) -> list:
        im = Image.new("RGB", (1440, 900), BG)
        draw = ImageDraw.Draw(im)
        text(draw, 40, 24, words=2, height=32)                    # tiêu đề màn ở lề
        draw.rounded_rectangle([x + 72, 330, x + 128, 386], radius=12, fill=(230, 205, 160))   # ô icon
        text(draw, x, 410, words=3, height=20)                    # câu mời, 200 px
        draw.rounded_rectangle([x + 40, 460, x + 160, 500], radius=8, fill=(212, 145, 43))     # nút chính
        path = tmp_path / f"state_{x}_light.png"
        im.save(path)
        return [f for f in dl.rule_r10(dl.Analysis(dl.Shot("qt", path))) if "cột trống" in f.detail]

    assert state(620) == []                                       # khối giữa màn: hai bên trống đều
    assert state(40)                                              # cùng khối dồn lề trái: nửa phải trống


def test_r10_vertically_centred_state_block_is_green_but_top_stuck_is_red(tmp_path):
    def state(x: int, y: int) -> list:
        im = Image.new("RGB", (1440, 900), BG)
        draw = ImageDraw.Draw(im)
        text(draw, 40, 24, words=2, height=32)                    # tiêu đề màn ở lề
        draw.rounded_rectangle([x + 72, y, x + 128, y + 56], radius=12, fill=(230, 205, 160))   # ô icon
        text(draw, x, y + 80, words=3, height=20)                 # câu mời
        draw.rounded_rectangle([x + 40, y + 130, x + 160, y + 170], radius=8, fill=(212, 145, 43))   # nút chính
        path = tmp_path / f"state_{x}_{y}_light.png"
        im.save(path)
        return [f for f in dl.rule_r10(dl.Analysis(dl.Shot("qt", path))) if "dải trống" in f.detail]

    assert state(620, 330) == []                                  # tâm khối ~45 % chiều cao dưới đầu màn (L10)
    assert state(620, 100)                                        # dính dưới đầu màn: hơn nửa màn dưới trống
    assert state(40, 330)                                         # giữa theo chiều dọc nhưng dồn trái


def test_r10_component_snapshot_is_skipped(tmp_path):
    im = Image.new("RGB", (960, 144), BG)
    text(ImageDraw.Draw(im), 20, 50)
    assert dl.rule_r10(analyse(tmp_path, im)) == []


# ---------------------------------------------------------------- R7 neo theo nhóm trạng thái

def player(cover_top: int) -> Image.Image:
    im, draw = canvas()
    draw.rectangle([60, cover_top, 1020, cover_top + 960], fill=(70, 45, 25))
    draw.ellipse([444, 1800, 636, 1992], fill=(212, 145, 43))     # nút phát
    return im


def test_r7_same_anchors_green_moved_cover_red(tmp_path):
    keys = {}
    for name, top in (("p_a_light.png", 300), ("p_b_light.png", 300), ("p_c_light.png", 420)):
        s = shot(tmp_path, player(top), name)
        keys[s.key] = dl.anchors(dl.Analysis(s))
    group = {"g": list(keys)}
    findings = dl.rule_r7(keys, group)
    assert {f.image for f in findings} == {"android/p_c_light.png"}
    assert all("cover_top" in f.detail for f in findings)
    same = {k: v for k, v in keys.items() if "p_c" not in k}
    assert dl.rule_r7(same, {"g": list(same)}) == []


# ---------------------------------------------------------------- ngoại lệ và cả lượt

def test_exceptions_must_name_one_image_with_a_reason(tmp_path):
    bad = tmp_path / "ex.json"
    for entry in ({"image": "android/*.png", "rule": "R6", "reason": "x"},
                  {"image": "android/a.png", "rule": "R6", "reason": " "},
                  {"image": "android/a.png", "rule": "R99", "reason": "x"},
                  {"image": "android/a.png", "rule": "R6", "reason": "x", "threshold": 5}):
        bad.write_text(json.dumps({"exceptions": [entry]}), encoding="utf-8")
        with pytest.raises(ValueError):
            dl.load_exceptions(bad)


def test_run_waives_named_exception_and_reports_stale(tmp_path):
    im, draw = canvas()
    column(draw, 60, rows=4)                                       # R10 đỏ
    s = shot(tmp_path, im, "empty_light.png")
    exceptions = [{"image": s.key, "rule": "R10", "reason": "thử"},
                  {"image": s.key, "rule": "R5", "reason": "không còn đỏ"}]
    report = dl.run([s], {}, exceptions, workers=1, trees=False)
    assert report["red_images"]["R10"] == 0 and report["waived"] == 1
    assert [e["rule"] for e in report["stale_exceptions"]] == ["R5"]


def test_repo_files_are_well_formed():
    dl.load_exceptions()
    groups = dl.load_groups()
    assert groups and all(len(m) >= 2 for m in groups.values())
    cases = json.loads((dl.ROOT / "scripts/design_lint_audit_cases.json").read_text(encoding="utf-8"))["cases"]
    assert len({c["image"] for c in cases}) >= 20 and all(c["rule"] in dl.RULES for c in cases)


@pytest.mark.skipif(not dl.ANDROID_SHOTS.is_dir(), reason="không có ảnh Roborazzi")
def test_runs_on_every_android_snapshot_without_error():
    shots = dl.collect(dl.ANDROID_SHOTS, None, None)
    report = dl.run(shots, dl.load_groups(), dl.load_exceptions(), workers=4)
    assert report["images"] == len(shots) > 300
    assert report["errors"] == []


# ================================================================ bước 2: luật trên cây UI

import design_lint_tree as dt  # noqa: E402


def tree(*nodes, width=360, height=780) -> dict:
    """Cây giả: mỗi nút (parent, bounds, **thuộc tính); id theo thứ tự."""
    out = []
    for i, (parent, bounds, extra) in enumerate(nodes):
        node = {"id": i, "parent": parent, "bounds": list(bounds), "visible": list(extra.pop("visible", bounds)), "children": []}
        node.update(extra)
        out.append(node)
    for node in out:
        if node["parent"] >= 0:
            out[node["parent"]]["children"].append(node["id"])
    return {"width": width, "height": height, "nodes": out}


ROOT = (-1, (0, 0, 360, 780), {})


def n(parent, l, t, r, b, **extra):
    return (parent, (l, t, r, b), extra)


def test_r1_tab_row_and_choice_row_and_list_are_green():
    tabs = tree(ROOT, *[n(0, 20 + i * 80, 100, 90 + i * 80, 148, role="tab", selected=i == 0) for i in range(3)])
    choice = tree(ROOT, *[n(0, 20 + i * 64, 100, 80 + i * 64, 144, role="radiobutton", selected=i == 1) for i in range(5)])
    listing = tree(ROOT, *[n(0, 0, 100 + i * 56, 360, 156 + i * 56, role="listitem", selected=i == 2) for i in range(8)])
    for t in (tabs, choice, listing):
        assert dt.rule_r1("k", t) == []


def test_r1_grid_of_choices_and_long_choice_row_are_red():
    grid = tree(ROOT, *[n(0, 20 + (i % 3) * 110, 100 + (i // 3) * 50, 120 + (i % 3) * 110, 144 + (i // 3) * 50,
                          selected=i == 2) for i in range(11)])
    long_row = tree(ROOT, *[n(0, i * 40, 100, 38 + i * 40, 144, role="radiobutton", selected=i == 0) for i in range(7)])
    mixed = tree(ROOT, n(0, 0, 100, 100, 148, role="tab", selected=True), n(0, 100, 100, 200, 148, role="radiobutton", selected=False))
    for t in (grid, long_row, mixed):
        assert [f.rule for f in dt.rule_r1("k", t)] == ["R1"]


def test_r1_slider_ticks_and_checked_menu_are_not_choice_groups():
    # Thanh trượt có `current`: không phải mục chọn-một. Menu có dấu chọn một cột: là danh sách.
    picker = tree(ROOT, *[n(0, 20 + i * 60, 100, 70 + i * 60, 148, selected=i == 2) for i in range(5)],
                  n(1, 20, 100, 70, 148, role="slider"), n(2, 80, 100, 130, 148, role="slider"))
    menu = tree(ROOT, *[n(0, 0, 100 + i * 48, 240, 148 + i * 48, role="menuitem", selected=i == 1) for i in range(6)])
    assert dt.rule_r1("k", menu) == []
    # Ba mục còn lại (không chứa slider) trên một hàng, vai rỗng: vẫn đỏ - chỉ bỏ đúng nút chứa slider.
    assert [f.rule for f in dt.rule_r1("k", picker)] == ["R1"] and "3 mục" in dt.rule_r1("k", picker)[0].detail
    grid_menu = tree(ROOT, *[n(0, (i % 2) * 120, 100 + (i // 2) * 48, 110 + (i % 2) * 120, 148 + (i // 2) * 48,
                               role="menuitem", selected=i == 1) for i in range(6)])
    assert [f.rule for f in dt.rule_r1("k", grid_menu)] == ["R1"]


def test_r3_gaps_on_scale_green_off_scale_red():
    good = tree(ROOT, n(0, 20, 100, 340, 124, text="Tiêu đề"), n(0, 20, 140, 340, 160, text="Dòng"),
                n(0, 20, 164, 340, 184, text="Phụ"))
    assert dt.rule_r3("k", good) == []
    bad = tree(ROOT, n(0, 20, 100, 340, 124, text="Tiêu đề"), n(0, 20, 142.3, 340, 160, text="Dòng"))
    findings = dt.rule_r3("k", bad)
    assert [f.rule for f in findings] == ["R3"] and "18.3" in findings[0].detail


def test_r3_gap_with_a_painted_piece_between_is_two_gaps_not_one():
    blocks = (n(0, 20, 100, 340, 124, text="Chưa có bìa"), n(0, 20, 190, 340, 210, text="Kéo hoặc dán ảnh"))
    button = n(-1, 20, 140, 160, 180, icon="image")          # nút của nhánh khác nằm giữa hai khối
    assert dt.rule_r3("k", tree(ROOT, *blocks, button)) == []
    beside = n(-1, 360, 140, 400, 180, icon="image")        # vật vẽ không nằm giữa theo chiều ngang: khe 66 dp vẫn đỏ
    findings = dt.rule_r3("k", tree(ROOT, *blocks, beside, width=420))
    assert [f.rule for f in findings] == ["R3"] and "66" in findings[0].detail


def test_r8_cut_text_and_overlap_red_clean_green():
    clean = tree(ROOT, n(0, 20, 100, 340, 124, text="Một"), n(0, 20, 130, 340, 150, text="Hai"))
    assert dt.rule_r8("k", clean) == []
    cut = tree(ROOT, n(0, 20, 760, 340, 790, text="-20 dB (mặc định)", visible=(20, 760, 340, 780)))
    assert "bị cắt" in dt.rule_r8("k", cut)[0].detail
    overlap = tree(ROOT, n(0, 20, 500, 340, 540, text="Câu đang đọc"), n(0, 120, 520, 260, 560, text="Tới câu đang nghe"))
    assert "chồng nhau" in dt.rule_r8("k", overlap)[0].detail


def test_r8_text_under_an_open_modal_is_covered_not_overlapping():
    page = [n(0, 20, 60, 340, 90, text="Chọn bài cho đoạn"), n(0, 20, 300, 340, 320, text="Air Prelude")]
    modal = [n(0, 0, 0, 360, 780, modal=True, z=70), n(3, 40, 40, 320, 400, type="FloatingPanel"),
             n(4, 60, 70, 300, 92, text="Đồi gió")]
    assert dt.rule_r8("k", tree(ROOT, *page, *modal)) == []
    # Hai hộp chữ chồng nhau TRONG cùng lớp modal vẫn đỏ, chữ trang chồng chữ trang vẫn đỏ.
    inside = tree(ROOT, *page, *modal, n(4, 100, 80, 300, 100, text="Scott Buckley"))
    assert any("chồng nhau" in f.detail for f in dt.rule_r8("k", inside))
    page_overlap = tree(ROOT, *page, n(0, 100, 70, 300, 95, text="Tìm tên bài"))
    assert any("chồng nhau" in f.detail for f in dt.rule_r8("k", page_overlap))


def test_r8_row_under_a_scroll_fade_is_not_a_hard_cut():
    def row():
        return n(0, 20, 760, 340, 800, text="Dùng", visible=(20, 760, 340, 780))
    fade = n(0, 0, 764, 360, 780, tag="scrollFadeBottom")
    assert dt.rule_r8("k", tree(ROOT, row(), fade)) == []
    assert "bị cắt" in dt.rule_r8("k", tree(ROOT, row()))[0].detail               # không có lớp mờ: cụt cứng
    off_side = n(0, 0, 0, 360, 16, tag="scrollFadeTop")                            # lớp mờ ở mép kia không che mép cắt
    assert "bị cắt" in dt.rule_r8("k", tree(ROOT, row(), off_side))[0].detail


def test_r11_font_scale_and_row_title_style():
    good = tree(ROOT, *[n(0, 0, 100 + i * 56, 360, 156 + i * 56, clickable=True) for i in range(3)],
                *[n(1 + i, 20, 110 + i * 56, 200, 130 + i * 56, text=f"Hàng {i}", font_size=16, font_weight=400, color="#1a1814")
                  for i in range(3)])
    assert dt.rule_r11("k", good) == []
    small = tree(ROOT, n(0, 20, 100, 200, 112, text="TẬP 2", font_size=10))
    assert "ngoài thang" in dt.rule_r11("k", small)[0].detail
    mixed = tree(ROOT, *[n(0, 0, 100 + i * 56, 360, 156 + i * 56, clickable=True) for i in range(3)],
                 *[n(1 + i, 20, 110 + i * 56, 200, 130 + i * 56, text=f"Hàng {i}", font_size=14 if i == 0 else 16,
                     font_weight=400, color="#1a1814") for i in range(3)])
    assert "khác kiểu" in dt.rule_r11("k", mixed)[0].detail


def test_r11_one_line_fit_shrink_is_on_the_scale():
    """OneLineFit thu chữ 14 xuống 13 cho vừa một dòng: vẫn thuộc thang; cùng cỡ mà không phải OneLineFit, hay OneLineFit xuống dòng, thì đỏ."""
    fit = tree(ROOT, n(0, 20, 100, 300, 116, text="Supertonic F1 - giọng nữ trầm ấm", font_size=13, type="OneLineFit", line_count=1))
    assert dt.rule_r11("k", fit) == []
    below = tree(ROOT, n(0, 20, 100, 300, 116, text="Tên", font_size=12 * dt.ONE_LINE_MIN_SCALE - 0.5, type="OneLineFit", line_count=1))
    assert "ngoài thang" in dt.rule_r11("k", below)[0].detail
    plain = tree(ROOT, n(0, 20, 100, 300, 116, text="Tên", font_size=13, type="Text", line_count=1))
    assert "ngoài thang" in dt.rule_r11("k", plain)[0].detail
    rows = tree(ROOT, *[n(0, 0, 100 + i * 56, 360, 156 + i * 56, clickable=True) for i in range(3)],
                *[n(1 + i, 20, 110 + i * 56, 200, 130 + i * 56, text=f"Giọng {i}", font_size=13 if i == 1 else 14, type="OneLineFit",
                    line_count=1, font_weight=500, color="#1a1814") for i in range(3)])
    assert dt.rule_r11("k", rows) == []


def test_r14_skips_data_names_in_one_line_fit():
    """Nút chọn giọng mang tên giọng dài (dữ liệu, qua OneLineFit) không phải nhãn giao diện; nút có nhãn chữ thường 6 chữ vẫn đỏ."""
    name = "Supertonic F1 - giọng nữ trầm ấm đọc truyện"
    data = tree(ROOT, n(0, 20, 100, 340, 140, role="radiobutton"), n(1, 50, 110, 300, 130, text=name, type="OneLineFit", line_count=1))
    assert dt.rule_r14("k", data) == []
    label = tree(ROOT, n(0, 20, 100, 340, 140, role="radiobutton"), n(1, 50, 110, 300, 130, text=name, type="Text", line_count=1))
    assert "chữ" in dt.rule_r14("k", label)[0].detail


def test_r11_artwork_text_and_selected_row_and_user_font_scale():
    # Chữ cái đầu trong ảnh nhân vật, tên trên bìa tự sinh, số trong icon lùi 15: hình vẽ co giãn, không theo thang chữ.
    art = tree(ROOT, n(0, 20, 100, 44, 124, type="AvatarPortrait"), n(1, 26, 106, 38, 118, text="L", font_size=7),
               n(0, 60, 100, 160, 240, type="GeneratedCover", graphic=True), n(3, 64, 110, 156, 130, text="Sách", font_size=17),
               n(0, 200, 100, 232, 132, type="SkipGlyph"), n(5, 206, 108, 226, 124, text="15", font_size=16.92))
    assert dt.rule_r11("k", art) == []
    # Cùng cỡ 7 nhưng là chữ giao diện: vẫn đỏ.
    assert "ngoài thang" in dt.rule_r11("k", tree(ROOT, n(0, 20, 100, 44, 124, text="L", font_size=7)))[0].detail
    # Hàng đang chọn (chữ hổ phách đậm 500) không so kiểu với hàng thường; hai hàng thường khác kiểu vẫn đỏ.
    rows = [n(0, 0, 100 + i * 56, 360, 156 + i * 56, clickable=True, selected=i == 1) for i in range(3)]
    texts = [n(1 + i, 20, 110 + i * 56, 200, 130 + i * 56, text=f"Chương {i}", font_size=14,
               font_weight=500 if i == 1 else 400, color="#8a5309" if i == 1 else "#1a1814") for i in range(3)]
    assert dt.rule_r11("k", tree(ROOT, *rows, *texts)) == []
    texts[2] = n(3, 20, 222, 200, 242, text="Chương 2", font_size=14, font_weight=700, color="#1a1814")
    assert "khác kiểu" in dt.rule_r11("k", tree(ROOT, *rows, *texts))[0].detail
    # Ảnh cỡ chữ 130 %: 18 × 1,3 = 23 px là thang; 13 × 1,3 = 17 px thì không. Ảnh cỡ thường: 23 px đỏ.
    title = tree(ROOT, n(0, 20, 0, 340, 29, text="Âm thanh", font_size=23))
    assert dt.rule_r11("qt/soundsheet_dark_130.png", title) == []
    assert dt.rule_r11("qt/soundsheet_dark.png", title)
    assert dt.rule_r11("qt/soundsheet_dark_130.png", tree(ROOT, n(0, 20, 0, 340, 29, text="Dùng", font_size=17)))


def test_r14_label_word_count_ignores_numbers_and_units():
    good = tree(ROOT, n(0, 20, 100, 200, 148, role="button", text="Nghe tiếp · Chương 4"),
                n(0, 20, 160, 200, 208, role="button", text="Tải (48 MB)"))
    assert dt.rule_r14("k", good) == []
    bad = tree(ROOT, n(0, 20, 100, 300, 148, role="button", text="Mở màn hình đang nghe"))
    assert "5 chữ" in dt.rule_r14("k", bad)[0].detail
    # Nút biểu tượng: mô tả trợ năng dài là đúng, không phải nhãn hiện; hàng danh sách mang dữ liệu, không xét.
    icon = tree(ROOT, n(0, 300, 100, 348, 148, role="button", description="Thêm tuỳ chọn cho Chương 4: Một cái tên"),
                n(0, 0, 160, 360, 216, role="listitem", text="Dế Mèn phiêu lưu ký tập hai"))
    assert dt.rule_r14("k", icon) == []
    unnamed = tree(ROOT, n(0, 300, 100, 348, 148, role="button"))
    assert "0 chữ" in dt.rule_r14("k", unnamed)[0].detail


def test_r14_dropdown_shows_its_value_and_markup_is_not_words():
    value = tree(ROOT, n(0, 20, 100, 340, 148, role="dropdownlist", text="Chương 12: Một buổi sáng ở bến sông"))
    styled = tree(ROOT, n(0, 20, 100, 200, 148, role="button", text="<span style='color:#a0600c'>Nghe</span>&nbsp;tiếp"))
    for t in (value, styled):
        assert dt.rule_r14("k", t) == []
    empty = tree(ROOT, n(0, 20, 100, 340, 148, role="dropdownlist"))
    long_button = tree(ROOT, n(0, 20, 100, 340, 148, role="button", text="<b>Thử</b> gửi trước rồi bỏ ghép"))
    assert "0 chữ" in dt.rule_r14("k", empty)[0].detail
    assert "6 chữ" in dt.rule_r14("k", long_button)[0].detail


def test_r9_parity_pair_compares_role_lines_token_height():
    a = tree(ROOT, n(0, 20, 100, 340, 148, role="button", text="Nghe tiếp", line_count=1, font_size=16, color="#1d1304"))
    same = tree(ROOT, n(0, 20, 100, 340, 147, role="button", text="Nghe tiếp", line_count=1, font_size=16, color="#1d1304"))
    other = tree(ROOT, n(0, 20, 100, 340, 181, role="button", text="Nghe tiếp", line_count=3, font_size=16, color="#1d1304"))
    pairs = [{"pair": "library-book", "android": "x", "qt": "y", "variants": ["_light"]}]
    assert dt.rule_r9({"android/x_light.png": a, "qt/y_light.png": same}, pairs) == []
    findings = dt.rule_r9({"android/x_light.png": a, "qt/y_light.png": other}, pairs)
    assert len(findings) == 1 and "lines 1 ≠ 3" in findings[0].detail and "cao" in findings[0].detail


def test_tree_files_are_found_next_to_qt_shots_and_in_android_build(tmp_path):
    png = tmp_path / "settings_listen_light.png"
    Image.new("RGB", (20, 20), BG).save(png)
    (tmp_path / "settings_listen_light.tree.json").write_text(json.dumps(
        tree(ROOT, n(0, 20, 100, 300, 148, role="button", text="Một hai ba bốn năm"))), encoding="utf-8")
    findings, count, errors = dt.lint_shots([dl.Shot("qt", png)])
    assert count == 1 and errors == [] and [f.rule for f in findings] == ["R14"]
    assert dt.tree_path(dl.Shot("android", Path("x/np_speed_light.png"))) == Path("x/np_speed_light.tree.json")
    assert len(dt.load_parity()) >= 10
