"""Quét mọi file git theo dõi (sẽ được đẩy/phát hành) tìm chữ truyện và phiên âm câu bị rò.

Ba phép thử, chỉ in đường dẫn và vị trí, không bao giờ in nội dung bị nghi:
  (a) phiên âm/IPA: >= 8 âm tiết phiên âm liền nhau trong một chuỗi;
  (b) đoạn văn tiếng Việt dài trong fixture/chuỗi test (>= LONG_VI_WORDS chữ, có dấu tiếng Việt);
  (c) chung một đoạn SHINGLE chữ liên tiếp với Corpus cục bộ (nếu có mặt). Corpus vắng thì in rõ là đã bỏ qua.

Chạy từ _internal: runtime/.venv/Scripts/python.exe -X utf8 scripts/public_leak_scan.py [--json]
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import io
import json
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
CODE_SUFFIXES = {".py", ".kt", ".java", ".ts", ".tsx", ".js", ".mjs", ".qml", ".cpp", ".h"}
PRIME = np.uint64(1099511628211)


def tracked(repo: Path = REPO) -> list[str]:
    names = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           capture_output=True, check=True).stdout.decode("utf-8").split("\0")
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
    normalized = re.sub(r"[\\/]+", "/", text).lower()
    # Assemble the signatures so the detector's source is subject to the same empty exception list.
    return ("c:" + "/users/" in normalized
            or "/".join(("appdata", "local", "temp", "claude")) in normalized)


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
    if b"\0" in data[:8192]:
        return []
    try:
        return [("", data.decode("utf-8-sig"))]
    except UnicodeDecodeError:
        return []


def strings_of(relative: str, text: str) -> list[tuple[str, str]]:
    """Các chuỗi để soi: giá trị chuỗi JSON, hay chuỗi trong code, hay từng dòng."""
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
    fixture = is_fixture(relative)
    for member, text in texts(path):
        for where, value in strings_of(member or relative, text):
            rule = "ipa>=8" if ipa_run(value) else "long-vietnamese" if fixture and long_vietnamese(value) else ""
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
    """Hash 64-bit ổn định (giữa các process) của mọi cụm SHINGLE chữ liên tiếp, chữ thường."""
    cache = {} if cache is None else cache
    words = WORD.findall(unicodedata.normalize("NFC", text).lower())
    if len(words) < SHINGLE:
        return np.empty(0, dtype=np.uint64)
    hashes = np.fromiter((_word_hash(w, cache) for w in words), dtype=np.uint64, count=len(words))
    count = len(words) - SHINGLE + 1
    combined = np.zeros(count, dtype=np.uint64)
    with np.errstate(over="ignore"):
        for offset in range(SHINGLE):
            combined = combined * PRIME + hashes[offset:offset + count]
    return combined


def corpus_root() -> Path | None:
    candidates = [os.environ.get("ABOOK_CORPUS", ""), str(REPO / "Corpus"), str(REPO.parent / "ABook" / "Corpus")]
    return next((Path(c) for c in candidates if c and Path(c).is_dir()), None)


def corpus_files(root: Path) -> list[Path]:
    found = []
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = [d for d in subdirs if d.lower() not in CORPUS_SKIP_DIRS and not d.lower().endswith(".dist-info")]
        for name in files:
            if Path(name).suffix.lower() in CORPUS_SUFFIXES and not re.match(r"(license|copying|requirements|readme)", name, re.I):
                found.append(Path(directory) / name)
    return sorted(found)


_INDEX: np.ndarray | None = None


def _load_index(path: str) -> None:
    global _INDEX
    _INDEX = np.load(path)


def _corpus_chunk(paths: list[str]) -> list[tuple[str, list[int]]]:
    """Trả (file Corpus, các hash chung) — chỉ hash, không chữ."""
    hits = []
    cache: dict = {}
    for name in paths:
        try:
            text = Path(name).read_text(encoding="utf-8", errors="ignore")
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


def corpus_overlap(sources: dict[str, list[str]], root: Path, workdir: Path, workers: int = 3) -> list[dict]:
    """sources: đường dẫn repo -> các đoạn chữ. Trả mỗi file repo chung >= 1 cụm SHINGLE chữ với Corpus."""
    names = sorted(sources)
    values_parts, owner_parts = [], []
    for number, relative in enumerate(names):
        for chunk in sources[relative]:
            values = np.unique(shingles(chunk))
            values_parts.append(values)
            owner_parts.append(np.full(values.size, number, dtype=np.int32))
    if not values_parts:
        return []
    all_values = np.concatenate(values_parts)
    order = np.argsort(all_values, kind="stable")
    all_values, all_owners = all_values[order], np.concatenate(owner_parts)[order]
    index = np.unique(all_values)
    if not index.size:
        return []
    workdir.mkdir(parents=True, exist_ok=True)
    index_path = workdir / "repo_shingles.npy"
    np.save(index_path, index)
    files = [str(p) for p in corpus_files(root)]
    if not files:
        raise ValueError("Corpus exists but no readable source files were selected")
    batches = [files[i:i + 200] for i in range(0, len(files), 200)]
    matches: dict[str, set[str]] = {}
    with ProcessPoolExecutor(max_workers=max(1, workers), initializer=_load_index, initargs=(str(index_path),)) as pool:
        for hits in pool.map(_corpus_chunk, batches):
            for corpus_file, common in hits:
                found = np.asarray(common, dtype=np.uint64)
                start = np.searchsorted(all_values, found, side="left")
                stop = np.searchsorted(all_values, found, side="right")
                for a, b in zip(start.tolist(), stop.tolist()):
                    for owner in set(all_owners[a:b].tolist()):
                        matches.setdefault(names[owner], set()).add(os.path.relpath(corpus_file, root))
    return [{"path": owner, "where": "corpus", "rule": f"shares>={SHINGLE}words",
             "corpus_files": sorted(found)[:5], "corpus_file_count": len(found)} for owner, found in sorted(matches.items())]


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
    root = corpus_root() if corpus is True else (corpus or None)
    if root is None:
        corpus_status = "bỏ qua kiểm Corpus: không thấy thư mục Corpus cục bộ (ABOOK_CORPUS)"
    else:
        work = workdir or (repo / "_internal/runtime/release_gate/public-leak")
        findings += corpus_overlap(sources, root, work)
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
    sys.exit(main())
