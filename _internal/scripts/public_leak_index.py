"""Persistent, hash-only Corpus postings used by the public leak scanner.

The manifest stores hashed relative paths, size, mtime_ns, file IDs and hashed
book identities. Sorted postings map every shingle to files (and hence books).
Keep common shingles too: deleting a book can make a common formula blocking.
No chapter text, tokens, titles or absolute Corpus paths are written here.
"""
from __future__ import annotations

from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

import numpy as np

# Bump for any change to inventory, decoding, credits, tokenization, shingling,
# book identity or common-book filtering, including imported credit rules.
ALGORITHM_VERSION = "corpus-postings-v2-k3"
SHARDS = 256
POSTING = np.dtype([("hash", "<u8"), ("file", "<u4")])


def _progress(message):
    if os.environ.get("ABOOK_LEAK_PROGRESS") == "1":
        print("public-leak index: " + message, file=sys.stderr, flush=True)


def _scanner():
    try:
        from scripts import public_leak_scan
    except ModuleNotFoundError:
        import public_leak_scan
    return public_leak_scan


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def cache_directory(root: Path, workdir: Path) -> Path:
    runtime = os.environ.get("ABOOK_RUNTIME")
    # Explicit runtime is shared across worktrees. Standalone callers/tests use
    # their private work directory rather than another checkout's cache.
    base = Path(runtime) / "cache/public_leak_index" if runtime else workdir / "corpus-index"
    return base / _hash(str(root.resolve()))


