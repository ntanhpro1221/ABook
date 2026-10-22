from pathlib import Path

from abook import importers
import pytest
import json


FIXTURES = Path(__file__).parent / "fixtures" / "import"


def test_a84_01_docx_notes_and_call_marks_stay_until_explicitly_removed():
    source = FIXTURES / "notes.docx"
    book = importers.import_text(source)
    text = "\n".join(c.text for c in book.chapters)
    assert "Lời chú thứ nhất." in text
    assert "Lời chú cuối sách về cơn mưa." in text
    assert "¹" in text and book.footnote_marks == 4
    dropped = importers.import_text(source, footnotes=importers.FootnoteChoice(True, "drop"))
    assert "Lời chú" not in "\n".join(c.text for c in dropped.chapters)
    assert "¹" not in "\n".join(c.text for c in dropped.chapters)
    assert importers.import_text(source).to_dict() == book.to_dict()


@pytest.mark.parametrize("name", ["a84_lead_one.txt", "a84_lead_two.txt"])
def test_a84_02_default_selection_keeps_every_preamble_word(name):
    book = importers.import_text(FIXTURES / name, split_chapters=True, keep_short=True)
    selected = importers.select_chapters(book, importers.default_picks(book))
    actual = "\n".join(c.text for c in selected.chapters).split()
    assert actual == (FIXTURES / name).read_text(encoding="utf-8").split()


def test_a84_02_studio_keeps_a_line_even_if_it_matches_book_title(tmp_path):
    from abook.webui import txt_split

    source = FIXTURES / "a84_lead_one.txt"
    folder = txt_split.split(source, tmp_path, "Đêm ấy tôi không về")
    assert "Đêm ấy tôi không về" in "\n".join(p.read_text(encoding="utf-8") for p in folder.glob("*.txt"))


def test_a84_03_pdf_running_lines_are_reversible_proposals():
    pages = json.loads((FIXTURES / "a84_pdf_lines.json").read_text(encoding="utf-8"))
    book = importers.import_pdf_pages(pages, "Sách")
    text = "\n".join(c.text for c in book.chapters)
    assert text.split() == " ".join(line for page in pages for line in page).split()
    assert text.count("Tôi vẫn chờ anh.") == 3
    assert all(f"Đồng hồ điểm {i} giờ." in text for i in (1, 2, 3))
    assert "1984" in text
    assert any(line == "Tôi vẫn chờ anh." for _, line in book.credits)


@pytest.mark.parametrize("change", ["insert", "rewrite", "rename"])
def test_a84_04_add_rejects_a_changed_preview_source(tmp_path, change):
    from tests.test_project_file import _app
    from abook.webui.server import ApiError

    source = tmp_path / "txt"
    source.mkdir()
    (source / "1.txt").write_text("Chương 1\nA.", encoding="utf-8")
    (source / "2.txt").write_text("Chương 2\nB.", encoding="utf-8")
    app = _app(tmp_path / "studio", tmp_path / "library")
    app.preview_text_book(str(source))
    if change == "insert":
        (source / "0.txt").write_text("Chương 0\nTrước.", encoding="utf-8")
    elif change == "rewrite":
        (source / "2.txt").write_text("Chương 2\nKhác.", encoding="utf-8")
    else:
        (source / "2.txt").rename(source / "0.txt")
    with pytest.raises(ApiError, match="[Bb]ạn.*xem lại"):
        app.add_text_book(str(source), chapters=[{"index": 2}])


def test_a84_06_studio_and_import_use_the_same_toc_cuts(tmp_path):
    from abook.webui import txt_split

    source = FIXTURES / "a84_toc.txt"
    book = importers.import_text(source, split_chapters=True)
    assert txt_split.plan(source)["chapters"] == len(book.chapters) == 4
    folder = txt_split.split(source, tmp_path)
    assert [p.read_text(encoding="utf-8").strip() for p in sorted(folder.glob("*.txt"))] == [c.text for c in book.chapters]


def test_a84_07_volume_line_belongs_to_the_next_chapter_everywhere(tmp_path):
    from abook.webui import txt_split

    source = FIXTURES / "a84_volume.txt"
    book = importers.import_text(source, split_chapters=True)
    folder = txt_split.split(source, tmp_path)
    assert [p.read_text(encoding="utf-8").strip() for p in sorted(folder.glob("*.txt"))] == [c.text for c in book.chapters]
    assert book.chapters[1].text.startswith("Tập 2\n")


def test_a84_08_prose_with_a_number_is_not_a_chapter_heading():
    book = importers.import_text(FIXTURES / "a84_prose.txt", split_chapters=True)
    assert len(book.chapters) == 2
    assert "Hồi hai đứa còn học" in book.chapters[0].text
    assert "Chương 1 này hay thật." in book.chapters[0].text
    assert importers.is_heading_line("Chương XIV: " + "Một phụ đề khá dài " * 3)


def test_a84_09_light_novel_special_sections_are_chapters():
    book = importers.import_text(FIXTURES / "a84_special.txt", split_chapters=True)
    assert len(book.chapters) == 7
    assert [c.title for c in book.chapters][-3:] == ["Lời bạt", "Minh họa", "Phần 1"]
    assert len(importers.default_picks(book)) == 7
    assert not importers.is_heading_line("Lời bạt của tôi rất dài.")


