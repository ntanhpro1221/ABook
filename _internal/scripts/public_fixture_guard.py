"""Audit public fixtures without echoing potentially private values."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

REPO = Path(__file__).resolve().parents[2]
EXCEPTIONS = Path(__file__).with_name("public_fixture_exceptions.json")
CONTEXT = re.compile(r"sentence|source_text|^(?:words|vietnamese_names)$|(?:source|sent)_sha256", re.I)
IPA = re.compile(r"[ˈˌɜɯɗɲŋəɛɔ]")


def violations(value, location="$", *, field="") -> list[str]:
    result = []
    if isinstance(value, dict):
        for key, child in value.items():
            if CONTEXT.search(key):
                result.append(f"{location}.{key}: sentence/context field")
            result.extend(violations(child, f"{location}.{key}", field=key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(violations(child, f"{location}[{index}]", field=field))
        # Splitting a sentence into an array must not bypass the limit.
        if value and all(isinstance(v, str) for v in value) and field == "syllables":
            result.extend(violations(" ".join(value), location, field=field))
    elif isinstance(value, str):
        run = 0
        for word in re.split(r"\s+|(?<=[a-zà-ỹ])-(?=[a-zà-ỹ])", value):
            phonetic = bool(IPA.search(word))
            if field in {"syllables", "transliteration", "romanization"}:
                phonetic = bool(re.search(r"\w", word))
            run = run + 1 if phonetic else 0
            if run >= 8:
                result.append(f"{location}: at least 8 consecutive phonetic syllables")
                break
    return result


def inspect_file(path: Path) -> list[str]:
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return []  # Audio/images have no text fields; never deserialize executable formats.
    try:
        return violations(json.loads(content))
    except ValueError:
        # Check non-JSON fixtures too, including escaped JSON in text snapshots.
        findings = violations(content)
        if re.search(r'["\'](?:sentence\w*|source_text|words|vietnamese_names|(?:source|sent)_sha256)["\']\s*:', content, re.I):
            findings.append("$: sentence/context field in text fixture")
        return findings


def fixture_paths(repo=REPO):
    names = subprocess.check_output(["git", "-C", str(repo), "ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    for name in sorted(set(names.decode("utf8").split("\0"))):
        path = Path(name)
        if any(part.lower() in {"fixtures", "fixture", "data", "testdata"} for part in path.parts) and (repo / path).is_file():
            yield path


def audit(repo=REPO):
    allowed = json.loads(EXCEPTIONS.read_text("utf8"))
    failures = []
    for relative in fixture_paths(repo):
        path = repo / relative
        found = inspect_file(path)
        if not found:
            continue
        entry = allowed.get(relative.as_posix())
        digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        # Never exempt the new public G2P data, regardless of manifest contents.
        if "_internal/tests/data" not in relative.as_posix() and entry and entry["sha256"] == digest:
            print(f"Reviewed fixture exception: {relative.as_posix()} ({entry['reason']})")
            continue
        failures.extend(f"{relative.as_posix()} {item}" for item in found)
    return failures


if __name__ == "__main__":
    errors = audit()
    print("\n".join(errors) if errors else "Public fixture privacy audit passed")
    raise SystemExit(bool(errors))
