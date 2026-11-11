"""Measure recorded UI pixels, without assuming that animation code is correct.

Run with the project's Python venv and a JSON manifest. Frame numbers are zero
based DECODED frames. Manifest checks: cover (multi-size template tracking with
independent aspect probes), flight (cover plus position continuity), bar (fixed-size template tracking), grid (coloured
artwork occupancy), fade (projection between recorded before/after pixels).
Each check supplies frames [first,last], reference frame/rect, search rect,
threshold and optional widths/aspects. Coordinates are source-video pixels.
Outputs per-frame evidence, explicit failures and UNKNOWN when a measurement
cannot be made. A missing match never counts as a successful aspect test.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw
from scipy.signal import fftconvolve


def frames(path):
    # Android screenrecord is variable-rate: ffmpeg's automatic sync can drop
    # transition frames when the clip contains long static intervals.
    reader = imageio_ffmpeg.read_frames(str(path), pix_fmt="rgb24", output_params=["-vsync", "0"])
    try:
        meta = next(reader)
        yield meta
        for raw in reader:
            yield np.frombuffer(raw, np.uint8).reshape(meta["size"][1], meta["size"][0], 3)
    finally:
        reader.close()


def crop(frame, rect):
    x, y, w, h = map(round, rect)
    return frame[y:y + h, x:x + w]


def sums(a, h, w):
    integral = np.pad(a, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    return integral[h:, w:] - integral[:-h, w:] - integral[h:, :-w] + integral[:-h, :-w]


def correlate(haystack, needle):
    """Normalized correlation; constant/blank regions cannot match artwork."""
    h, w = needle.shape
    if h > haystack.shape[0] or w > haystack.shape[1]:
        return -1., (0, 0)
    centered = needle - needle.mean()
    energy = float(np.square(centered).sum())
    if energy < 1e-6:
        raise ValueError("reference template has no pixel variance")
    n = h * w
    variance = np.maximum(0, sums(haystack * haystack, h, w) - sums(haystack, h, w) ** 2 / n)
    score = fftconvolve(haystack, centered[::-1, ::-1], mode="valid") / np.sqrt(np.maximum(1e-6, variance * energy))
    y, x = np.unravel_index(np.argmax(score), score.shape)
    return float(score[y, x]), (int(x), int(y))


def track(frame, template, check):
    search = check["search"]
    region = crop(frame, search)
    factor = min(1., check.get("analysis_width", 300) / region.shape[1])
    gray = np.asarray(Image.fromarray(region).resize((round(region.shape[1] * factor), round(region.shape[0] * factor))).convert("L"), dtype=np.float64)
    best = {"score": -1.}
    widths = check.get("widths", [template.shape[1]])
    aspects = check.get("aspects", [1.])
    for width in widths:
        for aspect in aspects:
            w = max(4, round(width * factor))
            h = max(4, round(width * template.shape[0] / template.shape[1] / aspect * factor))
            small = np.asarray(Image.fromarray(template).resize((w, h)).convert("L"), dtype=np.float64)
            score, (x, y) = correlate(gray, small)
            if score > best["score"]:
                best = {"score": round(score, 5), "rect": [round(search[0] + x / factor, 2), round(search[1] + y / factor, 2), round(w / factor, 2), round(h / factor, 2)], "aspect_error": round(abs(aspect - 1), 4)}
    return best


def track_covers(frame, templates, check):
    """Probe independent cover patches so viewport-edge clipping is not scaling.

    Each visible book is measured separately, and the worst matched aspect is
    retained. Unmatched books are reported, never assumed to have a good ratio.
    """
    matches = []
    for index, template in enumerate(templates):
        best = {"score": -2.}
        pieces = check.get("strips", 1)
        for piece in range(pieces):
            left = round(template.shape[1] * piece / pieces)
            right = round(template.shape[1] * (piece + 1) / pieces)
            patch = template[:, left:right]
            config = {**check}
            if "widths" in check:
                config["widths"] = [width * (right - left) / template.shape[1] for width in check["widths"]]
            result = track(frame, patch, config)
            if result["score"] > best["score"]:
                best = {**result, "template": index, "strip": piece}
            if best["score"] > .999 and best["aspect_error"] == 0:
                break
        matches.append(best)
    best = max(matches, key=lambda match: match["score"])
    measured = [match for match in matches if match["score"] >= check.get("threshold", .7)]
    return {**best, "aspect_error": max((match["aspect_error"] for match in measured), default=best.get("aspect_error", 0)),
        "measured_covers": measured, "unmatched_templates": [match["template"] for match in matches if match not in measured]}


def flight_continuity(rows, check):
    """Gate decoded adjacent frames in either direction, preserving their PTS.

    Endpoint dwell/jitter is not intermediate motion. A missing frame cannot be
    bridged, and a stationary cover cannot pass a flight check.
    """
    good = [r for r in rows if r["matched"]]
    if len(good) < 2:
        return {"continuity_pass": False, "intermediate_positions": 0, "jump_pairs": []}
    start = np.array(good[0]["rect"][:2])
    end = np.array(good[-1]["rect"][:2])
    vector = end - start
    distance = float(np.linalg.norm(vector))
    # The checked-in 300 ms deceleration curve travels about 46% on its first
    # 16 ms frame. Half the path admits that curve; the independent four-position
    # minimum still rejects two-step jumps and endpoint jitter.
    limit = check.get("max_step_px", distance * check.get("max_step_fraction", .5))
    steps = []
    for a, b in zip(rows, rows[1:]):
        if not (a["matched"] and b["matched"]):
            continue
        step = float(np.linalg.norm(np.array(b["rect"][:2]) - a["rect"][:2]))
        steps.append({"frames": [a["frame"], b["frame"]], "step_px": round(step, 2),
                      "dt_ms": round((b["time"] - a["time"]) * 1000, 3)})
    intermediate = []
    if distance > 0:
        for row in good:
            position = np.array(row["rect"][:2])
            progress = float(np.dot(position - start, vector) / distance ** 2)
            if .05 < progress < .95 and all(np.linalg.norm(position - p) > check.get("position_tolerance_px", 3) for p in intermediate):
                intermediate.append(position)
    jumps = [s for s in steps if s["step_px"] > limit]
    return {"travel_px": round(distance, 2), "max_step_limit_px": round(limit, 2),
            "max_position_step": max(steps, key=lambda s: s["step_px"], default=None),
            "jump_pairs": jumps, "intermediate_positions": len(intermediate),
            "min_intermediate_positions": check.get("min_intermediate_positions", 4),
            "continuity_pass": len(good) == len(rows) and distance >= check.get("min_travel_px", 20)
                and not jumps and len(intermediate) >= check.get("min_intermediate_positions", 4)}


def evaluate(manifest, output):
    video = Path(manifest["video"])
    timing = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(video), "-vf", "showinfo", "-vsync", "0", "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, check=True)
    pts = [float(value) for value in re.findall(r"\bn:\s*\d+.*?\bpts_time:([\d.e+-]+)", timing.stderr)]
    checks = manifest["checks"]
    needed = {int(c["reference"]) for c in checks if "reference" in c}
    needed |= {int(c[k]) for c in checks for k in ("before", "after") if k in c}
    references = {}
    stream = frames(video)
    meta = next(stream)
    for index, frame in enumerate(stream):
        if index in needed:
            references[index] = frame.copy()
    if needed - references.keys():
        raise ValueError(f"missing reference frames: {needed - references.keys()}")
    records = {c["name"]: [] for c in checks}
    templates = {c["name"]: [crop(references[c["reference"]], rect) for rect in (c.get("rects") or [c["rect"]])] for c in checks if "reference" in c}
    selected = set(manifest.get("contact_frames", []))
    thumbs = []
    stream = frames(video)
    next(stream)
    decoded = 0
    for index, frame in enumerate(stream):
        decoded += 1
        for check in checks:
            if not check["frames"][0] <= index <= check["frames"][1]:
                continue
            row = {"frame": index, "time": pts[index] if index < len(pts) else None}
            kind = check["kind"]
            if kind in ("cover", "flight", "bar"):
                if kind == "flight" and len(templates[check["name"]]) != 1:
                    raise ValueError("a flight must track exactly one cover")
                row.update(track_covers(frame, templates[check["name"]], check) if kind != "bar" else track(frame, templates[check["name"]][0], check))
                row["matched"] = row["score"] >= check.get("threshold", .7)
            elif kind == "grid":
                area = crop(frame, check["rect"]).astype(float)
                saturated = (area.max(2) - area.min(2) > check.get("chroma", 24)) & (area.max(2) > 50)
                row["artwork_pixels"] = int(saturated.sum())
                row["empty"] = row["artwork_pixels"] < check.get("min_pixels", 100)
            elif kind == "fade":
                start = crop(references[check["before"]], check["rect"]).astype(float)
                end = crop(references[check["after"]], check["rect"]).astype(float)
                delta = end - start
                energy = float(np.square(delta).sum())
                if energy < 1:
                    raise ValueError("fade endpoints are identical")
                current = crop(frame, check["rect"]).astype(float)
                if check.get("align"):
                    dx, dy = check["align"]
                    x, y, w, h = check["rect"]
                    search = [max(0, x - dx), max(0, y - dy), min(frame.shape[1], x + w + dx) - max(0, x - dx), min(frame.shape[0], y + h + dy) - max(0, y - dy)]
                    match = track(frame, end.astype(np.uint8), {"search": search, "widths": [w], "analysis_width": search[2]})
                    row["alignment_score"] = match["score"]
                    if match["score"] >= .65:
                        current = crop(frame, match["rect"]).astype(float)
                row["alpha"] = round(float(np.clip(np.sum((current - start) * delta) / energy, 0, 1)), 5)
                row["residual"] = round(float(np.sqrt(np.mean((current - start - row["alpha"] * delta) ** 2))), 3)
            else:
                raise ValueError(f"unknown check kind {kind}")
            records[check["name"]].append(row)
        if index in selected:
            thumb = Image.fromarray(frame)
            thumb.thumbnail((240, 534))
            panel = Image.new("RGB", (240, 562), "#171717")
            panel.paste(thumb, (0, 28))
            ImageDraw.Draw(panel).text((5, 5), str(index), fill="#ffbd50")
            thumbs.append(panel)
    summary = {}
    for check in checks:
        rows = records[check["name"]]
        kind = check["kind"]
        item = {"kind": kind, "measured_frames": len(rows)}
        if kind in ("cover", "flight", "bar"):
            good = [r for r in rows if r["matched"]]
            item["missing_frames"] = [r["frame"] for r in rows if not r["matched"]]
            if kind in ("cover", "flight"):
                item["max_aspect_error"] = max((r["aspect_error"] for r in good), default=None)
                item["aspect_unknown_frames"] = item["missing_frames"]
                item["pass"] = bool(rows) and not item["missing_frames"] and item["max_aspect_error"] <= .05
                if kind == "flight":
                    item.update(flight_continuity(rows, check))
                    item["pass"] = item["pass"] and item["continuity_pass"]
            else:
                ys = [r["rect"][1] for r in good]
                item["y_range_px"] = round(max(ys) - min(ys), 2) if ys else None
                item["pass"] = bool(ys) and not item["missing_frames"] and item["y_range_px"] <= check.get("tolerance", 2)
        elif kind == "grid":
            item["empty_frames"] = [r["frame"] for r in rows if r["empty"]]
            item["pass"] = bool(rows) and not item["empty_frames"]
        else:
            jumps = [(b["frame"], round(b["alpha"] - a["alpha"], 5)) for a, b in zip(rows, rows[1:])]
            item["max_alpha_step"] = max((v for _, v in jumps), default=None)
            item["pop_frames"] = [f for f, v in jumps if v > check.get("max_step", .65)]
            item["max_residual"] = max((r["residual"] for r in rows), default=None)
            item["pass"] = len(rows) > 1 and not item["pop_frames"]
        summary[check["name"]] = item
    output.parent.mkdir(parents=True, exist_ok=True)
    if decoded != len(pts):
        raise ValueError(f"frame/timestamp mismatch: {decoded} vs {len(pts)}")
    result = {"video": str(video), "metadata": meta, "decoded_frames": decoded, "timestamps": pts, "summary": summary, "frames": records}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if thumbs:
        columns = min(6, len(thumbs))
        sheet = Image.new("RGB", (240 * columns, 562 * ((len(thumbs) + columns - 1) // columns)), "#171717")
        for i, thumb in enumerate(thumbs):
            sheet.paste(thumb, (i % columns * 240, i // columns * 562))
        sheet.save(output.with_suffix(".png"))
    print(json.dumps({"decoded_frames": decoded, "summary": summary}, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = evaluate(config, args.output)
    raise SystemExit(0 if all(v["pass"] for v in result["summary"].values()) else 1)
