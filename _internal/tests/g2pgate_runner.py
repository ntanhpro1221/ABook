"""CPU-only production frontend runner and disjoint mismatch accounting."""

from __future__ import annotations

from collections import Counter, defaultdict
from difflib import SequenceMatcher

from g2pgate_policy import TONES, normalized_phones

from abook.readaloud import japanese_policy, shared_rulings, vieneu, vieneu_engine
from abook.readaloud.phoneme_policy import Rulings, book_rulings


def app_output(token: str, token_class: str) -> str:
    origin = {"japanese": "ja", "korean": "ko"}.get(token_class)
    if token_class == "mixed" and token.isascii():
        from abook.readaloud import names

        origin = names.term_origin(token) or "ja"
    # Supply book/roster evidence, not oracle readings. Real production readers
    # materialize the same book_name_readings/shared_rulings before synthesis.
    readings = japanese_policy.book_name_readings([], [token], origin)
    roster = {token: {"western": "en", "korean": "ko", "japanese": "ja"}.get(token_class, "vi")}
    if token_class in {"western", "korean", "japanese"}:
        readings.update(shared_rulings.name_readings(roster, origin))
    rulings = (
        Rulings(names=set(token.lower().split()))
        if token_class in {"vietnamese", "chinese"}
        else Rulings(foreign=shared_rulings.foreign_names(roster))
    )
    with book_rulings(rulings):
        shown, parts = vieneu.units(token, 256, origin, readings=readings, direct_english=True)
        return " ".join(
            vieneu_engine.phonemize(p.pieces, source=p.text(shown), rulings=rulings) for p in parts
        )


def mismatch_kind(actual: str, target: str) -> str:
    a, b = normalized_phones(actual), normalized_phones(target)
    if a == b:
        return "match"
    if "".join(c for c in a if c not in TONES) == "".join(c for c in b if c not in TONES):
        return "tone"
    if any(c in a for c in "æɪʊɹɾʌɚθð") and not any(c in b for c in "æɪʊɹɾʌɚθð"):
        return "lang"
    edits = SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    kinds = {op for op, *_ in edits if op != "equal"}
    if kinds == {"insert"}:
        return "missing"
    if kinds == {"delete"}:
        return "extra"
    return "phone"


def compare(rows, expected):
    results = []
    for row in rows:
        key = row["class"] + ":" + row["token"]
        gold = expected[key]
        actual = app_output(row["token"], row["class"])
        opts = gold["phones"]
        hit = any(normalized_phones(actual) == normalized_phones(p) for p in opts)
        target = (
            max(
                opts,
                key=lambda p: SequenceMatcher(None, normalized_phones(actual), normalized_phones(p)).ratio(),
            )
            if opts
            else ""
        )
        results.append(
            dict(
                row,
                actual=actual,
                target=target,
                kind="match" if hit else mismatch_kind(actual, target),
                ambiguity=gold["ambiguity"],
            )
        )
    return results


def table(results):
    grouped = defaultdict(Counter)
    for row in results:
        count = grouped[row["class"]]
        count["n"] += 1
        count[row["kind"]] += 1
        count["ambiguous"] += bool(row.get("ambiguity"))
    lines = [
        "class | n | mismatches | rate | lang | tone | missing | phone | extra | text ambiguous",
        "---|---:|---:|---:|---:|---:|---:|---:|---:|---:",
    ]
    for cls, c in sorted(grouped.items()):
        n = c["n"]
        bad = n - c["match"]
        lines.append(
            f"{cls} | {n} | {bad} | {bad / n:.2%} | "
            + " | ".join(f"{c[k]} ({c[k] / n:.2%})" for k in ["lang", "tone", "missing", "phone", "extra"])
            + f" | {c['ambiguous']}"
        )
    return "\n".join(lines)
