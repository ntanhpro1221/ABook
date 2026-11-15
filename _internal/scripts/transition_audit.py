"""Measure a recorded shared-element transition against its settled endpoints.

The config supplies independent reference frames, cover rectangles and inclusive
frame ranges (zero based). No source artwork is stored by this tool. Opacity is
an estimate from least-squares pixel mixtures, not an Android alpha measurement.
Run: python -X utf8 scripts/transition_audit.py recording.mp4 config.json out.json
Dependencies used only by this offline audit: PyAV, NumPy, Pillow, SciPy.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from scipy.signal import correlate


def read_video(path):
    import av
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        frames, times = [], []
        for frame in container.decode(stream):
            frames.append(frame.to_ndarray(format="rgb24"))
            times.append(float(frame.pts * frame.time_base))
    if len(frames) < 3 or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("Video needs at least three frames with increasing timestamps")
    return frames, np.asarray(times)


def gray(image):
    return np.asarray(image, dtype=np.float32).mean(axis=2)


def resize(image, width, height):
    return np.asarray(Image.fromarray(image).resize((width, height), Image.Resampling.BILINEAR))


def cover_height(width):
    # Match native positive half-pixel rounding (99px -> 149px), rather than
    # Python's even-number rounding, which distorts every odd-width template.
    return int(width * 1.5 + .5)


def ncc(image, template):
    """Zero-mean normalized correlation at every valid template location."""
    h, w = template.shape
    centered = template - template.mean()
    norm = np.linalg.norm(centered)
    if norm < 1e-5:
        raise ValueError("Cover template has no visual detail")
    integral = np.pad(image.astype(np.float64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    squared = np.pad(image.astype(np.float64)**2, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    def sums(a):
        return a[h:, w:] - a[:-h, w:] - a[h:, :-w] + a[:-h, :-w]
    variance = np.maximum(0, sums(squared) - sums(integral)**2 / (h*w))
    score = correlate(image, centered, mode="valid", method="fft") / np.maximum(norm * np.sqrt(variance), 1e-5)
    return np.where(variance > 1, np.clip(score, -1, 1), -1)


def locate(frame, templates, widths, search=None):
    """Coarse multiscale matching, then native-resolution position/size refinement."""
    height, width = frame.shape[:2]
    x0, y0, x1, y1 = search or (0, 0, width, height)
    region = frame[y0:y1, x0:x1]
    factor = 4
    small = gray(resize(region, max(1, region.shape[1]//factor), max(1, region.shape[0]//factor)))
    candidates = []
    # Match the inside of the artwork so corner radius and progress badges do
    # not become a stronger signal than the cover itself.
    for template in templates:
        coarse = []
        for side in widths:
            side = int(side)
            full = resize(template, side, cover_height(side))
            inset = max(1, round(side*.1))
            patch = full[inset:-inset, inset:-inset]
            tw, th = max(2, patch.shape[1]//factor), max(2, patch.shape[0]//factor)
            if th > small.shape[0] or tw > small.shape[1]:
                continue
            score = ncc(small, gray(resize(patch, tw, th)))
            at = np.unravel_index(np.argmax(score), score.shape)
            value = float(score[at])
            coarse.append((value, (int(at[1]*factor-inset+x0), int(at[0]*factor-inset+y0), side), template))
        # Downsampling can rank a neighbouring scale or the other endpoint's
        # template first. Refine several hypotheses from BOTH references so a
        # coarse alias cannot manufacture an endpoint error or a reversal.
        candidates.extend(sorted(coarse, key=lambda item: item[0], reverse=True)[:3])
    if not candidates:
        raise ValueError("Search region is smaller than the cover")
    refined = (-1, None)
    for _, (bx, by, bw), template in candidates:
        for side in range(max(8, bw-4), bw+5):
            inset = max(1, round(side*.1))
            full = resize(template, side, cover_height(side))
            patch = gray(full[inset:-inset, inset:-inset])
            left, top = max(0, bx+inset-7), max(0, by+inset-7)
            right = min(width, bx+inset+patch.shape[1]+8)
            bottom = min(height, by+inset+patch.shape[0]+8)
            if bottom-top < patch.shape[0] or right-left < patch.shape[1]:
                continue
            score = ncc(gray(frame[top:bottom, left:right]), patch)
            at = np.unravel_index(np.argmax(score), score.shape)
            value = float(score[at])
            if value > refined[0]:
                refined = (value, [int(left+at[1]-inset), int(top+at[0]-inset), side, cover_height(side)])
    if refined[1] is None:
        raise ValueError("Cover hypotheses lie outside the image")
    return {"rect": refined[1], "confidence": round(refined[0], 5)}


def opacity_series(frames, library, page, region, exclude):
    x, y, w, h = region
    mask = np.zeros(library.shape[:2], dtype=bool)
    mask[y:y+h, x:x+w] = True
    for rect in exclude:
        bx, by, bw, bh = map(lambda value: int(round(value)), rect)
        mask[max(0, by-4):by+bh+4, max(0, bx-4):bx+bw+4] = False
    # Sample the quiet background, then fit both independent settled screens.
    background = np.median(np.concatenate([library[mask], page[mask]]), axis=0)
    a, b = library.astype(float)-background, page.astype(float)-background
    mask &= np.maximum(np.linalg.norm(a, axis=2), np.linalg.norm(b, axis=2)) > 30
    if mask.sum() < 32:
        raise ValueError("Opacity ROI lacks independent screen content")
    basis = np.stack([a[mask].ravel(), b[mask].ravel()], axis=1)
    if np.linalg.cond(basis) > 100:
        raise ValueError("Settled reference screens are not distinguishable")
    inverse = np.linalg.pinv(basis)
    return [np.clip(inverse @ (frame.astype(float)-background)[mask].ravel(), 0, 1).tolist() for frame in frames]


def audit(frames, times, config):
    if len(frames) != len(times) or len(frames) < 3 or np.any(np.diff(times) <= 0):
        raise ValueError("Frames need matching increasing timestamps")
    library, page = (frames[config[k]] for k in ("library_frame", "page_frame"))
    start, end = (np.array(config[k], dtype=float) for k in ("source", "target"))
    templates = [library[int(start[1]):int(start[1]+start[3]), int(start[0]):int(start[0]+start[2])],
                 page[int(end[1]):int(end[1]+end[3]), int(end[0]):int(end[0]+end[2])]]
    widths = range(max(12, int(min(start[2], end[2])*.8)), int(max(start[2], end[2])*1.2)+1, 3)
    tracks, reports = {}, {}
    for direction in ("open", "close"):
        lo, hi = config[direction]
        indices = list(range(lo, hi+1))
        if lo < 0 or hi >= len(frames) or lo >= hi:
            raise ValueError("Invalid inclusive frame range")
        tracking = [locate(frames[i], templates, widths, config.get("search")) for i in indices]
        rects = np.array([item["rect"] for item in tracking], dtype=float)
        reference_a, reference_b = (start, end) if direction == "open" else (end, start)
        delta = reference_b-reference_a
        moving = np.abs(delta) > 2
        steps = np.diff(rects, axis=0)
        reverse_px = float(np.max(np.maximum(0, -steps[:, moving]*np.sign(delta[moving])))) if moving.any() else 0
        distance = np.linalg.norm(delta)
        progress = ((rects-reference_a) @ delta) / max(distance**2, 1)
        max_step = float(np.max(np.linalg.norm(steps, axis=1)) / max(distance, 1))
        static_drift = float(np.max(np.abs(rects[:, ~moving]-reference_a[~moving]))) if (~moving).any() else 0
        opacity = opacity_series([frames[i] for i in indices], library, page,
                                 config.get("opacity_roi", [0, 0, library.shape[1], library.shape[0]]), rects.tolist())
        opacity_step = float(np.max(np.abs(np.diff(np.array(opacity), axis=0))))
        def corners(rect):
            return np.concatenate((rect[:2], rect[:2]+rect[2:]))
        error = max(float(np.max(np.abs(corners(rects[0])-corners(reference_a)))),
                    float(np.max(np.abs(corners(rects[-1])-corners(reference_b)))))
        # Include a content fade that continues after the cover has landed.
        # screenrecord omits unchanged frames: never count an idle timestamp gap
        # before the first changed frame as animation time.
        mixture = np.array(opacity)
        departure = np.max(np.abs(mixture - mixture[0]), axis=1)
        arrival = np.max(np.abs(mixture - mixture[-1]), axis=1)
        # A percentage cutoff shortens an eased flight differently in each
        # direction, especially when page/content alpha multiply. Measure the
        # cover against the same native-pixel endpoint tolerance as the landing
        # gate; independently retain any content fade beyond that flight.
        corner_rects = np.column_stack((rects[:, :2], rects[:, :2]+rects[:, 2:]))
        pose_departure = np.max(np.abs(corner_rects-corners(reference_a)), axis=1)
        pose_arrival = np.max(np.abs(corner_rects-corners(reference_b)), axis=1)
        active = np.flatnonzero(((pose_departure > 2) & (pose_arrival > 2)) |
                                ((departure > .02) & (arrival > .02)))
        cadence = min(1/30, float(np.median(np.diff(times))))
        if len(active):
            first, last = lo+int(active[0]), lo+int(active[-1])
            begin = max(float(times[max(lo, first-1)]), float(times[first])-cadence)
            finish = min(float(times[min(hi, last+1)]), float(times[last])+cadence)
            duration = finish-begin
        else:
            duration = 0
        failures = []
        if min(t["confidence"] for t in tracking) < config.get("min_confidence", .55): failures.append("cover_match_uncertain")
        if error > 2: failures.append("cover_endpoint")
        if reverse_px > 2: failures.append("cover_reversed")
        if static_drift > 2: failures.append("cover_axis_drift")
        if max_step > .25: failures.append("cover_jump")
        if opacity_step > .25: failures.append("screen_opacity_jump")
        if not .27 <= duration <= .48: failures.append("duration_outside_token")
        reports[direction] = {"frames": [lo, hi], "duration_ms": round(duration*1000, 2),
                              "sampling_uncertainty_ms": round(cadence*1000, 2),
                              "active_frames": [lo+int(active[0]), lo+int(active[-1])] if len(active) else [],
                              "active_samples": int(len(active)),
                              "max_active_frame_gap_ms": round(float(np.max(np.diff(times[lo+active]))) * 1000, 2) if len(active)>1 else None,
                              "endpoint_error_px": error, "reverse_px": reverse_px,
                              "static_axis_drift_px": static_drift,
                              "max_cover_step": round(max_step, 4), "max_opacity_step": round(opacity_step, 4),
                              "failures": failures}
        tracks[direction] = [{"frame": i, "time": float(times[i]), **t, "opacity_estimate": o}
                             for i, t, o in zip(indices, tracking, opacity)]
    durations = [reports[d]["duration_ms"] for d in ("open", "close")]
    symmetry_limit = max(40, max(durations)*.15)
    nominal_symmetric = abs(durations[0]-durations[1]) <= symmetry_limit
    # Each transition boundary falls between captured samples. Preserve the
    # point estimates and nominal verdict, and compare the closest ends of
    # their one-sample uncertainty intervals. Never invent interpolated frames.
    uncertainty = sum(reports[d]["sampling_uncertainty_ms"] for d in ("open", "close"))
    symmetric = abs(durations[0]-durations[1]) <= symmetry_limit + uncertainty
    stationary = []
    for x, y, w, h in config.get("stationary_rois", []):
        reference = frames[config["library_frame"]][y:y+h, x:x+w].astype(float)
        error = max(float(np.abs(frame[y:y+h, x:x+w].astype(float)-reference).mean()/255)
                    for frame in frames)
        stationary.append({"rect": [x, y, w, h], "max_mean_pixel_change": round(error, 5),
                           "pass": error <= .025})
    return {"pass": symmetric and all(roi["pass"] for roi in stationary) and not any(r["failures"] for r in reports.values()),
            "symmetric": symmetric, "measurements": reports, "tracks": tracks,
            "nominal_symmetric": nominal_symmetric,
            "symmetry_limit_ms": round(symmetry_limit, 2),
            "symmetry_sampling_uncertainty_ms": round(uncertainty, 2),
            "stationary_regions": stationary,
            "method": "native-resolution multiscale NCC; settled-pixel mixture opacity estimate"}


def main():
    frames, times = read_video(sys.argv[1])
    result = audit(frames, times, json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
    Path(sys.argv[3]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "tracks"}, ensure_ascii=False))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
