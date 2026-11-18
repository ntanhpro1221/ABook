"""The public repo must not gain lines that name the owner's machine: their projects folder, a user profile folder, the
computer's name or a LAN address.

left174: 151 tracked files carried a projects-folder path (139 with the forward-slash spelling: build scripts, probes, docs,
test fixtures); 145 after the Qt build files took theirs from ABOOK_TOOLS_ROOT. leftfix (review L8) widened the ratchet:

- four kinds of private reference: the projects folder on any drive, `<drive>:\\Users\\<name>` (a real profile, not a
  placeholder), the computer's own name (read at test time, never written here) and RFC 1918 LAN addresses;
- counted per file and per kind (lines that match), so a file already on the list cannot gain a new private line.

tests/fixtures/private_paths_files.json is the ratchet: a count may only go down, a file or kind not listed may never
appear, and a count that drops must be lowered in the same change. A new tool takes its paths from an environment
variable or an argument (score_voice_pool.py: --projects / ABOOK_VOICE_POOL_PROJECTS; desktop_qt/build.bat,
CMakeLists.txt and tools/qt_sdk.py: ABOOK_TOOLS_ROOT / ABOOK_PYTHON, default relative to the checkout).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
FIXTURE = ROOT / "tests/fixtures/private_paths_files.json"
# Written in pieces so this file never matches itself.
FOLDER = "N" + "ovels"
KINDS = {
    # Drive letter, colon, slash(es) or backslash(es), then the projects folder name.
    "folder": r"[A-Za-z]:[\\/]+" + FOLDER,
    # A real user profile folder; placeholders (<user>, %USERNAME%, $env:USERNAME, Public, Default) are fine.
    "users": r"[A-Za-z]:[\\/]+U" + r"sers[\\/]+[^\\/ \"'<>%$*{}]+",
    # RFC 1918 addresses: the owner's LAN. Documentation ranges (192.0.2.x, 198.51.100.x, 203.0.113.x) are the public examples to use.
    # POSIX ERE (git grep -E): plain groups, no (?:...).
    "lan": r"\b(192\.168|10\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01]))\.[0-9]{1,3}\.[0-9]{1,3}\b",
}
PLACEHOLDER_USERS = re.compile(r"[\\/](?:Public|Default|All Users|runneradmin)\b", re.I)


def machine_names() -> list[str]:
    """This computer's names, read now (never stored in the repo); generic names are skipped."""
    names = {socket.gethostname(), os.environ.get("COMPUTERNAME", "")}
    return sorted(name for name in names if len(name) >= 4 and name.lower() not in {"localhost", "runner", "build"})


def git_counts(args: list[str]) -> dict[str, int]:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not available")
    done = subprocess.run([git, "-C", str(REPO), "grep", "-c", "-I", *args, "--", "."], capture_output=True, text=True, encoding="utf-8")
    if done.returncode not in (0, 1):
        pytest.skip(f"git grep failed: {done.stderr.strip()}")
    counts = {}
    for line in done.stdout.splitlines():
        path, _, count = line.rpartition(":")
        if path:
            counts[path.replace("\\", "/")] = int(count)
    return counts


def users_counts() -> dict[str, int]:
    """Lines naming a real profile folder (placeholder profiles dropped line by line)."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not available")
    done = subprocess.run([git, "-C", str(REPO), "grep", "-n", "-I", "-i", "-E", KINDS["users"], "--", "."], capture_output=True, text=True, encoding="utf-8")
    counts: dict[str, int] = {}
    regex = re.compile(KINDS["users"], re.I)
    for line in done.stdout.splitlines():
        path, _, rest = line.partition(":")
        text = rest.partition(":")[2]
        if any(not PLACEHOLDER_USERS.search(hit.group(0)) for hit in regex.finditer(text)):
            counts[path.replace("\\", "/")] = counts.get(path.replace("\\", "/"), 0) + 1
    return counts


def current_private_lines() -> dict[str, dict[str, int]]:
    found: dict[str, dict[str, int]] = {}
    per_kind = {
        "folder": git_counts(["-i", "-E", KINDS["folder"]]),
        "users": users_counts(),
        "lan": git_counts(["-E", KINDS["lan"]]),
    }
    host: dict[str, int] = {}
    for name in machine_names():
        for path, count in git_counts(["-i", "-F", "-w", name]).items():
            host[path] = host.get(path, 0) + count
    per_kind["host"] = host
    for kind, counts in per_kind.items():
        for path, count in counts.items():
            found.setdefault(path, {})[kind] = count
    return found


def test_patterns_see_each_kind_and_skip_placeholders():
    folder = re.compile(KINDS["folder"], re.I)
    for text in ("D:/" + FOLDER + "/ABook", "d:\\" + FOLDER.lower() + "\\x", "D:\\\\" + FOLDER + "\\\\qt"):
        assert folder.search(text), text
    assert not folder.search("<ABOOK_TOOLS_ROOT>/native_desk_proto/qt611")
    users = re.compile(KINDS["users"], re.I)
    assert users.search("C:\\" + "Users\\someone\\AppData\\Local")
    assert users.search("c:/" + "users/someone/x")
    for placeholder in ("C:\\" + "Users\\<user>\\x", "C:\\" + "Users\\%USERNAME%\\x", "C:\\" + "Users\\$env:USERNAME"):
        assert not users.search(placeholder), placeholder
    assert PLACEHOLDER_USERS.search("C:\\" + "Users\\Public\\Documents")
    lan = re.compile(KINDS["lan"])
    for text in ("http://192.168.1.20:8765", "10.0.0.7", "172.20.3.4"):
        assert lan.search(text), text
    for text in ("192.0.2.10", "203.0.113.5", "172.32.0.1", "8.8.8.8"):
        assert not lan.search(text), text


def test_no_file_gains_a_private_line():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    allowed: dict[str, dict[str, int]] = data["files"]
    current = current_private_lines()
    grown = [f"{path} {kind} {count} > {allowed.get(path, {}).get(kind, 0)}"
             for path, kinds in sorted(current.items()) for kind, count in kinds.items() if count > allowed.get(path, {}).get(kind, 0)]
    assert not grown, ("these tracked files gained a line naming the owner's machine (folder, profile, computer name or LAN address); "
                       "use an environment variable, an argument or a documentation address instead: " + ", ".join(grown))
    shrunk = [f"{path} {kind} {count} < {current.get(path, {}).get(kind, 0)}"
              for path, kinds in sorted(allowed.items()) for kind, count in kinds.items() if current.get(path, {}).get(kind, 0) < count]
    assert not shrunk, (f"these counts went down; lower them in {FIXTURE.relative_to(ROOT).as_posix()} so the ratchet tightens: "
                        + ", ".join(shrunk))


def test_fixture_is_sorted_and_counted():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert list(data["files"]) == sorted(data["files"])
    assert data["count"] == sum(sum(kinds.values()) for kinds in data["files"].values())
    assert all(kinds and all(kind in {*KINDS, "host"} and count > 0 for kind, count in kinds.items()) for kinds in data["files"].values())
    # The computer's own name is read at test time and must never be stored, not even as a fixture key.
    assert not any("host" in kinds for kinds in data["files"].values()) or machine_names()
