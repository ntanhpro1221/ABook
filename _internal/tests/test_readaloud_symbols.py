"""Ký hiệu trong "Nghe ngay" (VieNeu): `abook.readaloud.symbols` đọc theo ngữ cảnh ±3 chữ. Câu mẫu tự viết, không lấy từ truyện.
Cùng các câu này chạy bên điện thoại (`SymbolsTest.kt`, dữ liệu dùng chung ở tests/fixtures/vieneu/android/text.json)."""
from __future__ import annotations

import pytest

from abook.readaloud import vieneu
from abook.webui import word_timing


def _said(text: str) -> str:
    toks = word_timing.tokens(text)
    said = vieneu.spoken_tokens(toks, None, True)
    assert len(said) == len(toks)  # số chữ không đổi: mốc thời gian không lệch
    return " ".join(said)


# ---- Bậc 0: im hay ngắt ------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, said", [
    ("Anh · em · chúng ta cùng đi.", "Anh,  em,  chúng ta cùng đi."),  # chấm giữa: ngắt
    ("Số 2^10 là 1024, còn ^ lẻ loi thì im.", "Số 2 mũ 10 là 1024, còn  lẻ loi thì im."),  # giữa hai số là "mũ"
    ("Nếu a < b thì 3 > 2, nhưng < hay > đứng một mình thì im.", "Nếu a < b thì 3 > 2, nhưng,  hay  đứng một mình thì im."),  # so sánh giữ cho engine
    ("Số #7 và # đơn độc.", "Số 7 và  đơn độc."),
    ("Gửi thư tới nam@example.com hoặc nhắn @ đây.", "Gửi thư tới nam@example.com hoặc nhắn a còng đây."),
    ("Chửi thề kiểu !@#$% cho vui.", "Chửi thề kiểu  cho vui."),
    ("Cậu cười (^_^) rồi (°ω°) và (=_=) xong.", "Cậu cười  rồi  và  xong."),
    ("Chuyện hay === hết phần một === rồi.", "Chuyện hay  hết phần một  rồi."),
    ("▲ Tăng nhiều ▼ giảm bớt.", " Tăng nhiều  giảm bớt."),  # đã có chữ chỉ hướng: mũi tên im
    ("《Kiếm Thánh》x3 và <<Ray Hawk>> và <\"Ma Vương\"> và <Chạy đi, mau!>.", "Kiếm Thánh,nhân 3 và, Ray Hawk, và, \"Ma Vương\" và, Chạy đi, mau!."),
    ("Cô gọi ☎ 0912345678 ngay.", "Cô gọi điện thoại 0912345678 ngay."),
])
def test_a_symbol_without_a_reading_is_silent_or_a_pause(text: str, said: str) -> None:
    assert _said(text) == said


# ---- Bậc 1: gạch chéo, tiền, độ, phần trăm -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, said", [
    ("Ngày 3/9 và tỉ lệ 1/3 và 10 người/ngày.", "Ngày 3 tháng 9 và tỉ lệ 1 phần 3 và 10 người mỗi ngày."),
    ("Hôm nay ngày 5/3 trời đẹp, sinh nhật 12/10 của cô, thứ Hai 3/9 nữa.", "Hôm nay ngày 5 tháng 3 trời đẹp, sinh nhật ngày 12 tháng 10 của cô, thứ Hai ngày 3 tháng 9 nữa."),
    ("Mùng 5/3 vui, hạn nộp 15/8 nhé, ngày 2/9/2026 và tỉ lệ 5/3.", "Mùng 5 tháng 3 vui, hạn nộp ngày 15 tháng 8 nhé, ngày 2/9/2026 và tỉ lệ 5/3."),
    ("Tối đa 3/5 rồi. HP 5813/5813 và 15/8 nữa.", "Tối đa 3 phần 5 rồi. hát pê 5813/5813 và 15/8 nữa."),  # không có chữ chỉ ngày: chỉ số / tỉ lệ / phân số, không đọc ngày
    ("Giá $5, 100$ và 30°C.", "Giá 5 đô la, 100 đô la và 30°C."),
    ("Điểm tăng 2 × 3 lần, 4x3 là mười hai, x5 mạnh hơn.", "Điểm tăng 2 nhân 3 lần, 4 nhân 3 là mười hai, nhân 5 mạnh hơn."),
    ("Nhiệt độ -5 độ, từ 7 – 8cm, 3 -> 5 người, A -> B -> C.", "Nhiệt độ âm 5 độ, từ 7 đến 8cm, 3 thành 5 người, A rồi B rồi C."),
    ("Tiền là 3-1 và hạng 4★.", "Tiền là 3 1 và hạng 4 sao."),
])
def test_a_symbol_with_a_number_is_read_by_its_neighbours(text: str, said: str) -> None:
    assert _said(text) == said


