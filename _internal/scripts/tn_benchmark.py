"""Measure Vietnamese text normalization at the two application speech boundaries.

No model, network, audio generation, or Corpus text is needed. Expected strings
are authored independently in tests/fixtures/tn_benchmark/cases.jsonl.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unicodedata

INTERNAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTERNAL))
FIXTURE = INTERNAL / "tests/fixtures/tn_benchmark/cases.jsonl"
BASELINE = FIXTURE.with_name("baseline.json")
CATEGORIES = (
    "cardinal_small", "cardinal_large", "decimal", "ordinal", "roman",
    "date", "time", "range", "percentage", "currency", "unit", "phone_code",
    "abbrev_vi", "abbrev_en", "english", "japanese", "symbol", "url_email",
    "vocalization", "punctuation", "uppercase", "game",
)
PATHS = ("nghe_ngay", "studio")
PROFILE = {
    "engine": "VieNeu", "speaks_english": True, "direct_english": True,
    "origin": "ja for japanese; None otherwise", "book_readings": {},
    "boundary": "text before engine phonemization; no synthesis",
}


def normalize(text: str) -> str:
    """Fold case/whitespace and terminal punctuation, retaining inner syntax."""
    text = " ".join(unicodedata.normalize("NFC", text).casefold().split())
    while text and unicodedata.category(text[-1]).startswith("P"):
        text = text[:-1].rstrip()
    return text


def load_cases(path: Path = FIXTURE) -> list[dict]:
    cases = []
    seen = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        case = json.loads(line)
        if set(case) != {"id", "category", "text", "expected", "note"}:
            raise ValueError(f"line {number}: incorrect fields")
        if not all(isinstance(case[key], str) and case[key].strip()
                   for key in ("id", "category", "text", "note")):
            raise ValueError(f"line {number}: empty or non-string field")
        expected = case["expected"]
        answers = [expected] if isinstance(expected, str) else expected
        if not isinstance(answers, list) or not answers or not all(isinstance(x, str) and normalize(x) for x in answers):
            raise ValueError(f"line {number}: invalid expected strings")
        if case["id"] in seen or case["category"] not in CATEGORIES:
            raise ValueError(f"line {number}: duplicate id or unknown category")
        seen.add(case["id"])
        cases.append(case)
    counts = Counter(case["category"] for case in cases)
    if len(cases) < 400 or any(counts[category] < 20 for category in CATEGORIES):
        raise ValueError("Need >=400 cases and >=20 per category")
    if len({case["text"] for case in cases}) != len(cases):
        raise ValueError("Duplicate input text")
    return cases


class SpeechBoundaries:
    """Use production entry points with empty book dictionaries and fixed origins."""

    def __enter__(self):
        from abook.config import build_settings
        from abook.database import ProjectDB
        from abook.tts import TTSCoordinator

        self.temp = tempfile.TemporaryDirectory(prefix="tn-benchmark-")
        self.coordinators = {}
        for origin in (None, "ja"):
            db = ProjectDB(Path(self.temp.name) / f"{origin}.sqlite3")
            coordinator = TTSCoordinator(build_settings(), db, lambda _message: None)
            # These are book-context caches, not replacements for TN functions.
            # Fix the origin explicitly so detection on a short test sentence
            # cannot change the normalization target between cases.
            coordinator._book_origin = (origin,)
            coordinator._book_names = {}
            coordinator._shared_rulings = (None,)
            self.coordinators[origin] = coordinator
        return self

    def __exit__(self, *_exc):
        self.coordinators.clear()
        self.temp.cleanup()

    def read(self, case: dict) -> dict[str, str]:
        from abook.readaloud.vieneu import MAX_CHARS, units

        origin = "ja" if case["category"] == "japanese" else None
        _tokens, parts = units(case["text"], MAX_CHARS["turbo"], origin, True, {}, direct_english=True)
        instant = " ".join(piece for part in parts for piece in part.pieces)
        studio = self.coordinators[origin].spoken_text({"text": case["text"]})
        return {"nghe_ngay": instant, "studio": studio}


def evaluate(cases: list[dict]) -> dict:
    from abook.quality_policy import quality_implementation_hash

    counts = {category: {path: {"correct": 0, "total": 0} for path in PATHS} for category in CATEGORIES}
    failures = []
    results = []
    with SpeechBoundaries() as boundaries:
        for case in cases:
            expected = case["expected"]
            accepted = {normalize(x) for x in ([expected] if isinstance(expected, str) else expected)}
            got = boundaries.read(case)  # Exceptions must fail the run, not become wrong answers.
            passed = {}
            for path in PATHS:
                passed[path] = normalize(got[path]) in accepted
                cell = counts[case["category"]][path]
                cell["total"] += 1
                cell["correct"] += int(passed[path])
                if not passed[path]:
                    failures.append({**case, "path": path, "got": got[path]})
            results.append({"id": case["id"], "category": case["category"], "got": got, "passed": passed})
    for cells in counts.values():
        for cell in cells.values():
            cell["percent"] = round(100 * cell["correct"] / cell["total"], 2)
    return {"schema_version": 1, "profile": PROFILE, "case_count": len(cases),
            "cases_sha256": hashlib.sha256(json.dumps(cases, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            "quality_implementation_hash": quality_implementation_hash(), "categories": counts,
            "overall": {path: {"correct": sum(c[path]["correct"] for c in counts.values()), "total": len(cases),
                               "percent": round(100 * sum(c[path]["correct"] for c in counts.values()) / len(cases), 2)}
                        for path in PATHS},
            "failures": failures, "results": results}


def baseline_of(report: dict) -> dict:
    return {key: report[key] for key in ("schema_version", "profile", "case_count", "cases_sha256",
                                       "quality_implementation_hash", "categories", "overall")}


def check_floor(report: dict, baseline: dict) -> None:
    """Compare integer numerators; there is zero permitted drop per category."""
    for key in ("case_count", "cases_sha256", "profile"):
        if report[key] != baseline[key]:
            raise ValueError(f"Benchmark definition changed: {key}; review and remeasure explicitly")
    for category in CATEGORIES:
        for path in PATHS:
            cell, floor = report["categories"][category][path], baseline["categories"][category][path]
            if cell["total"] != floor["total"] or cell["correct"] < floor["correct"]:
                raise ValueError(f"Score below committed floor: {category}/{path}: {cell} < {floor}")


def markdown(report: dict) -> str:
    lines = ["# TN benchmark", "", "Text before engine phonemization; no audio accuracy claim.", "",
             "| Category | N | Nghe ngay | Studio |", "|---|---:|---:|---:|"]
    for category, cells in report["categories"].items():
        lines.append(f"| {category} | {cells['studio']['total']} | {cells['nghe_ngay']['percent']:.2f}% | {cells['studio']['percent']:.2f}% |")
    lines += [f"| **Overall** | {report['case_count']} | {report['overall']['nghe_ngay']['percent']:.2f}% | {report['overall']['studio']['percent']:.2f}% |", "", "## Mismatches", ""]
    for failure in report["failures"]:
        lines += [f"### {failure['id']} / {failure['path']}", "",
                  "```json", json.dumps({key: failure[key] for key in ("text", "expected", "got", "note")}, ensure_ascii=False), "```", ""]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=FIXTURE)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-baseline", type=Path)
    args = parser.parse_args(argv)
    report = evaluate(load_cases(args.cases))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "report.md").write_text(markdown(report), encoding="utf-8")
    if args.check_baseline:
        check_floor(report, json.loads(args.check_baseline.read_text(encoding="utf-8")))
    print(json.dumps({"case_count": report["case_count"], "overall": report["overall"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
