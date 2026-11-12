"""Regression checks for the public-source guard. No model or audio generation."""
from __future__ import annotations

import hashlib
import json
import subprocess

from scripts import leak_scan


def test_corpus_uses_seven_words_and_original_audit_directory_rules(tmp_path):
    corpus = tmp_path / "Corpus"
    book = corpus / "Invented manual"
    book.mkdir(parents=True)
    sentence = "Hộp men tím chứa chín nhãn đồng màu lam."
    (book / "01.txt").write_text(sentence, encoding="utf-8")
    ignored = corpus / "_gold"
    ignored.mkdir()
    private = "Bảy khay sứ đỏ xếp sát ngăn tủ vải."
    (ignored / "note.txt").write_text(private, encoding="utf-8")
    files = [("docs/example.md", sentence), ("test.py", private)]
    assert [(p, n, k) for p, n, k, _ in leak_scan.scan_corpus(files, corpus)] == [
        ("docs/example.md", 1, "corpus")
    ]
    assert not leak_scan.scan_corpus([("short.txt", "Hộp men tím chứa chín nhãn")], corpus)


def test_escaped_and_unaccented_copies_are_still_copies(tmp_path):
    corpus = tmp_path / "Corpus"
    book = corpus / "Invented manual"
    book.mkdir(parents=True)
    sentence = "Hộp men tím chứa chín nhãn đồng màu lam."
    (book / "01.txt").write_text(sentence, encoding="utf-8")
    escaped = sentence.encode("ascii", "backslashreplace").decode("ascii")
    assert escaped != sentence and "\\u" in escaped
    bare = "hop men tim chua chin nhan dong mau lam"
    files = [("escaped.py", f'book = "{escaped}"'), ("bare.md", bare), ("other.md", "hop men tim chua bay nhan xanh")]
    assert sorted(p for p, _, _, _ in leak_scan.scan_corpus(files, corpus)) == ["bare.md", "escaped.py"]


def test_reviewed_ipa_files_are_exact_paths():
    text = " ".join(["k" + chr(0x259)] * 8)
    named = sorted(leak_scan.IPA_REVIEWED_FILES)[0]
    files = [(named, text), (named + ".copy", text)]
    pending, reviewed = leak_scan.apply_reviews(files, leak_scan.scan_ipa(files))
    assert [p for p, _, _, _ in reviewed] == [named]
    assert [p for p, _, _, _ in pending] == [named + ".copy"]


def test_ipa_threshold_and_review_is_bound_to_exact_line():
    text = " ".join(["k" + chr(0x259)] * 8)
    assert not leak_scan.scan_ipa([("a.txt", " ".join(text.split()[:7]))])
    assert leak_scan.scan_ipa([("a.txt", text)])
    review = {"entries": [{
        "kind": "ipa", "path": "a.txt",
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "reason": "Synthetic threshold fixture",
    }]}
    files = [("a.txt", text + "\n" + text + " p"), (leak_scan.ALLOWLIST_PATH, json.dumps(review))]
    pending, reviewed = leak_scan.apply_reviews(files, leak_scan.scan_ipa(files))
    assert len(pending) == len(reviewed) == 1
    assert pending[0][1] == 2


def test_machine_name_is_read_at_runtime_and_private_ranges_are_checked(monkeypatch):
    monkeypatch.setenv("COMPUTERNAME", "Fixture" + "-Workstation")
    monkeypatch.setenv("HOSTNAME", "Fixture" + "-Workstation")
    monkeypatch.setattr(leak_scan.socket, "gethostname", lambda: "localhost")
    monkeypatch.setattr(leak_scan.socket, "getaddrinfo", lambda *a: [])
    real_tail = ".".join(map(str, (100, 80, 20, 30)))
    real_lan = ".".join(map(str, (192, 168, 88, 99)))
    findings = leak_scan.scan_machine([("a.txt", "\n".join([
        "Fixture" + "-Workstation", real_tail, real_lan, "100.64.0.1", "192.0.2.7",
    ]))])
    assert [n for _, n, _, _ in findings] == [1, 2, 3]


def test_absent_corpus_prints_skip_but_still_checks_machine(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(leak_scan, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(leak_scan, "tracked_files", lambda *a: [("a.txt", "nothing private")])
    monkeypatch.setattr(leak_scan, "default_corpus", lambda *a: None)
    assert leak_scan.main([]) == 0
    assert "SKIPPED - no private corpus found" in capsys.readouterr().err


def test_revision_reader_scans_committed_bytes_instead_of_checkout(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "sample.txt"
    source.write_text("committed bytes", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "sample.txt"], check=True)
    subprocess.run([
        "git", "-C", str(tmp_path), "-c", "user.name=Fixture",
        "-c", "user.email=fixture@example.org", "commit", "-qm", "Add fixture",
    ], check=True)
    source.write_text("uncommitted bytes", encoding="utf-8")
    assert leak_scan.tracked_files(tmp_path, "HEAD") == [("sample.txt", "committed bytes")]


def test_public_tree_has_no_private_text():
    # main() prints an explicit skip if the independent Corpus is not present.
    assert leak_scan.main([]) == 0


def test_listed_audio_counts_until_its_bytes_change(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF old")
    blob = subprocess.run(["git", "-C", str(tmp_path), "hash-object", "a.wav"],
                          capture_output=True, text=True, check=True).stdout.strip()
    inventory = json.dumps({"entries": [{"path": "a.wav", "blob": blob, "reason": "fixture"}]})
    files = [(leak_scan.PENDING_AUDIO_PATH, inventory)]
    assert leak_scan.pending_audio(tmp_path, files, None) == ["a.wav"]
    subprocess.run(["git", "-C", str(tmp_path), "add", "a.wav"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.org",
                    "commit", "-qm", "Add fixture"], check=True)
    assert leak_scan.pending_audio(tmp_path, files, "HEAD") == ["a.wav"]
    wav.write_bytes(b"RIFF regenerated")
    assert leak_scan.pending_audio(tmp_path, files, None) == []
