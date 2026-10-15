package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Test
import vn.abook.player.vieneu.VieneuUnits

/** Ký hiệu đọc theo ngữ cảnh (Symbols.kt): cùng các ca với tests/test_readaloud_symbols.py (câu mẫu tự viết); số chữ không đổi. */
class SymbolsTest {
    private fun said(text: String): String {
        val toks = VieneuUnits.tokens(text)
        val out = VieneuUnits.spokenTokens(toks)
        assertEquals(toks.size, out.size)
        return out.joinToString(" ")
    }

    private fun check(vararg cases: Pair<String, String>) {
        for ((text, expected) in cases) assertEquals(text, expected, said(text))
    }

    @Test
    fun aSymbolWithoutAReadingIsSilentOrAPause() = check(
        "Anh · em · chúng ta cùng đi." to "Anh,  em,  chúng ta cùng đi.",
        "Số 2^10 là 1024, còn ^ lẻ loi thì im." to "Số 2 mũ 10 là 1024, còn  lẻ loi thì im.",
        "Nếu a < b thì 3 > 2, nhưng < hay > đứng một mình thì im." to "Nếu a < b thì 3 > 2, nhưng,  hay  đứng một mình thì im.",
        "Số #7 và # đơn độc." to "Số 7 và  đơn độc.",
        "Gửi thư tới nam@example.com hoặc nhắn @ đây." to "Gửi thư tới nam@example.com hoặc nhắn a còng đây.",
        "Chửi thề kiểu !@#\$% cho vui." to "Chửi thề kiểu  cho vui.",
        "Cậu cười (^_^) rồi (°ω°) và (=_=) xong." to "Cậu cười  rồi  và  xong.",
        "Chuyện hay === hết phần một === rồi." to "Chuyện hay  hết phần một  rồi.",
        "▲ Tăng nhiều ▼ giảm bớt." to " Tăng nhiều  giảm bớt.",
        "《Kiếm Thánh》x3 và <<Ray Hawk>> và <\"Ma Vương\"> và <Chạy đi, mau!>." to "Kiếm Thánh,nhân 3 và, Ray Hawk, và, \"Ma Vương\" và, Chạy đi, mau!.",
        "Cô gọi ☎ 0912345678 ngay." to "Cô gọi điện thoại 0912345678 ngay.",
    )

    @Test
    fun aSymbolWithANumberIsReadByItsNeighbours() = check(
        "Ngày 3/9 và tỉ lệ 1/3 và 10 người/ngày." to "Ngày 3 tháng 9 và tỉ lệ 1 phần 3 và 10 người mỗi ngày.",
        "Hôm nay ngày 5/3 trời đẹp, sinh nhật 12/10 của cô, thứ Hai 3/9 nữa." to "Hôm nay ngày 5 tháng 3 trời đẹp, sinh nhật ngày 12 tháng 10 của cô, thứ Hai ngày 3 tháng 9 nữa.",
        "Mùng 5/3 vui, hạn nộp 15/8 nhé, ngày 2/9/2026 và tỉ lệ 5/3." to "Mùng 5 tháng 3 vui, hạn nộp ngày 15 tháng 8 nhé, ngày 2/9/2026 và tỉ lệ 5/3.",
        "Tối đa 3/5 rồi. HP 5813/5813 và 15/8 nữa." to "Tối đa 3 phần 5 rồi. hát pê 5813/5813 và 15 tháng 8 nữa.",
        "Giá \$5, 100\$ và 30°C." to "Giá 5 đô la, 100 đô la và 30°C.",
        "Điểm tăng 2 × 3 lần, 4x3 là mười hai, x5 mạnh hơn." to "Điểm tăng 2 nhân 3 lần, 4 nhân 3 là mười hai, nhân 5 mạnh hơn.",
        "Nhiệt độ -5 độ, từ 7 – 8cm, 3 -> 5 người, A -> B -> C." to "Nhiệt độ âm 5 độ, từ 7 đến 8cm, 3 thành 5 người, A rồi B rồi C.",
        "Tiền là 3-1 và hạng 4★." to "Tiền là 3 1 và hạng 4 sao.",
    )

