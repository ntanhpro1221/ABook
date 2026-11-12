"""Luật "tên ngay trước 'nói:' là người nói" im khi tên là người NGHE hay mẩu tên bị cắt (cuốn 2: ~29 câu)."""
from __future__ import annotations

from abook.analysis import _trailing_speech_attribution


def test_the_listener_named_before_the_speech_verb_is_not_the_speaker() -> None:
    for text in (
        'Nhìn Neeshka, Salgueiro và tổ thợ in dọn bàn, Levski quay sang Lucien nói:',
        'Ông mở hộp tem rồi nhìn Lucien nói:',
        'Công tước James cầm tờ phiếu nhìn Tử tước Harrison nói:',
        'Lucien gấp lịch tàu rồi dùng giọng Beaulac nói:',
        'Sau khi so màu mực, ông khẽ cười với Heidi nói:',
        'Xếp xong hộp mực, Benjamin chỉ tay về đám người Lucien nói:',
        'Lucien kiểm lại nhãn của Heidi, sau đó quay sang tổ thợ Annick nói:',
        'Lucien chưa đọc bảng kê mà dùng giọng nghiêm nghị của một thợ in nói:',
    ):
        assert _trailing_speech_attribution(text) is None, text


def test_a_name_cut_short_by_its_accents_is_not_a_name() -> None:
    assert _trailing_speech_attribution('Chưa rõ cách đóng dấu của Giáo Sư, Triết Gia hỏi:') is None
    assert _trailing_speech_attribution('một tay giữ cuộn giấy của Trịnh Vĩnh Mong nói:') is None


def test_the_subject_still_takes_the_line() -> None:
    assert _trailing_speech_attribution("Lucien nói:") == "Lucien"
    assert _trailing_speech_attribution("Rồi Lucien nói:") == "Lucien"
    assert _trailing_speech_attribution("Sau đó, Lucien hỏi:") == "Lucien"
    assert _trailing_speech_attribution('Khi tổ thợ đóng xong hộp mực, tổng giám mục Augustus nói:') == "Augustus"
    assert _trailing_speech_attribution('Đại hồng y vừa kiểm kê Philip nói:') == "Philip"
    assert _trailing_speech_attribution('Nhìn Natasha với tờ phiếu trên tay, Bá tước Barady nói:') == "Barady"
    assert _trailing_speech_attribution('chưa kể mực vẫn còn đủ, thế nên Raventi nói:') == "Raventi"
