"""Measure Vietnamese text normalization at the two application speech boundaries.

No model, network, audio generation, or Corpus text is needed. Expected strings
are authored independently in tests/fixtures/tn_benchmark/cases.jsonl.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
import re
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
STAGES = ("string", "post_g2p")
PROFILE = {
    "engine": "VieNeu", "speaks_english": True, "direct_english": True,
    "origin": "ja for japanese; None otherwise", "book_readings": {},
    "boundary": "text and production VieNeu phonemes; no synthesis",
    "string_comparison": "NFC, casefold, hyphens as spaces, whitespace, terminal punctuation",
    "phoneme_comparison": "NFC, no punctuation, word separators or whitespace; preserve IPA stress, tone and emotion tokens",
}


def normalize(text: str) -> str:
    """Fold case, hyphens, whitespace and terminal punctuation."""
    text = unicodedata.normalize("NFC", text).casefold()
    text = " ".join("".join(" " if ch in "-‐‑" else ch for ch in text).split())
    while text and unicodedata.category(text[-1]).startswith("P"):
        text = text[:-1].rstrip()
    return text


def normalize_phonemes(text: str) -> str:
    """Keep phonetic distinctions and cue identity while ignoring separators."""
    parts = re.split(r"(<\|emotion_\d+\|>)", unicodedata.normalize("NFC", text))
    return "".join(part if re.fullmatch(r"<\|emotion_\d+\|>", part) else
                   "".join(ch for ch in part if not ch.isspace() and
                           not unicodedata.category(ch).startswith("P") and ch not in "|‿")
                   for part in parts)


def studio_phonemes(text: str, source: str) -> str:
    from abook.readaloud.phoneme_policy import sentence_case
    from abook.tts import keep_vieneu_final_mark
    from vieneu_utils.phonemize_text import normalize_to_chunks_v3_with_gaps, phonemize_text_with_emotions

    keep_vieneu_final_mark()
    with sentence_case(text, source):
        chunks, _gaps = normalize_to_chunks_v3_with_gaps(text, max_chars=256)
        return " ".join(phonemize_text_with_emotions(chunk) for chunk in chunks)


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

    def read(self, case: dict) -> tuple[dict[str, str], dict[str, str]]:
        from abook.readaloud.vieneu import MAX_CHARS, units
        from abook.readaloud.vieneu_engine import phonemize

        origin = "ja" if case["category"] == "japanese" else None
        tokens, parts = units(case["text"], MAX_CHARS["turbo"], origin, True, {}, direct_english=True)
        instant = " ".join(piece for part in parts for piece in part.pieces)
        studio = self.coordinators[origin].spoken_text({"text": case["text"]})
        return ({"nghe_ngay": instant, "studio": studio},
                {"nghe_ngay": " ".join(phonemize(part.pieces, source=part.text(tokens)) for part in parts),
                 "studio": studio_phonemes(studio, case["text"])})


def evaluate(cases: list[dict]) -> dict:
    from abook.quality_policy import quality_implementation_hash
    from abook.readaloud.vieneu_engine import phonemize

    counts = {category: {path: {stage: {"correct": 0, "total": 0} for stage in STAGES}
                              for path in PATHS} for category in CATEGORIES}
    failures = []
    results = []
    with SpeechBoundaries() as boundaries:
        for case in cases:
            expected = case["expected"]
            answers = [expected] if isinstance(expected, str) else expected
            accepted = {normalize(x) for x in answers}
            # Expected readings skip application TN, then use each engine's same
            # G2P path with their own spelling as source, without book rulings.
            expected_phonemes = {
                "nghe_ngay": [phonemize([answer], source=answer) for answer in answers],
                "studio": [studio_phonemes(answer, answer) for answer in answers],
            }
            got, phones = boundaries.read(case)  # Exceptions must fail the run.
            passed = {}
            for path in PATHS:
                passed[path] = {
                    "string": normalize(got[path]) in accepted,
                    "post_g2p": normalize_phonemes(phones[path]) in
                                {normalize_phonemes(x) for x in expected_phonemes[path]},
                }
                for stage in STAGES:
                    cell = counts[case["category"]][path][stage]
                    cell["total"] += 1
                    cell["correct"] += int(passed[path][stage])
                    if not passed[path][stage]:
                        failures.append({**case, "path": path, "stage": stage, "got": got[path],
                                         "got_phonemes": phones[path], "expected_phonemes": expected_phonemes[path]})
            results.append({"id": case["id"], "category": case["category"], "got": got,
                            "got_phonemes": phones, "expected_phonemes": expected_phonemes, "passed": passed})
    for cells in counts.values():
        for path_cells in cells.values():
            for cell in path_cells.values():
                cell["percent"] = round(100 * cell["correct"] / cell["total"], 2)
    profile = {**PROFILE, "packages": {name: version(name) for name in ("sea-g2p", "vieneu")},
               "nghe_ngay_g2p": "abook.readaloud.vieneu_engine.phonemize(Unit.pieces, source=Unit.text)",
               "studio_g2p": "keep_vieneu_final_mark; sentence_case; normalize_to_chunks_v3_with_gaps; phonemize_text_with_emotions"}
    return {"schema_version": 2, "profile": profile, "case_count": len(cases),
            "cases_sha256": hashlib.sha256(json.dumps(cases, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            "quality_implementation_hash": quality_implementation_hash(), "categories": counts,
            "overall": {path: {stage: {"correct": sum(c[path][stage]["correct"] for c in counts.values()), "total": len(cases),
                               "percent": round(100 * sum(c[path][stage]["correct"] for c in counts.values()) / len(cases), 2)} for stage in STAGES}
                        for path in PATHS},
            "failures": failures, "results": results}


def baseline_of(report: dict) -> dict:
    return {key: report[key] for key in ("schema_version", "profile", "case_count", "cases_sha256",
                                       "quality_implementation_hash", "categories", "overall")}


def check_floor(report: dict, baseline: dict) -> None:
    """Compare integer numerators; there is zero permitted drop per category."""
    for key in ("schema_version", "case_count", "cases_sha256", "profile"):
        if report[key] != baseline[key]:
            raise ValueError(f"Benchmark definition changed: {key}; review and remeasure explicitly")
    for category in CATEGORIES:
        for path in PATHS:
            for stage in STAGES:
                cell, floor = report["categories"][category][path][stage], baseline["categories"][category][path][stage]
                if cell["total"] != floor["total"] or cell["correct"] < floor["correct"]:
                    raise ValueError(f"Score below committed floor: {category}/{path}/{stage}: {cell} < {floor}")


def score_table(report: dict) -> str:
    lines = ["| Category | N | Nghe ngay chuỗi | Nghe ngay sau G2P | Studio chuỗi | Studio sau G2P |",
             "|---|---:|---:|---:|---:|---:|"]
    for category, cells in report["categories"].items():
        values = [f"{cells[path][stage]['correct']}/{cells[path][stage]['total']} = {cells[path][stage]['percent']:.2f}%"
                  for path in PATHS for stage in STAGES]
        lines.append(f"| {category} | {cells['studio']['string']['total']} | " + " | ".join(values) + " |")
    values = [f"{report['overall'][path][stage]['correct']}/{report['case_count']} = {report['overall'][path][stage]['percent']:.2f}%"
              for path in PATHS for stage in STAGES]
    lines.append(f"| **Overall** | {report['case_count']} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def priorities(report: dict, frequency: dict) -> dict:
    ranking = []
    for category in CATEGORIES:
        mismatch = sum(1 - report['categories'][category][path]['post_g2p']['correct'] /
                       report['categories'][category][path]['post_g2p']['total'] for path in PATHS) / len(PATHS)
        count = frequency['counts'][category]
        rate = count / frequency['whitespace_tokens'] * 100000
        ranking.append({'category': category, 'count': count, 'per_100k_tokens': round(rate, 3),
                        'mean_mismatch_fraction': round(mismatch, 6), 'priority_proxy': round(rate * mismatch, 4)})
    ranking.sort(key=lambda item: -item['priority_proxy'])
    return {'formula': 'pattern hits / whitespace tokens * 100000 * mean(two path post-G2P mismatch fractions)',
            'warning': 'Prioritization proxy only; phoneme agreement is not acoustic accuracy.', 'ranking': ranking}


def priority_table(priority: dict) -> str:
    lines = ['| Hạng | Lớp | Số dấu hiệu mẫu | /100k từ | Sai sau G2P trung bình | Điểm ưu tiên |',
             '|---:|---|---:|---:|---:|---:|']
    for rank, item in enumerate(priority['ranking'][:10], 1):
        lines.append(f"| {rank} | {item['category']} | {item['count']} | {item['per_100k_tokens']:.3f} | "
                     f"{item['mean_mismatch_fraction'] * 100:.1f}% | {item['priority_proxy']:.3f} |")
    return '\n'.join(lines)


def markdown(report: dict, priority: dict) -> str:
    lines = ["# TN benchmark", "", "Two boundaries: text and production VieNeu G2P; no synthesis or acoustic accuracy claim.",
             "Cloud engines (Edge/Azure/Google/FPT) perform their own TN and are outside this measurement.", "",
             score_table(report), "", "## Priority by post-G2P errors", "", priority_table(priority), "",
             "## Phoneme diagnostics: top five categories", "",
             "Up to ten failing cases per category and path, in fixture order; all failures are shown when fewer exist.", ""]
    for item in priority['ranking'][:5]:
        for path in PATHS:
            selected = [failure for failure in report['failures'] if failure['category'] == item['category'] and
                        failure['path'] == path and failure['stage'] == 'post_g2p'][:10]
            lines += [f"### {item['category']} / {path}: {len(selected)} cases", ""]
            for failure in selected:
                lines += ["```json", json.dumps({key: failure[key] for key in
                          ('id', 'text', 'expected', 'got', 'got_phonemes', 'expected_phonemes')}, ensure_ascii=False), "```", ""]
    lines += ["## All mismatches (each stage)", ""]
    for failure in report["failures"]:
        lines += [f"### {failure['id']} / {failure['path']} / {failure['stage']}", "",
                  "```json", json.dumps({key: failure[key] for key in
                  ("text", "expected", "got", "got_phonemes", "expected_phonemes", "note")}, ensure_ascii=False), "```", ""]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=FIXTURE)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-baseline", type=Path)
    parser.add_argument("--frequency", type=Path, default=INTERNAL / "docs/tn_benchmark/corpus_frequency.json")
    args = parser.parse_args(argv)
    report = evaluate(load_cases(args.cases))
    priority = priorities(report, json.loads(args.frequency.read_text(encoding='utf-8')))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (args.output_dir / "report.md").write_text(markdown(report, priority), encoding="utf-8", newline="\n")
    (args.output_dir / "priority.json").write_text(json.dumps(priority, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline="\n")
    if args.check_baseline:
        check_floor(report, json.loads(args.check_baseline.read_text(encoding="utf-8")))
    print(json.dumps({"case_count": report["case_count"], "overall": report["overall"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
