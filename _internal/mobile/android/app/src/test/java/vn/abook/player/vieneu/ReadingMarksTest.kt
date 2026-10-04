package vn.abook.player.vieneu

import org.junit.Assert.assertEquals
import org.junit.Test

/** Marks sea-g2p reads as words ("~", English thousands, <angle brackets>, " / ") are fixed for reading only (`reading_marks` of vieneu.py); same cases as test_readaloud_vieneu.py. */
class ReadingMarksTest {
    private fun said(text: String): String {
        val (tokens, units) = VieneuUnits.units(text, 256)
        assertEquals(tokens.joinToString(" "), units.joinToString(" ") { it.text(tokens) })
        return units.flatMap { it.pieces }.joinToString(" ")
    }

    private fun check(vararg cases: Pair<String, String>) {
        for ((text, expected) in cases) assertEquals(text, expected, said(text))
    }

    @Test
    fun aTildeIsDroppedOrReadAsARange() = check(
        "Hmm~ Har~kun? EMMMMM~!" to "hừm Har kun? em…!",
        "Ưm~~~, xong. Ô ~, vậy sao. Ồ~”." to "Ưm, xong. Ô, vậy sao. Ồ”.",
        "Từ 10,000 ~ 15,000 đồng và 3~5 người." to "Từ 10000 đến 15000 đồng và 3 đến 5 người.",
        "Khoảng ~50 người, “~50” nữa." to "Khoảng ~50 người, “~50” nữa.",
        "~" to "",
    )

    @Test
    fun englishThousandsLoseTheirCommas() = check(
        "Có 500,000 đồng, 100,000 yen và 1,419 / 3,419." to "Có 500000 đồng, 100000 yên và 1419 / 3419.",
        "Trả 2,000,000, xong." to "Trả 2000000, xong.",
        "Giá 1,500 và 1,5 và 3,25 và 12,3456." to "Giá 1500 và 1,5 và 3,25 và 12,3456.",
        "Số 1.234,567 và 9.389.700 và 1,234.5 và 1,234,5." to "Số 1.234,567 và 9.389.700 và 1,234.5 và 1,234,5.",
    )

    @Test
    fun angleBracketsAroundWordsAreNotComparisons() = check(
        "Tên là <Angel Wings> đó." to "Tên là, Angel Wings, đó.",
        "Dùng <khiên> đi và <Gấu?> kìa." to "Dùng khiên đi và Gấu? kìa.",
        "<Tiêu chuẩn đánh giá>" to "Tiêu chuẩn đánh giá",
        "Phần IV <Hạ> thôi." to "Phần bốn Hạ thôi.",
        "Kỹ năng 《Xiềng Xích》 và 〈Ánh〉 cùng 《lẻ." to "Kỹ năng, Xiềng Xích, và Ánh cùng lẻ.",
        "< Thật Tuyệt vời>, xong." to "Thật Tuyệt vời, xong.",
        "Rồi 〈Wish Upon〉[Cầu ước] nữa." to "Rồi, Wish Upon,[Cầu ước], nữa.",
        "3 < 5 và 8 > 2, <3 và >:) và <50/50>." to "3 < 5 và 8 > 2, và và 50/50.",
        "a <b c d e f g h i j k l m n o p" to "a b c d e f g h i j k l m n o p",
    )

    @Test
    fun aSlashBetweenTwoWordsIsAPause() = check(
        "Bị 【Đóng băng / yếu】 rồi." to "Bị, 【Đóng băng, yếu】, rồi.",
        "Chạy / bay." to "Chạy, bay.",
        "HP: 5813 / 5813 và 3/5, 15/8, 3 / 5." to "hát pê: 5813 / 5813 và 3 phần 5, 15/8, 3 / 5.",
        "Mở/đóng và km/h." to "Mở/đóng và km/h.",
    )

    @Test
    fun numbersAreReadTheWayAListenerHearsThem() = check(
        "Chia 3/5 chai, 1/2 và 180/300, 5/3 và 15/8." to "Chia 3 phần 5 chai, 1 phần 2 và 180/300, 5/3 và 15/8.",
        "Lớp 1-1, được 1-3-1, dài 3-4000 từ, 3-5 người." to "Lớp 1 1, được 1 3 1, dài 3 đến 4000 từ, 3 đến 5 người.",
        "Ngày 01-10-2026, số 090-123-4567, tỉ số 3-1, giờ 9-5." to "Ngày 01-10-2026, số 090-123-4567, tỉ số 3 1, giờ 9 5.",
        "Sự kiện x2 và ×3, (\$1 USD) và \$5." to "Sự kiện nhân 2 và nhân 3, (1 đô la u ét đê) và 5 đô la.",
    )

    @Test
    fun smileysStarsDashesAndCjkPunctuation() = check(
        "Xong :3 nào >:)! <3 vl -_- ;) orz" to "Xong nào ! vl",
        "*từ* (*) đ* b*** xong" to "từ () đờ… bờ… xong",
        "Babi—người đã. Nên— Cảm ơn. Làm—” rồi nha-- ừ." to "Babi, người đã. Nên, Cảm ơn. Làm—” rồi nha-- ừ.",
        "Đi，nhà ta. 734：Chúng ta？" to "Đi, nhà ta. 734: Chúng ta?",
    )

    @Test
    fun aSystemFrameGluedToWordsGetsAPauseAtBothEnds() = check(
        "Tên là【Song Kiếm Thuật】!” rồi." to "Tên là,【Song Kiếm Thuật】!” rồi.",
        "Của 【Trường】rất xinh. Khung 【 Số dư 】 nữa." to "Của, 【Trường】,rất xinh. Khung, 【 Số dư 】, nữa.",
        "Tiến hóa: [Bậc 1] xong [1] và kỹ năng [Hỏa] nữa." to "Tiến hóa: [Bậc 1] xong [1] và kỹ năng, [Hỏa], nữa.",
    )

    @Test
    fun longNumericOrUnclosedAngleBrackets() = check(
        "<mình vẫn ổn mà, chỉ hơi mệt sau một ngày dài…thôi kệ> hết" to "mình vẫn ổn mà, chỉ hơi mệt sau một ngày dài…thôi kệ, hết",
        "Tên <game> <50/50>. < Thật Tuyệt vời. Còn x < y." to "Tên game 50/50. Thật Tuyệt vời. Còn x < y.",
    )

    @Test
    fun theWordCountNeverChanges() {
        val text = "Hmm~ ~ 10,000 ~ 15,000 <Angel Wings> Chạy / bay 《x》"
        val (tokens, units) = VieneuUnits.units(text, 256)
        assertEquals(tokens.size, VieneuUnits.spokenTokens(tokens).size)
        assertEquals(text, units.joinToString(" ") { it.text(tokens) })
    }
}
