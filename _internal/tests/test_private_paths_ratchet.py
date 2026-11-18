"""The public repo must not gain files that name the owner's own folders (drive letter + the projects folder).

left174: 151 tracked files carried such a path (139 with the forward-slash spelling: build scripts, probes, docs, test
fixtures); 145 after the Qt build files took theirs from ABOOK_TOOLS_ROOT. The list in
tests/fixtures/private_paths_files.json is a ratchet: a file not on it may never gain such a path, and a file that
loses its last one must leave the list in the same change, so the count only goes down. A new tool takes its
paths from an environment variable or an argument (score_voice_pool.py: --projects / ABOOK_VOICE_POOL_PROJECTS;
desktop_qt/build.bat and tools/qt_sdk.py: ABOOK_TOOLS_ROOT, default the folder holding the checkout).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
FIXTURE = ROOT / "tests/fixtures/private_paths_files.json"
# Drive letter, colon, slash(es) or backslash(es), then the projects folder name - written so this file never matches itself.
FOLDER = "N" + "ovels"
PATTERN = r"[A-Za-z]:[\\/]+" + FOLDER


def tracked_with_private_path() -> list[str]:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not available")
    done = subprocess.run([git, "-C", str(REPO), "grep", "-l", "-I", "-i", "-E", PATTERN, "--", "."],
                          capture_output=True, text=True, encoding="utf-8")
    if done.returncode not in (0, 1):
        pytest.skip(f"git grep failed: {done.stderr.strip()}")
    return sorted(line.strip().replace("\\", "/") for line in done.stdout.splitlines() if line.strip())


def test_pattern_sees_both_slash_styles_and_any_case():
    regex = re.compile(PATTERN, re.I)
    for text in ("D:/" + FOLDER + "/ABook", "d:\\" + FOLDER.lower() + "\\x", "D:\\\\" + FOLDER + "\\\\qt"):
        assert regex.search(text), text
    assert not regex.search("<ABOOK_TOOLS_ROOT>/native_desk_proto/qt611")


def test_no_new_file_names_a_private_folder():
    allowed = set(json.loads(FIXTURE.read_text(encoding="utf-8"))["files"])
    current = tracked_with_private_path()
    added = [path for path in current if path not in allowed]
    assert not added, ("these tracked files name a private folder; use an environment variable or an argument instead: "
                       + ", ".join(added))
    fixed = sorted(allowed - set(current))
    assert not fixed, ("these files no longer name a private folder; remove them from "
                       f"{FIXTURE.relative_to(ROOT).as_posix()} so the ratchet tightens: " + ", ".join(fixed))


def test_fixture_is_sorted_and_counted():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["files"] == sorted(set(data["files"]))
    assert data["count"] == len(data["files"])
