"""Đáp án chuẩn khoá theo seq: dấu chữ `.seqtext` bắt parser tách chương khác trước khi điểm tụt vì cây thước.

Chỉ dùng chữ giả cực ngắn - chữ truyện là riêng tư.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "model_eval"))

import gold_fingerprint  # noqa: E402
import score_models  # noqa: E402
from score_models import (  # noqa: E402
    GoldTextMismatch,
    aligned_gold,
    aligned_gold_multi,
    exit_on_gold_mismatch,
    load_gold,
    read_seqtext,
    segment_fingerprint,
    write_seqtext,
)

BOOK = "truyen_gia"
TEXTS = ["Một.", "Hai.", "Ba.", "Bốn.", "Năm."]


@pytest.fixture(autouse=True)
def _fresh_warnings():
    score_models._WARNED.clear()
    yield
    score_models._WARNED.clear()


def make_project(root: Path, chapters: dict[str, list[str]], name: str = "project") -> Path:
    """Project sqlite tối thiểu: đủ cột cho read_project lẫn read_segment_texts."""
    folder = root / name
    folder.mkdir(parents=True)
    connection = sqlite3.connect(folder / "project.sqlite3")
    connection.executescript(
        """
        CREATE TABLE chapters (id INTEGER PRIMARY KEY, title TEXT, chapter_index INTEGER);
        CREATE TABLE segments (chapter_id INTEGER, seq INTEGER, kind TEXT, speaker TEXT, gender TEXT, age TEXT,
                               emotion TEXT, intensity INTEGER, pace TEXT, volume TEXT, confidence REAL,
                               status TEXT, text TEXT);
        CREATE TABLE book (settings_json TEXT, analysis_model_name TEXT);
        INSERT INTO book VALUES ('{"analysis": {"model": "m"}}', 'm');
        """
    )
    for index, (title, texts) in enumerate(chapters.items(), 1):
        connection.execute("INSERT INTO chapters VALUES (?, ?, ?)", (index, title, index))
        for seq, text in enumerate(texts, 1):
            connection.execute(
                "INSERT INTO segments VALUES (?, ?, 'narration', 'NARRATOR', 'unknown', '', 'neutral', 0, 'normal', "
                "'normal', 1.0, 'analyzed', ?)",
                (index, seq, text),
            )
    connection.commit()
    connection.close()
    return folder


def make_gold(root: Path, chapter: str, seqs: range | list[int], fingerprint_of: list[str] | None = None,
              where: Path | None = None) -> Path:
    """Thư mục đáp án giả: mỗi seq một dòng N rút gọn; `fingerprint_of` (chữ từng đoạn, seq từ 1) thì ghi cả .seqtext."""
    folder = where or (root / BOOK)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{chapter}.txt").write_bytes(("# chú thích\n" + "".join(f"{seq} N\n" for seq in seqs)).encode("utf-8"))
    if fingerprint_of is not None:
        write_seqtext(folder / f"{chapter}.seqtext", dict(enumerate(fingerprint_of, 1)), ["thử"])
    return folder


def test_a_matching_project_passes_silently(tmp_path: Path, capsys) -> None:
    gold_dir = make_gold(tmp_path, "351", range(1, 6), TEXTS)
    project = make_project(tmp_path, {"351": TEXTS})
    result = aligned_gold(gold_dir, project, {"351"})
    assert sorted(result) == [("351", seq) for seq in range(1, 6)]
    assert capsys.readouterr().err == ""


def test_no_sidecar_warns_once_and_uses_the_gold_as_is(tmp_path: Path, capsys) -> None:
    gold_dir = make_gold(tmp_path, "351", range(1, 6))
    project = make_project(tmp_path, {"351": TEXTS})
    assert len(aligned_gold(gold_dir, project, {"351"})) == 5
    assert len(aligned_gold(gold_dir, project, {"351"})) == 5
    err = capsys.readouterr().err.splitlines()
    assert err == [f"CẢNH BÁO gold {BOOK}/351: chưa có dấu chữ (.seqtext) - không kiểm được gióng đoạn"]


def test_one_extra_split_segment_is_caught_with_the_first_shifted_seq(tmp_path: Path, capsys) -> None:
    """Ca 09-10: parser tách "Hai." làm hai đoạn, mọi đáp án phía sau lệch một seq mà điểm vẫn ra con số."""
    gold_dir = make_gold(tmp_path, "351", range(1, 6), TEXTS)
    split = ["Một.", "Hai", ".", "Ba.", "Bốn.", "Năm."]
    project = make_project(tmp_path, {"351": split})
    with pytest.raises(GoldTextMismatch) as caught:
        aligned_gold(gold_dir, project, {"351"})
    assert (caught.value.bad, caught.value.total, caught.value.first_seq) == (4, 5, 2)
    assert f"CẢNH BÁO gold {BOOK}/351: 4/5 đoạn lệch chữ, seq đầu 2" in capsys.readouterr().err
    assert f"{BOOK}/351" in str(caught.value) and "4/5" in str(caught.value)


def test_a_variant_keyed_to_the_other_segmentation_is_picked_when_its_text_matches(tmp_path: Path, capsys) -> None:
    gold_dir = make_gold(tmp_path, "351", range(1, 6), TEXTS)
    split = ["Một.", "Hai", ".", "Ba.", "Bốn.", "Năm."]
    # biến thể "aaa" (xếp trước) không khớp chữ nên bị bỏ qua; "new" khớp đúng project này
    make_gold(tmp_path, "351", range(1, 6), ["x"] * 5, where=gold_dir / "_variants" / "aaa")
    make_gold(tmp_path, "351", range(1, 7), split, where=gold_dir / "_variants" / "new")
    project = make_project(tmp_path, {"351": split})
    result = aligned_gold(gold_dir, project, {"351"})
    assert sorted(result) == [("351", seq) for seq in range(1, 7)]
    err = capsys.readouterr().err
    assert "đoạn lệch chữ, seq đầu 2" in err and f"gold {BOOK}/351: dùng biến thể new (khớp chữ)" in err


def test_a_variant_is_never_read_as_gold(tmp_path: Path) -> None:
    gold_dir = make_gold(tmp_path, "351", range(1, 3), TEXTS[:2])
    make_gold(tmp_path, "351", range(1, 9), ["x"] * 8, where=gold_dir / "_variants" / "old")
    assert sorted(load_gold(gold_dir)) == [("351", 1), ("351", 2)]


def test_a_few_stray_segments_under_half_a_percent_keep_the_main_gold_with_a_warning(tmp_path: Path, capsys) -> None:
    texts = [f"câu {number}." for number in range(400)]
    gold_dir = make_gold(tmp_path, "351", range(1, 401), texts)
    edited = list(texts)
    edited[199] = "câu khác hẳn."  # 1/400 = 0,25%
    project = make_project(tmp_path, {"351": edited})
    assert len(aligned_gold(gold_dir, project, {"351"})) == 400
    assert f"CẢNH BÁO gold {BOOK}/351: 1/400 đoạn lệch chữ, seq đầu 200" in capsys.readouterr().err


def test_a_segment_missing_from_the_project_counts_as_a_mismatch(tmp_path: Path) -> None:
    gold_dir = make_gold(tmp_path, "351", range(1, 6), TEXTS)
    project = make_project(tmp_path, {"351": TEXTS[:3]})  # seq 4, 5 vắng
    with pytest.raises(GoldTextMismatch) as caught:
        aligned_gold(gold_dir, project, {"351"})
    assert (caught.value.bad, caught.value.first_seq) == (2, 4)


def test_cosmetic_whitespace_and_unicode_form_do_not_count_as_a_difference(tmp_path: Path, capsys) -> None:
    gold_dir = make_gold(tmp_path, "351", range(1, 3), ["Tiếng Việt  nhé.", "Hai."])
    # NFD (dấu rời), khoảng trắng kép, NBSP, xuống dòng và khoảng trắng thừa hai đầu
    noisy = ["  Tiếng Việt\n nhé. ", "\tHai.\n"]
    project = make_project(tmp_path, {"351": noisy})
    assert len(aligned_gold(gold_dir, project, {"351"})) == 2
    assert capsys.readouterr().err == ""
    assert segment_fingerprint("a  b") == segment_fingerprint(" a b\n") != segment_fingerprint("ab")
    assert len(segment_fingerprint("x")) == 12


def test_a_chapter_the_project_does_not_hold_is_left_alone(tmp_path: Path, capsys) -> None:
    gold_dir = make_gold(tmp_path, "351", range(1, 6), TEXTS)
    make_gold(tmp_path, "352", range(1, 3), where=gold_dir)
    project = make_project(tmp_path, {"351": TEXTS})
    assert len(aligned_gold(gold_dir, project)) == 7
    assert capsys.readouterr().err == "", "chương 352 không có trong project nên không có gì để kiểm"


def test_several_projects_each_align_the_chapter_they_hold(tmp_path: Path) -> None:
    gold_dir = make_gold(tmp_path, "351", range(1, 6), TEXTS)
    split = ["Một.", "Hai", ".", "Ba.", "Bốn.", "Năm."]
    make_gold(tmp_path, "351", range(1, 7), split, where=gold_dir / "_variants" / "new")
    make_gold(tmp_path, "352", range(1, 3), ["A", "B"], where=gold_dir)
    one = make_project(tmp_path, {"351": split}, "p1")
    two = make_project(tmp_path, {"352": ["A", "B"]}, "p2")
    result = aligned_gold_multi(gold_dir, [one, two], {"351", "352"})
    assert sorted(result) == [("351", seq) for seq in range(1, 7)] + [("352", 1), ("352", 2)]


def test_gold_fingerprint_writes_a_sidecar_that_then_validates(tmp_path: Path, capsys) -> None:
    gold_dir = make_gold(tmp_path, "351", range(1, 6))
    project = make_project(tmp_path, {"351": TEXTS})
    assert gold_fingerprint.main([str(project), str(gold_dir), "--chapter", "351"]) == 0
    sidecar = gold_dir / "351.seqtext"
    raw = sidecar.read_bytes()
    assert b"\r" not in raw and raw.startswith(b"# ")
    assert read_seqtext(sidecar) == {seq: segment_fingerprint(text) for seq, text in enumerate(TEXTS, 1)}
    assert "5 đoạn" in raw.decode("utf-8").splitlines()[1]
    capsys.readouterr()
    assert len(aligned_gold(gold_dir, project, {"351"})) == 5
    assert capsys.readouterr().err == ""
    # không ghi đè khi thiếu --force
    assert gold_fingerprint.main([str(project), str(gold_dir), "--chapter", "351"]) == 1
    assert gold_fingerprint.main([str(project), str(gold_dir), "--chapter", "351", "--force"]) == 0
    # chương project không có: mã 2
    assert gold_fingerprint.main([str(project), str(gold_dir), "--chapter", "999"]) == 2
    # biến thể vào _variants/<nhãn>/
    assert gold_fingerprint.main([str(project), str(gold_dir), "--chapter", "351", "--variant", "v1"]) == 0
    assert (gold_dir / "_variants" / "v1" / "351.seqtext").is_file()
    assert sorted(load_gold(gold_dir)) == [("351", seq) for seq in range(1, 6)]


def test_the_scoring_cli_exits_with_code_3_on_a_misaligned_gold(tmp_path: Path, monkeypatch, capsys) -> None:
    gold_dir = make_gold(tmp_path, "351", range(1, 6), TEXTS)
    good = make_project(tmp_path, {"351": TEXTS}, "good")
    bad = make_project(tmp_path, {"351": ["Một.", "Hai", ".", "Ba.", "Bốn.", "Năm."]}, "bad")
    monkeypatch.setattr(score_models, "GOLD_ROOT", gold_dir.parent)
    assert score_models.main([str(good), "--gold", BOOK]) == 0
    capsys.readouterr()
    with pytest.raises(SystemExit) as caught:
        score_models.main([str(bad), "--gold", BOOK])
    assert caught.value.code == 3
    assert f"gold {BOOK}/351" in capsys.readouterr().err


def test_the_exit_decorator_turns_the_exception_into_code_3(capsys) -> None:
    @exit_on_gold_mismatch
    def run() -> int:
        raise GoldTextMismatch("b", "1", 3, 10, 7)

    with pytest.raises(SystemExit) as caught:
        run()
    assert caught.value.code == 3
    assert "gold b/1: 3/10" in capsys.readouterr().err


def test_seqtext_lines_must_be_tab_separated(tmp_path: Path) -> None:
    path = tmp_path / "351.seqtext"
    path.write_bytes(b"# c\n1\tabc\n\n2 abc\n")
    with pytest.raises(ValueError):
        read_seqtext(path)
