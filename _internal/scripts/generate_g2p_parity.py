"""Freeze the desktop frontend's exact output for the Kotlin/host-JNI contract.

Only isolated public tokens enter the checked-in fixture. Calibration sentences
must stay outside the repository; --private-out requires the original clips and
verifies their hashes before generating the optional JVM input.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abook.readaloud import japanese_policy, names, shared_rulings, vieneu, vieneu_engine
from abook.readaloud.phoneme_policy import Rulings, book_rulings

DATA = ROOT / "tests/data/g2pgate"


def load(path: Path):
    return json.loads(path.read_text("utf8"))


def case(identity, cls, text, origin, readings, rulings, *, book_names=False):
    # These are book inputs (sharedWords/readings), as transported to the phone.
    applied = (
        {**japanese_policy.book_name_readings([], [text], origin), **readings} if book_names else readings
    )
    with book_rulings(rulings):
        shown, units = vieneu.units(text, 256, origin, readings=applied, direct_english=True)
        expected = [
            {
                "pieces": u.pieces,
                "phonemes": vieneu_engine.phonemize(u.pieces, source=u.text(shown), rulings=rulings),
            }
            for u in units
        ]
    return {
        "id": identity,
        "class": cls,
        "text": text,
        "origin": origin,
        "readings": readings,
        "book_names": book_names,
        "rulings": {"names": sorted(rulings.names), "foreign": sorted(rulings.foreign)},
        "units": expected,
        "phonemes": " ".join(u["phonemes"] for u in expected),
    }


def public_cases():
    result = []
    for i, row in enumerate(load(DATA / "tokens.json")):
        token, cls = row["token"], row["class"]
        origin = {"japanese": "ja", "korean": "ko"}.get(cls)
        if cls == "mixed" and token.isascii():
            origin = names.term_origin(token) or "ja"
        roster = {token: {"western": "en", "korean": "ko", "japanese": "ja"}.get(cls, "vi")}
        readings = (
            shared_rulings.name_readings(roster, origin) if cls in {"western", "korean", "japanese"} else {}
        )
        rulings = (
            Rulings(names=set(shared_rulings.vietnamese_names(roster)))
            if cls in {"vietnamese", "chinese"}
            else Rulings(foreign=set(shared_rulings.foreign_names(roster)))
        )
        result.append(case(f"token:{i:03d}", cls, token, origin, readings, rulings, book_names=True))
    return result


def occurrence_cases():
    """Authored contexts; full sentence phones are written only outside Git."""
    rows = load(ROOT / "tests/fixtures/readaloud/normalized_occurrences/cases.json")
    return [case(row["id"], "normalized_occurrence", row["text"], row.get("origin"), {},
                 Rulings(names=set(row["names"]))) for row in rows]


def private_cases(source: Path, context: Path):
    clips = {c["id"]: c for c in load(source)}
    rows = load(context)
    assert set(clips) == {r["id"] for r in rows}
    result = []
    for row in rows:
        text = clips[row["id"]]["title"]
        assert hashlib.sha256(text.encode()).hexdigest() == row["source_sha256"], row["id"]
        readings = {**shared_rulings.name_readings(row["roster_origins"], row["origin"]), **row["readings"]}
        result.append(
            case(
                row["id"],
                "calibration",
                text,
                row["origin"],
                readings,
                Rulings(names=set(row["vietnamese_names"])),
            )
        )
    return result


def stretch_cases():
    """Synthetic cries: every Vietnamese vowel/tone plus mixed and short runs."""
    tokens = ["đââââââyy", "Eeeê", "Gìì", "Gaààoo", "Piiim", "hẵẵng", "bậập", "ớớ", "ừừ"]
    for vowel in "aăâeêioôơuưy":
        for tone in "\u0300\u0301\u0303\u0309\u0323":
            char = unicodedata.normalize('NFC', unicodedata.normalize('NFD', vowel) + tone)
            tokens.append('b' + char * 4 + 'n' if vowel in 'ăâ' else 't' + char * 4 if vowel == 'y' else char * 4)
            if vowel in 'ăây':
                tokens.append(char * 4)
    tokens += [unicodedata.normalize('NFD', token) for token in tokens[:9]]
    tokens += ["Ưư", "Êii", "Ồồ", "Hãy cứu tôi với!", "hưu", "lưu", "mưu", "bưu", "cừu", "tửu", "ưu", "hữu", "cựu",
               "soóc", "moóc", "goòng", "voọc", "boong", "xoong", "khuỷu", "hươu", "rượu"]
    return [case(f"stretch:{i:03d}", "marked_stretch", token, None, {}, Rulings()) for i, token in enumerate(tokens)]


def payload(cases):
    # Regenerate from current desktop code instead of storing the unrelated quality hash.
    return {
        "sea_g2p": importlib.metadata.version("sea-g2p"),
        "comparison": "exact UTF-8 phonemes; no stress, tone, whitespace or punctuation folding",
        "cases": cases,
    }


def write(path: Path, cases, *, check=False):
    payload_ = payload(cases)
    if check:
        assert load(path) == payload_, f"Desktop parity fixture is stale: {path}"
        print(f"Verified {len(cases)} cases: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload_, ensure_ascii=False, indent=2) + "\n", encoding="utf8", newline="\n")
    print(f"Wrote {len(cases)} cases: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-out", type=Path, default=DATA / "desktop_parity.json")
    parser.add_argument("--calibration-source", type=Path)
    parser.add_argument("--private-out", type=Path)
    parser.add_argument("--occurrence-out", type=Path, help="authored occurrence parity output outside the repository")
    parser.add_argument("--calibration-context", type=Path, default=Path("D:/Novels/ABook/Corpus/g2pgate/calibration_context.json"))
    parser.add_argument(
        "--check", action="store_true", help="verify existing fixtures without rewriting them"
    )
    args = parser.parse_args()
    if bool(args.private_out) != bool(args.calibration_source):
        parser.error("--private-out and --calibration-source must be supplied together")
    if args.private_out and (args.calibration_source.resolve().is_relative_to(ROOT.parent) or args.calibration_context.resolve().is_relative_to(ROOT.parent)):
        parser.error("private calibration inputs must be outside the repository")
    if args.private_out and args.private_out.resolve().is_relative_to(ROOT.parent):
        parser.error("private calibration output must be outside the repository")
    if args.occurrence_out and args.occurrence_out.resolve().is_relative_to(ROOT.parent):
        parser.error("sentence phonemes must stay outside the repository")
    write(args.public_out, public_cases(), check=args.check)
    write(args.public_out.with_name("stretches_parity.json"), stretch_cases(), check=args.check)
    if args.private_out:
        write(args.private_out, private_cases(args.calibration_source, args.calibration_context), check=args.check)
    if args.occurrence_out:
        write(args.occurrence_out, occurrence_cases(), check=args.check)


if __name__ == "__main__":
    main()
