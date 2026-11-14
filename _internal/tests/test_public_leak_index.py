"""Cache equivalence and invalidation use original, generated workshop prose."""
import json
import os
from pathlib import Path

import numpy as np
import pytest

from scripts import public_leak_index as index
from scripts import public_leak_scan as scan


def prose(prefix):
    return " ".join(prefix + chr(97 + i) for i in range(16))


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    monkeypatch.setenv("ABOOK_RUNTIME", str(tmp_path / "runtime"))
    root = tmp_path / "corpus"
    root.mkdir()
    return root


def chapter(root, book, name, text):
    path = root / book / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def reference(sources, corpus):
    """Original candidate intersection without process startup or disk cache."""
    candidates = np.unique(np.concatenate([scan.shingles(s) for chunks in sources.values() for s in chunks]))
    scan._INDEX = candidates
    hits = [(Path(p).relative_to(corpus).as_posix(), values)
            for p, values in scan._corpus_chunk([str(p) for p in scan.corpus_files(corpus)])]
    owners = {}
    for name, chunks in sources.items():
        for chunk in chunks:
            for h in scan.shingles(chunk):
                owners.setdefault(int(h), set()).add(name)
    return scan.overlap_findings(owners, hits)


def cached(sources, corpus, tmp_path):
    return scan.corpus_overlap(sources, corpus, tmp_path / "work", workers=1)


def test_cold_warm_and_new_public_candidates_equal_reference(corpus, tmp_path, monkeypatch):
    a, b, shared = prose("anvil"), prose("copper"), prose("workshop")
    for book in ("A", "B", "C"):
        chapter(corpus, book, "001.txt", shared)
    chapter(corpus, "A", "002.txt", a)
    chapter(corpus, "B", "002.txt", b)
    sources = {"one.txt": [a, shared], "two.txt": [a]}
    expected = reference(sources, corpus)
    assert cached(sources, corpus, tmp_path) == expected
    monkeypatch.setattr(scan, "read_corpus_text", lambda _: pytest.fail("Warm lookup reread chapter text"))
    assert cached(sources, corpus, tmp_path) == expected
    # Cache is independent of the public candidates used to build it.
    assert [r["path"] for r in cached({"new.txt": [b]}, corpus, tmp_path)] == ["new.txt"]
    directory = index.cache_directory(corpus, tmp_path / "work")
    data = b"".join(p.read_bytes() for p in directory.iterdir() if p.is_file())
    assert all(s.encode() not in data for s in (a, b, shared))
    manifest = json.loads((directory / "manifest.json").read_text())
    assert all(len(key) == 64 for key in manifest["files"])


def test_edit_add_delete_only_hashes_changed_chapters_and_recomputes_k(corpus, tmp_path, monkeypatch):
    common, other = prose("lathe"), prose("flute")
    first = chapter(corpus, "A", "001.txt", common)
    second = chapter(corpus, "B", "001.txt", common)
    third = chapter(corpus, "C", "001.txt", common)
    sources = {"public.txt": [common, other]}
    assert cached(sources, corpus, tmp_path) == []
    read = scan.read_corpus_text
    observed = []

    def record(path):
        observed.append(path)
        return read(path)

    monkeypatch.setattr(scan, "read_corpus_text", record)
    third.unlink()
    write = index._write_shard
    monkeypatch.setattr(index, "_write_shard", lambda *args: pytest.fail("Delete rewrote index postings"))
    assert len(cached(sources, corpus, tmp_path)) == 1
    assert observed == []
    monkeypatch.setattr(index, "_write_shard", write)
    directory = index.cache_directory(corpus, tmp_path / "work")
    original = {p: p.read_bytes() for p in directory.glob("*.bin")}
    size = first.stat().st_size
    first.write_text(other, encoding="utf-8")
    assert first.stat().st_size == size
    os.utime(first, ns=(first.stat().st_atime_ns, first.stat().st_mtime_ns + 1_000_000))
    added = chapter(corpus, "D", "002.txt", other)
    actual = cached(sources, corpus, tmp_path)
    assert set(observed) == {first, added}
    assert second not in observed
    assert actual == reference(sources, corpus)
    assert all(p.read_bytes() == data for p, data in original.items())


