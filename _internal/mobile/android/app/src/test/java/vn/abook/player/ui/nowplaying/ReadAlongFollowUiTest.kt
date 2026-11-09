package vn.abook.player.ui.nowplaying

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.height
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.theme.AbookTheme

/** Chủ sách 09-11: mất tô từ; cuộn chỉ nhảy theo đoạn; mỗi lần vào tab Đọc theo lại cuộn vội từ trên xuống. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class ReadAlongFollowUiTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    private class Clock(start: Long) : PlayerPosition {
        val now = mutableLongStateOf(start)
        override val milliseconds: State<Long> = now
        override val sleepRemainingMs: State<Long> = mutableLongStateOf(0L)
        override fun sample() {}
    }

    private val sentence = "Một đoạn dài vừa đủ để xuống nhiều dòng trên màn điện thoại, đọc từng chữ một cho tới khi hết cả đoạn này mới sang đoạn sau, chữ cứ thế chảy mãi."

    /** Mỗi đoạn 10 giây, mỗi chữ chia đều. */
    private fun paragraph(index: Int, withWords: Boolean = true, endExtra: Long = 0): ReadParagraph {
        val tokens = Regex("\\S+").findAll(sentence).toList()
        val start = index * 10_000L
        val step = 10_000L / tokens.size
        return ReadParagraph(index, sentence, start, start + 10_000, true,
            if (withWords) tokens.mapIndexed { i, match -> WordTiming(start + i * step, start + (i + 1) * step + endExtra, match.range.first, match.range.last + 1) } else emptyList())
    }

    private fun text(count: Int = 200) = ReadAlongState("book", 1, List(count) { paragraph(it) })

    private fun paragraphTop(index: Int) = rule.onNodeWithTag("paragraph_$index").getUnclippedBoundsInRoot().top
    private fun viewport() = rule.onNodeWithTag("read_along_text").getUnclippedBoundsInRoot()

    @Test fun openingMidChapterStandsAtTheCurrentLineWithoutScrollingThroughTheChapter() {
        val clock = Clock(1_230_000)
        rule.mainClock.autoAdvance = false
        rule.setContent { AbookTheme(true) { ReadAlongPane(text(), clock, Modifier.fillMaxSize()) } }
        // Khung ngay sau khi dựng: chỉ vài nhịp đồng hồ khung hình, chưa đủ cho bất cứ cú cuộn hoạt hoạ nào.
        rule.mainClock.advanceTimeByFrame()
        rule.mainClock.advanceTimeByFrame()
        rule.waitForIdle()
        val view = viewport()
        val at = (paragraphTop(123) - view.top) / view.height
        assertTrue("đoạn đang đọc phải đứng trong vùng đọc ngay khung đầu, đang ở $at", at in 0.05f..0.5f)
        rule.onNodeWithTag("paragraph_0").assertDoesNotExistOnScreen()
    }

    private fun androidx.compose.ui.test.SemanticsNodeInteraction.assertDoesNotExistOnScreen() {
        assertTrue("không có đoạn đầu chương nào được dựng", fetchSemanticsNodes(this).isEmpty())
    }

    private fun fetchSemanticsNodes(node: androidx.compose.ui.test.SemanticsNodeInteraction) =
        runCatching { listOf(node.fetchSemanticsNode()) }.getOrDefault(emptyList())

    @Test fun theListFollowsTheWordLineInsideAParagraphAndKeepsItInTheReadingZone() {
        val clock = Clock(1_230_000)
        rule.setContent { AbookTheme(true) { ReadAlongPane(text(), clock, Modifier.fillMaxSize()) } }
        rule.waitForIdle()
        val start = paragraphTop(123)
        clock.now.longValue = 1_239_000 // từ gần cuối cùng đoạn: dòng dưới, cùng câu
        rule.waitForIdle()
        val moved = paragraphTop(123)
        assertTrue("đoạn phải trôi lên theo dòng của từ ($start -> $moved)", moved < start - 20.dp)
        val view = viewport()
        val placed = paragraphTop(123).let { (it - view.top) / view.height }
        assertTrue("đầu đoạn đã lên trên chỗ đọc: $placed", placed < ReadFollow.PLACE_AT)
    }

    @Test fun aSentenceWithoutWordMarksStillFollowsTheSentence() {
        val clock = Clock(1_230_000)
        val state = ReadAlongState("book", 1, List(200) { paragraph(it, withWords = false) })
        rule.setContent { AbookTheme(true) { ReadAlongPane(state, clock, Modifier.fillMaxSize()) } }
        rule.waitForIdle()
        clock.now.longValue = 1_240_000
        rule.waitForIdle()
        val view = viewport()
        val at = (paragraphTop(124) - view.top) / view.height
        assertEquals(ReadFollow.PLACE_AT, at, 0.03f)
    }

    /** Vẽ cả cửa sổ ra ảnh (đồ hoạ thật của Robolectric NATIVE). */
    private fun pixels(): IntArray {
        rule.waitForIdle()
        val view = rule.activity.window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        rule.runOnUiThread { view.draw(Canvas(bitmap)) }
        return IntArray(bitmap.width * bitmap.height).also { bitmap.getPixels(it, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height) }
    }

    /** Điểm ảnh mang màu nhấn (cam: đỏ hơn lam rõ) - nền câu và nền từ; chữ xám không tính. Nền từ đậm hơn nền câu nên có từ là nhiều điểm cam đậm hơn. */
    private fun inked(pixels: IntArray, strong: Boolean) = pixels.count {
        val red = (it shr 16) and 0xff
        val blue = it and 0xff
        red - blue > if (strong) 48 else 14
    }

    /** Có mốc từ thì có nền từ - kể cả khi mốc về sau chữ (giọng máy đọc xong clip) và khi mốc đổi tiếp. */
    @Test fun wordMarksArrivingLaterAreDrawn() {
        val clock = Clock(5_000)
        var state by mutableStateOf(ReadAlongState("book", 1, List(5) { paragraph(it, withWords = false) }))
        rule.setContent { AbookTheme(true) { ReadAlongPane(state, clock, Modifier.fillMaxSize()) } }
        val noWord = pixels()
        assertTrue("câu đang đọc có nền", inked(noWord, false) > 500)
        assertEquals("chưa có mốc từ: không có nền từ", 0, inked(noWord, true))
        state = ReadAlongState("book", 1, List(5) { paragraph(it) })
        val word = pixels()
        assertTrue("có mốc từ thì có nền từ: ${inked(word, true)}", inked(word, true) > 200)
        assertTrue("nền câu vẫn còn", inked(word, false) > 500)
        state = ReadAlongState("book", 1, List(5) { paragraph(it, endExtra = 1) })
        val again = pixels()
        assertTrue("mốc đổi tiếp: nền từ vẫn còn", inked(again, true) > 200)
    }
}
