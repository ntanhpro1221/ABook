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
}
