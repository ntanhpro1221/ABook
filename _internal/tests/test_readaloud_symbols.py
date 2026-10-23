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
    ("Mùng 5/3 vui, hạn nộp 15/8 nhé, ngày 2/9/2026 và tỉ lệ 5/3.", "Mùng 5 tháng 3 vui, hạn nộp ngày 15 tháng 8 nhé, ngày 2/9/2026 và tỉ lệ 5 trên 3."),
    ("Tối đa 3/5 rồi. HP 5813/5813 và 15/8 nữa.", "Tối đa 3 phần 5 rồi. hát pê 5813 trên 5813 và 15 tháng 8 nữa."),  # "3/5" phân số, thanh chỉ số nói "trên" ngay (Edge không qua sea-g2p); "15/8" lớn hơn 12 ở số đầu mà vế sau là tháng hợp lệ: ngày tháng
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
    ("Hẹn 12:30 chia tay ở cổng.", "Hẹn 12:30 chia tay ở cổng."),
    ("Họ chia tay 9:05 sáng, đóng 6:00 lệ phí.", "Họ chia tay 9:05 sáng, đóng 6:00 lệ phí."),
    ("Tỉ lệ 7:3, tỉ số 2:1, chia 8:2.", "Tỉ lệ 7 3, tỉ số 2 1, chia 8 2."),
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
    ("Boost 3x, 100x cấp độ, 0.5x tốc độ.", "Boost 3 lần, 100 lần cấp độ, 0,5 lần tốc độ."),
    # 14. cặp đôi
    ("Aki × Rin là một cặp, Bảng Nhiệm Vụ × Nhiệm Vụ Phụ mở ra, 3 × 4.", "Aki và Rin là một cặp, Bảng Nhiệm Vụ,  Nhiệm Vụ Phụ mở ra, 3 nhân 4."),
    # 15. khác
    ("Cô ấy ≠ chị ta.", "Cô ấy không phải là chị ta."),
])
def test_the_leads_decisions_of_04_10(text: str, said: str) -> None:
    assert _said(text) == said


# ---- tn10 (16-10): quy ước đọc ký hiệu vòng 2 - "-" trước số, mũi tên, "/", "x", "↓", "=", "*", toàn khổ, "+" ----------------------------
@pytest.mark.parametrize("text, said", [
    ("Nhiệt độ -5 độ, tọa độ (-3, 4) và năm -2324. Bị [Thất bại: -90%], HP -20, Blue -1, MK-2, rồi 10 - 3 = 7 và 8-2=6.",
     "Nhiệt độ âm 5 độ, tọa độ (âm 3, 4) và năm âm 2324. Bị, [Thất bại: trừ 90%], hát pê trừ 20, Blue trừ 1, em ca-2, rồi 10 trừ 3 bằng 7 và 8 trừ 2 bằng 6."),
    ("Còn -50% Nhanh nhẹn, thanh máu của Shido -1. Tôi mười tám (-2) nhé.",
     "Còn trừ 50% Nhanh nhẹn, thanh máu của Shido trừ 1. Tôi mười tám (âm 2) nhé."),
    ("Đánh giá 4/5 sao, điểm 9.7/10, hết 1/4 máu, rồi 24/7. Ngày 8/3 là ngày hội, còn 3/4 cốc nước.",
     "Đánh giá 4 trên 5 sao, điểm 9.7 trên 10, hết 1 phần tư máu, rồi 24 trên 7. Ngày 8 tháng 3 là ngày hội, còn 3 phần tư cốc nước."),
    ("Hầm trú -> Một ngày mới -> Mặt trời. → Biến hóa → Honnoshi. Tokyo → Osaka. Máu 10 → 20 → 30.",
     "Hầm trú rồi Một ngày mới rồi Mặt trời.  Biến hóa rồi Honnoshi. Tokyo thành Osaka. Máu 10 rồi 20 rồi 30."),
    ("Bá Vương bị chọc giận. ATK↑ DEF↓. Lượt đọc: ↓ và Đông 4↓ xong.",
     "Bá Vương bị chọc giận. a tê ca tăng đê e ép giảm. Lượt đọc: giảm và Đông 4 xong."),
    ("Cho y=ax² và x >= 3, a <= 5. ８－２＝６ ＡＢＣ １２ ＋ xong.",
     "Cho y bằng ax² và x lớn hơn hoặc bằng 3, a nhỏ hơn hoặc bằng 5. 8 trừ 2 bằng 6 ABC 12 + xong."),
    ("Trans+Edit và 2+3=5, A + B. Tầng 8x và năm 200x, 19××, từ 0x đến 1x. Tăng 3x tốc độ, 5x damage.",
     "Trans và Edit và 2+3 bằng 5, A cộng B. Tầng 8 ích và năm 200 ích, 19 ích ích, từ 0 lần đến 1 lần. Tăng 3 lần tốc độ, 5 lần damage."),
    ("Hình hent*i và E**alibur, *boing**boing* rồi “*Khụ*Khụ*” xong.",
     "Hình hent… i và E… alibur, boing, boing rồi “Khụ, Khụ” xong."),
])
def test_the_symbol_conventions_of_tn10(text: str, said: str) -> None:
    assert _said(text) == said


