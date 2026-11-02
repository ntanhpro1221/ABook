package vn.abook.player.ui.pip

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.theme.AbookTheme

/**
 * Nội dung PiP cùng thứ với cửa sổ mini của bản máy tính (`MiniPlayer.qml`): tên sách và tên chương ở đáy bìa, chữ xuống dòng, KHÔNG BAO GIỜ bị cắt. Dòng nào hiện
 * do đo ([planPipText]): khổ rộng có cả hai; khổ hẹp (tên sách xuống nhiều dòng, không vừa) chỉ còn tên chương; tên chương rất dài vẫn đủ chữ và nằm trọn trong khung.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class PipContentTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private fun show(width: Dp, book: String = "Tắt đèn", chapter: String = "Chương 1") {
        val state = PlayerState(bookId = "b1", bookTitle = book, chapterId = 1, chapterTitle = chapter, playing = true, durationMs = 600_000)
        rule.setContent {
            AbookTheme(false) {
                Box(Modifier.size(width, width * 3 / 2)) { PipContent(state, { 150_000L }, CoverLoader(1 shl 20)) }
            }
        }
        rule.waitForIdle()
    }

    private fun count(tag: String) = rule.onAllNodesWithTag(tag).fetchSemanticsNodes().size

    private fun layout(tag: String): TextLayoutResult {
        val out = mutableListOf<TextLayoutResult>()
        rule.onNodeWithTag(tag).performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(out) }
        return out.single()
    }

    /** Mọi chữ có mặt, không dòng nào bị cắt, và khối chữ nằm trọn trong khung PiP. */
    private fun assertWholeAndInside(tag: String, text: String) {
        val frame = rule.onNodeWithTag("pip_content").getUnclippedBoundsInRoot()
        val result = layout(tag)
        assertEquals("$tag đủ mọi chữ", text, result.layoutInput.text.text.replace("\u00A0", " ").replace("\u2060", ""))
        // hasVisualOverflow báo oan với chữ một dòng ngắn hơn khung (bề rộng đoạn = bề rộng ràng buộc, kích thước = bề rộng chữ), nên kiểm từng điều "bị cắt" đúng nghĩa:
        assertFalse("$tag tràn chiều cao", result.didOverflowHeight)
        assertTrue("$tag có dòng bị cắt …", (0 until result.lineCount).none { result.isLineEllipsized(it) })
        assertEquals("$tag dòng cuối chứa hết chữ", result.layoutInput.text.length, result.getLineEnd(result.lineCount - 1, visibleEnd = false))
        assertFalse("$tag không có dấu …", result.layoutInput.text.text.contains("…"))
        val box = rule.onNodeWithTag(tag).getUnclippedBoundsInRoot()
        assertTrue("$tag trong khung: $box / $frame", box.left >= frame.left && box.right <= frame.right && box.top >= frame.top && box.bottom <= frame.bottom)
    }

    @Test
    fun wideFrameShowsTheBookTitleAndTheChapterTitleInThatOrder() {
        show(240.dp)
        val book = rule.onNodeWithTag("pip_book_title").getUnclippedBoundsInRoot()
        val chapter = rule.onNodeWithTag("pip_chapter_title").getUnclippedBoundsInRoot()
        val progress = rule.onNodeWithTag("pip_progress").getUnclippedBoundsInRoot()
        rule.onNodeWithTag("pip_book_title").assertTextEquals("Tắt đèn")
        rule.onNodeWithTag("pip_chapter_title").assertTextEquals("Chương 1")
        assertTrue("tên sách trên tên chương", book.bottom <= chapter.top)
        assertTrue("tên chương trên dải tiến độ", chapter.bottom <= progress.top)
        assertWholeAndInside("pip_book_title", "Tắt đèn")
        assertWholeAndInside("pip_chapter_title", "Chương 1")
    }

    @Test
    fun theSmallestRealPipStillShowsBoth() {
        show(160.dp)
        assertEquals(1, count("pip_book_title"))
        assertEquals(1, count("pip_chapter_title"))
    }

    @Test
    fun aNarrowFrameWhereBothDoNotFitKeepsOnlyTheChapterTitle() {
        show(96.dp, book = "Tên cuốn sách khá dài của chúng tôi")
        assertEquals("tên sách đã nằm trên bìa tự vẽ", 0, count("pip_book_title"))
        assertEquals(1, count("pip_chapter_title"))
        assertEquals(1, count("pip_progress"))
        assertWholeAndInside("pip_chapter_title", "Chương 1")
    }

    @Test
    fun aVeryLongChapterTitleKeepsEveryWordAndStaysInsideTheFrame() {
        val long = "Chương một trăm hai mươi ba: người đi tìm một cái tên rất dài cho một chương còn dài hơn nữa, dài đến mức một dòng của cửa sổ nhỏ không thể chứa nổi " +
            "mà chữ vẫn phải đủ, không bớt đi một chữ nào, và không được tràn ra ngoài khung của cửa sổ"
        show(160.dp, chapter = long)
        assertEquals("tên sách nhường chỗ", 0, count("pip_book_title"))
        assertTrue("xuống nhiều dòng", layout("pip_chapter_title").lineCount > 1)
        assertWholeAndInside("pip_chapter_title", long)
    }

    @Test
    fun aLongBookTitleWrapsInsteadOfBeingCutWhenThereIsRoom() {
        val long = "Một cái tên sách dài vừa phải"
        show(240.dp, book = long)
        assertEquals(1, count("pip_book_title"))
        assertTrue(layout("pip_book_title").lineCount > 1)
        assertWholeAndInside("pip_book_title", long)
    }
}
