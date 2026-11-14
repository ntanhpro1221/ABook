"""The public scanner must inspect resources, inline test strings and documentation."""
from pathlib import Path

import pytest

from scripts import public_leak_scan as scan


@pytest.mark.parametrize("relative", ["tests/data/sample.json", "fixtures/a.txt",
    "mobile/android/app/src/test/resources/a.json", "tests/test_inline.py", "docs/example.md"])
def test_ipa_and_long_text_in_every_public_surface(tmp_path, relative):
    path = tmp_path / "sample"
    path.write_text('"' + " ".join(["kəː"] * 8) + '"', encoding="utf-8")
    assert any(f["rule"] == "ipa>=8" for f in scan.inspect(relative, path))
    path.write_text('"' + " ".join(["thử"] * 40) + '"', encoding="utf-8")
    assert any(f["rule"] == "long-vietnamese" for f in scan.inspect(relative, path))
    assert not scan.ipa_run(" ".join(["kəː"] * 7))


def test_sentence_cannot_be_hidden_in_a_json_array(tmp_path):
    import json
    path = tmp_path / "sample.json"
    path.write_text(json.dumps({"phones": ["kəː"] * 8}), encoding="utf-8")
    assert scan.inspect("sample.json", path)


def test_multiline_and_implicit_python_literal_joining_are_checked(tmp_path):
    path = tmp_path / "sample.py"
    path.write_text('value = ("' + " ".join(["kəː"] * 4) + ' "\n"' + " ".join(["kəː"] * 4) + '")', encoding="utf-8")
    assert scan.inspect("tests/test_multiline.py", path)
    path.write_text(('thử ' * 20) + '\n' + ('thử ' * 20), encoding="utf-8")
    assert scan.inspect("docs/long.md", path)


def test_binary_metadata_and_utf16_paths_are_not_exempt(tmp_path):
    path = tmp_path / "metadata.bin"
    value = "C:" + "/Users/Example"
    for data in (b"\0metadata" + value.encode(), value.encode("utf-16")):
        path.write_bytes(data)
        assert scan.private_file(path)


@pytest.mark.parametrize("slash", ["/", "\\", "\\\\"])
def test_private_path_signatures_have_no_exceptions(slash):
    assert scan.private_path("C:" + slash + "Users" + slash + "Example")
    assert scan.private_path(slash.join(["AppData", "Local", "Temp", "claude", "session"]))
    assert not scan.private_path("C:/Profiles/Example")


