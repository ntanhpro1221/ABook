"""Generated artwork only: exercise the video judge with known pixel geometry."""
import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import pytest

spec = importlib.util.spec_from_file_location("transition_audit", Path(__file__).parents[1] / "scripts/transition_audit.py")
audit_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_tool)


def recording(cut=False, miss=False, reverse=False):
    rng = np.random.default_rng(45)
    art = rng.integers(30, 230, (90, 60, 3), dtype=np.uint8)
    library = Image.new("RGB", (240, 400), (20, 20, 20))
    detail = library.copy()
    ImageDraw.Draw(library).rectangle((110, 40, 210, 120), fill=(180, 140, 70))
    ImageDraw.Draw(detail).rectangle((100, 190, 220, 220), fill=(80, 170, 160))
    source, target = [20, 270, 48, 72], [20, 35, 60, 90]
    base_a, base_b = np.asarray(library), np.asarray(detail)
    def render(p, offset=0):
        backdrop = ((1-p)*base_a+p*base_b).astype(np.uint8)
        frame = Image.fromarray(backdrop)
        x, y, w, h = np.rint((1-p)*np.array(source)+p*np.array(target)).astype(int)
        frame.paste(Image.fromarray(art).resize((w, h), Image.Resampling.BILINEAR), (x+offset, y))
        return np.asarray(frame)
    path = np.linspace(0, 1, 22).tolist()
    if cut: path = [0, 0, .65, .9, 1]
    if reverse: path[9] = .2
    values = [0]*3 + path + [1]*3 + path[::-1] + [0]*3
    frames = [render(p, 6 if miss and i == 3 else 0) for i, p in enumerate(values)]
    end_open = 3+len(path)-1
    begin_close = end_open+4
    return frames, np.arange(len(values))/60, {
        "library_frame": 0, "page_frame": end_open+1,
        "source": source, "target": target, "open": [3, end_open],
        "close": [begin_close, begin_close+len(path)-1], "opacity_roi": [95, 0, 140, 250],
    }


def test_continuous_symmetric_recording_passes():
    result = audit_tool.audit(*recording())
    assert result["pass"], result["measurements"]
    assert result["measurements"]["close"]["endpoint_error_px"] <= 2


@pytest.mark.parametrize("fault,expected", [("cut", "cover_jump"), ("miss", "cover_endpoint"), ("reverse", "cover_reversed")])
def test_planted_faults_fail(fault, expected):
    result = audit_tool.audit(*recording(**{fault: True}))
    assert not result["pass"]
    assert expected in result["measurements"]["open"]["failures"]
    if fault == "cut":
        assert "screen_opacity_jump" in result["measurements"]["open"]["failures"]


def test_flat_template_is_rejected():
    with pytest.raises(ValueError, match="no visual detail"):
        audit_tool.ncc(np.zeros((30, 30)), np.zeros((10, 10)))


def test_odd_width_cover_preserves_native_half_pixel_rounding():
    assert audit_tool.cover_height(99) == 149
    assert audit_tool.cover_height(112) == 168


def test_opacity_cut_fails_even_when_cover_moves_smoothly():
    frames, times, config = recording()
    # Only the independent content ROI snaps; artwork follows its clean path.
    for i in range(3, config["open"][1]+1):
        frames[i] = frames[i].copy()
        frames[i][:250, 95:] = frames[0 if i < 12 else config["page_frame"]][:250, 95:]
    result = audit_tool.audit(frames, times, config)
    assert "screen_opacity_jump" in result["measurements"]["open"]["failures"]
    assert "cover_jump" not in result["measurements"]["open"]["failures"]


def test_asymmetry_and_sparse_idle_timestamps():
    frames, times, config = recording()
    # A recorder may emit no frames during a long settled page. That gap must
    # not inflate either animation. A slower return must still fail symmetry.
    times[config["close"][0]:] += 5
    clean = audit_tool.audit(frames, times, config)
    assert clean["pass"], clean["measurements"]
    first = config["close"][0]
    times[first:] = times[first] + (times[first:]-times[first])*1.4
    result = audit_tool.audit(frames, times, config)
    assert not result["symmetric"]
    assert not result["pass"]


