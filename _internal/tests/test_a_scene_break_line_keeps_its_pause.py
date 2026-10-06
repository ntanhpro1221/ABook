"""A line that is only a separator ("***", "◆", "———") is a scene change, not a full stop.

It has no readable text, so segmentation used to drop it and bump the previous sentence's pause to the same ~230 ms as any
other sentence end: the audiobook had no long pause where the scene changes, and the music planner (which looks for a
separator) never saw one. The segment before the line now carries SCENE_BREAK_MS and a persistent `scene_break` flag; the
text itself is untouched.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from abook.audio_io import _source_timeline
from abook.database import ProjectDB
from abook.expression import PAUSE_CEILING_MS, narrative_break_ms
from abook.pipeline import SEGMENTATION_CHECKPOINT_FIELDS, BookPipeline
from abook.text_processing import SCENE_BREAK_MS, is_scene_break_line, segment_chapter_text
from abook.webui.music_scenes import chapter_scenes, hard_break

SEPARATORS = ["***", "* * *", "◆", "◇◇◇", "———", "---", "~~~", "○", "＊＊＊", "◆ ◇ ◆", "※", "-----", "= = =", "###", "· · ·", "⁂"]
# Một-hai dấu kẻ đứng RIÊNG một đoạn là ngăn cảnh (đo 06-10: 9/10 trúng ranh giới cảnh); trong một đoạn nhiều dòng thì không.
LONE_SEPARATORS = ["-", "--", "*", "~", "=", "#", "＊"]
NOT_SEPARATORS = ["...", ". . .", "…", "……", "“", "”", "\"", "—", "– –", "Chương 1", "Chương 1: ***", "***hay***", "0 0 0",
                  "ooo", "?", "?!", "!!!", "(…)", "[***]", "", "   "]


def _text(separator: str) -> str:
    return f"Gió thổi qua đồi.\n\n{separator}\n\nSáng hôm sau, mưa tạnh."


@pytest.mark.parametrize("separator", SEPARATORS)
def test_a_separator_line_is_a_scene_break(separator: str) -> None:
    assert is_scene_break_line(separator)
    rows = segment_chapter_text(1, _text(separator))
    assert [row["text"] for row in rows] == ["Gió thổi qua đồi.", "Sáng hôm sau, mưa tạnh."], "the text is not altered"
    assert rows[0]["break_ms"] == SCENE_BREAK_MS == 1500 and rows[0]["scene_break"] is True
    assert rows[1]["scene_break"] is False and rows[1]["break_ms"] == 0, "chapter end: no pause, no mark"


@pytest.mark.parametrize("line", LONE_SEPARATORS)
def test_a_lone_short_rule_is_a_scene_break_only_on_its_own(line: str) -> None:
    assert is_scene_break_line(line, alone=True) and not is_scene_break_line(line)
    rows = segment_chapter_text(1, _text(line))
    assert [row["text"] for row in rows] == ["Gió thổi qua đồi.", "Sáng hôm sau, mưa tạnh."]
    assert rows[0]["scene_break"] is True and rows[0]["break_ms"] == SCENE_BREAK_MS
    inside = segment_chapter_text(1, f"Gió thổi qua đồi.\n{line}\nSáng hôm sau, mưa tạnh.")
    assert not any(row["scene_break"] for row in inside), "inside a multi-line paragraph it is not a break"


@pytest.mark.parametrize("line", NOT_SEPARATORS)
def test_an_ellipsis_a_quote_mark_or_a_title_is_not_a_scene_break(line: str) -> None:
    assert not is_scene_break_line(line)
    rows = segment_chapter_text(1, _text(line))
    assert not any(row["scene_break"] for row in rows)
    assert all(row["break_ms"] < SCENE_BREAK_MS for row in rows)


def test_a_separator_inside_a_paragraph_and_repeated_separators() -> None:
    rows = segment_chapter_text(1, "Cô đi về.\n***\n***\nAnh ở lại.\n\nTrời tối.")
    assert [row["scene_break"] for row in rows] == [True, False, False]
    assert rows[0]["break_ms"] == SCENE_BREAK_MS
    assert rows[1]["break_ms"] == 380, "the paragraph break after an ordinary line is unchanged"


def test_a_separator_with_nothing_before_it_or_closing_the_chapter_marks_nothing() -> None:
    rows = segment_chapter_text(1, "***\n\nTrời tối.\n\n***")
    assert [row["scene_break"] for row in rows] == [False]
    assert rows[0]["break_ms"] == 0


def test_a_long_sentence_split_in_chunks_marks_only_the_last_chunk() -> None:
    rows = segment_chapter_text(1, ("Cô đi rất xa, " * 12).strip() + ".\n\n***\n\nAnh ở lại.", max_chars=60)
    marked = [index for index, row in enumerate(rows) if row["scene_break"]]
    assert marked == [len(rows) - 2] and rows[marked[0]]["break_ms"] == SCENE_BREAK_MS
    assert all(row["break_ms"] < SCENE_BREAK_MS for row in rows[: marked[0]])


def test_the_mark_is_stored_and_checked_on_resume(tmp_path: Path) -> None:
    rows = segment_chapter_text(1, _text("***"))
    db = ProjectDB(tmp_path / "project.sqlite3")
    db.initialize_book(title="Book", project_root=tmp_path, settings={}, settings_hash="s", input_manifest_hash="m")
    chapter_id = db.ensure_chapters([{"chapter_index": 1, "title": "One", "input_path": tmp_path / "one.txt",
                                      "input_sha256": "src", "input_size": 1, "output_mp3": tmp_path / "one.mp3"}])[0]
    db.replace_chapter_segments(chapter_id, rows)
    stored = db.list_segments(chapter_id=chapter_id)
    assert [(row["break_ms"], row["scene_break"]) for row in stored] == [(SCENE_BREAK_MS, 1), (0, 0)]
    assert "scene_break" in SEGMENTATION_CHECKPOINT_FIELDS
    for expected, checkpoint in zip(rows, stored):
        assert all(expected[field] == checkpoint[field] for field in SEGMENTATION_CHECKPOINT_FIELDS)


def test_a_database_made_before_the_flag_gains_the_column(tmp_path: Path) -> None:
    import sqlite3

    path = tmp_path / "project.sqlite3"
    ProjectDB(path).initialize_book(title="Book", project_root=tmp_path, settings={}, settings_hash="s", input_manifest_hash="m")
    with sqlite3.connect(path) as conn:
        conn.execute("ALTER TABLE segments DROP COLUMN scene_break")
    ProjectDB(path).initialize_book(title="Book", project_root=tmp_path, settings={}, settings_hash="s", input_manifest_hash="m")
    with sqlite3.connect(path) as conn:
        assert "scene_break" in {row[1] for row in conn.execute("PRAGMA table_info(segments)")}


def test_the_pause_survives_the_expression_rules_and_their_ceiling() -> None:
    assert SCENE_BREAK_MS > PAUSE_CEILING_MS, "this is the case the ceiling would clip"
    feeling = {"kind": "dialogue", "emotion": "angry", "intensity": 3, "text": "Đi đi!", "scene_break": True}
    following = {"kind": "dialogue", "emotion": "afraid", "intensity": 3, "text": "Không!"}
    assert narrative_break_ms(SCENE_BREAK_MS, feeling, None, following) == SCENE_BREAK_MS
    ordinary = dict(feeling, scene_break=False)
    assert narrative_break_ms(380, ordinary, None, following) <= PAUSE_CEILING_MS


def test_the_pause_reaches_the_audio_concat_entries(tmp_path: Path) -> None:
    rows = segment_chapter_text(1, _text("***"))
    db_rows = []
    for index, row in enumerate(rows):
        wav = tmp_path / f"{index}.wav"
        sf.write(wav, (0.0005 * np.sin(np.arange(24000) / 7.0)).astype(np.float32), 24000, subtype="PCM_16")
        db_rows.append({**row, "wav_path": str(wav), "voice_profile_id": 0, "emotion": "neutral", "intensity": 0})

    class _Db:
        @staticmethod
        def list_voice_profiles() -> list:
            return []

    pipeline = BookPipeline.__new__(BookPipeline)
    pipeline.db = _Db()
    pipeline.paths = type("Paths", (), {"work": tmp_path / "work"})()
    pipeline.log = lambda *_args, **_kwargs: None
    entries = pipeline._chapter_delivery_wavs({"chapter_index": 1}, db_rows)
    assert [ms for _path, ms in entries] == [SCENE_BREAK_MS, 0]
    _elapsed, break_ranges, _joins = _source_timeline(entries, 24000)
    assert [round(end - start, 3) for start, end in break_ranges] == [1.5]


def test_the_flag_reaches_the_music_planner() -> None:
    scene = [{"id": index, "text": f"Câu {index}.", "kind": "narration", "emotion": "neutral", "intensity": 0,
              "start": index * 5.0, "end": index * 5.0 + 4.0} for index in range(30)]
    scene[14]["sceneBreak"] = True
    assert hard_break(scene[15], scene[14]) == "separator"
    assert hard_break(scene[14], scene[13]) is None and hard_break(scene[15]) is None
    scenes = chapter_scenes({"chapterId": 1, "segments": scene})
    assert [(item["reason"], item["firstSegment"]) for item in scenes] == [("chapter_start", 0), ("separator", 15)]
