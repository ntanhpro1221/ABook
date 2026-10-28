"""Offscreen review runner; normal priority, isolated desktop, no benchmarks."""
from pathlib import Path
import argparse
import json
import os
import sys

from guarded_process import run_guarded


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--input")
    parser.add_argument("--shots")
    parser.add_argument("--case", action="append", default=[])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    folder = root / "build/layout-review"
    folder.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", CMAKE_BUILD_PARALLEL_LEVEL="2")
    env["PATH"] = r"D:\Novels\native_desk_proto\qt611\6.10.3\msvc2022_64\bin;" + env["PATH"]
    env["ABOOK_GLYPH_AUDIT"] = str(folder / f"{args.label}-glyphs.json")
    if args.shots:
        env["ABOOK_WIDE_SHOTS"] = args.shots
    else:
        env.pop("ABOOK_WIDE_SHOTS", None)
    if args.build:
        source = (root / "build.bat").read_text(encoding="utf-8")
        source = source.replace("set HERE=%~dp0", "set HERE=" + str(root) + "\\")
        bat = folder / f"{args.label}.bat"
        bat.write_bytes(source.replace("\n", "\r\n").encode("utf-8"))
        command = ["cmd.exe", "/d", "/c", str(bat)]
    else:
        command = [str(root / "build/width_tests/WidthTests.exe"), "-o", str(folder / f"{args.label}-test.txt") + ",txt"]
        if args.input:
            command += ["-input", str(root / "tests/width" / args.input)]
        command += args.case
    with (folder / f"{args.label}.log").open("wb") as log:
        result = run_guarded(command, cwd=root, env=env, log=log)
    (folder / f"{args.label}-exit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result), flush=True)
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
