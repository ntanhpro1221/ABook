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
        "Hmm~ Har~kun? EMMMMM~!" to "Hmm Har kun? EMMMMM!",
        "Ưm~~~, xong. Ô ~, vậy sao. Ồ~”." to "Ưm, xong. Ô, vậy sao. Ồ”.",
        "Từ 10,000 ~ 15,000 đồng và 3~5 người." to "Từ 10000 đến 15000 đồng và 3 đến 5 người.",
        "Khoảng ~50 người, “~50” nữa." to "Khoảng ~50 người, “~50” nữa.",
        "~" to "",
    )

    @Test
    fun englishThousandsLoseTheirCommas() = check(
        "Có 500,000 đồng, 100,000 yen và 1,419 / 3,419." to "Có 500000 đồng, 100000 yen và 1419 / 3419.",
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
        "Rồi 〈Wish Upon〉[Cầu ước] nữa." to "Rồi, Wish Upon,[Cầu ước] nữa.",
        "3 < 5 và 8 > 2, <3 và >:) và <50/50>." to "3 < 5 và 8 > 2, <3 và >:) và <50/50>.",
        "a <b c d e f g h i j k l m n o p" to "a <b c d e f g h i j k l m n o p",
    )

    @Test
    fun aSlashBetweenTwoWordsIsAPause() = check(
        "Bị 【Đóng băng / yếu】 rồi." to "Bị 【Đóng băng, yếu】 rồi.",
        "Chạy / bay." to "Chạy, bay.",
        "HP: 5813 / 5813 và 3/5, 15/8, 3 / 5." to "HP: 5813 / 5813 và 3/5, 15/8, 3 / 5.",
        "Mở/đóng và km/h." to "Mở/đóng và km/h.",
    )

    @Test
    fun theWordCountNeverChanges() {
        val text = "Hmm~ ~ 10,000 ~ 15,000 <Angel Wings> Chạy / bay 《x》"
        val (tokens, units) = VieneuUnits.units(text, 256)
        assertEquals(tokens.size, VieneuUnits.spokenTokens(tokens).size)
        assertEquals(text, units.joinToString(" ") { it.text(tokens) })
    }
}
