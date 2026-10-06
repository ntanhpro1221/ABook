"""Tab "Cần nghe lại": câu hỏng sau mọi lần thử (tượng thanh "Tách tách tách", chữ lạ) sửa CHỮ ĐEM ĐỌC ngay trên thẻ (soát
UX a5/a6 01-10: chỉ có "Thu lại", mà thu lại y chữ thì hỏng y như cũ). Thẻ cần băm chữ để gửi yêu cầu, thấy chữ đang chờ áp,
và câu đã có cách xử lý thì không còn tính là "chưa xem"."""
from __future__ import annotations

from pathlib import Path

from abook import listener_overrides
from abook.webui import reviews
from tests.test_listener_speakers import _book


def test_a_failed_line_offers_a_spoken_fix_and_counts_as_handled_once_written(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE segments SET status='failed', wav_path=NULL WHERE stable_id='c1s1'")
    root = paths.root

    item = next(entry for entry in reviews.review_items(root) if entry["stableId"] == "c1s1")
    assert (item["kind"], item["textSha256"], item["spoken"], item["pendingSpoken"]) == ("failed", "sha-c1s1", None, None)
    assert reviews.review_view(root, {}, include_minor=False)["pending"] == 1

    listener_overrides.request_line(root, "c1s1", "sha-c1s1", spoken="tách, tách, tách", now=100.0)
    item = next(entry for entry in reviews.review_items(root) if entry["stableId"] == "c1s1")
    assert item["pendingSpoken"] == "tách, tách, tách"
    assert reviews.review_view(root, {}, include_minor=False)["pending"] == 0, "đã có cách xử lý: không còn chờ xem"

    # Dây chuyền áp: câu về hàng chờ thu bằng chữ mới, thẻ hết "chờ áp" (rời hàng vì không còn hỏng).
    assert db.apply_listener_line(stable_id="c1s1", text_sha256="sha-c1s1", spoken="tách, tách, tách") is not None
    assert all(entry["stableId"] != "c1s1" for entry in reviews.review_items(root))


def test_a_line_whose_own_take_was_cleaned_up_plays_from_the_chapter_audio(tmp_path: Path) -> None:
    """WAV riêng của câu đã dọn sau khi ghép chương: thẻ vẫn nghe được, bằng đúng đoạn ấy trong file chương (mốc như đọc
    theo) - trước đây nút nghe tắt hẳn."""
    paths, db = _book(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE segments SET wav_duration=2.0, break_ms=500")
        conn.execute("UPDATE segments SET status='warning', asr_similarity=0.5 WHERE stable_id IN ('c1s2', 'c1s3')")
        conn.execute("UPDATE segments SET status='failed' WHERE stable_id='c1s3'")
    root = paths.root

    item = next(entry for entry in reviews.review_items(root) if entry["stableId"] == "c1s2")
    assert (item["playable"], item["chapterClip"]) == (False, None), "chương chưa có file MP3 thì chưa có gì để nghe"

    chapters = root / "output" / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    (chapters / "001.mp3").write_bytes(b"not audio")  # không đọc được độ dài: mốc cộng từ các câu, không co giãn
    items = {entry["stableId"]: entry for entry in reviews.review_items(root)}
    assert items["c1s2"]["chapterClip"] == {"start": 5.0, "end": 7.0}, "câu thứ ba: 2 x (2 s + 0,5 s nghỉ)"
    assert items["c1s3"]["chapterClip"] is None, "câu hỏng chưa từng có bản thu - không lấy đoạn chương"
