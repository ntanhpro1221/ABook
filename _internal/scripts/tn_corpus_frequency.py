"""Count NSW candidate patterns in a deterministic story-stratified sample.

Only aggregate counts and a sample fingerprint are emitted. Source sentences,
tokens, book titles, chapter names and paths are never included in the report.
Patterns overlap and are recall-limited proxies, not annotated NSW labels.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import public_leak_scan as scan
from scripts.tn_benchmark import CATEGORIES

PATTERNS = {
    "cardinal_small": r"(?<![\w.,])\d{1,3}(?![\w.,])",
    "cardinal_large": r"(?<!\w)(?:\d{4,}|\d{1,3}(?:[.,]\d{3})+)(?!\w)",
    "decimal": r"(?<!\w)\d+[.,]\d+(?!\w)",
    "ordinal": r"\bthứ\s+\d+\b",
    "roman": r"(?-i:\b[IVXLCDM]+\b)",
    "date": r"\b(?:\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?|\d{4}-\d{2}-\d{2})\b",
    "time": r"\b\d{1,2}(?::\d{2}(?::\d{2})?|h(?:\d{2})?)(?!\w)",
    "range": r"\b\d+(?:[.,]\d+)?\s*[-–—~]\s*\d+(?:[.,]\d+)?\b",
    "percentage": r"\d+(?:[.,]\d+)?\s*%",
    "currency": r"[$¥€£₫]|\b\d[\d.,]*\s*(?:đồng|yên|USD|JPY|EUR|VND|đ)(?!\w)",
    "unit": r"\b\d[\d.,]*\s*(?:km(?:/h)?|kg|m[²³23]|°C|cm|mm|mg|ml|m/s|m|g|l|W|V|Hz|GB|dB|ha)(?!\w)",
    "phone_code": r"(?<!\w)0\d{8,10}(?!\w)|\b(?:mã|PIN|OTP)\s+[A-Z0-9]+\b",
    "abbrev_vi": r"\b(?:TP\.|ThS\.|PGS\.|GS\.|TS\.|BS\.|KS\.|UBND|Q\.\s*\d+|P\.\s*\d+|v\.v\.|THPT|THCS|ĐH|CĐ|KTX|SĐT|CMND)(?!\w)",
    "abbrev_en": r"(?-i:\b(?:HP|MP|NPC|TV|CEO|OK|CPU|GPU|PDF|USB|GPS|FPS|RPG|EXP|FAQ|VIP|DJ|AC|AI)\b)|\bvs\.",
    "english": r"\b(?:game|level|boss|skill|item|team|server|file|link|email|video|menu|online|offline|save|enter|reset|chat|status|update)\b",
    "japanese": r"\b\w+-(?:san|kun|chan|sama|senpai)\b|\b(?:senpai|sensei|kouhai|arigatou|ohayou|konnichiwa|onii|onee)\b",
    "symbol": r"[&@#%+=/×→★♪≥≤≠±÷©]",
    "url_email": r"(?:https?://|ftp://|www\.)\S+|\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b",
    "vocalization": r"\b([aáàảãạăâeéèẻẽẹêoóòỏõọôơuúùủũụưiíìỉĩịyh])\1{2,}\w*|\b(?:hmm+|hừmm+|haizz+|grrr+|(?:ha|hi|hu){3,})\b",
    "punctuation": r"\.{3,}|…|[–—]|(?<!\d)\s-\s|[!?]{2,}",
    "uppercase": r"(?-i:\b[A-ZÀ-ỸĐ]{2,}(?:\s+[A-ZÀ-ỸĐ]{2,})+\b)",
    "game": r"\bLv\.?\s*\d+|\bx\d+\b|\b\d+x\b|[+]\d+\s*(?:STR|DEX|INT|ATK|DEF)\b|\b\d+/\d+\b",
}


def sample_counts(corpus: Path, max_stories: int = 100, per_story: int = 4) -> dict:
    if max_stories < 1 or per_story < 1:
        raise ValueError("Sample limits must be positive")
    grouped = defaultdict(list)
    for path in scan.corpus_files(corpus):
        grouped[scan.story_identity(path.relative_to(corpus))].append(path)
    if not grouped:
        raise ValueError("No story chapters found")
    digest_key = lambda value: hashlib.sha256(value.encode("utf-8")).digest()
    stories = sorted(grouped, key=digest_key)[:max_stories]
    patterns = {category: re.compile(PATTERNS[category], re.IGNORECASE) for category in CATEGORIES}
    counts = dict.fromkeys(CATEGORIES, 0)
    digest = hashlib.sha256()
    file_count = characters = words = 0
    for story in stories:
        selected = sorted(grouped[story], key=lambda p: digest_key(p.relative_to(corpus).as_posix()))[:per_story]
        for path in selected:
            text = scan.read_corpus_text(path)
            # No prose is printed or persisted, including in error messages.
            digest.update(digest_key(path.relative_to(corpus).as_posix()))
            digest.update(hashlib.sha256(text.encode("utf-8")).digest())
            file_count += 1
            characters += len(text)
            words += len(text.split())
            for category, pattern in patterns.items():
                counts[category] += sum(1 for _ in pattern.finditer(text))
    return {"schema_version": 1, "method": "sha256-ranked stories, then sha256-ranked chapters",
            "available_stories": len(grouped), "sample_stories": len(stories), "sample_chapters": file_count,
            "max_stories": max_stories, "chapters_per_story": per_story,
            "sample_sha256": digest.hexdigest(), "characters": characters, "whitespace_tokens": words,
            "patterns": PATTERNS, "counts": counts,
            "per_100k_tokens": {category: round(count * 100000 / words, 3) for category, count in counts.items()},
            "limitations": "Overlapping regex proxies; dates/ranges/fractions overlap; English/Japanese use short lists; no human labels or population accuracy inference."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stories", type=int, default=100)
    parser.add_argument("--chapters-per-story", type=int, default=4)
    args = parser.parse_args()
    result = sample_counts(args.corpus, args.stories, args.chapters_per_story)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("sample_stories", "sample_chapters", "whitespace_tokens")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
