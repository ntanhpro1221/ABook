"""Capture actual QML screens with fixture HTTP/audio, isolated desktop and focus guard."""
import argparse
import json
import os
from pathlib import Path

from hidden_suite import wait_for_machine
from guarded_process import run_guarded

ROOT = Path(__file__).resolve().parents[1]


def run(folder, tests, capture=True, probe=False, expected_images=72):
    folder.mkdir(parents=True, exist_ok=True)
    waited = wait_for_machine()
    qt = Path("D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64")
    if not (qt / "plugins/platforms/qoffscreen.dll").is_file():
        raise RuntimeError("Offscreen plugin missing")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_SCALE_FACTOR="1",
               QT_QPA_PLATFORM_PLUGIN_PATH=str(qt / "plugins/platforms"), ABOOK_WIDE_SHOTS=str(folder) if capture else "",
               PATH=str(qt / "bin") + os.pathsep + os.environ["PATH"])
    env["ABOOK_GLYPH_AUDIT"] = str(folder / "glyph-audit.json")
    if probe:
        env["ABOOK_GLYPH_PROBE"] = "1"
    with (folder / "runner.log").open("wb") as log:
        result = run_guarded([str(ROOT / "build/width_tests/WidthTests.exe"),
                              *([] if tests == ["all"] else tests),
                              "-o", str(folder / "tests.txt") + ",txt"],
                             cwd=ROOT, env=env, log=log)
    code = result["exit_code"]
    images = sorted(folder.glob("*.png"))
    from PIL import Image
    dimensions = {f.name: list(Image.open(f).size) for f in images}
    glyphs = json.loads((folder / "glyph-audit.json").read_text(encoding="utf-8"))
    result.update(wait=waited, backend="software", dimensions=dimensions,
                  glyph_hits=glyphs["hit_count"], text_observations=glyphs["text_observations"])
    (folder / "audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in result.items() if k != "dimensions"}), flush=True)
    if probe:
        if code != 1 or glyphs["hit_count"] != 1 or glyphs["hits"][0]["codepoint"] != "U+10FFFF":
            raise RuntimeError("Glyph negative control did not reject the missing character")
        return
    if code or glyphs["hit_count"] or (capture and len(images) != expected_images):
        raise RuntimeError(f"Validation failed: exit={code}, glyphs={glyphs['hit_count']}, images={len(images)}")
    for filename, size in dimensions.items():
        if size != [int(Path(filename).stem.rsplit("_", 1)[1]), 900]:
            raise RuntimeError(f"Wrong image dimensions: {filename}: {size}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--tests", nargs="+", default=["WideScreens::test_screens"])
    parser.add_argument("--no-capture", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--expected-images", type=int, default=72)
    args = parser.parse_args()
    run(args.folder.resolve(), args.tests, not args.no_capture, args.probe, args.expected_images)
