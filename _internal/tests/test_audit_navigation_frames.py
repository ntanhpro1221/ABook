"""The pixel gate must reject blanks and independent width/height distortion."""
import numpy as np
from PIL import Image
import imageio_ffmpeg

from scripts.audit_navigation_frames import evaluate, track, track_covers


def artwork(seed=42):
    rng = np.random.default_rng(seed)
    return (rng.random((90, 60, 3)) * 255).astype(np.uint8)


def test_cover_tracker_rejects_blank_and_measures_aspect_independently():
    template = artwork()
    check = {"search": [0, 0, 200, 200], "widths": [60], "aspects": [.8, 1., 1.2]}
    frame = np.zeros((200, 200, 3), np.uint8)
    assert track(frame, template, check)["score"] < .1
    frame[20:110, 30:90] = template
    good = track(frame, template, check)
    assert good["score"] > .99
    assert good["aspect_error"] == 0
    frame[:] = 0
    frame[20:95, 30:90] = np.asarray(Image.fromarray(template).resize((60, 75)))
    bad = track(frame, template, check)
    assert bad["score"] > .99
    assert bad["aspect_error"] > .05


def test_bar_tracker_follows_vertical_displacement_instead_of_reporting_a_fixed_y():
    template = artwork()
    check = {"search": [0, 0, 200, 200]}
    ys = []
    for y in [10, 40, 70]:
        frame = np.zeros((200, 200, 3), np.uint8)
        frame[y:y + 90, 30:90] = template
        match = track(frame, template, check)
        assert match["score"] > .99
        ys.append(match["rect"][1])
    assert max(ys) - min(ys) == 60


def video(path, values):
    writer = imageio_ffmpeg.write_frames(str(path), (200, 200), fps=30,
        codec="libx264rgb", pix_fmt_out="rgb24", macro_block_size=1,
        output_params=["-crf", "0", "-preset", "ultrafast"])
    writer.send(None)
    try:
        for value in values:
            writer.send(value.tobytes())
    finally:
        writer.close()


def test_recorded_pop_is_rejected_and_a_multi_frame_fade_passes(tmp_path):
    target = np.zeros((200, 200, 3), np.uint8)
    target[20:110, 30:90] = artwork()
    for name, alphas, expected in [("pop", [0, 0, 1, 1], False), ("fade", [0, .25, .5, .75, 1], True)]:
        path = tmp_path / f"{name}.mp4"
        video(path, [(target * alpha).astype(np.uint8) for alpha in alphas])
        result = evaluate({"video": str(path), "checks": [{"name": name, "kind": "fade", "frames": [0, len(alphas)-1],
            "before": 0, "after": len(alphas)-1, "rect": [30, 20, 60, 90]}]}, tmp_path / f"{name}.json")
        assert result["decoded_frames"] == len(alphas)
        assert result["summary"][name]["pass"] is expected


def test_recorded_empty_grid_frame_cannot_pass_the_gate(tmp_path):
    blank = np.zeros((200, 200, 3), np.uint8)
    full = blank.copy(); full[20:110, 30:90] = artwork()
    path = tmp_path / "grid.mp4"
    video(path, [full, blank, full])
    result = evaluate({"video": str(path), "checks": [{"name": "grid", "kind": "grid", "frames": [0, 2],
        "rect": [0, 0, 200, 200]}]}, tmp_path / "grid.json")
    assert result["summary"]["grid"]["empty_frames"] == [1]
    assert result["summary"]["grid"]["pass"] is False


def test_one_good_cover_cannot_hide_another_distorted_cover():
    first, second = artwork(42), artwork(43)
    frame = np.zeros((200, 250, 3), np.uint8)
    frame[20:110, 10:70] = first
    frame[20:110, 120:192] = np.asarray(Image.fromarray(second).resize((72, 90)))
    result = track_covers(frame, [first, second], {"search": [0, 0, 250, 200], "widths": [60, 72], "aspects": [1., 1.2], "threshold": .95})
    assert len(result["measured_covers"]) == 2
    assert result["aspect_error"] > .05
