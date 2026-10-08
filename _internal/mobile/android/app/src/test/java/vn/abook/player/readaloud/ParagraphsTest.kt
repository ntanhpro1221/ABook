package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Test

/** Cùng các ca với ui/src/listen/textScript.test.ts (`paragraphsOf`): đổi bên nào phải đổi cả bên kia. */
class ParagraphsTest {
    @Test
    fun splitsOnBlankLinesAndJoinsTheLinesATypesetterBroke() {
        assertEquals(
            listOf("Một dòng bị bẻ giữa chừng.", "Đoạn hai.", "Đoạn ba."),
            Paragraphs.of("Một dòng bị\nbẻ giữa chừng.\n\nĐoạn hai.\r\n\r\n\r\nĐoạn ba.\n"),
        )
    }

    @Test
    fun takesEachLineAsAParagraphWhenTheFileHasNoBlankLineAtAll() {
        assertEquals(listOf("Dòng một.", "Dòng hai.", "Dòng ba."), Paragraphs.of("Dòng một.\nDòng hai.\n  Dòng ba.  \n"))
    }

    @Test
    fun keepsEachLineAParagraphInAFileThatHasOnlyAFewBlankLines() {
        assertEquals(
            listOf("Chương 1", "Dòng một.", "Dòng hai!", "“Dòng ba?”", "Dòng bốn"),
            Paragraphs.of("Chương 1\n\nDòng một.\nDòng hai!\n“Dòng ba?”\nDòng bốn"),
        )
        assertEquals(listOf("Tựa", "x".repeat(201), "không dấu"), Paragraphs.of("Tựa\n\n${"x".repeat(201)}\nkhông dấu"))
    }

    @Test
    fun stillJoinsLinesATypesetterBrokeMidSentence() {
        assertEquals(
            listOf("A", "Một dòng dài bị bẻ, một dòng nữa kết thúc. Rồi câu sau tiếp và hết."),
            Paragraphs.of("A\n\nMột dòng dài bị bẻ,\nmột dòng nữa kết thúc.\nRồi câu sau tiếp\nvà hết."),
        )
    }

    @Test
    fun skipsOnlyTheChosenLinesAmongTheFirstSixOfTheChapter() {
        val text = "Chương 2\n\nDịch:  Nhóm A\n\nMở đầu.\n\nDịch: Nhóm A"
        assertEquals(listOf("Chương 2", "Mở đầu."), Paragraphs.of(Paragraphs.withoutLines(text, listOf("Dịch: Nhóm A"))))
        assertEquals(text, Paragraphs.withoutLines(text, emptyList()))
        val late = (1..6).joinToString("\n") { "Dòng $it." } + "\nDịch: Nhóm A"
        assertEquals(7, Paragraphs.of(Paragraphs.withoutLines(late, listOf("Dịch: Nhóm A"))).size) // ngoài 6 dòng đầu: giữ
    }

    @Test
    fun givesNothingForAnEmptyChapter() {
        assertEquals(emptyList<String>(), Paragraphs.of("\n \n\n"))
    }

    @Test
    fun aBlankLineMayHoldTabsAndNonBreakingSpaces() {
        assertEquals(listOf("A", "B"), Paragraphs.of("A\n \t \nB"))
    }

    @Test
    fun squeezesTheSameWhitespaceAsJavaScript() {
        // \s của JS: U+00A0 và U+FEFF là khoảng trắng, U+0085 thì không.
        assertEquals(listOf("a b c"), Paragraphs.of("﻿a  b　c "))
        assertEquals(listOf("a\u0085b"), Paragraphs.of("a\u0085b"))
    }

    @Test
    fun oldMacLineEndingsCountAsNewlines() {
        assertEquals(listOf("A", "B"), Paragraphs.of("A\r\rB"))
    }

    // Cùng các ca với textScript.test.ts ("web note markers"): mã chú thích của trang web bị bỏ như máy tính, khoảng trắng gọn lại.
    @Test
    fun dropsWebNoteMarkersLikeTheDesktop() {
        assertEquals(listOf("Anh ta đi rồi. Cô ở lại."), Paragraphs.of("Anh ta đi rồi. [note54360] Cô ở lại."))
        assertEquals(listOf("Anh đi rồi."), Paragraphs.of("Anh đi rồi[NOTE7][ note12 ]."))
        assertEquals(listOf("Một", "Hai."), Paragraphs.of("Một[note1]\n\n[ NOTE22 ]Hai.[note3]"))
    }

    @Test
    fun keepsBracketsThatAreNotWebNoteMarkers() {
        assertEquals(listOf("Xem [Note] và [1] và [note] và [note1a]."), Paragraphs.of("Xem [Note] và [1] và [note] và [note1a]."))
    }

    @Test
    fun aCreditLineWithAMarkerIsStillSkipped() {
        val text = "Chương 2\n\nDịch: Nhóm A [note12]\n\nMở đầu."
        assertEquals(listOf("Chương 2", "Mở đầu."), Paragraphs.of(Paragraphs.withoutLines(text, listOf("Dịch: Nhóm A"))))
    }
}
