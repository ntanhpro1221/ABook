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


@pytest.mark.parametrize("slash", ["/", "\\", "\\\\"])
def test_private_path_signatures_have_no_exceptions(slash):
    assert scan.private_path("C:" + slash + "Users" + slash + "Example")
    assert scan.private_path(slash.join(["AppData", "Local", "Temp", "claude", "session"]))
    assert not scan.private_path("C:/Profiles/Example")


def test_corpus_exact_eight_word_overlap_and_no_plaintext_evidence(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sentence = " ".join("synthetic" + chr(97 + i) for i in range(12))
    (corpus / "book.txt").write_text(sentence, encoding="utf-8")
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
