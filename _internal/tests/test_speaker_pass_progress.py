"""Màn dự án nói về lượt "người nói từng câu" (speaker_pass.py): tên bước, tiến độ chương, thời gian còn lại (+~6 %)."""
from __future__ import annotations

from pathlib import Path

from abook import speaker_pass as sp
from abook.config import build_settings, save_settings
from abook.webui import store
from tests.test_listener_speakers import _book


def _analysed_book(tmp_path: Path, *, paired: bool):
    paths, db = _book(tmp_path)
    settings = build_settings("high_quality", {"analysis": {"model": "abook-analyzer:v5" if paired else "qwen3:8b"}})
    save_settings(paths.settings, settings)
    db.update_book(status="analyzing", stage="speaker_pass")
    with db.connect() as conn:
        conn.execute("UPDATE segments SET status='analyzed', wav_path=NULL, wav_sha256=NULL")
    return paths, db


def test_the_project_page_shows_the_speaker_pass_as_its_own_step(tmp_path: Path) -> None:
    paths, db = _analysed_book(tmp_path, paired=True)
    summary = store.summarize(paths.root, running=True)
    assert summary["phase"] == "analysis" and summary["statusLabel"] == "Đang xác định người nói từng câu"
    assert summary["speakerPass"] == {"done": 0, "total": 1, "active": True}
    assert summary["eta"] == {"phase": "speaker", "seconds": round(sp.SPEAKER_PASS_SECONDS_PER_CHAPTER)}
    assert summary["progress"]["analysis"] == round(1 - store.SPEAKER_PASS_SHARE, 4), "phân tích chưa đầy khi lượt chưa xong"

    chapter = int(db.list_chapters()[0]["id"])
    rows = [r for r in db.list_segments(chapter_id=chapter) if str(r["kind"]) in ("dialogue", "thought")]
    db.commit_speaker_pass_chapter(chapter, [(int(r["id"]), str(r["speaker"]), str(r["speaker"])) for r in rows], {}, seconds=30.0)
    done = store.summarize(paths.root, running=True)
    assert done["speakerPass"] == {"done": 1, "total": 1, "active": True}
    assert done["progress"]["analysis"] == 1.0 and done["eta"] == {"phase": "speaker", "seconds": 0}

    db.update_book(status="analyzing", stage="full_book_analysis")
    assert store.summarize(paths.root, running=True)["statusLabel"] == "Đang phân tích truyện"
    db.update_book(status="paused", stage="paused")
    assert store.summarize(paths.root, running=False)["statusLabel"] != "Đang xác định người nói từng câu"


def test_the_analysis_estimate_already_counts_the_pass_that_follows_it(tmp_path: Path, monkeypatch) -> None:
    paths, db = _analysed_book(tmp_path, paired=True)
    db.update_book(status="analyzing", stage="full_book_analysis")
    with db.connect() as conn:
        conn.execute("UPDATE segments SET status='pending' WHERE seq = 0")
    monkeypatch.setattr(store, "_rate", lambda *_args: 1.0)         # 1 câu/giây: 1 câu chờ = 1 giây
    eta = store.summarize(paths.root, running=True)["eta"]
    assert eta == {"phase": "analysis", "seconds": 1 + round(sp.SPEAKER_PASS_SECONDS_PER_CHAPTER)}


def test_a_book_without_the_pass_is_summarised_as_before(tmp_path: Path) -> None:
    paths, _db = _analysed_book(tmp_path, paired=False)
    summary = store.summarize(paths.root, running=True)
    assert summary["speakerPass"] is None and summary["progress"]["analysis"] == 1.0
