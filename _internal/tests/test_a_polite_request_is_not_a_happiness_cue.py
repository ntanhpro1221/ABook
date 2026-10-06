"""Công thức lịch sự ("vui lòng", "làm ơn") không phải cue vui: lời từ chối lạnh lùng không bị ép happy.

Hai thầy gán nhãn 06-10: "Cô vui lòng rời khỏi đây được không?" - host đọc "vui" là cue happy và chỉ cho phép happy.
"""
from __future__ import annotations

from abook.analysis import _direct_cue_allowed_emotions, _semantic_cue_matches


def test_vui_long_in_a_cold_refusal_allows_any_emotion() -> None:
    text = "“Xin lỗi, giờ tôi đang bận. Cô vui lòng ra ngoài được không?”"
    assert "happy" not in _semantic_cue_matches(text)
    assert _direct_cue_allowed_emotions(text) == ()


def test_lam_on_is_not_a_happiness_cue() -> None:
    assert "happy" not in _semantic_cue_matches("“Làm ơn để tôi yên.”")


def test_real_joy_is_still_a_happiness_cue() -> None:
    for text in ("Cô bé vui quá, nhảy cẫng lên.", "Anh vui vẻ gật đầu.", "Cả nhà vui mừng khôn xiết."):
        assert _direct_cue_allowed_emotions(text) == ("happy",), text