# ---- 15 điều Lead quyết 04-10 -----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, said", [
    # 1. số lượng vật phẩm
    ("Nhận được [Quặng sắt x4] và R-Lọ mana x10, rồi 1x Cuộn phép.", "Nhận được, [Quặng sắt nhân 4], và R-Lọ mana nhân 10, rồi 1 Cuộn phép."),
    # 2. tỉ lệ, đấu tay đôi, kèo cược
    ("Chia tiền 7:3 nhé.", "Chia tiền 7 3 nhé."),
    ("Hai người đấu 1:1 ở sân sau, rồi đấu 1-1 tiếp.", "Hai người đấu 1 chọi 1 ở sân sau, rồi đấu 1 chọi 1 tiếp."),
    ("Kèo cược 3.17:1 là cao.", "Kèo cược 3 phẩy mười bảy ăn 1 là cao."),
    # 3. chỉ số sau dấu hai chấm là âm, lượng đổi là trừ
    ("Độ thiện cảm: -20, rồi -50% Nhanh nhẹn, [Sức mạnh -5], Mất thêm -15%.", "Độ thiện cảm: âm 20, rồi trừ 50% Nhanh nhẹn, [Sức mạnh trừ 5], Mất thêm trừ 15%."),
    ("Điểm Lv.-1 hiện ra.", "Điểm lờ vê.âm 1 hiện ra."),
    # 4. #CHỮ im, S#.1 là cảnh
    ("#KHÔNG là thẻ, S#.1 mở màn, #5 là số.", "KHÔNG là thẻ, cảnh 1 mở màn, số 5 là số."),
    # 5. Q&A, S&M, và
    ("Mục Q&A, ban nhạc S&M, kiếm & khiên.", "Mục hỏi đáp, ban nhạc S en M, kiếm và khiên."),
    # 6. cộng giữa danh từ là "và", đầu tên kỹ năng im
    ("Kiếm + khiên thì hợp, +Hỏa cầu.", "Kiếm và khiên thì hợp, Hỏa cầu."),
    # 7. xếp hạng
    ("Thầy giáo > Học trò > Sơ sinh, 5 > 3.", "Thầy giáo hơn Học trò hơn Sơ sinh, 5 > 3."),
    # 8. dấu bằng
    ("Vương đô = Thủ đô, 2 + 3 = 5, nhìn =)) xong.", "Vương đô bằng Thủ đô, 2 + 3 bằng 5, nhìn  xong."),
    # 9. đường dẫn
    ("Xem tại https://example.org/abc?x=1 nhé.", "Xem tại đường dẫn nhé."),
    # 10. thang sao
    ("★★★☆☆ và ★5,0 và ★MAX, ★★☆ -> ★★★ rồi.", "ba sao và 5 phẩy 0 sao và sao tối đa, hai sao thành ba sao rồi."),
    # 11. giới tính
    ("Tộc: Elf ♀, giới: ♂, Ayame♀ xong.", "Tộc: Elf nữ, giới: nam, Ayame xong."),
    # 12. tăng giảm
    ("Tấn công (↑1), phòng thủ ▲(0.15).", "Tấn công (tăng 1), phòng thủ tăng (0 phẩy mười lăm)."),
    # 13. gấp
    ("Boost 3x, 100x cấp độ, 0.5x tốc độ.", "Boost gấp 3, gấp 100 lần cấp độ, 0,5 lần tốc độ."),
    # 14. cặp đôi
    ("Aki × Rin là một cặp, Bảng Nhiệm Vụ × Nhiệm Vụ Phụ mở ra, 3 × 4.", "Aki và Rin là một cặp, Bảng Nhiệm Vụ,  Nhiệm Vụ Phụ mở ra, 3 nhân 4."),
    # 15. khác
    ("Cô ấy ≠ chị ta.", "Cô ấy không phải là chị ta."),
])
def test_the_leads_decisions_of_04_10(text: str, said: str) -> None:
    assert _said(text) == said


def test_a_phone_number_without_the_symbol_is_unchanged() -> None:
    assert _said("Gọi 0912345678 nhé.") == "Gọi 0912345678 nhé."
