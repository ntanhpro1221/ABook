"""Attribute corpus overlaps using paths and distinct shingle counts only.

Use --legacy to reproduce the inventory/tokenizer after Lead's initial patch.
An optional --findings JSON limits repository inputs to previously reported paths.
No source text, token, or shingle hash is emitted.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
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


def legacy_files(root: Path) -> list[Path]:
    found = []
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = [d for d in subdirs if d.lower() not in scan.CORPUS_SKIP_DIRS
                      and not d.lower().endswith(".dist-info")]
        if Path(directory) == root:
            subdirs[:] = [d for d in subdirs if d.lower() not in {"claude", "releases", "research", "s", "keys"}]
        found.extend(Path(directory) / name for name in files if Path(name).suffix.lower() in scan.CORPUS_SUFFIXES
                     and not re.match(r"(license|copying|requirements|readme)", name, re.I))
    return sorted(found)


def legacy_shingles(text: str, cache=None) -> np.ndarray:
    cache = {} if cache is None else cache
    words = scan.WORD.findall(unicodedata.normalize("NFC", text).lower())
    count = max(0, len(words) - scan.SHINGLE + 1)
    hashes = np.fromiter((scan._word_hash(w, cache) for w in words), dtype=np.uint64, count=len(words))
    combined = np.zeros(count, dtype=np.uint64)
    with np.errstate(over="ignore"):
        for offset in range(scan.SHINGLE):
            combined = combined * scan.PRIME + hashes[offset:offset + count]
    return combined


def _init(index_path, legacy):
    global _INDEX, _SHINGLES, _LEGACY
    _INDEX = np.load(index_path, mmap_mode="r")
    _SHINGLES = legacy_shingles if legacy else scan.shingles
    _LEGACY = legacy


def _chunk(paths):
    hits, cache = [], {}
    for name in paths:
        text = Path(name).read_text(encoding="utf-8", errors="ignore") if _LEGACY else scan.read_corpus_text(Path(name))
        values = _SHINGLES(text, cache)
        positions = np.searchsorted(_INDEX, values)
        positions[positions >= len(_INDEX)] = 0
        common = np.unique(values[_INDEX[positions] == values])
        if common.size:
            hits.append((name, common.tolist()))
        if len(cache) > 2_000_000:
            cache.clear()
    return hits


def diagnose(repo, corpus, *, legacy=False, wanted=None, workers=3):
    shingler = legacy_shingles if legacy else scan.shingles
    owners = defaultdict(set)
    for name in scan.tracked(repo):
        if wanted is not None and name not in wanted:
            continue
        for _, value in scan.texts(repo / name):
            for value_hash in np.unique(shingler(value)).tolist():
                owners[value_hash].add(name)
    if not owners:
        return {"findings": [], "directories": []}
    files = legacy_files(corpus) if legacy else scan.corpus_files(corpus)
    matches = defaultdict(dict)
    groups = defaultdict(lambda: {"paths": set(), "sources": set(), "pairs": 0})
    with tempfile.TemporaryDirectory(prefix="leak-diagnose-") as work:
        index = Path(work) / "index.npy"
        np.save(index, np.array(sorted(owners), dtype=np.uint64))
        with scan.windowless_workers(), ProcessPoolExecutor(max_workers=min(3, max(1, workers)), initializer=_init,
                                 initargs=(str(index), legacy)) as pool:
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--findings", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus = scan.corpus_root()
    if corpus is None:
        parser.error("No Corpus found")
    wanted = None
    if args.findings:
        wanted = {f["path"] for f in json.loads(args.findings.read_text(encoding="utf-8"))["findings"]
                  if f["rule"] == f"shares>={scan.SHINGLE}words"}
    result = diagnose(scan.REPO, corpus, legacy=args.legacy, wanted=wanted)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"findings": len(result["findings"]), "directories": result["directories"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