# ---- Vòng 3 (tn11): khoảng giờ, chuỗi phím, ↓ ↑, × dấu / nhân, x sau số, dấu trừ, chia, trên ------------------------------
@pytest.mark.parametrize("text, said", [
    ("Họp 8:00 → 10:00 sáng. Lv3 → Lv4, đỏ → xanh.", "Họp 8:00 đến 10:00 sáng. level 3 thành level 4, đỏ thành xanh."),  # hai giờ là khoảng "đến", không phải bảng chỉ số
    ("Nhấn ↑↑↓↓←→←→BABA nhé, bay →→→→ đi.", "Nhấn lên lên xuống xuống trái phải trái phải bê a bê a nhé, bay  đi."),
    ("Sức mạnh 9↓, DEF↓ và (9↓) nữa.", "Sức mạnh 9 giảm, đê e ép giảm và (9 giảm) nữa."),
    ("↓ = Có", "xuống là Có"),
    ("Cậu nhớ [—↓] nhé.", "Cậu nhớ, [—], nhé."),
    ("Đáp án của em là ×. Tên 〇〇 ×× và ○×△ xong. Fit Course × Pro Master. Gói ×Course. Tính 3×4 và 100×99×98×⋯×3.", "Đáp án của em là . Tên 〇〇  và ○ xong. Fit Course,  Pro Master. Gói ích Course. Tính 3 nhân 4 và 100 nhân 99 nhân 98 nhân⋯nhân 3."),
    ("Năm 9x, thứ 9x, chương 9x, 3x tuổi. Tính sin 2x + 1 = 3x.", "Năm 9 ích, thứ 9 ích, chương 9 ích, 3 ích tuổi. Tính sin 2 ích + 1 bằng 3 ích."),
    ("Nhận 10x Sức mạnh, (2x Intelligence), kính ngắm 8x, 1x Cuộn phép, mã 202X.", "Nhận 10 lần Sức mạnh, (2 lần Intelligence), kính ngắm 8 lần, 1 Cuộn phép, mã 202 ích."),
    ("-25 máu. “-1600” vàng. Kết toán -1600 vàng, đòn -25 máu.", "âm 25 máu. “âm 1600” vàng. Kết toán âm 1600 vàng, đòn trừ 25 máu."),
    ("Tuyệt mệnh -10: giảm máu. 1-2-3 -25 xong.", "Tuyệt mệnh trừ 10: giảm máu. 1 2 3 trừ 25 xong."),
    ("Sức khỏe / 2. HP 100/250 và 8/3.", "Sức khỏe chia 2. hát pê 100 trên 250 và 8 tháng 3."),
])
def test_the_symbol_conventions_of_tn11(text: str, said: str) -> None:
    assert _said(text) == said


# ---- "/" giữa hai đơn vị đo là "trên": để nguyên cả cặp, sea-g2p đọc "ki lô mét trên giờ" (soát UX a23) ----------------------------------
@pytest.mark.parametrize("text, said", [
    ("Xe chạy 50km/h, gió 3 m/s và 60 km/h.", "Xe chạy 50km/h, gió 3 m/s và 60 km/h."),
    ("Tốc độ km/h thôi, nặng 3 kg/m2, thuốc 5 mg/ml, đổ 2 L/h.", "Tốc độ km/h thôi, nặng 3 kg/m2, thuốc 5 mg/ml, đổ 2 L/h."),
    # không phải hai đơn vị: luật cũ
    ("Chọn và/hoặc bỏ, Mở/đóng cửa, ngày 12/3, ăn 1/2 cái, 10 DP/ngày, size M/L.",
     "Chọn và, hoặc bỏ, Mở, đóng cửa, ngày 12 tháng 3, ăn 1 phần 2 cái, 10 DP mỗi ngày, size M, L."),
    ("Hạn 10 lần/ngày, 3 chương/tuần.", "Hạn 10 lần mỗi ngày, 3 chương mỗi tuần."),
])
def test_a_slash_between_two_units_is_left_for_the_per_reading(text: str, said: str) -> None:
    assert _said(text) == said


def test_a_phone_number_without_the_symbol_is_unchanged() -> None:
    assert _said("Gọi 0912345678 nhé.") == "Gọi 0912345678 nhé."