def test_near_limit_duration_reports_point_estimate_and_sampling_uncertainty():
    frames, times, config = recording()
    first = config["close"][0]
    times[first:] = times[first] + (times[first:]-times[first])*1.2
    result = audit_tool.audit(frames, times, config)
    assert not result["nominal_symmetric"]
    assert result["symmetric"]
    assert 30 < result["symmetry_sampling_uncertainty_ms"] < 40


def test_incomplete_or_unordered_timestamps_are_rejected():
    frames, times, config = recording()
    with pytest.raises(ValueError, match="timestamps"):
        audit_tool.audit(frames, times[:-1], config)
    times[4] = times[3]
    with pytest.raises(ValueError, match="timestamps"):
        audit_tool.audit(frames, times, config)


def test_native_refinement_preserves_known_endpoints_with_two_templates():
    # Smooth, low-frequency artwork exposes scale aliases that random noise
    # does not. Endpoints are independent crops, including a one-pixel shift.
    art = Image.new("RGB", (224, 336), (22, 45, 66))
    draw = ImageDraw.Draw(art)
    for radius in range(90, 500, 80):
        draw.ellipse((-radius, 336-radius, radius, 336+radius), outline=(80, 100, 110), width=2)
    draw.rectangle((20, 25, 112, 40), fill=(240, 230, 200))
    source = np.asarray(art.resize((198, 297), Image.Resampling.BILINEAR))
    target = np.asarray(art)
    for x, y, template in [(40, 432, source), (40, 209, target)]:
        frame = np.full((850, 400, 3), 245, dtype=np.uint8)
        frame[y:y+template.shape[0], x:x+template.shape[1]] = template
        located = audit_tool.locate(frame, [source, target], range(158, 270, 3), [20, 180, 300, 800])
        assert located["rect"] == [x, y, template.shape[1], template.shape[0]]
        assert located["confidence"] > .999


def test_stationary_chrome_detects_a_single_frame_blink():
    frames, times, config = recording()
    config["stationary_rois"] = [[0, 380, 240, 20]]
    assert audit_tool.audit(frames, times, config)["pass"]
    frames[12] = frames[12].copy()
    frames[12][380:] = 255
    result = audit_tool.audit(frames, times, config)
    assert not result["pass"]
    assert not result["stationary_regions"][0]["pass"]


def test_sideways_cover_jump_is_not_hidden_by_vertical_progress():
    frames, times, config = recording()
    frame = frames[12].copy()
    # Move only the cover band; both independent endpoint screens stay intact.
    frame[:, 20:95] = (20, 20, 20)
    frame[:, 30:105] = frames[12][:, 20:95]
    frames[12] = frame
    result = audit_tool.audit(frames, times, config)
    assert not result["pass"]
    assert "cover_axis_drift" in result["measurements"]["open"]["failures"]


def test_eased_timing_keeps_visible_pixel_tails(monkeypatch):
    # Calibrate timing separately from matching: both independently known paths
    # take 350ms. A 2% progress cutoff discards a still-visible three-pixel tail
    # on the return and biases its duration when content alpha is squared.
    frames, times, config = recording()
    def emphasized(x):
        low, high = 0., 1.
        for _ in range(40):
            t = (low+high)/2
            actual = 3*(1-t)**2*t*.4 + 3*(1-t)*t*t*.2 + t**3
            if actual < x: low = t
            else: high = t
        t = (low+high)/2
        return 3*(1-t)*t*t+t**3
    path = np.array([emphasized(i/21) for i in range(22)])
    source, target = np.array(config["source"]), np.array(config["target"])
    rects = iter([np.rint(source+(target-source)*p).tolist() for p in path] +
                 [np.rint(target+(source-target)*p).tolist() for p in path])
    mixtures = iter([[[1-p, p*p] for p in path], [[p, (1-p)**2] for p in path]])
    monkeypatch.setattr(audit_tool, "locate", lambda *args: {"rect": next(rects), "confidence": 1.})
    monkeypatch.setattr(audit_tool, "opacity_series", lambda *args: next(mixtures))
    result = audit_tool.audit(frames, times, config)
    assert result["measurements"]["close"]["duration_ms"] >= 300
    assert result["symmetric"]
