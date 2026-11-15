"""Inventory UI data-loss and asynchronous entry points. Unreviewed additions fail closed.

The review file records the exact statement, its guard and its consequence. This is a
source regression gate, not a claim that text matching proves runtime safety.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "scripts/ui_actions_reviewed.json"
SURFACES = (ROOT / "ui/src", ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui", ROOT / "desktop_qt/qml")
LOSS = re.compile(r"\b(?:delete\w*|remove(?!EventListener|Listener)\w*|forget\w*|unpair\w*|revoke\w*|discard\w*|clearLogs|clearCache|resetAudioFx|unsave)\s*\(|\b(?:remove\w*|unsave)\.mutate(?:Async)?\s*\(|method:\s*[\"']DELETE[\"']|(?:Api\.(?:call|quiet)|request)\([\"']DELETE[\"']")
ASYNC = re.compile(r"\b(?:async\s+function|suspend\s+fun|async\s*\(|scope\.launch\s*\{|(?:Api\.(?:call|quiet)|store\.request)\()|on(?:Click|Activated|CheckedChange|Select)\s*[=:].*\b(?:async|await|void)\b")


def inventory(text: str, path: str) -> list[dict]:
    found = []
    occurrences: dict[tuple[str, str], int] = {}
    for line, raw in enumerate(text.splitlines(), 1):
        statement = raw.strip()
        if not statement or statement.startswith(("//", "*", "/*", "import ")):
            continue
        # Function declarations describe a boundary, not an action that executes it.
        loss = LOSS.search(statement) and not re.search(r"\b(?:fun|function)\s+(?:delete|remove|forget|unpair|revoke)\w*\s*\(", statement)
        for kind, applies in (("destructive", loss), ("pending", ASYNC.search(statement))):
            if not applies:
                continue
            key = (kind, statement)
            occurrence = occurrences[key] = occurrences.get(key, 0) + 1
            identity = hashlib.sha256(f"{path}\0{kind}\0{statement}\0{occurrence}".encode()).hexdigest()[:20]
            found.append(dict(id=identity, kind=kind, path=path, line=line, statement=statement, occurrence=occurrence))
    return found


def scan(root: Path = ROOT) -> list[dict]:
    result = []
    for surface in SURFACES:
        local = root / surface.relative_to(ROOT)
        for path in sorted(local.rglob("*")):
            if path.suffix not in (".tsx", ".kt", ".qml", ".ts", ".js") or ".test." in path.name or "gallery" in path.parts or "generated" in path.name:
                continue
            result.extend(inventory(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix()))
    return result


def icon_findings(root: Path = ROOT) -> list[str]:
    found = []
    for path in (root / "mobile/android/app/src/main/java/vn/abook/player/ui").rglob("*.kt"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"SwapContent\(([^\n]+)\)\s*\{\s*(\w+)\s*->", text):
            arguments, value = match.group(1), match.group(2)
            body = text[match.end():match.end() + 240]
            icon_only = re.match(r"\s*(?:if\s*\([^\n]+\)\s*)?(?:\w*Icon|\w*Glyph)\(", body)
            if icon_only and "inPlace = true" not in arguments:
                found.append(f"{path.relative_to(root)}: icon uses the translating SwapContent default; use StateIcon or inPlace")
        # Sliding a page is intentional. A status icon is explicitly in-place.
        for match in re.finditer(r"(?:fun\s+(?:StateIcon|PlayPauseGlyph)|AnimatedContent\s*\((?=[\s\S]{0,400}(?:targetState\s*=\s*\w*(?:[Ii]con|[Gg]lyph)|label\s*=\s*\"[^\"]*(?:icon|glyph)))[\s\S]{0,40}|label\s*=\s*\"[^\"]*(?:state-icon|status-icon)[^\"]*\")", text):
            part = text[match.start():match.start() + 1600]
            if re.search(r"slide(?:In|Out)(?:Horizontally|Vertically)", part):
                found.append(f"{path.relative_to(root)}: status icon contains a slide transition")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args()
    current = scan()
    if args.inventory:
        args.inventory.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{len(current)} UI statements inventoried")
        return 0
    reviews = json.loads(REVIEW.read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in reviews}
    problems = icon_findings()
    source_hashes: dict[str, str] = {}
    for item in current:
        review = by_id.get(item["id"])
        if item["path"] not in source_hashes:
            source_hashes[item["path"]] = hashlib.sha256((ROOT / item["path"]).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        source_hash = source_hashes[item["path"]]
        allowed = ("confirmation", "undo", "internal") if item["kind"] == "destructive" else ("pending", "internal", "read-only")
        if not review or review.get("source_sha256") != source_hash or review.get("path") != item["path"] or review.get("kind") != item["kind"] or review.get("disposition") not in allowed or not review.get("guard", "").strip() or not review.get("reason", "").strip():
            problems.append(f"{item['path']}:{item['line']}: unreviewed {item['kind']}: {item['statement']}")
    for problem in problems:
        print(problem)
    print(f"UI action review: {len(current)} statements, {len(problems)} unreviewed/invalid")
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