@contextmanager
def _lock(directory: Path):
    """Serialize readers/writers so abandoned generations can be safely removed."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "index.lock").open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            if not handle.tell():
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            # LK_LOCK only retries ten times; use an explicit blocking loop.
            import time
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.2)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _inventory(root: Path):
    scan = _scanner()
    files = scan.corpus_files(root)
    if not files:
        raise ValueError("Corpus exists but no readable source files were selected")
    records, paths, books = {}, {}, {}
    for path in files:
        relative = path.relative_to(root)
        key = _hash(relative.as_posix())
        stat = path.stat()
        parent = relative.parent
        if parent not in books:
            books[parent] = _hash(scan.story_identity(relative))
        records[key] = [stat.st_size, stat.st_mtime_ns, books[parent]]
        paths[key] = path
    return records, paths


def _read_manifest(directory: Path):
    try:
        value = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if value["algorithm"] != ALGORITHM_VERSION or len(value["shards"]) != SHARDS:
            return None
        files = value["files"]
        ids = []
        for key, record in files.items():
            if len(key) != 64 or len(record) != 4 or len(record[2]) != 64:
                return None
            if any(type(record[i]) is not int or record[i] < 0 for i in (0, 1, 3)):
                return None
            ids.append(record[3])
        if len(set(ids)) != len(ids) or any(i >= 2**32 for i in ids):
            return None
        if type(value["next_id"]) is not int or not max(ids, default=-1) < value["next_id"] <= 2**32:
            return None
        for segments in value["shards"]:
            for shard in segments:
                # Never follow paths supplied by a damaged manifest.
                if (not isinstance(shard["name"], str) or Path(shard["name"]).name != shard["name"]
                        or not shard["name"].endswith(".bin") or len(shard["sha256"]) != 64):
                    return None
        payload = json.dumps({k: value[k] for k in ("algorithm", "files", "shards", "next_id")},
                             sort_keys=True, separators=(",", ":")).encode()
        if hashlib.sha256(payload).hexdigest() != value["sha256"]:
            return None
        return value
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _read_shard(directory: Path, entry: dict) -> np.ndarray:
    data = (directory / entry["name"]).read_bytes()
    if len(data) % POSTING.itemsize or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("Invalid Corpus index shard checksum")
    return np.frombuffer(data, dtype=POSTING)


def _write_shard(directory: Path, generation: str, number: int, records: np.ndarray) -> dict:
    name = f"{generation}-{number:02x}.bin"
    target = directory / name
    temporary = target.with_suffix(".tmp")
    data = records.tobytes()
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    return {"name": name, "sha256": hashlib.sha256(data).hexdigest()}


def _build_lane(task):
    """Hash changed chapters once; each worker owns its temporary shard files."""
    lane, tasks = task
    scan = _scanner()
    cache, pending = {}, []
    handles = {}

    def flush():
        if not pending:
            return
        rows = np.concatenate(pending)
        pending.clear()
        rows = rows[np.argsort(rows["hash"])]
        buckets = (rows["hash"] >> np.uint64(56)).astype(np.uint8)
        edges = np.r_[0, np.flatnonzero(buckets[1:] != buckets[:-1]) + 1, len(rows)]
        for a, b in zip(edges[:-1], edges[1:]):
            number = int(buckets[a])
            if number not in handles:
                handles[number] = (Path(lane) / f"{number:02x}.bin").open("wb")
            handles[number].write(rows[a:b].tobytes())

    try:
        for offset, (file_id, name, size, mtime) in enumerate(tasks, 1):
            path = Path(name)
            values = np.unique(scan.shingles(scan.read_corpus_text(path), cache))
            stat = path.stat()
            if (stat.st_size, stat.st_mtime_ns) != (size, mtime):
                raise ValueError("Corpus changed while hashing; retry the scan")
            if values.size:
                rows = np.empty(values.size, dtype=POSTING)
                rows["hash"], rows["file"] = values, file_id
                pending.append(rows)
            if offset % 200 == 0:
                flush()
            if offset % 10000 == 0 or offset == len(tasks):
                _progress(f"worker {Path(lane).name}: {offset}/{len(tasks)} chapters")
            if len(cache) > 2_000_000:
                cache.clear()
        flush()
    finally:
        for handle in handles.values():
            handle.close()
    return len(tasks)


def _worker_count(requested: int) -> int:
    import psutil
    available = psutil.virtual_memory().available
    if available < 6 * 1024**3:
        raise RuntimeError("Corpus indexing requires at least 6 GiB available RAM")
    return min(3, max(1, requested), max(1, (os.cpu_count() or 1) - 1),
               max(1, int((available - 4 * 1024**3) // (2 * 1024**3))))


def _publish(directory: Path, files: dict, shards: list, next_id: int):
    value = {"algorithm": ALGORITHM_VERSION, "files": files, "shards": shards, "next_id": next_id}
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    value["sha256"] = hashlib.sha256(payload).hexdigest()
    temporary = directory / "manifest.tmp"
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, separators=(",", ":"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, directory / "manifest.json")
    return value


def _update(directory: Path, inventory: dict, paths: dict, old, workers: int):
    previous = old["files"] if old else {}
    files = {}
    # IDs are never reused: deleted files can still have immutable postings in
    # older segments. Only IDs in the current manifest participate in lookup.
    next_id = old["next_id"] if old else 0
    changed = []
    removed = {r[3] for key, r in previous.items() if key not in inventory or r[:3] != inventory[key]}
    for key, record in inventory.items():
        if key in previous and previous[key][:3] == record:
            files[key] = previous[key]
        else:
            if next_id >= 2**32:
                raise ValueError("Corpus file ID limit exceeded; remove the private cache and retry")
            files[key] = [*record, next_id]
            changed.append((next_id, str(paths[key]), record[0], record[1]))
            next_id += 1
    scan = _scanner()
    generation = uuid.uuid4().hex
    _progress(f"hashing {len(changed)} changed/new chapters; removing {len(removed)} old file IDs")
    with tempfile.TemporaryDirectory(prefix="build-", dir=directory) as temporary:
        lanes = []
        if changed:
            # Small synthetic corpora do not benefit from process startup.
            count = _worker_count(workers) if len(changed) >= 200 else 1
            for number in range(count):
                lane = Path(temporary) / str(number)
                lane.mkdir()
                lanes.append(lane)
            tasks = [(str(lane), changed[n::count]) for n, lane in enumerate(lanes)]
            if count == 1:
                _build_lane(tasks[0])
            else:
                with scan.windowless_workers(), ProcessPoolExecutor(max_workers=count) as pool:
                    list(pool.map(_build_lane, tasks))
        shards = []
        for number in range(SHARDS):
            parts = []
            for lane in lanes:
                path = lane / f"{number:02x}.bin"
                if path.exists():
                    parts.append(np.fromfile(path, dtype=POSTING))
            # Append only changed chapters. Existing postings remain immutable;
            # the live file-ID map removes edits/deletions without rewriting the
            # full index. Even a delete-only update performs no shard writes.
            segments = list(old["shards"][number]) if old else []
            if parts:
                rows = np.concatenate(parts)
                rows = rows[np.argsort(rows["hash"], kind="stable")]
                segments.append(_write_shard(directory, generation, number, rows))
            shards.append(segments)
            if (number + 1) % 32 == 0:
                _progress(f"published shard data {number + 1}/{SHARDS}")
    return files, shards, next_id


def _query(directory: Path, manifest: dict, candidates: np.ndarray, paths: dict):
    matches = {}
    buckets = candidates >> np.uint64(56)
    for number, segments in enumerate(manifest["shards"]):
        wanted = candidates[buckets == number]
        for entry in segments:
            # Verify every byte even when this shard has no public candidates.
            rows = _read_shard(directory, entry)
            if not len(wanted) or not len(rows):
                continue
            starts = np.searchsorted(rows["hash"], wanted, side="left")
            stops = np.searchsorted(rows["hash"], wanted, side="right")
            for value, a, b in zip(wanted, starts, stops):
                for file_id in rows["file"][a:b]:
                    if int(file_id) in paths:
                        matches.setdefault(int(file_id), []).append(int(value))
    return [(paths[file_id], hashes) for file_id, hashes in sorted(matches.items())]


def collect(candidates: np.ndarray, root: Path, workdir: Path, workers: int):
    directory = cache_directory(root, workdir)
    with _lock(directory):
        inventory, paths = _inventory(root)
        old = _read_manifest(directory)
        unchanged = old is not None and {k: v[:3] for k, v in old["files"].items()} == inventory
        # Verify during lookup on the warm path, avoiding a second full read.
        # A damaged shard invalidates the generation, never means no overlap.
        hits = None
        if unchanged:
            try:
                by_id = {old["files"][key][3]: path.relative_to(root).as_posix() for key, path in paths.items()}
                hits = _query(directory, old, candidates, by_id)
            except (OSError, ValueError):
                old = None
        elif old:
            try:
                for segments in old["shards"]:
                    for entry in segments:
                        _read_shard(directory, entry)
            except (OSError, ValueError):
                old = None
        if hits is None:
            files, shards, next_id = _update(directory, inventory, paths, old, workers)
            # Detect changed, added and deleted chapters during a long build.
            if _inventory(root)[0] != inventory:
                raise ValueError("Corpus changed while indexing; retry the scan")
            old = _publish(directory, files, shards, next_id)
            by_id = {old["files"][key][3]: path.relative_to(root).as_posix() for key, path in paths.items()}
            hits = _query(directory, old, candidates, by_id)
        live = {entry["name"] for segments in old["shards"] for entry in segments}
        for path in directory.glob("*.bin"):
            if path.name not in live:
                path.unlink()
        return hits, len(inventory)
