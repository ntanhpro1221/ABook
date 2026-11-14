"""Attribute corpus overlaps using paths and distinct shingle counts only.

Use --initial to reproduce the inventory/tokenizer after Lead's initial patch.
An optional --findings JSON limits repository inputs to previously reported paths.
No Corpus text, token, or shingle hash is emitted. --repo-evidence explicitly
adds matching spans read only from public repository files.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata

import numpy as np

try:
    from scripts import public_leak_scan as scan
except ModuleNotFoundError:
    import public_leak_scan as scan


def initial_files(root: Path) -> list[Path]:
    found = []
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = [d for d in subdirs if d.lower() not in scan.CORPUS_SKIP_DIRS
                      and not d.lower().endswith(".dist-info")]
        if Path(directory) == root:
            subdirs[:] = [d for d in subdirs if d.lower() not in {"claude", "releases", "research", "s", "keys"}]
        found.extend(Path(directory) / name for name in files if Path(name).suffix.lower() in scan.CORPUS_SUFFIXES
                     and not re.match(r"(license|copying|requirements|readme)", name, re.I))
    return sorted(found)


def initial_shingles(text: str, cache=None) -> np.ndarray:
    cache = {} if cache is None else cache
    words = scan.WORD.findall(unicodedata.normalize("NFC", text).lower())
    count = max(0, len(words) - scan.SHINGLE + 1)
    hashes = np.fromiter((scan._word_hash(w, cache) for w in words), dtype=np.uint64, count=len(words))
    combined = np.zeros(count, dtype=np.uint64)
    with np.errstate(over="ignore"):
        for offset in range(scan.SHINGLE):
            combined = combined * scan.PRIME + hashes[offset:offset + count]
    return combined


def _init(index_path, initial):
    global _INDEX, _SHINGLES, _INITIAL
    _INDEX = np.load(index_path, mmap_mode="r")
    _SHINGLES = initial_shingles if initial else scan.shingles
    _INITIAL = initial


def _chunk(paths):
    hits, cache = [], {}
    for name in paths:
        text = Path(name).read_text(encoding="utf-8", errors="ignore") if _INITIAL else scan.read_corpus_text(Path(name))
        values = _SHINGLES(text, cache)
        positions = np.searchsorted(_INDEX, values)
        positions[positions >= len(_INDEX)] = 0
        common = np.unique(values[_INDEX[positions] == values])
        if common.size:
            hits.append((name, common.tolist()))
        if len(cache) > 2_000_000:
            cache.clear()
    return hits


def _initial_diagnose(repo, corpus, *, initial=False, wanted=None, workers=3):
    shingler = initial_shingles if initial else scan.shingles
    owners = defaultdict(set)
    for name in scan.tracked(repo):
        if wanted is not None and name not in wanted:
            continue
        for _, value in scan.texts(repo / name):
            for value_hash in np.unique(shingler(value)).tolist():
                owners[value_hash].add(name)
    if not owners:
        return {"findings": [], "directories": []}
    files = initial_files(corpus) if initial else scan.corpus_files(corpus)
    matches = defaultdict(dict)
    groups = defaultdict(lambda: {"paths": set(), "sources": set(), "pairs": 0})
    with tempfile.TemporaryDirectory(prefix="leak-diagnose-") as work:
        index = Path(work) / "index.npy"
        np.save(index, np.array(sorted(owners), dtype=np.uint64))
        with scan.windowless_workers(), ProcessPoolExecutor(max_workers=min(3, max(1, workers)), initializer=_init,
                                 initargs=(str(index), initial)) as pool:
            for number, hits in enumerate(pool.map(_chunk, [[str(p) for p in files[i:i + 200]]
                                                           for i in range(0, len(files), 200)]), 1):
                for source, hashes in hits:
                    relative = Path(source).relative_to(corpus).as_posix()
                    counts = defaultdict(int)
                    for value_hash in hashes:
                        for owner in owners[value_hash]:
                            counts[owner] += 1
                    group = "/".join(Path(relative).parts[:2]) if relative.startswith("_") else Path(relative).parts[0]
                    entry = groups[group]
                    entry["sources"].add(relative)
                    for owner, count in counts.items():
                        matches[owner][relative] = count
                        entry["paths"].add(owner)
                        entry["pairs"] += count
                if number % 100 == 0:
                    print(f"diagnosis: {min(number * 200, len(files))}/{len(files)} files", file=sys.stderr, flush=True)
    return {"corpus_file_count": len(files),
            "findings": [{"path": owner, "corpus_matches": mapping} for owner, mapping in sorted(matches.items())],
            "directories": [{"directory": group, "repository_files": len(v["paths"]),
                             "corpus_files": len(v["sources"]), "shingle_pairs": v["pairs"]}
                            for group, v in sorted(groups.items())]}


def repository_evidence(text, wanted):
    """Yield exact public spans using the scanner's token/window boundaries."""
    text = unicodedata.normalize("NFC", text)
    tokens = list(scan.PROSE_TOKEN.finditer(text))
    words = [match.group(1) if match.group(1) and match.group(1).isalpha() else "" for match in tokens]
    starts = (i for i in range(len(tokens) - scan.SHINGLE + 1)
              if all(words[i:i + scan.SHINGLE])
              and sum(len(w) > 1 for w in words[i:i + scan.SHINGLE]) >= scan.SHINGLE // 2)
    for start, value in zip(starts, scan.shingles(text).tolist()):
        if value in wanted:
            offset = tokens[start].start()
            yield value, {"line": text.count("\n", 0, offset) + 1,
                          "repo_text": text[offset:tokens[start + scan.SHINGLE - 1].end()]}


def summarize(repo, owners, hits, *, repo_evidence=False):
    """Summarize one complete intersection; never reread private text to print."""
    frequencies = scan.story_frequencies(hits)
    kept = {h for h, books in frequencies.items() if len(books) < scan.COMMON_STORY_MIN}
    matches = defaultdict(dict)
    counts = Counter()
    for source, hashes in hits:
        for value in hashes:
            if value in kept:
                for owner in owners[value]:
                    counts[owner, source] += 1
    groups = defaultdict(lambda: {"paths": set(), "sources": set(), "pairs": 0})
    for (owner, source), count in sorted(counts.items()):
        matches[owner][source] = count
        group = "/".join(Path(source).parts[:2]) if source.startswith("_") else Path(source).parts[0]
        groups[group]["paths"].add(owner)
        groups[group]["sources"].add(source)
        groups[group]["pairs"] += count
    findings = [{"path": owner, "corpus_matches": mapping} for owner, mapping in sorted(matches.items())]
    if repo_evidence:
        for finding in findings:
            wanted = {h for h in kept if finding["path"] in owners[h]}
            evidence = {}
            for member, text in scan.texts(repo / finding["path"]):
                for value, span in repository_evidence(text, wanted):
                    evidence.setdefault(value, {**span, "where": member,
                                                "story_count": len(frequencies[value])})
            finding["repository_shingles"] = list(evidence.values())
    return {
        "common_story_min": scan.COMMON_STORY_MIN,
        "unfiltered_finding_count": len({owner for found in owners.values() for owner in found}),
        "matched_shingle_count": len(frequencies),
        "suppressed_shingle_count": len(frequencies) - len(kept),
        "story_frequency_distribution": [{"stories": n, "shingles": count}
                                          for n, count in sorted(Counter(map(len, frequencies.values())).items())],
        "threshold_sweep": [{"minimum_stories": k,
                             "remaining_files": len({owner for h, books in frequencies.items() if len(books) < k
                                                     for owner in owners[h]})} for k in (2, 3, 4, 5, 8)],
        "findings": findings,
        "directories": [{"directory": group, "repository_files": len(v["paths"]),
                         "corpus_files": len(v["sources"]), "shingle_pairs": v["pairs"]}
                        for group, v in sorted(groups.items())],
    }


def diagnose(repo, corpus, *, initial=False, wanted=None, workers=3, repo_evidence=False):
    if initial:
        if repo_evidence:
            raise ValueError("Repository evidence is supported only for the current scanner")
        return _initial_diagnose(repo, corpus, initial=True, wanted=wanted, workers=workers)
    sources = {name: [text for _, text in scan.texts(repo / name)] for name in scan.tracked(repo)
               if wanted is None or name in wanted}
    with tempfile.TemporaryDirectory(prefix="leak-diagnose-") as work:
        owners, hits, count = scan.collect_corpus_matches(sources, corpus, Path(work), workers)
    return {"corpus_file_count": count, **summarize(repo, owners, hits, repo_evidence=repo_evidence)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initial", action="store_true")
    parser.add_argument("--findings", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-evidence", action="store_true", help="include public repository spans, never Corpus prose")
    args = parser.parse_args()
    corpus = scan.corpus_root()
    if corpus is None:
        parser.error("No Corpus found")
    wanted = None
    if args.findings:
        wanted = {f["path"] for f in json.loads(args.findings.read_text(encoding="utf-8"))["findings"]
                  if f["rule"] == f"shares>={scan.SHINGLE}words"}
    result = diagnose(scan.REPO, corpus, initial=args.initial, wanted=wanted, repo_evidence=args.repo_evidence)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"findings": len(result["findings"]), "directories": result["directories"]}, ensure_ascii=False))


if __name__ == "__main__":
    sys.path.insert(0, str(scan.REPO / "_internal"))
    main()