def test_deleted_file_ids_are_never_reused_by_a_later_addition(corpus, tmp_path):
    chapter(corpus, "A", "001.txt", prose("keeper"))
    removed = chapter(corpus, "B", "001.txt", prose("erased"))
    sources = {"public.txt": [prose("erased")]}
    assert cached(sources, corpus, tmp_path)
    removed.unlink()
    assert cached(sources, corpus, tmp_path) == []
    chapter(corpus, "C", "001.txt", prose("unseen"))
    assert cached(sources, corpus, tmp_path) == []


@pytest.mark.parametrize("damage", ["manifest", "shard", "missing", "version", "unreadable"])
def test_corrupt_or_incompatible_cache_rebuilds(corpus, tmp_path, monkeypatch, damage):
    text = prose("rivets")
    path = chapter(corpus, "A", "001.txt", text)
    sources = {"public.txt": [text]}
    expected = cached(sources, corpus, tmp_path)
    directory = index.cache_directory(corpus, tmp_path / "work")
    manifest = directory / "manifest.json"
    if damage == "manifest":
        manifest.write_bytes(b"broken")
    elif damage in {"shard", "missing"}:
        target = next(directory / entry["name"] for segments in json.loads(manifest.read_text())["shards"]
                      for entry in segments
                      if (directory / entry["name"]).stat().st_size)
        if damage == "missing":
            target.unlink()
        else:
            data = bytearray(target.read_bytes())
            data[0] ^= 1
            target.write_bytes(data)
    elif damage == "version":
        monkeypatch.setattr(index, "ALGORITHM_VERSION", "synthetic-next-version")
    else:
        read_shard = index._read_shard
        attempts = []

        def unreadable_once(*args):
            attempts.append(1)
            if len(attempts) == 1:
                raise PermissionError("synthetic unreadable cache")
            return read_shard(*args)

        monkeypatch.setattr(index, "_read_shard", unreadable_once)
    seen = []
    read = scan.read_corpus_text
    monkeypatch.setattr(scan, "read_corpus_text", lambda p: (seen.append(p), read(p))[1])
    assert cached(sources, corpus, tmp_path) == expected
    assert seen == [path]


def test_failed_publish_preserves_previous_generation(corpus, tmp_path, monkeypatch):
    text = prose("pliers")
    chapter(corpus, "A", "001.txt", text)
    sources = {"public.txt": [text]}
    expected = cached(sources, corpus, tmp_path)
    chapter(corpus, "B", "002.txt", prose("clamps"))
    replace = index.os.replace

    def fail_manifest(source, target):
        if Path(target).name == "manifest.json":
            raise OSError("synthetic interrupted publication")
        return replace(source, target)

    monkeypatch.setattr(index.os, "replace", fail_manifest)
    with pytest.raises(OSError, match="interrupted"):
        cached(sources, corpus, tmp_path)
    monkeypatch.setattr(index.os, "replace", replace)
    assert cached(sources, corpus, tmp_path) == expected


def test_chapter_read_error_fails_instead_of_publishing_empty_index(corpus, tmp_path, monkeypatch):
    text = prose("bolts")
    chapter(corpus, "A", "001.txt", text)
    monkeypatch.setattr(scan, "read_corpus_text", lambda _: (_ for _ in ()).throw(PermissionError("synthetic")))
    with pytest.raises(PermissionError):
        cached({"public.txt": [text]}, corpus, tmp_path)
    assert not (index.cache_directory(corpus, tmp_path / "work") / "manifest.json").exists()


def test_worker_budget_requires_memory_and_caps_coordinator_plus_workers(monkeypatch):
    import psutil
    from types import SimpleNamespace
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=5 * 1024**3))
    with pytest.raises(RuntimeError, match="6 GiB"):
        index._worker_count(32)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=12 * 1024**3))
    assert 1 <= index._worker_count(32) <= 3
