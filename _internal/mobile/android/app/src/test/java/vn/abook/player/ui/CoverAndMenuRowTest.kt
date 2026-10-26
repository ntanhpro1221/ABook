package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
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

