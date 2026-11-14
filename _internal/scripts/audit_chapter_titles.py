"""Report proposed display-name changes. Never edit a project or a package.

Use --projects for source projects, --packages for .abook roots and --libraries
for a library containing projects, .abook files or extracted package folders.
All report output goes to stdout; redirect it outside the repository.
"""
from __future__ import annotations

import argparse
import codecs
import contextlib
import fnmatch
import json
import os
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from abook import book_paths
from abook.chapter_titles import chapter_name, fallback_positions, first_heading, full_name, read_opening
from abook.webui import store
from abook.webui.peer_paths import safe_relative

_PREVIOUS_HEADING = re.compile(
    r"^\s*((?:chương|chapter|hồi|quyển|phần|tiết)\s*[\dIVXLC]+)\s*(?:[-:–—.·|]+\s*(.*?))?\s*$", re.I)
_ORDER = re.compile(r"^\s*0\d*(?:\s*[-_.:]+\s*|\s+)(\S.*)$")


def previous_name(stored: str, first: str) -> str:
    match = _PREVIOUS_HEADING.fullmatch(first) if len(first) <= 160 else None
    if match:
        name = match[1].strip()
        return full_name((name[:1].upper() + name[1:], (match[2] or "").strip()))
    if stored.strip().isdecimal():
        return f"Chương {int(stored)}"
    order = _ORDER.fullmatch(stored)
    return order[1].strip() if order else stored.strip()


def change(chapter: int, index: int, before: str, after: str) -> dict:
    return {"chapterId": chapter, "index": index, "before": before, "after": after}


def project(path: Path) -> dict:
    root = path.parent
    result = {"kind": "project", "path": str(root), "changes": [], "unreadableSources": []}
    with contextlib.closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        headings = {int(row["chapter_id"]): str(row["text"] or "") for row in db.execute(
            "SELECT chapter_id,text,MIN(seq) FROM segments GROUP BY chapter_id")}
        edits = store.chapter_title_overrides(root)
        current = store.chapter_names(db, root)
        columns = {row[1] for row in db.execute("PRAGMA table_info(chapters)")}
        rows = db.execute("SELECT * FROM chapters ORDER BY chapter_index").fetchall()
        for row in rows:
            cid, index = int(row["id"]), int(row["chapter_index"])
            source = book_paths.safe_source(root, row["input_path"]) if "input_path" in columns else None
            opening = read_opening(source)
            if not opening:
                result["unreadableSources"].append(cid)
            first = next((line.strip() for line in opening.splitlines() if line.strip()), "")
            old = previous_name(str(row["title"]), headings.get(cid, first))
            edit = edits.get(cid)
            old_parts = (old, "")
            # Apply overrides separately to preserve subtitle-only and title-only edits.
            old_match = _PREVIOUS_HEADING.fullmatch(headings.get(cid, first))
            if old_match:
                name = old_match[1].strip()
                old_parts = (name[:1].upper() + name[1:], (old_match[2] or "").strip())
            before = full_name(store.apply_chapter_title(*old_parts, edit))
            after = current[cid]["full"]
            if before != after:
                result["changes"].append(change(cid, index, before, after))
    return result


def bounded_json(archive: zipfile.ZipFile, member: str):
    info = archive.getinfo(member)
    if info.file_size > 32 * 1024 * 1024:
        raise ValueError(f"oversized metadata: {member}")
    return json.loads(archive.read(info))


