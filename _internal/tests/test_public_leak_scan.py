"""The public scanner must inspect resources, inline test strings and documentation."""
from pathlib import Path
import json
import hashlib

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


def test_reviewed_bytes_must_match_and_generic_review_cannot_waive_corpus(tmp_path, monkeypatch):
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


def test_corpus_review_pins_individual_shingles_and_file_bytes(tmp_path, monkeypatch):
    name = "public.txt"
    path = tmp_path / name
    approved, injected = synthetic_prose("approved"), synthetic_prose("injected")
    path.write_bytes((approved + "\n").encode("utf-8"))
    corpus = tmp_path / "corpus" / "Book"
    corpus.mkdir(parents=True)
    (corpus / "001.txt").write_text(approved, encoding="utf-8")
    entry = {"sha256": scan.digest(path), "rules": [],
             "reason": "Public synthetic coincidence reviewed for this test only",
             "corpus_review": {"classification": "i", "reason": "Synthetic individually checked public shingles",
                               "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "shingles": sorted({f"{int(h):016x}" for h in scan.shingles(approved)})}}
    monkeypatch.setattr(scan, "tracked", lambda _: [name])
    monkeypatch.setattr(scan, "load_reviewed", lambda: {name: entry})

    def audit():
        return scan.audit(tmp_path, corpus=corpus.parent, workdir=tmp_path / "index")

    assert audit()["findings"] == []
    assert audit()["waived"] == 1
    # CRLF-only edits keep the legacy normalized pin, but expire Corpus approval.
    path.write_bytes((approved + "\r\n").encode("utf-8"))
    assert entry["sha256"] == scan.digest(path)
    assert audit()["findings"]
    # Even a whitespace edit expires the pinned file review.
    path.write_text(approved + " ", encoding="utf-8")
    assert audit()["findings"]
    # Updating only the byte pin cannot authorize newly injected story shingles.
    path.write_text(approved + "\n\n" + injected, encoding="utf-8")
    entry["sha256"] = scan.digest(path)
    entry["corpus_review"]["file_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (corpus / "001.txt").write_text(approved + "\n\n" + injected, encoding="utf-8")
    result = audit()
    assert len(result["findings"]) == 1
    assert result["findings"][0]["reviewed_shingle_count"] == len(entry["corpus_review"]["shingles"])
    assert set(result["findings"][0]["shingle_hashes"]) == {f"{int(h):016x}" for h in scan.shingles(injected)}


def test_new_corpus_match_expires_approval_even_without_public_file_edit(tmp_path, monkeypatch):
    name = "public.txt"
    approved, other = synthetic_prose("approved"), synthetic_prose("other")
    path = tmp_path / name
    path.write_text(approved + "\n\n" + other, encoding="utf-8")
    reviewed = {name: {"sha256": scan.digest(path), "rules": [],
                       "corpus_review": {"classification": "i", "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "shingles": [
                           f"{int(h):016x}" for h in set(scan.shingles(approved))]}}}
    hashes = [f"{int(h):016x}" for h in set(scan.shingles(approved + "\n\n" + other))]
    blocking, waived = scan.apply_reviews([
        {"path": name, "rule": f"shares>={scan.SHINGLE}words", "shingle_hashes": hashes}], reviewed, tmp_path)
    assert not waived and blocking[0]["shingle_hashes"]
    # A Corpus-only approval cannot waive unrelated long text or IPA warnings.
    assert scan.apply_reviews([{"path": name, "rule": "long-vietnamese"}], reviewed, tmp_path)[0]


@pytest.mark.parametrize("review", [
    {"classification": "ii", "shingles": ["0123456789abcdef"]},
    {"classification": "i", "shingles": []},
    {"classification": "i", "shingles": ["whole-file"]},
    {"classification": "i", "shingles": ["0123456789abcdef"] * 2},
])
def test_corpus_review_requires_explicit_classification_and_exact_hashes(tmp_path, review):
    path = tmp_path / "reviewed.json"
    path.write_text(json.dumps({"public.txt": {"sha256": "a" * 64,
                    "reason": "Synthetic review schema validation case",
                    "corpus_review": {"reason": "Reviewed contextual coincidence for this file", "file_sha256": "b" * 64, **review}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Corpus review"):
        scan.load_reviewed(path)


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
    # A correctly byte-pinned generic review still cannot approve new prose.
    monkeypatch.setattr(scan, "load_reviewed", lambda: {"injected.txt": {
        "sha256": scan.digest(public / "injected.txt"), "rules": [],
        "corpus_review": {"classification": "i", "file_sha256": hashlib.sha256((public / "injected.txt").read_bytes()).hexdigest(),
                          "shingles": ["0000000000000000"]}}})
    result = scan.audit(public, corpus=local_corpus.parent, workdir=tmp_path / "index")
    assert any(f["path"] == "injected.txt" and f["rule"] == f"shares>={scan.SHINGLE}words"
               for f in result["findings"]), "Injected real story excerpt was missed"
    if excerpt in str(result):
        pytest.fail("Diagnostic output exposed story text", pytrace=False)


def synthetic_prose(prefix="synthetic", count=12):
    return " ".join(prefix + chr(97 + i) for i in range(count))


def test_common_shingles_are_suppressed_at_k_books_but_unique_leaks_survive(tmp_path):
    common, unique = synthetic_prose(), synthetic_prose("private")
    corpus = tmp_path / "corpus"
    for i in range(scan.COMMON_STORY_MIN):
        chapter = corpus / ("Book " + chr(97 + i)) / "001.txt"
        chapter.parent.mkdir(parents=True)
        chapter.write_text(common + ("\n\n" + unique if i == 0 else ""), encoding="utf-8")
    result = scan.corpus_overlap({"common.txt": [common], "leak.txt": [unique]},
                                 corpus, tmp_path / "index", workers=1)
    assert [f["path"] for f in result] == ["leak.txt"]
    assert result[0]["corpus_story_count"] == 1
    assert unique not in str(result) and common not in str(result)


def test_k_minus_one_books_still_block_and_chapters_and_mirrors_count_once(tmp_path):
    sentence = synthetic_prose()
    corpus = tmp_path / "corpus"
    paths = ["Some Book/001.txt", "Some Book/002.txt", "Some Book/volume/003.txt",
             "_full/truyen/123-some-book/004.txt", "_dup/some_book/005.txt",
             "_gold/model_eval_gold/some_book/006.txt", "Another Book/001.txt"]
    for relative in paths:
        chapter = corpus / relative
        chapter.parent.mkdir(parents=True, exist_ok=True)
        chapter.write_text(sentence, encoding="utf-8")
    result = scan.corpus_overlap({"leak.txt": [sentence]}, corpus, tmp_path / "index", workers=1)
    assert result[0]["corpus_story_count"] == scan.COMMON_STORY_MIN - 1
    assert result[0]["corpus_file_count"] == len(paths)


@pytest.mark.parametrize("relative", [
    "Some Book/001.txt", "Some Book/volume/001.txt", "_full/ai-dich/123-some-book/001.txt",
    "_dup/some_book/001.txt", "_gold/some_book/001.txt",
    "_gold/model_eval_gold/some_book/001.txt",
    "_gold/gold_v3x_2026-11-14/gold_v3x/some_book/001.txt",
])
def test_book_identity_collapses_mirrors_and_volume_subfolders(relative):
    assert scan.story_identity(Path(relative)) == "somebook"


def test_filtering_common_prefix_does_not_hide_the_unique_remainder(tmp_path):
    common, unique = synthetic_prose(), synthetic_prose("private")
    hits = [(f"Book {chr(97 + i)}/001.txt", scan.shingles(common).tolist())
            for i in range(scan.COMMON_STORY_MIN)]
    hits[0][1].extend(scan.shingles(unique).tolist())
    owners = {h: {"leak.txt"} for _, values in hits for h in values}
    result = scan.overlap_findings(owners, hits)
    assert [f["path"] for f in result] == ["leak.txt"]
    assert result[0]["corpus_file_count"] == 1


def test_existing_credit_rules_remove_only_edge_metadata_without_joining_prose(tmp_path):
    prose = synthetic_prose()
    credit = "Translator: " + " ".join(chr(97 + i) * 3 for i in range(8))
    advert = "Đọc truyện aaaa bbbb cccc dddd tại example.com"
    assert scan.shingles(credit).size and scan.shingles(advert).size
    assert not scan.shingles(scan.without_source_credits(credit)).size
    assert not scan.shingles(scan.without_source_credits(advert)).size
    assert set(scan.shingles(scan.without_source_credits(credit + "\n\n" + prose + "\n\n" + advert))) == set(scan.shingles(prose))
    # A matching-looking line in the interior or quoted speech stays covered.
    interior = (prose + "\n") * 7 + credit + "\n" + (prose + "\n") * 7
    assert credit in scan.without_source_credits(interior)
    dialogue = '“' + advert + '”'
    assert dialogue in scan.without_source_credits(dialogue)
    halves = " ".join(prose.split()[:4]) + "\n" + credit + "\n" + " ".join(prose.split()[4:8])
    assert not scan.shingles(scan.without_source_credits(halves)).size


def test_diagnosis_reports_frequency_and_public_evidence_only_on_request(tmp_path):
    from scripts import public_leak_diagnose as diagnosis
    sentence = synthetic_prose()
    path = tmp_path / "public.txt"
    path.write_text(sentence, encoding="utf-8")
    values = scan.shingles(sentence).tolist()
    owners = {h: {path.name} for h in values}
    hits = [("Book/001.txt", values), ("_gold/Book/002.txt", values)]
    result = diagnosis.summarize(tmp_path, owners, hits)
    assert result["story_frequency_distribution"] == [{"stories": 1, "shingles": 5}]
    assert sentence not in str(result)
    assert "repository_shingles" not in result["findings"][0]
    explicit = diagnosis.summarize(tmp_path, owners, hits, repo_evidence=True)
    evidence = explicit["findings"][0]["repository_shingles"]
    assert len(evidence) == 5
    assert all(row["story_count"] == 1 and row["repo_text"] in sentence for row in evidence)
    common = [(f"Book {chr(97 + i)}/001.txt", values) for i in range(scan.COMMON_STORY_MIN)]
    assert not diagnosis.summarize(tmp_path, owners, common, repo_evidence=True)["findings"]


def test_repository_evidence_stays_aligned_across_unicode_numeric_tokens():
    from scripts import public_leak_diagnose as diagnosis
    sentence = synthetic_prose()
    wanted = set(scan.shingles(sentence).tolist())
    evidence = list(diagnosis.repository_evidence(sentence + " Ⅳ " + sentence, wanted))
    assert len(evidence) == 10
    assert all(scan.shingles(span["repo_text"]).tolist() == [value] for value, span in evidence)
