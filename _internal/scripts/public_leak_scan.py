"""Find story text and sentence phonemes in every public Git file.

Report paths and locations only, never suspected prose. Check long IPA runs,
long Vietnamese strings, and eight consecutive prose words shared with local
story chapters. Report explicitly when the local Corpus is unavailable.

Run from _internal: python -X utf8 scripts/public_leak_scan.py [--json].
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import unicodedata
import zipfile

import numpy as np

REPO = Path(__file__).resolve().parents[2]
REVIEWED = Path(__file__).with_name("public_leak_reviewed.json")
SHINGLE = 8
# Three independent book folders establish a shared formula. Two may still be
# editions/aliases of the same work; chapter counts never establish commonness.
COMMON_STORY_MIN = 3
IPA_RUN = 8
LONG_VI_WORDS = 40
# Ký tự chỉ có trong phiên âm (IPA của sea-g2p / espeak), không có trong chữ Việt thường.
IPA = re.compile(r"[ˈˌːɜɯɗɲŋəɛɔɣʃʒθðæʌʊɪɑɐɹɾʔ]")
VI_MARK = re.compile(r"[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]", re.I)
WORD = re.compile(r"[^\W\d_]+")
STRING_LITERAL = re.compile(r'"((?:[^"\\\n]|\\.){20,})"|\'((?:[^\'\\\n]|\\.){20,})\'')
ZIP_SUFFIXES = {".epub", ".docx", ".abook", ".zip", ".odt"}
ZIP_TEXT = {".xhtml", ".html", ".htm", ".xml", ".txt", ".json", ".opf", ".ncx", ".md"}
TAG = re.compile(r"<[^>]+>")
# Fixture/chuỗi test: nơi chữ truyện có thể bị chép vào. Code sản phẩm và docs vẫn qua (a) và (c).
FIXTURE_PARTS = {"fixtures", "fixture", "data", "testdata", "resources", "snapshots", "tests", "test", "androidtest"}
# Thư mục không phải chữ truyện trong Corpus (môi trường Python, gói node, bản build).
CORPUS_SKIP_DIRS = {".venv", "venv", "site-packages", "node_modules", "lib", "libs", "__pycache__", ".git", "build",
                    "dist", "scripts", "tools", "include", "share"}
CORPUS_SUFFIXES = {".txt", ".md"}
# Top-level Corpus folders that hold no story of their own: agent notes, R8 mapping archives (Kotlin identifiers),
# research notes and specs, scratch specs and key docs. Story excerpts quoted there come from the story folders,
# which stay indexed, so skipping these loses no leak while app code stops matching identifiers and specs.
CORPUS_NON_STORY_DIRS = {"claude", "releases", "research", "s", "keys"}
CORPUS_COLLECTIONS = {"truyen", "ai-dich", "sang-tac", "khac", "merged"}
CORPUS_TECHNICAL_DIRS = CORPUS_SKIP_DIRS | {
    "android", "docs", "spec", "specs", "mapping", "mappings", "notes", "survey",
    "research", "releases", "tests", "test", "src", "vendor", "runtime",
}
CHAPTER_NAME = re.compile(r"(?:\[\d+\].*|\d+[a-z]?(?:[ ._-].*)?|(?:ch|chapter|chuong|chương)[ ._-]*\d+.*)$", re.I)
# Keep digits/underscores/escapes intact until validation: x00 must never become x.
PROSE_TOKEN = re.compile(
    r"\r?\n[ \t\r]*\n|\\(?:[uU][0-9a-fA-F]{4,8}|x[0-9a-fA-F]{2}|.)"
    r"|\b[a-z]+[A-Z]\w*|\b\w*[\d_]\w*|\b([^\W\d_]+)\b"
    r"|[^\w\s.,!?;:'\"“”‘’«»—–…()\[\]{}-]"
)
GOLD_ROW = re.compile(r"^\d+\s+(?:[NDT](?:,[NDT])*|H)(?:\s+.*)?$")
GOLD_START = re.compile(r"\s*(?:#[^\n]*\n\s*)*\d+\s+[NDTH](?:[,\s]|$)")
QUOTED_EVIDENCE = re.compile(r'“([^”\n]+)”|"([^"\n]+)"|«([^»\n]+)»')
CHAPTER_HEADING = re.compile(r"^(?:chương|chapter|tập|vol(?:ume)?)[ .:-]*(?:\d|[ivxlcdm]+\b)", re.I)
CHAPTER_METADATA = re.compile(
    r"^(?:tên truyện|tác giả|dịch giả|nhóm dịch|nguồn|book title|author|translator|source)\s*:", re.I
)
CODE_SUFFIXES = {".py", ".kt", ".java", ".ts", ".tsx", ".js", ".mjs", ".qml", ".cpp", ".h"}
PRIME = np.uint64(1099511628211)


def tracked(repo: Path = REPO) -> list[str]:
    names = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           capture_output=True, check=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.decode("utf-8").split("\0")
    return sorted(name for name in set(names) if name and (repo / name).is_file())


def is_fixture(relative: str) -> bool:
    path = PurePosixPath(relative)
    name = path.name.lower()
    return (path.suffix.lower() in {".md", ".rst", ".txt"}
            or any(part.lower() in FIXTURE_PARTS for part in path.parts[:-1])
            or "fixture" in name
            or (path.suffix.lower() in CODE_SUFFIXES
                and re.search(r"(^test_|_test\.|\.test\.|^tst_|tests?\.kt$)", name) is not None))


def private_path(text: str) -> bool:
    normalized = re.sub(r"[\\/]+", "/", text.replace("\0", "")).lower()
    # Assemble the signatures so the detector's source is subject to the same empty exception list.
    return ("c:" + "/users/" in normalized
            or "/".join(("appdata", "local", "temp", "claude")) in normalized)


def private_file(path: Path) -> bool:
    # Include binary metadata and UTF-16 ASCII signatures, as well as members of archives.
    return private_path(path.read_bytes().decode("utf-8", "ignore")) or any(private_path(text) for _, text in texts(path))


def texts(path: Path) -> list[tuple[str, str]]:
    """(vị trí, chữ) của một file: file văn bản, hay từng mục văn bản trong zip (epub/docx/abook)."""
    data = path.read_bytes()
    if path.suffix.lower() == ".gz":
        import gzip

        try:
            data = gzip.decompress(data)
        except OSError:
            return []
    if path.suffix.lower() in ZIP_SUFFIXES and data[:2] == b"PK":
        found = []
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for member in archive.namelist():
                    if PurePosixPath(member).suffix.lower() in ZIP_TEXT:
                        raw = archive.read(member).decode("utf-8", "replace")
                        found.append((member, TAG.sub(" ", raw)))
        except (zipfile.BadZipFile, OSError, RuntimeError):
            return []
        return found
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return [("", data.decode("utf-16", "replace"))]
    if b"\0" in data[:8192]:
        return []
    try:
        return [("", data.decode("utf-8-sig"))]
    except UnicodeDecodeError:
        return []


def strings_of(relative: str, text: str) -> list[tuple[str, str]]:
    """Các chuỗi để soi: giá trị chuỗi JSON, hay chuỗi trong code, hay từng dòng."""
    if relative.lower().endswith(".py"):
        try:
            return [(f"line {node.lineno}", node.value) for node in ast.walk(ast.parse(text))
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        except SyntaxError:
            pass  # Malformed source still receives the conservative textual scan below.
    if relative.lower().endswith((".md", ".rst", ".txt")):
        return [(f"paragraph {i}", block) for i, block in enumerate(re.split(r"\n\s*\n", text), 1)]
    if relative.lower().endswith((".json", ".jsonl")) or text.lstrip()[:1] in {"{", "["}:
        values: list[tuple[str, str]] = []

        def walk(value, where):
            if isinstance(value, dict):
                for key, child in value.items():
                    walk(child, f"{where}.{key}")
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, f"{where}[{index}]")
                # Tách câu ra mảng âm tiết không được lách luật.
                if value and all(isinstance(v, str) and len(v.split()) <= 2 for v in value):
                    values.append((where, " ".join(value)))
            elif isinstance(value, str):
                values.append((where, value))

        try:
            if relative.lower().endswith(".jsonl"):
                for number, line in enumerate(text.splitlines(), 1):
                    if line.strip():
                        walk(json.loads(line), f"line {number}")
            else:
                walk(json.loads(text), "$")
            return values
        except ValueError:
            pass
    found = []
    for match in re.finditer(r'"""(.*?)"""|`([^`]+)`', text, re.S):
        found.append((f"line {text[:match.start()].count(chr(10)) + 1}", match.group(1) or match.group(2)))
    for number, line in enumerate(text.splitlines(), 1):
        literals = [a or b for a, b in STRING_LITERAL.findall(line)]
        found += [(f"line {number}", item) for item in literals] or [(f"line {number}", line)]
    return found


def ipa_run(value: str) -> bool:
    run = 0
    for token in re.split(r"[\s\-]+", value):
        run = run + 1 if IPA.search(token) else 0
        if run >= IPA_RUN:
            return True
    return False


def long_vietnamese(value: str) -> bool:
    words = WORD.findall(value)
    return len(words) >= LONG_VI_WORDS and sum(bool(VI_MARK.search(w)) for w in words) >= len(words) // 4


def inspect(relative: str, path: Path) -> list[dict]:
    """Một dòng cho mỗi (file, luật): số chỗ và chỗ đầu tiên, không kèm nội dung."""
    found: dict[str, dict] = {}
    for member, text in texts(path):
        for where, value in strings_of(member or relative, text):
            rule = "ipa>=8" if ipa_run(value) else "long-vietnamese" if long_vietnamese(value) else ""
            if rule:
                entry = found.setdefault(rule, {"path": relative, "rule": rule, "count": 0,
                                                "where": f"{member}:{where}" if member else where})
                entry["count"] += 1
    return list(found.values())


def _word_hash(word: str, cache: dict) -> int:
    value = cache.get(word)
    if value is None:
        value = cache[word] = int.from_bytes(hashlib.blake2b(word.encode("utf-8"), digest_size=8).digest(), "little")
    return value


def shingles(text: str, cache: dict | None = None) -> np.ndarray:
    """Hash consecutive prose words; invalid tokens break a run, never disappear."""
    cache = {} if cache is None else cache
    # Only the letter alternative is captured; every invalid token yields an
    # empty sentinel. Punctuation is skipped by the regex, not by a Python loop.
    words = [token.lower() if token.isalpha() else ""
             for token in PROSE_TOKEN.findall(unicodedata.normalize("NFC", text))]
    if len(words) < SHINGLE:
        return np.empty(0, dtype=np.uint64)
    valid = np.fromiter(map(bool, words), dtype=np.int32, count=len(words))
    totals = np.concatenate(([0], np.cumsum(valid)))
    keep = totals[SHINGLE:] - totals[:-SHINGLE] == SHINGLE
    # Alphabet/codec tables contain letters, but are not eight prose words.
    substantive = np.concatenate(([0], np.cumsum([len(w) > 1 for w in words])))
    keep &= substantive[SHINGLE:] - substantive[:-SHINGLE] >= SHINGLE // 2
    if not keep.any():
        return np.empty(0, dtype=np.uint64)
    hashes = np.fromiter((_word_hash(w, cache) if w else 0 for w in words),
                         dtype=np.uint64, count=len(words))
    count = len(words) - SHINGLE + 1
    combined = np.zeros(count, dtype=np.uint64)
    with np.errstate(over="ignore"):
        for offset in range(SHINGLE):
            combined = combined * PRIME + hashes[offset:offset + count]
    return combined[keep]


def corpus_root() -> Path | None:
    candidates = [os.environ.get("ABOOK_CORPUS", ""), str(REPO / "Corpus"), str(REPO.parent / "ABook" / "Corpus")]
    return next((Path(c) for c in candidates if c and Path(c).is_dir()), None)


def is_story_chapter(relative: Path) -> bool:
    """Numbered TXT/MD chapters in book folders or supported chapter collections.

    Root notes and named technical files are not chapter sources. _full contains
    category/book/chapter; _dup and _gold contain book/chapter, optionally nested
    in an evaluation collection. Hidden/underscore backup trees are never books.
    """
    parts = relative.parts
    if relative.suffix.lower() not in CORPUS_SUFFIXES or not CHAPTER_NAME.fullmatch(relative.stem):
        return False
    if len(parts) < 2:
        return False
    top = parts[0].lower()
    if top == "_full":
        if len(parts) < 4 or parts[1].lower() not in CORPUS_COLLECTIONS:
            return False
        folders = parts[2:-1]
    elif top in {"_dup", "_gold"}:
        if len(parts) < 3:
            return False
        folders = parts[1:-1]
    else:
        if top in CORPUS_NON_STORY_DIRS or top.startswith(("_", ".")):
            return False
        folders = parts[:-1]
    return not any(p.startswith(("_", ".")) or p.lower() in CORPUS_TECHNICAL_DIRS for p in folders)


def corpus_files(root: Path) -> list[Path]:
    found = []
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = [d for d in subdirs if d.lower() not in CORPUS_TECHNICAL_DIRS
                     and not d.lower().endswith(".dist-info")
                     and (not d.startswith(("_", ".")) or (Path(directory) == root and d in {"_full", "_dup", "_gold"}))]
        if Path(directory) == root:
            subdirs[:] = [d for d in subdirs if d.lower() not in CORPUS_NON_STORY_DIRS]
        for name in files:
            path = Path(directory) / name
            if is_story_chapter(path.relative_to(root)):
                found.append(path)
    return sorted(found)


def _title_key(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return " ".join(WORD.findall("".join(c for c in text if not unicodedata.combining(c))))


def read_corpus_text(path: Path) -> str:
    """Read chapter prose, separating annotation rows from quoted evidence.

    Gold TXT files use seq/kind/speaker/delivery rows, not chapter prose (see
    GOLD_GUIDE.md). Only explicitly quoted comment evidence belongs in the index.
    Raw chapter files, including raw chapters under _gold, remain intact.
    """
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    if GOLD_START.match(text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        rows = [line for line in lines if not line.startswith("#")]
        if rows and all(GOLD_ROW.fullmatch(line) for line in rows):
            return "\n\n".join(next(part for part in match.groups() if part)
                                for line in lines if line.startswith("#")
                                for match in QUOTED_EVIDENCE.finditer(line))
    # Imported book/chapter titles are metadata, even when a title is a sentence.
    # Bound this to the preamble; identical words inside the story remain indexed.
    titles = {_title_key(re.sub(r"^\d+[-_]", "", parent.name)) for parent in list(path.parents)[:3]}
    preamble, separator, rest = text.partition("\n\n")
    kept = [line for line in preamble.splitlines()
            if _title_key(line) not in titles and not CHAPTER_METADATA.match(line.strip())
            and not CHAPTER_HEADING.match(line.strip()) and not line.lstrip().startswith("# ")]
    text = "\n".join(kept) + separator + rest
    return without_source_credits(text)


def without_source_credits(text: str) -> str:
    """Reuse the importer credit rules at chapter edges, never inside dialogue.

    Blank paragraphs replace removed lines, so surrounding prose cannot join
    into a new shingle. Do not use the broader author-note removal heuristic.
    """
    from abook.text_processing import (
        CREDIT_LINE_PATTERN, CREDIT_WINDOW_LINES, CREDIT_TAIL_WINDOW_LINES,
        tail_credit_line,
    )

    lines = text.splitlines()
    filled = [i for i, line in enumerate(lines) if line.strip()]
    drop = {i for i in filled[:CREDIT_WINDOW_LINES] if CREDIT_LINE_PATTERN.match(lines[i].strip())}
    for i in reversed(filled[-CREDIT_TAIL_WINDOW_LINES:]):
        line = lines[i].strip()
        if not tail_credit_line(line):
            break
        drop.add(i)
    return "\n".join("\n" if i in drop else line for i, line in enumerate(lines))


def story_identity(relative: Path) -> str:
    """Book-folder identity shared by chapters, volumes and mirrored collections.

    Fold accents, separators and an optional numeric catalogue prefix. This
    merges spelling-equivalent folder names, not arbitrary translated titles.
    Unrecognized aliases remain a documented limitation of folder identities.
    """
    parts = relative.parts
    if parts[0] == "_full":
        book = parts[2]
    elif parts[0] in {"_dup", "_gold"}:
        folders = list(parts[1:-1])
        while len(folders) > 1 and (folders[0] == "model_eval_gold" or folders[0].startswith("gold_v")):
            folders.pop(0)
        book = folders[0]
    else:
        book = parts[0]
    return _title_key(re.sub(r"^\d+[-_]", "", book)).replace(" ", "")


def story_frequencies(hits: list[tuple[str, list[int]]]) -> dict[int, set[str]]:
    """Document frequency uses distinct books, never files or occurrences."""
    frequencies: dict[int, set[str]] = defaultdict(set)
    for relative, hashes in hits:
        book = story_identity(Path(relative))
        for value in hashes:
            frequencies[value].add(book)
    return dict(frequencies)


_INDEX: np.ndarray | None = None


@contextmanager
def windowless_workers():
    """Bypass the Windows venv redirector while retaining its environment.

    The redirector adds a process and breaks multiprocessing's PID/pipe handshake.
    Mirror multiprocessing's own venv launch, using the base windowless binary.
    Restore the caller's spawn executable and environment when the pool closes.
    """
    if os.name != "nt":
        yield
        return
    from multiprocessing import spawn

    executable = Path(sys._base_executable).with_name("pythonw.exe")
    if not executable.is_file():
        raise RuntimeError("A windowless Python interpreter is required for scanner workers")
    previous = spawn.get_executable()
    launcher = os.environ.get("__PYVENV_LAUNCHER__")
    multiprocessing.set_executable(str(executable))
    os.environ["__PYVENV_LAUNCHER__"] = sys.executable
    try:
        yield
    finally:
        multiprocessing.set_executable(previous)
        if launcher is None:
            os.environ.pop("__PYVENV_LAUNCHER__", None)
        else:
            os.environ["__PYVENV_LAUNCHER__"] = launcher


def _load_index(path: str) -> None:
    global _INDEX
    _INDEX = np.load(path, mmap_mode="r")


def _corpus_chunk(paths: list[str]) -> list[tuple[str, list[int]]]:
    """Trả (file Corpus, các hash chung) — chỉ hash, không chữ."""
    hits = []
    cache: dict = {}
    for name in paths:
        try:
            text = read_corpus_text(Path(name))
        except OSError:
            continue
        values = shingles(text, cache)
        if not values.size:
            continue
        position = np.searchsorted(_INDEX, values)
        position[position >= len(_INDEX)] = 0
        common = values[_INDEX[position] == values]
        if common.size:
            hits.append((name, sorted(set(int(v) for v in common))))
        if len(cache) > 2_000_000:
            cache.clear()
    return hits


def collect_corpus_matches(sources: dict[str, list[str]], root: Path, workdir: Path,
                           workers: int = 3) -> tuple[dict[int, set[str]], list[tuple[str, list[int]]], int]:
    """Intersect against every chapter; keep only matching hashes, never prose.

    Computing document frequency only for public candidate hashes is equivalent
    to filtering the complete private index, without materializing that index.
    """
    names = sorted(sources)
    values_parts, owner_parts = [], []
    for number, relative in enumerate(names):
        for chunk in sources[relative]:
            values = np.unique(shingles(chunk))
            values_parts.append(values)
            owner_parts.append(np.full(values.size, number, dtype=np.int32))
    if not values_parts:
        return {}, [], 0
    all_values = np.concatenate(values_parts)
    order = np.argsort(all_values, kind="stable")
    all_values, all_owners = all_values[order], np.concatenate(owner_parts)[order]
    index = np.unique(all_values)
    if not index.size:
        return {}, [], 0
    workdir.mkdir(parents=True, exist_ok=True)
    index_path = workdir / "repo_shingles.npy"
    np.save(index_path, index)
    files = [str(p) for p in corpus_files(root)]
    if not files:
        raise ValueError("Corpus exists but no readable source files were selected")
    batches = [files[i:i + 200] for i in range(0, len(files), 200)]
    matches = []
    with windowless_workers(), ProcessPoolExecutor(max_workers=min(3, max(1, workers)), initializer=_load_index,
                                                   initargs=(str(index_path),)) as pool:
        for batch_number, hits in enumerate(pool.map(_corpus_chunk, batches), 1):
            for corpus_file, common in hits:
                matches.append((Path(corpus_file).relative_to(root).as_posix(), common))
            if os.environ.get("ABOOK_LEAK_PROGRESS") == "1" and (batch_number % 50 == 0 or batch_number == len(batches)):
                print(f"public-leak Corpus: {min(batch_number * 200, len(files))}/{len(files)} files",
                      file=sys.stderr, flush=True)
    matching_values = np.array(sorted({h for _, hashes in matches for h in hashes}), dtype=np.uint64)
    start = np.searchsorted(all_values, matching_values, side="left")
    stop = np.searchsorted(all_values, matching_values, side="right")
    owners = {int(h): {names[owner] for owner in all_owners[a:b].tolist()}
              for h, a, b in zip(matching_values, start, stop)}
    return owners, matches, len(files)


def overlap_findings(owners: dict[int, set[str]], hits: list[tuple[str, list[int]]],
                     *, common_min: int = COMMON_STORY_MIN) -> list[dict]:
    frequencies = story_frequencies(hits)
    matches: dict[str, set[str]] = defaultdict(set)
    for relative, hashes in hits:
        for value in hashes:
            if len(frequencies[value]) < common_min:
                for owner in owners[value]:
                    matches[owner].add(relative)
    return [{"path": owner, "where": "corpus", "rule": f"shares>={SHINGLE}words",
             "corpus_files": sorted(found)[:5], "corpus_file_count": len(found),
             "corpus_story_count": len({story_identity(Path(p)) for p in found})}
            for owner, found in sorted(matches.items())]


def corpus_overlap(sources: dict[str, list[str]], root: Path, workdir: Path, workers: int = 3) -> list[dict]:
    owners, hits, _ = collect_corpus_matches(sources, root, workdir, workers)
    return overlap_findings(owners, hits)


def load_reviewed(path: Path = REVIEWED) -> dict[str, dict]:
    """Ngoại lệ đã duyệt từng file: ghim sha256, lý do riêng (không dùng chung một câu cho nhiều file)."""
    entries = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    reasons = [entry.get("reason", "").strip() for entry in entries.values()]
    if any(len(reason) < 20 for reason in reasons) or len(set(reasons)) != len(reasons):
        raise ValueError("public_leak_reviewed.json: mỗi mục cần lý do riêng, cụ thể (>= 20 ký tự, không trùng)")
    return entries


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def audit(repo: Path = REPO, corpus: Path | None | bool = True, workdir: Path | None = None) -> dict:
    names = tracked(repo)
    if not names:
        raise ValueError("public-leak: git không liệt kê file nào - không có gì đã được kiểm")
    reviewed = load_reviewed()
    findings: list[dict] = []
    sources: dict[str, list[str]] = {}
    for relative in names:
        path = repo / relative
        findings += inspect(relative, path)
        chunks = [text for _, text in texts(path)]
        if chunks:
            sources[relative] = chunks
    if not sources:
        raise ValueError("public-leak: no readable text files were inspected")
    root = corpus_root() if corpus is True else (corpus or None)
    if root is None:
        corpus_status = "bỏ qua kiểm Corpus: không thấy thư mục Corpus cục bộ (ABOOK_CORPUS)"
    else:
        work = workdir or (repo / "_internal/runtime/release_gate/public-leak")
        findings += corpus_overlap(sources, root, work, workers=max(1, int(os.environ.get("ABOOK_LEAK_WORKERS", "3"))))
        corpus_status = f"đã kiểm Corpus: {root}"
    stale = sorted(set(reviewed) - set(names))
    blocking = []
    waived = []
    for finding in findings:
        entry = reviewed.get(finding["path"])
        if entry and entry.get("sha256") == digest(repo / finding["path"]) and finding["rule"] != f"shares>={SHINGLE}words":
            waived.append(finding)
        else:
            blocking.append(finding)
    return {"files": len(names), "text_files": len(sources), "corpus": corpus_status, "findings": blocking,
            "waived": len(waived), "stale_reviewed": stale}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-corpus", action="store_true", help="chỉ (a)/(b); in rõ là đã bỏ qua Corpus")
    args = parser.parse_args(argv)
    result = audit(corpus=False if args.no_corpus else True)
    if args.no_corpus:
        result["corpus"] = "bỏ qua kiểm Corpus: --no-corpus"
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["corpus"])
        for finding in result["findings"]:
            print(f"{finding['path']} [{finding['rule']}] {finding['where']}")
        print(f"{result['files']} file, {len(result['findings'])} chỗ nghi, {result['waived']} đã duyệt")
    return 1 if result["findings"] or result["stale_reviewed"] else 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO / "_internal"))
    sys.exit(main())
