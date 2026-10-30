package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.components.CoverFit
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.PencilIcon
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Hai luật chung: bìa sinh không bao giờ cắt tên (dù rất dài, có nhãn tập), dòng menu giữ biểu tượng + "Sắp có" ở tâm dòng chữ đầu. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class CoverAndMenuRowTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    private fun show(content: @Composable () -> Unit) {
        rule.setContent { AbookTheme(false) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { content() } } }
    }

    private val longTitle = List(40) { "Đường núi lúa nắng mưa hạc bến phố" }.joinToString(" ")

    @Test
    fun generatedCoverFitsAVeryLongTitleAboveThePartLabel() {
        show {
            Box(Modifier.width(120.dp).testTag("cover_box")) { BookCover(null, longTitle, 12, CoverLoader(), 120.dp) }
        }
        rule.waitForIdle()
        val cover = rule.onNodeWithTag("cover_box").getUnclippedBoundsInRoot()
        val title = rule.onNodeWithTag("cover_title", useUnmergedTree = true).getUnclippedBoundsInRoot()
        val part = rule.onNodeWithTag("cover_part", useUnmergedTree = true).getUnclippedBoundsInRoot()
        assertTrue("tên vượt mép dưới bìa: $title / $cover", title.bottom <= cover.bottom)
        assertTrue("tên chạy xuống nhãn tập: $title / $part", title.bottom <= part.top)
        assertTrue("nhãn tập vượt mép bìa: $part / $cover", part.bottom <= cover.bottom)
        // Ô chữ vừa khung chưa đủ: chữ bên trong cũng không được tràn (tràn = bị cắt im lặng).
        for (tag in listOf("cover_title", "cover_part")) {
            val layouts = mutableListOf<TextLayoutResult>()
            rule.onNodeWithTag(tag, useUnmergedTree = true).fetchSemanticsNode().config[SemanticsActions.GetTextLayoutResult].action!!(layouts)
            assertTrue("$tag tràn: ${layouts.single().size}", !layouts.single().hasVisualOverflow)
        }
        rule.onRoot().captureRoboImage("src/test/snapshots/cover_long_title.png")
    }

    /** Cỡ chữ đã vừa được nhớ ([vn.abook.player.ui.components.CoverFit]): lần dựng sau lấy từ bộ nhớ (không dàn thử) và dàn ra đúng như lần `StepBased` tự tìm, không tràn. */
    @Test
    fun rememberedFitLaysOutExactlyWhatTheSearchChose() {
        val store = CoverFit.of(rule.activity.applicationContext)
        var round by mutableIntStateOf(0)
        show {
            key(round) {
                Box(Modifier.width(120.dp).testTag("cover_box")) { BookCover(null, "$longTitle riêng", 12, CoverLoader(), 120.dp) }
            }
        }
        fun layouts() = listOf("cover_title", "cover_part").map { tag ->
            val found = mutableListOf<TextLayoutResult>()
            rule.onNodeWithTag(tag, useUnmergedTree = true).fetchSemanticsNode().config[SemanticsActions.GetTextLayoutResult].action!!(found)
            found.single()
        }
        // Hộp chữ + bề cao từng dòng + bề rộng dòng đầu: đổi cỡ chữ dù một bậc 0,25 sp cũng làm một trong chúng đổi.
        fun shape(results: List<TextLayoutResult>) = results.map { r ->
            listOf(r.size.width, r.size.height, r.lineCount, r.getLineBottom(r.lineCount - 1).toInt(), r.getLineRight(0).toInt())
        }
        rule.waitForIdle()
        val searched = shape(layouts())
        val entries = store.size()
        val hitsBefore = store.hits
        assertTrue("lần đầu phải nhớ cỡ của tên + nhãn tập", entries >= 2)
        round++
        rule.waitForIdle()
        val remembered = layouts()
        assertTrue("lần dựng sau không dùng bộ nhớ", store.hits >= hitsBefore + 2)
        assertEquals("không được nhớ thêm mục lạ", entries, store.size())
        assertEquals("dàn chữ theo cỡ đã nhớ khác lần tự tìm", searched, shape(remembered))
        assertTrue("tràn sau khi dùng cỡ đã nhớ", remembered.none { it.hasVisualOverflow })
    }

    @Test
    fun menuRowKeepsIconAndSoonOnTheFirstLineCenter() {
        show {
            Column(Modifier.width(240.dp)) {
                MenuRow("Một việc có cái tên khá dài để xuống dòng hai lần", tag = "row", soon = true) { ink -> PencilIcon(ink) }
            }
        }
        val row = rule.onNodeWithTag("row").getUnclippedBoundsInRoot()
        val icon = rule.onNodeWithTag("row_icon", useUnmergedTree = true).getUnclippedBoundsInRoot()
        val soon = rule.onNodeWithText("Sắp có", useUnmergedTree = true).getUnclippedBoundsInRoot()
        val firstLineCenter = row.top + 12.dp + 12.dp
        val iconCenter = (icon.top + icon.bottom) / 2
        val soonCenter = (soon.top + soon.bottom) / 2
        assertEquals(firstLineCenter.value, iconCenter.value, 1f)
        assertEquals(firstLineCenter.value, soonCenter.value, 1f)
        assertTrue("hàng phải cao hơn một dòng khi nhãn xuống dòng", row.bottom - row.top > 48.dp)
    }
}

