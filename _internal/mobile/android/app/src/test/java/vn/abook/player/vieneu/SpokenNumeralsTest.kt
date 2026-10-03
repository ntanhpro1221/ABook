package vn.abook.player.vieneu

import org.junit.Assert.assertEquals
import org.junit.Test

/** Roman numerals after a common noun are read as numbers (`spoken_tokens` of vieneu.py); the shown words never change. Same cases as test_readaloud_vieneu.py. */
class SpokenNumeralsTest {
    private fun said(text: String): String {
        val (tokens, units) = VieneuUnits.units(text, 256)
        assertEquals(tokens.joinToString(" "), units.joinToString(" ") { it.text(tokens) })
        return units.flatMap { it.pieces }.joinToString(" ")
    }

    @Test
    fun aRomanNumeralAfterAWordIsReadAsANumber() {
        assertEquals("Trường Phổ thông hai và Trường Phổ thông ba", said("Trường Phổ thông II và Trường Phổ thông III"))
        assertEquals("Chương bốn bắt đầu ở trang 132.", said("Chương IV bắt đầu ở trang 132."))
        assertEquals("Thế chiến hai kết thúc năm 1945.", said("Thế chiến II kết thúc năm 1945."))
        assertEquals("Benedict ba lên ngôi.", said("Benedict III lên ngôi."))
        assertEquals("Cuối chương mười bốn.", said("Cuối chương XIV."))
        assertEquals("Mục mười lăm, hai mươi bốn và ba mươi chín.", said("Mục XV, XXIV và XXXIX."))
        assertEquals("Học kỳ \"hai\" bắt đầu.", said("Học kỳ \"II\" bắt đầu."))
        // one letter (I, V, X) only after a numbered noun, or two capitalised names in a row
        assertEquals("Chương một, thế kỷ mười, thế chiến một và Phần năm.", said("Chương I, thế kỷ X, thế chiến I và Phần V."))
        assertEquals("Lớp năm, hạng mười, số một, bài năm.", said("Lớp V, hạng X, số I, bài V."))
        assertEquals("Mục hai, năm và X.", said("Mục II, V và X."))
        assertEquals("Vua Louis mười lên ngôi.", said("Vua Louis X lên ngôi."))
    }

    @Test
    fun otherCapitalsAndHeadingsAreLeftAlone() {
        assertEquals("một. Mở đầu", said("I. Mở đầu"))
        assertEquals("chín) Phụ lục", said("IX) Phụ lục"))
        for (same in listOf("I am here.", "I.", "Xong rồi. I am đây.", "Anh ấy là MC của CV VIP, ở DIV.", "Mã XL và IIII và VX.",
            "Chương iv và Chương Iv.", "Khoa CV II",
            "Ông X, nhân vật X, tia X, điểm V, loại I.", "Ông ta nói rằng I", "Hoàng đế Napoleon I và Napoleon I.", "Trường Phổ thông I")) assertEquals(same, said(same))
    }

    @Test
    fun numbersAreReadTheVietnameseWay() {
        assertEquals(listOf("một", "bốn", "năm", "mười", "mười một", "mười bốn", "mười lăm", "hai mươi", "hai mươi mốt", "hai mươi bốn", "hai mươi lăm",
            "ba mươi", "ba mươi mốt", "ba mươi lăm", "ba mươi chín"),
            listOf(1, 4, 5, 10, 11, 14, 15, 20, 21, 24, 25, 30, 31, 35, 39).map(VieneuUnits::vietnameseNumber))
        assertEquals(listOf(1, 4, 9, 14, 39, null, null, null, null), listOf("I", "IV", "IX", "XIV", "XXXIX", "XL", "IIII", "VX", "").map(VieneuUnits::romanValue))
    }
}
