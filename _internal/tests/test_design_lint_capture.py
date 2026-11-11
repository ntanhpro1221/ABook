"""Regression cases for missing measurements and the capture sidecar contract."""
import hashlib
import json
from pathlib import Path
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import design_lint as dl
import design_lint_tree as dt
from test_design_lint import ROOT, n, tree, analyse, canvas, button, player, shot


def test_unknown_selection_role_and_multiple_selected_are_red():
    unknown = tree(ROOT, n(0, 0, 10, 80, 54, selected=True), n(0, 80, 10, 160, 54, selected=False))
    multiple = tree(ROOT, n(0, 0, 10, 80, 54, role="tab", selected=True),
                    n(0, 80, 10, 160, 54, role="tab", selected=True))
    assert dt.rule_r1("k", unknown)
    assert dt.rule_r1("k", multiple)


@pytest.mark.parametrize("gap,red", [(0, False), (4.5, False), (4.51, True), (64, False), (65, True), (96, True)])
def test_spacing_tolerance_and_large_gaps(gap, red):
    data = tree(ROOT, n(0, 20, 10, 300, 34, text="A"), n(0, 20, 34 + gap, 300, 58 + gap, text="B"))
    assert bool(dt.rule_r3("k", data)) is red


def test_unrelated_columns_do_not_create_spacing_pairs():
    data = tree(ROOT, n(0, 0, 0, 180, 700), n(0, 180, 0, 360, 700),
                n(1, 0, 100, 180, 124, text="A"), n(2, 180, 142, 360, 166, text="B"))
    assert not dt.rule_r3("k", data)


def test_clipping_in_multiline_gap_is_green_but_through_line_is_red():
    lines = [{"bounds": [20, 100, 300, 120]}, {"bounds": [20, 132, 300, 152]}]
    good = tree(ROOT, n(0, 20, 100, 300, 152, text="A\nB", lines=lines, visible=[20, 100, 300, 128]))
    bad = tree(ROOT, n(0, 20, 100, 300, 152, text="A\nB", lines=lines, visible=[20, 100, 300, 140]))
    assert not dt.rule_r8("k", good)
    assert dt.rule_r8("k", bad)


def test_floating_label_fully_inside_reading_box_is_red():
    data = tree(ROOT, n(0, 20, 100, 340, 300, text="Reading paragraph"),
                n(0, 100, 180, 250, 220, text="Follow"))
    assert dt.rule_r8("k", data)


@pytest.mark.parametrize("size,red", [(11.9, True), (12, False), (13, True), (16, False), (16.3, True)])
def test_type_scale_has_no_lower_font_exception(size, red):
    data = tree(ROOT, n(0, 20, 100, 300, 124, text="A", font_size=size))
    assert bool(dt.rule_r11("k", data)) is red


def test_parity_checks_style_and_background_and_four_dp_boundary():
    def screen(**extra):
        return tree(ROOT, n(0, 20, 100, 300, extra.pop("bottom", 148), role="button", text="Play",
                            line_count=1, font_size=16, color="#1a1814", **extra))
    pairs = [{"pair": "now-playing", "android": "a", "qt": "b", "variants": ["_light"]}]
    def findings(a, b):
        return dt.rule_r9({"android/a_light.png": a, "qt/b_light.png": b}, pairs)
    assert not findings(screen(), screen(bottom=152))
    assert findings(screen(), screen(bottom=152.01))
    assert findings(screen(control_style="underline"), screen(control_style="filled"))
    assert findings(screen(background_color="#d4912b"), screen(background_color="#ffffff"))


def test_capture_pair_checksum_and_invalid_parent_fail_loudly(tmp_path):
    png = tmp_path / "frame.png"
    Image.new("RGB", (360, 780)).save(png)
    data = tree(ROOT, n(0, 20, 100, 300, 124, text="A", font_size=16))
    data.update(image=png.name, image_sha256=hashlib.sha256(png.read_bytes()).hexdigest())
    sidecar = png.with_suffix(".tree.json")
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    assert dt.load(dl.Shot("android", png))["nodes"][1]["text"] == "A"
    Image.new("RGB", (360, 780), "white").save(png)
    with pytest.raises(ValueError, match="checksum"):
        dt.load(dl.Shot("android", png))
    data.pop("image_sha256")
    data["nodes"][1]["parent"] = 1
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="parents"):
        dt.load(dl.Shot("android", png))


def test_missing_sidecar_is_reported_as_unmeasured(tmp_path):
    assert dt.coverage([dl.Shot("web", tmp_path / "x.png")])["web"] == {"images": 1, "sidecars": 0}


@pytest.mark.parametrize("platform", ["android", "qt", "web"])
def test_main_button_height_uses_audit_range_on_every_platform(tmp_path, platform):
    im, draw = canvas()
    button(draw, 900, 120)  # 40 dp is outside the requested 44..56 range.
    scaled = im if platform == "android" else im.resize((360, 780), Image.Resampling.NEAREST)
    path = tmp_path / "x_light.png"
    scaled.save(path)
    assert any("cao 40" in f.detail for f in dl.rule_r4(dl.Analysis(dl.Shot(platform, path))))


def test_horizontal_anchor_movement_is_red(tmp_path):
    a = shot(tmp_path, player(300), "a_light.png")
    moved = player(300)
    # Shift the entire image horizontally while preserving the cover's vertical coordinate.
    moved.paste(player(300), (12, 0))
    b = shot(tmp_path, moved, "b_light.png")
    anchors = {s.key: dl.anchors(dl.Analysis(s)) for s in (a, b)}
    assert any("cover_left" in f.detail for f in dl.rule_r7(anchors, {"g": list(anchors)}))