    @Test
    fun theLeadsDecisionsOf0410() = check(
        "Nhận được [Quặng sắt x4] và R-Lọ mana x10, rồi 1x Cuộn phép." to "Nhận được, [Quặng sắt nhân 4], và R-Lọ mana nhân 10, rồi 1 Cuộn phép.",
        "Chia tiền 7:3 nhé." to "Chia tiền 7 3 nhé.",
        "Hai người đấu 1:1 ở sân sau, rồi đấu 1-1 tiếp." to "Hai người đấu 1 chọi 1 ở sân sau, rồi đấu 1 chọi 1 tiếp.",
        "Kèo cược 3.17:1 là cao." to "Kèo cược 3 phẩy mười bảy ăn 1 là cao.",
        "Độ thiện cảm: -20, rồi -50% Nhanh nhẹn, [Sức mạnh -5], Mất thêm -15%." to "Độ thiện cảm: âm 20, rồi trừ 50% Nhanh nhẹn, [Sức mạnh trừ 5], Mất thêm trừ 15%.",
        "Điểm Lv.-1 hiện ra." to "Điểm lờ vê.âm 1 hiện ra.",
        "#KHÔNG là thẻ, S#.1 mở màn, #5 là số." to "KHÔNG là thẻ, cảnh 1 mở màn, số 5 là số.",
        "Mục Q&A, ban nhạc S&M, kiếm & khiên." to "Mục hỏi đáp, ban nhạc S en M, kiếm và khiên.",
        "Kiếm + khiên thì hợp, +Hỏa cầu." to "Kiếm và khiên thì hợp, Hỏa cầu.",
        "Thầy giáo > Học trò > Sơ sinh, 5 > 3." to "Thầy giáo hơn Học trò hơn Sơ sinh, 5 > 3.",
        "Vương đô = Thủ đô, 2 + 3 = 5, nhìn =)) xong." to "Vương đô bằng Thủ đô, 2 + 3 bằng 5, nhìn  xong.",
        "Xem tại https://example.org/abc?x=1 nhé." to "Xem tại đường dẫn nhé.",
        "★★★☆☆ và ★5,0 và ★MAX, ★★☆ -> ★★★ rồi." to "ba sao và 5 phẩy 0 sao và sao tối đa, hai sao thành ba sao rồi.",
        "Tộc: Elf ♀, giới: ♂, Ayame♀ xong." to "Tộc: Elf nữ, giới: nam, Ayame xong.",
        "Tấn công (↑1), phòng thủ ▲(0.15)." to "Tấn công (tăng 1), phòng thủ tăng (0 phẩy mười lăm).",
        "Boost 3x, 100x cấp độ, 0.5x tốc độ." to "Boost gấp 3, gấp 100 lần cấp độ, 0,5 lần tốc độ.",
        "Aki × Rin là một cặp, Bảng Nhiệm Vụ × Nhiệm Vụ Phụ mở ra, 3 × 4." to "Aki và Rin là một cặp, Bảng Nhiệm Vụ,  Nhiệm Vụ Phụ mở ra, 3 nhân 4.",
        "Cô ấy ≠ chị ta." to "Cô ấy không phải là chị ta.",
    )


    @Test
    fun theSymbolConventionsOfTn10() = check(
        "Nhiệt độ -5 độ, tọa độ (-3, 4) và năm -2324. Bị [Thất bại: -90%], HP -20, Blue -1, MK-2, rồi 10 - 3 = 7 và 8-2=6." to
            "Nhiệt độ âm 5 độ, tọa độ (âm 3, 4) và năm âm 2324. Bị, [Thất bại: trừ 90%], hát pê trừ 20, Blue trừ 1, em ca-2, rồi 10 trừ 3 bằng 7 và 8 trừ 2 bằng 6.",
        "Còn -50% Nhanh nhẹn, thanh máu của Shido -1. Tôi mười tám (-2) nhé." to
            "Còn trừ 50% Nhanh nhẹn, thanh máu của Shido trừ 1. Tôi mười tám (âm 2) nhé.",
        "Đánh giá 4/5 sao, điểm 9.7/10, hết 1/4 máu, rồi 24/7. Ngày 8/3 là ngày hội, còn 3/4 cốc nước." to
            "Đánh giá 4/5 sao, điểm 9.7 trên 10, hết 1 phần tư máu, rồi 24/7. Ngày 8 tháng 3 là ngày hội, còn 3 phần tư cốc nước.",
        "Hầm trú -> Một ngày mới -> Mặt trời. → Biến hóa → Honnoshi. Tokyo → Osaka. Máu 10 → 20 → 30." to
            "Hầm trú rồi Một ngày mới rồi Mặt trời.  Biến hóa rồi Honnoshi. Tokyo thành Osaka. Máu 10 rồi 20 rồi 30.",
        "Bá Vương bị chọc giận. ATK↑ DEF↓. Lượt đọc: ↓ và Đông 4↓ xong." to
            "Bá Vương bị chọc giận. a tê ca tăng đê e ép giảm. Lượt đọc: giảm và Đông 4 xong.",
        "Cho y=ax² và x >= 3, a <= 5. ８－２＝６ ＡＢＣ １２ ＋ xong." to
            "Cho y bằng ax² và x lớn hơn hoặc bằng 3, a nhỏ hơn hoặc bằng 5. 8 trừ 2 bằng 6 ABC 12 + xong.",
        "Trans+Edit và 2+3=5, A + B. Tầng 8x và năm 200x, 19××, từ 0x đến 1x. Tăng 3x tốc độ, 5x damage." to
            "Trans và Edit và 2+3 bằng 5, A cộng B. Tầng 8 ích và năm 200 ích, 19 ích ích, từ 0 lần đến 1 lần. Tăng gấp 3 lần tốc độ, gấp 5 lần damage.",
        "Hình hent*i và E**alibur, *boing**boing* rồi “*Khụ*Khụ*” xong." to
            "Hình hent… i và E… alibur, boing, boing rồi “Khụ, Khụ” xong.",
    )

    @Test
    fun aSlashBetweenTwoUnitsIsLeftForThePerReading() = check(
        "Xe chạy 50km/h, gió 3 m/s và 60 km/h." to "Xe chạy 50km/h, gió 3 m/s và 60 km/h.",
        "Tốc độ km/h thôi, nặng 3 kg/m2, thuốc 5 mg/ml, đổ 2 L/h." to "Tốc độ km/h thôi, nặng 3 kg/m2, thuốc 5 mg/ml, đổ 2 L/h.",
        "Chọn và/hoặc bỏ, Mở/đóng cửa, ngày 12/3, ăn 1/2 cái, 10 DP/ngày, size M/L." to
            "Chọn và, hoặc bỏ, Mở, đóng cửa, ngày 12 tháng 3, ăn 1 phần 2 cái, 10 DP mỗi ngày, size M, L.",
        "Hạn 10 lần/ngày, 3 chương/tuần." to "Hạn 10 lần mỗi ngày, 3 chương mỗi tuần.",
    )

    @Test
    fun aPhoneNumberWithoutTheSymbolIsUnchanged() = check("Gọi 0912345678 nhé." to "Gọi 0912345678 nhé.")
}