def test_corpus_exact_eight_word_overlap_and_no_plaintext_evidence(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sentence = " ".join("synthetic" + chr(97 + i) for i in range(12))
    (corpus / "Some Book").mkdir()
    (corpus / "Some Book" / "001.txt").write_text(sentence, encoding="utf-8")
    result = scan.corpus_overlap({"docs/a.md": [sentence], "short.py": [" ".join(sentence.split()[:7])]},
                                 corpus, tmp_path / "index", workers=1)
    assert [r["path"] for r in result] == ["docs/a.md"]
    assert sentence not in str(result)


def test_empty_inventory_fails_and_missing_corpus_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(scan, "tracked", lambda _: [])
    with pytest.raises(ValueError, match="git"):
        scan.audit(tmp_path, corpus=False)
    (tmp_path / "safe.txt").write_text("synthetic fixture", encoding="utf-8")
    monkeypatch.setattr(scan, "tracked", lambda _: ["safe.txt"])
    result = scan.audit(tmp_path, corpus=False)
    assert result["files"] == 1 and "bỏ qua kiểm Corpus" in result["corpus"]


def test_public_git_files_contain_no_private_machine_or_session_path():
    findings = [name for name in scan.tracked() if scan.private_file(scan.REPO / name)]
    assert findings == [], findings


def test_reviewed_bytes_must_match_and_corpus_overlap_cannot_be_waived(tmp_path, monkeypatch):
    name = "synthetic.json"
    path = tmp_path / name
    content = '"' + " ".join(["kəː"] * 8) + '"'
    path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(scan, "tracked", lambda _: [name])
    monkeypatch.setattr(scan, "load_reviewed", lambda: {
        name: {"sha256": scan.digest(path), "reason": "Synthetic phoneme test for hash validation"},
    })
    pinned = scan.load_reviewed()
    monkeypatch.setattr(scan, "load_reviewed", lambda: pinned)
    result = scan.audit(tmp_path, corpus=False)
    assert result["waived"] == 1 and result["findings"] == []
    path.write_text(content + " ", encoding="utf-8")
    assert scan.audit(tmp_path, corpus=False)["findings"]
    path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(scan, "corpus_overlap", lambda *a, **k: [
        {"path": name, "rule": f"shares>={scan.SHINGLE}words", "where": "synthetic", "count": 1},
    ])
    result = scan.audit(tmp_path, corpus=tmp_path)
    assert [r["rule"] for r in result["findings"]] == [f"shares>={scan.SHINGLE}words"]


def test_non_story_folders_at_corpus_root_are_not_indexed(tmp_path):
    for folder in ("claude/memory", "releases/android/0.1.0", "research/tn", "S/x", "keys"):
        (tmp_path / folder).mkdir(parents=True)
        (tmp_path / folder / "note.md").write_text("app strings and identifiers", encoding="utf-8")
    (tmp_path / "Some Book" / "claude").mkdir(parents=True)
    (tmp_path / "Some Book" / "claude" / "ch1.txt").write_text("story", encoding="utf-8")
    (tmp_path / "Some Book" / "ch2.txt").write_text("story", encoding="utf-8")
    found = [p.relative_to(tmp_path).as_posix() for p in scan.corpus_files(tmp_path)]
    assert found == ["Some Book/ch2.txt", "Some Book/claude/ch1.txt"]


@pytest.mark.parametrize("relative", [
    "Book/001.txt", "Book/014a.txt", "Book/[001] synthetic chapter.txt",
    "Book/chapter-12.md", "Book/Chương 12.txt",
    "_full/truyen/123-book/000.txt", "_full/ai-dich/123-book/001.txt",
    "_full/sang-tac/Book/002.txt", "_full/khac/Book/003.txt", "_full/merged/Book/004.txt",
    "_dup/Book/005.txt", "_gold/Book/006.txt", "_gold/model_eval_gold/Book/007.txt",
    "_gold/gold_v3x_2026-11-14/gold_v3x/Book/008.txt",
])
def test_story_chapter_inventory_includes_each_collection(tmp_path, relative):
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text("synthetic", encoding="utf-8")
    assert scan.corpus_files(tmp_path) == [path]


@pytest.mark.parametrize("relative", [
    "README.md", "_NEW_JA.md", "Book/notes.md", "Book/spec.txt", "Book/mapping.txt",
    "_gold/_trees/Book/001.txt", "_gold/_ui_branch_backup/Book/001.txt",
    "_gold/_a2w5/001.txt", "_gold/model_eval_gold/Book/notes.md",
    "_full/tools/001.txt", "_full/survey/Book/001.txt", "_full/android/Book/001.txt",
    "Book/android/001.txt", "Book/docs/001.txt", "Book/src/001.txt", ".claude/001.txt",
    "_survey/Book/001.txt", "research/Book/001.txt", "g2pgate/calibration_context.json",
])
def test_non_story_inventory_is_excluded(tmp_path, relative):
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("synthetic", encoding="utf-8")
    assert scan.corpus_files(tmp_path) == []


@pytest.mark.parametrize("value", [
    " ".join(str(i) for i in range(20)),
    " ".join(r"\x" + format(i, "02x") for i in range(20)),
    " ".join("field_" + str(i) for i in range(20)),
    " ".join(["getValue", "setValue", "someField", "otherField"] * 3),
    " ".join(["++", "==", "->"] * 8),
    "a b c d e f g h i j k l m n o p",
    "alpha beta gamma delta 123 epsilon zeta eta theta",
    "alpha beta gamma delta field_name epsilon zeta eta theta",
    "alpha beta gamma delta + epsilon zeta eta theta",
    "alpha beta gamma delta\n\nepsilon zeta eta theta",
])
def test_non_prose_tokens_cannot_form_or_bridge_a_shingle(value):
    assert not scan.shingles(value).size


def test_prose_punctuation_case_and_accents_remain_matchable():
    sentence = " ".join("synthetic" + chr(97 + i) for i in range(12))
    punctuated = sentence.capitalize().replace(" ", ", ") + "!"
    assert set(scan.shingles(sentence)) == set(scan.shingles(punctuated))
    import unicodedata
    accented = " ".join(["thử"] * 12)
    assert set(scan.shingles(accented)) == set(scan.shingles(unicodedata.normalize("NFD", accented)))
    assert scan.shingles("McSynthetic " + sentence).size == 6


def test_gold_labels_and_notes_are_not_story_but_quoted_evidence_is(tmp_path):
    path = tmp_path / "001.txt"
    labels = "1 D SPEAKER neutral,sad,angry,happy,nervous,confused,afraid,surprised 0-3 normal normal u"
    evidence = " ".join("synthetic" + chr(97 + i) for i in range(12))
    path.write_text(labels + "\n# " + evidence, encoding="utf-8")
    assert scan.read_corpus_text(path) == ""
    path.write_text(labels + '\n# "' + evidence + '"', encoding="utf-8")
    assert scan.read_corpus_text(path) == evidence
    path.write_text(evidence, encoding="utf-8")
    assert scan.read_corpus_text(path) == evidence


def test_chapter_preamble_metadata_is_not_story_and_body_is_preserved(tmp_path):
    title = " ".join("synthetic" + chr(97 + i) for i in range(12))
    book = tmp_path / title
    book.mkdir()
    path = book / "001.txt"
    body = " ".join("prose" + chr(97 + i) for i in range(12))
    path.write_text(title + "\nChapter 1\nAuthor: synthetic\n\n" + body, encoding="utf-8")
    selected = scan.read_corpus_text(path)
    assert scan.shingles(title).size
    assert set(scan.shingles(selected)) == set(scan.shingles(body))
    # The same words in the body cannot be discarded as a title match.
    path.write_text("Chapter 1\n\n" + title, encoding="utf-8")
    assert set(scan.shingles(scan.read_corpus_text(path))) == set(scan.shingles(title))


def test_diagnosis_attributes_every_source_with_counts_only(tmp_path):
    from scripts import public_leak_diagnose as diagnosis
    corpus = tmp_path / "corpus"
    repo = tmp_path / "repo"
    repo.mkdir()
    sentence = " ".join("synthetic" + chr(97 + i) for i in range(12))
    for relative in ("Book/001.txt", "_gold/Book/002.txt"):
        path = corpus / relative
        path.parent.mkdir(parents=True)
        path.write_text(sentence, encoding="utf-8")
    (repo / "public.txt").write_text(sentence, encoding="utf-8")
    # The diagnostic reads the same public inventory as the main scanner.
    import subprocess
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    result = diagnosis.diagnose(repo, corpus, workers=1)
    assert result["findings"] == [{"path": "public.txt", "corpus_matches": {
        "Book/001.txt": 5, "_gold/Book/002.txt": 5}}]
    assert sentence not in str(result)


def test_real_story_excerpt_in_temporary_public_file_is_detected(tmp_path, monkeypatch):
    root = scan.corpus_root()
    if root is None:
        pytest.skip("Local story Corpus is unavailable")
    files = scan.corpus_files(root)
    if not files:
        pytest.skip("No supported story chapters in local Corpus")
    # Keep all source prose in temporary files; pytest assertions expose no excerpt.
    excerpt = None
    for chapter in files:
        for line in chapter.read_text(encoding="utf-8", errors="ignore").splitlines():
            words = line.split()
            for start in range(max(0, len(words) - 11)):
                candidate = " ".join(words[start:start + 12])
                if scan.shingles(candidate).size >= 5:
                    excerpt = candidate
                    break
            if excerpt is not None:
                break
        if excerpt is not None:
            break
    assert excerpt is not None, "No twelve-word prose span found in selected chapters"
    local_corpus = tmp_path / "corpus" / "Book"
    local_corpus.mkdir(parents=True)
    (local_corpus / "001.txt").write_text(chapter.read_text(encoding="utf-8"), encoding="utf-8")
    public = tmp_path / "public"
    public.mkdir()
    (public / "injected.txt").write_text(excerpt, encoding="utf-8")
    monkeypatch.setattr(scan, "tracked", lambda _: ["injected.txt"])
    monkeypatch.setattr(scan, "load_reviewed", lambda: {})
    result = scan.audit(public, corpus=local_corpus.parent, workdir=tmp_path / "index")
    assert any(f["path"] == "injected.txt" and f["rule"] == f"shares>={scan.SHINGLE}words"
               for f in result["findings"]), "Injected real story excerpt was missed"
    if excerpt in str(result):
        pytest.fail("Diagnostic output exposed story text", pytrace=False)