def test_a84_10_docx_breaks_keep_word_boundaries():
    book = importers.import_text(FIXTURES / "a84_breaks.docx")
    text = " ".join(c.text for c in book.chapters)
    assert text.count("Xin chào.") == 4
    assert "Xinchào" not in text


def test_a84_11_txt_separating_controls_keep_words_and_heading_boundaries():
    book = importers.import_text(FIXTURES / "a84_controls.txt", split_chapters=True)
    assert len(book.chapters) == 3
    assert book.chapters[0].text.split() == ["Xin", "chào."] * 5


def test_a84_12_docx_reads_final_tracked_move_once():
    text = " ".join(c.text for c in importers.import_text(FIXTURES / "a84_moves.docx").chapters)
    assert text.count("Xin chào.") == 1
    assert text.count("Đã chuyển.") == 1
    assert "Đã thêm." in text and "Đã xoá." not in text


@pytest.mark.parametrize("name", ["meta", "plain"])
def test_a84_13_lone_h1_is_kept_in_default_book(name):
    book = importers.import_text(FIXTURES / f"a84_h1_{name}.docx", keep_short=True)
    book = importers.select_chapters(book, importers.default_picks(book))
    text = "\n".join(book.chapter_source(c) for c in book.chapters)
    assert text.count("Lời mở đầu") == 1
    assert "Câu chuyện bắt đầu." in text


def test_a84_14_docx_inherited_and_outline_headings_split():
    book = importers.import_text(FIXTURES / "a84_styles.docx")
    assert [c.title for c in book.chapters] == ["Bến đò", "Cơn mưa", "Đêm xuống", "Bình minh"]


@pytest.mark.parametrize("name", ["le", "be", "tail"])
def test_a84_15_bad_txt_bytes_are_reported_without_replacement(name):
    with pytest.raises(importers.ImportFailed, match="Bạn.*UTF-8"):
        importers.import_text(FIXTURES / f"a84_bad_{name}.txt")


def test_a84_16_original_long_names_decide_folder_order(tmp_path):
    rows = json.loads((FIXTURES / "a84_long_names.json").read_text(encoding="utf-8"))
    for row in reversed(rows):
        (tmp_path / row["name"]).write_text(row["text"], encoding="utf-8")
    book = importers.import_text(tmp_path)
    assert [c.text for c in book.chapters] == [r["text"] for r in rows]
    assert [c.title for c in book.chapters] == [Path(r["name"]).stem for r in rows]


def test_a84_18_sparse_pdf_keeps_text_and_warns_about_image_pages():
    pages = json.loads((FIXTURES / "a84_sparse_pdf.json").read_text(encoding="utf-8"))
    book = importers.import_pdf_pages(pages, "Sách")
    assert book.chapters[0].title == "Chương 1"
    assert "Một ngày yên ả" in book.chapters[0].text
    assert any("9 trang không có chữ" in n for n in book.notes)
    with pytest.raises(importers.ImportFailed):
        importers.import_pdf_pages([[] for _ in range(10)], "Scan")


def test_a84_17_unicode_filename_order_matches_shared_contract(tmp_path):
    names = json.loads((FIXTURES / "a84_unicode_names.json").read_text(encoding="utf-8"))
    for name in reversed(names):
        (tmp_path / name).write_text(name, encoding="utf-8")
    book = importers.import_text(tmp_path)
    assert [c.text for c in book.chapters] == ["A01.txt", "a1.txt", "Straße1.txt", "STRASSE2.txt", "Ánh2.txt", "ÁNH10.txt", "Σ1.txt", "ς2.txt", "σ10.txt"]


@pytest.mark.parametrize("name,reason,action", [("scan.pdf", "chữ", "OCR"), ("a84_locked.pdf", "mật khẩu", "mở khóa")])
def test_a84_19_pdf_errors_say_why_and_what_you_can_do(name, reason, action):
    with pytest.raises(importers.ImportFailed) as caught:
        importers.import_text(FIXTURES / name)
    message = str(caught.value)
    assert reason in message and "Bạn" in message and action in message


def test_a84_03_pdf_defaults_are_visible_suggestions_and_never_delete_source_text():
    from abook.webui import textbook
    pages = json.loads((FIXTURES / "a84_pdf_headers.json").read_text(encoding="utf-8"))
    book = importers.import_pdf_pages(pages, "Sách")
    preview = textbook.preview(book)
    proposals = preview["suggestions"]
    assert any(p["line"] == "TÊN SÁCH" and p.get("defaultOn") for p in proposals)
    assert all(any(p["line"] == str(i) and p.get("defaultOn") for p in proposals) for i in (1, 2, 3))
    assert all(not p.get("defaultOn") for p in proposals if "Một câu chuyện" in p["line"])
    assert " ".join(c.text for c in book.chapters).split() == " ".join(line for page in pages for line in page).split()


def test_a84_generated_sources_match_disk():
    from tests.a84_import_fixtures import sources, kotlin_casefold
    for name, data in sources().items():
        assert (FIXTURES / name).read_bytes() == data, name
    assert (FIXTURES.parents[2] / "mobile/android/app/src/main/java/vn/abook/player/ImportCaseFold.kt").read_text(encoding="utf-8") == kotlin_casefold()
