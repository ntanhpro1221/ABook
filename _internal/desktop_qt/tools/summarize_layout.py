"""Collect every rendered-geometry hit and verify the exported PNG matrix."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--shots", type=Path)
    parser.add_argument("--allow-hits", action="store_true")
    args = parser.parse_args()
    scenes, failures = [], []
    for path in args.logs:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "LAYOUT_AUDIT " in line:
                scenes.append(json.loads(line.split("LAYOUT_AUDIT ", 1)[1]))
            if "FAIL!" in line:
                failures.append(line)
    if not scenes:
        raise RuntimeError("No layout scenes found")
    names = [row["scene"] for row in scenes]
    if len(names) != len(set(names)):
        raise RuntimeError("Duplicate scene names")
    hits = [dict(scene=row["scene"], **hit) for row in scenes for hit in row["hits"]]
    shots = []
    if args.shots:
        for scene in names:
            width = int(scene.rsplit("_", 1)[1])
            if width == 1440:
                continue
            path = args.shots / ((scene if scene.startswith("parity_") else "layout_" + scene) + ".png")
            expected = (width, 900 if width == 1024 else 1080)
            with Image.open(path) as image:
                image.load()
                if image.size != expected:
                    raise RuntimeError(f"{path}: {image.size} != {expected}")
            shots.append(dict(file=path.name, width=expected[0], height=expected[1],
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        (args.shots / "layout_manifest.json").write_text(
            json.dumps(shots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    result = dict(logs=[str(p) for p in args.logs], scene_count=len(scenes),
                  hit_count=len(hits), rules=dict(Counter(hit["rule"] for hit in hits)),
                  hits=hits, failures=failures, scenes=scenes, screenshots=shots)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"{len(scenes)} scenes, {len(hits)} hits, {len(failures)} test failures, {len(shots)} verified PNGs")
    return int(bool(hits or failures) and not args.allow_hits)


if __name__ == "__main__":
    raise SystemExit(main())
