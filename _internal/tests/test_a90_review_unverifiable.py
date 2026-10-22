"""a90 V1: mọi cảnh báo "ASR không phán xử được" (và mã ghép bằng `|`) vào nhóm "Chưa kiểm được", không hiện transcript ảo."""
import pytest

from abook.webui import reviews

HALLUCINATION = "Cảm ơn các bạn đã theo dõi."


@pytest.mark.parametrize("code, similarity", [
    ("ASR_UNVERIFIABLE_SHORT_TEXT", 0.9),
    ("ASR_TRANSCRIPT_TIMELINE_IMPOSSIBLE", 0.1),
    ("ASR_TRANSCRIPT_RATE_IMPOSSIBLE", 0.3),
    ("TTS_GENERATION_CEILING_REACHED|ASR_TRANSCRIPT_TIMELINE_IMPOSSIBLE", 0.1),
    ("TTS_GENERATION_CEILING_REACHED|ASR_UNVERIFIABLE_SHORT_TEXT", 0.95),
    ("ASR_LOCKED_NAME_ANCHOR_REVIEW|ASR_TRANSCRIPT_RATE_IMPOSSIBLE", 0.5),
])
def test_unanswerable_asr_warnings_are_unverified_whatever_the_similarity(code, similarity):
    assert reviews._kind("warning", code, similarity) == "unverified"


@pytest.mark.parametrize("code", ["", "ASR_MISMATCH_UNRESOLVED", "ASR_LOCKED_NAME_ANCHOR_MISMATCH", "TTS_GENERATION_CEILING_REACHED"])
def test_other_warnings_keep_their_kind(code):
    assert reviews._kind("warning", code, 0.95) in ("text", "name")
    assert reviews._kind("warning", code, 0.5) in ("text-low", "name-low")


def test_review_rows_show_unverifiable_lines_by_default_without_the_phantom_transcript(tmp_path):
    from tests.test_listener_speakers import _book

    paths, db = _book(tmp_path)
    codes = {"c1s1": "ASR_UNVERIFIABLE_SHORT_TEXT", "c1s2": "ASR_TRANSCRIPT_RATE_IMPOSSIBLE",
             "c1s3": "TTS_GENERATION_CEILING_REACHED|ASR_TRANSCRIPT_TIMELINE_IMPOSSIBLE"}
    with db.connect() as connection:
        for stable_id, code in codes.items():
            connection.execute("UPDATE segments SET status='warning', warning_code=?, asr_text=?, asr_similarity=0.9"
                               " WHERE stable_id=?", (code, HALLUCINATION, stable_id))
    view = reviews.review_view(paths.root, {}, include_minor=False)
    assert {item["stableId"] for item in view["items"]} == set(codes)
    assert all(item["kind"] == "unverified" and item["heard"] == "" for item in view["items"])
    assert view["counts"]["unverified"] == 3 and view["pending"] == 3
    assert "không kiểm được" in reviews.REASONS["unverified"]