def manifest_changes(book: dict, edits: dict, json_read, opening_read, result: dict) -> dict:
    """The same comparison for archives and extracted library folders."""
    result["title"] = book.get("title", "")
    chapter_edits = edits.get("chapters", {}) if isinstance(edits, dict) else {}
    chapters = book.get("chapters", [])
    positions = fallback_positions([str(chapter.get("title", "")) for chapter in chapters])
    for position, (fallback, chapter) in enumerate(zip(positions, chapters), 1):
        cid, index = int(chapter["id"]), int(chapter.get("index", position))
        before = chapter.get("fullTitle") or full_name((chapter.get("title", ""), chapter.get("subtitle", "")))
        edit = chapter_edits.get(str(cid))
        if edit:
            before = full_name(store.apply_chapter_title(str(chapter.get("title", "")), str(chapter.get("subtitle", "")), edit))
        opening = ""
        if chapter.get("script"):
            script = json_read(chapter["script"])
            opening = next((str(segment.get("text", "")) for segment in script.get("segments", []) if segment.get("text")), "")
        elif chapter.get("text"):
            opening = opening_read(chapter["text"])
        if not opening:
            result["missingOpenings"].append(cid)
        proposed = chapter_name(chapter.get("title", ""), opening, index=index if fallback is not None else None)
        if not first_heading(opening):
            proposed = (proposed[0], chapter.get("subtitle", ""))
        after = full_name(store.apply_chapter_title(*proposed, edit))
        if before != after:
            result["changes"].append(change(cid, index, before, after))
    return result


def package(path: Path) -> dict:
    result = {"kind": "package", "path": str(path), "changes": [], "missingOpenings": [],
              "note": "Unmarked standalone titles require source projects; scripts supply explicit headings only."}
    with zipfile.ZipFile(path) as archive:
        book = bounded_json(archive, "book.json")
        edits = bounded_json(archive, "edits.json") if "edits.json" in archive.namelist() else {}

        def opening_read(member):
            with archive.open(member) as handle:
                return codecs.getincrementaldecoder("utf-8")().decode(handle.read(8192), final=False)

        return manifest_changes(book, edits, lambda member: bounded_json(archive, member), opening_read, result)


def installed(path: Path) -> dict:
    """Inspect an extracted package without loading or modifying its library state."""
    root = path.parent

    def read(member: str, opening: bool = False) -> bytes:
        if not safe_relative(member):
            raise ValueError("unsafe package member")
        source = book_paths.inside(root, root / member)
        with source.open("rb") as handle:
            raw = handle.read(8192 if opening else 32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024:
            raise ValueError("oversized package metadata")
        return raw

    book = json.loads(read("book.json"))
    if not isinstance(book, dict) or "package" not in book:
        raise ValueError("not an extracted book package")
    result = {"kind": "installed", "path": str(root), "title": book.get("title", ""),
              "changes": [], "missingOpenings": []}
    edits = json.loads(read("edits.json")) if (root / "edits.json").is_file() else {}
    return manifest_changes(book, edits, lambda member: json.loads(read(member)),
                            lambda member: codecs.getincrementaldecoder("utf-8")().decode(read(member, opening=True), final=False), result)


def walk(root: Path, pattern: str, errors: list) -> list[Path]:
    """Like rglob, but a folder that vanishes or is locked mid-scan (a running job) is reported, not fatal."""
    found = []
    for folder, _, files in os.walk(root, onerror=lambda error: errors.append({"path": error.filename, "error": error.strerror})):
        found += [Path(folder) / name for name in files if fnmatch.fnmatch(name, pattern)]
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects", type=Path, action="append", default=[])
    parser.add_argument("--packages", type=Path, action="append", default=[])
    parser.add_argument("--libraries", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, help="write JSON here; diagnostic logging stays separate")
    args = parser.parse_args()
    results, errors, visited = [], [], set()
    for roots, pattern, inspect in ((args.projects + args.libraries, "project.sqlite3", project),
                                    (args.packages + args.libraries, "*.abook", package),
                                    (args.libraries, "book.json", installed)):
        for root in roots:
            if not root.exists():
                errors.append({"path": str(root), "error": "root does not exist"})
                continue
            paths = [root] if root.is_file() else walk(root, pattern, errors)
            for path in paths:
                path = path.resolve()
                if path in visited:
                    continue
                visited.add(path)
                try:
                    results.append(inspect(path))
                except (OSError, ValueError, KeyError, sqlite3.Error, zipfile.BadZipFile) as error:
                    errors.append({"path": str(path), "error": str(error)})
    report = json.dumps({"readOnly": True, "booksScanned": len(results), "booksChanged": sum(bool(book["changes"]) for book in results),
                         "chaptersChanged": sum(len(book["changes"]) for book in results), "books": results, "errors": errors}, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
