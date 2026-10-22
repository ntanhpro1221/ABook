"""a89 V8: yêu cầu bị dây chuyền từ chối không im lặng - nhận biết ngay khi gửi (lời dẫn rồi đổi người nói), có câu tiếng Việt ở nhật ký, có thẻ trong hộp việc."""
from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path

import pytest

from abook import listener_overrides as lo
from abook.database import ProjectDB
from abook.models import ProjectPaths
from abook.webui import humanize, store, work_items
from tests.test_listener_speakers import _book


def _sha(paths, stable_id: str) -> str:
    with closing(store.connect(paths.root)) as connection:
        return str(connection.execute("SELECT text_sha256 FROM segments WHERE stable_id=?", (stable_id,)).fetchone()[0])


def _dialogue_with_speaker(paths) -> tuple[str, str, str]:
    with closing(store.connect(paths.root)) as connection:
        row = connection.execute("SELECT stable_id, text_sha256, speaker FROM segments WHERE kind='dialogue' AND voice_profile_id IS NOT NULL LIMIT 1").fetchone()
    return str(row["stable_id"]), str(row["text_sha256"]), str(row["speaker"])


def test_a_speaker_request_after_a_pending_narration_fix_is_refused_up_front(tmp_path: Path) -> None:
    paths, _db = _book(tmp_path)
    stable_id, sha, speaker = _dialogue_with_speaker(paths)
    assert store.speaker_request_problem(paths.root, stable_id, sha, speaker) is None
    lo.request_line(paths.root, stable_id, sha, kind="narration", now=10.0)
    assert store.speaker_request_problem(paths.root, stable_id, sha, speaker) == lo.NOT_SPEECH
    lo.request_line(paths.root, stable_id, sha, kind="dialogue", now=20.0)  # đổi ý: lại là lời thoại
    assert store.speaker_request_problem(paths.root, stable_id, sha, speaker) is None


def test_the_rejection_has_plain_vietnamese_text_in_the_activity_log(tmp_path: Path) -> None:
    paths, _db = _book(tmp_path)
    stable_id, sha, speaker = _dialogue_with_speaker(paths)
    db = ProjectDB(ProjectPaths.build(paths.root).db)
    db.event("warning", "LISTENER_OVERRIDE_REJECTED", f"Không gán được câu {stable_id} cho {speaker!r} (not_speech).",
             {"stable_id": stable_id, "speaker": speaker, "problem": lo.NOT_SPEECH})
    texts = [item["text"] for item in store.activity(paths.root) if item["kind"] == "event"]
    assert len(texts) == 1
    assert "not_speech" not in texts[0] and "lời dẫn" in texts[0] and stable_id not in texts[0], texts
    assert humanize.event_level("LISTENER_OVERRIDE_REJECTED", "warning") == "warning"


def test_every_rejection_code_has_a_reason() -> None:
    codes = {value for name, value in vars(lo).items()
             if name.isupper() and isinstance(value, str) and name in {
                 "MULTI_WORD", "NOT_VIETNAMESE", "UNKNOWN_LINE", "SOURCE_CHANGED", "NOT_SPEECH", "NO_VOICE", "UNKNOWN_CHARACTER",
                 "NOT_A_CHARACTER", "UNKNOWN_PRESET", "BAD_GENDER", "BAD_KIND", "BAD_EMOTION", "BAD_TEXT", "VOICE_TAKEN", "NARRATOR_VOICE_ONLY"}}
    assert codes <= set(humanize.REJECTED_REASON)


def test_a_rejected_request_that_is_still_waiting_gets_a_card_and_a_withdrawn_one_does_not(tmp_path: Path) -> None:
    paths, _db = _book(tmp_path)
    stable_id, sha, speaker = _dialogue_with_speaker(paths)
    lo.request_speaker(paths.root, stable_id, sha, speaker, now=30.0)
    db = ProjectDB(ProjectPaths.build(paths.root).db)
    db.event("warning", "LISTENER_OVERRIDE_REJECTED", "x", {"stable_id": stable_id, "speaker": speaker, "problem": lo.NO_VOICE})
    cards = [item for item in work_items.work_items(paths.root)["items"] if item["kind"] == "refused"]
    assert len(cards) == 1
    card = cards[0]
    assert card["refused"] == {"section": "speakers", "key": stable_id, "requestedAt": 30.0}
    assert "chưa có giọng" in card["problem"] and "no_voice" not in json.dumps(card, ensure_ascii=False)
    lo.withdraw_requests(paths.root, "speakers", [stable_id], 30.0)
    assert not [item for item in work_items.work_items(paths.root)["items"] if item["kind"] == "refused"]
    lo.request_speaker(paths.root, stable_id, sha, "SOMEONE ELSE", now=40.0)  # yêu cầu khác: sự kiện cũ không còn nói về nó
    assert not [item for item in work_items.work_items(paths.root)["items"] if item["kind"] == "refused"]
