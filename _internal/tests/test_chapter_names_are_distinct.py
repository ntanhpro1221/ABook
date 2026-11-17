"""Two chapters never share a display name, and a named prologue takes no chapter number.

Regression from a shipped book (15-11): a prologue whose heading was not recognized got "Chương 1" from its book position,
next to the real "Chương 1"; another book showed "Mở đầu, Chương 2, ..." with no "Chương 1". When the source file cannot be
read, the opening is rebuilt from the stored paragraphs so a standalone heading still counts. Titles are synthetic.
"""
from __future__ import annotations

from pathlib import Path

from abook import chapter_titles
from abook.config import build_settings, settings_hash
from abook.database import ProjectDB
from abook.io_utils import sha256_file
from abook.models import ProjectPaths
from abook.webui import store


def test_the_rules() -> None:
    assert chapter_titles.is_named_matter("Phần mở đầu") and chapter_titles.is_named_matter("Mở đầu - Gió đầu mùa")
    assert not chapter_titles.is_named_matter("Chương 1") and not chapter_titles.is_named_matter("")
    assert chapter_titles.fallback_numbers([1, 2, 3, 4], [True, False, False, True]) == [None, 1, 2, None]
    assert chapter_titles.fallback_numbers([None, 2], [False, False]) == [None, 2]
    assert chapter_titles.distinct_fallbacks(["Chương 1", "Chương 1", "Chương 2"], [True, False, False],
                                             ["000", "001", "002"]) == ["Chương 0", "Chương 1", "Chương 2"]
    assert chapter_titles.distinct_fallbacks(["Chương 1", "Chương 1"], [False, False], ["a", "b"]) == ["Chương 1", "Chương 1"], \
        "chỉ tên theo số được đổi; tiêu đề thật giữ nguyên"


def _project(tmp_path: Path, chapters: list[list[tuple[int, str]]]) -> Path:
    """chapters: per chapter, (paragraph_index, text) segments. Sources sit OUTSIDE the project, as in hand-made books."""
    paths = ProjectPaths.build(tmp_path / "project")
    settings = build_settings()
    db = ProjectDB(paths.db)
    db.initialize_book(title="T", project_root=paths.root, settings=settings, settings_hash=settings_hash(settings),
                       input_manifest_hash="manifest")
    outside = tmp_path / "corpus"
    outside.mkdir()
    for number, segments in enumerate(chapters):
        source = outside / f"{number:03d}.txt"
        source.write_text("\n\n".join(text for _p, text in segments), encoding="utf-8")
        chapter = db.ensure_chapters([{"chapter_index": number + 1, "title": f"{number:03d}", "input_path": source,
                                       "input_sha256": sha256_file(source), "input_size": source.stat().st_size,
                                       "output_mp3": paths.chapters / f"{number:03d}.mp3"}])[0]
        db.replace_chapter_segments(chapter, [{"stable_id": f"c{number}s{seq}", "seq": seq, "paragraph_index": paragraph,
                                               "text": text, "text_sha256": f"h{number}-{seq}", "kind_hint": "narration"}
                                              for seq, (paragraph, text) in enumerate(segments)])
    return paths.root


def _names(root: Path) -> list[str]:
    with store.connect(root) as connection:
        return [item["name"] for _id, item in sorted(store.chapter_names(connection, root).items())]


PROSE = "Trời mưa suốt đêm và con đường về làng ngập nước, ai cũng ở trong nhà chờ sáng."


def test_an_unrecognized_prologue_never_takes_the_name_of_a_real_chapter(tmp_path: Path) -> None:
    root = _project(tmp_path, [[(0, PROSE), (0, "Mọi người đều ngủ.")], [(0, "Chương 1"), (1, "Sáng hôm sau.")],
                               [(0, "Chương 2"), (1, "Chiều.")]])
    names = _names(root)
    assert len(set(names)) == len(names), names
    assert names[1:] == ["Chương 1", "Chương 2"]


def test_a_named_prologue_takes_no_number(tmp_path: Path) -> None:
    root = _project(tmp_path, [[(0, "Phần mở đầu"), (1, PROSE)], [(0, PROSE), (1, "Rồi trời tạnh.")],
                               [(0, PROSE), (1, "Rồi gió nổi.")]])
    assert _names(root) == ["Phần mở đầu", "Chương 1", "Chương 2"]


def test_a_standalone_heading_counts_when_the_source_cannot_be_read(tmp_path: Path) -> None:
    """Heading and prose are separate paragraphs (a blank line between) - the same boundary the source file had."""
    root = _project(tmp_path, [[(0, "Mở đầu - Một buổi sáng"), (1, PROSE)], [(0, "Lần gặp thứ chín"), (1, PROSE)]])
    assert _names(root) == ["Mở đầu", "Lần gặp thứ chín"]


def test_the_importer_uses_the_same_rules() -> None:
    from abook import importers

    body = PROSE + "\n\nRồi trời tạnh và mọi người ra đồng."
    book = importers.ImportedBook("T", text_has_title=True, chapters=[
        importers.Chapter("000", "Phần mở đầu\n\n" + body), importers.Chapter("001", body), importers.Chapter("002", body)])
    shown = [chapter.name or chapter.title for chapter in importers._finish(book).chapters]
    assert shown == ["Phần mở đầu", "Chương 1", "Chương 2"]

    book = importers.ImportedBook("T", text_has_title=True, chapters=[
        importers.Chapter("001", body), importers.Chapter("002", "Chương 1\n\n" + body)])
    shown = [chapter.name or chapter.title for chapter in importers._finish(book).chapters]
    assert len(set(shown)) == len(shown), shown


def test_a_heading_glued_to_its_prose_is_not_a_standalone_title(tmp_path: Path) -> None:
    root = _project(tmp_path, [[(0, "Lần gặp thứ chín"), (0, PROSE)], [(0, "Lần gặp thứ mười"), (0, PROSE)]])
    assert _names(root) == ["Chương 1", "Chương 2"]
