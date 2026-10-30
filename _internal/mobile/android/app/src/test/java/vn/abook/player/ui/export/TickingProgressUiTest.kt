package vn.abook.player.ui.export

import androidx.activity.ComponentActivity
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.text.TextLayoutResult
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class TickingProgressUiTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun exportCountsChangeInPlaceWithoutRollingAndUseRealTabularDigits() {
        val progress = mutableStateOf(ExportProgress("11/11 chương · 11%", "Đang xuất sách", .11f))
        rule.setContent { AbookTheme { ProgressLine(progress, null) } }
        rule.waitForIdle()
        val label = rule.onNodeWithTag("export_progress_text", useUnmergedTree = true)
        val before = label.getUnclippedBoundsInRoot()
        fun layout(): TextLayoutResult {
            val results = mutableListOf<TextLayoutResult>()
            label.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(results) }
            return results.single()
        }
        val oldWidth = layout().size.width
        rule.mainClock.autoAdvance = false
        rule.runOnIdle {
            progress.value = ExportProgress("44/44 chương · 44%", "Đang xuất sách", .44f)
            androidx.compose.runtime.snapshots.Snapshot.sendApplyNotifications()
        }
        // First frame schedules recomposition; the second commits the changed text.
        repeat(2) { rule.mainClock.advanceTimeByFrame() }
        for (time in listOf(16L, 40L, 80L, 160L, 320L)) {
            rule.mainClock.advanceTimeBy(time)
            label.assertTextEquals("44/44 chương · 44%")
            rule.onAllNodesWithText("11/11 chương · 11%", useUnmergedTree = true).assertCountEquals(0)
            rule.onAllNodesWithTag("export_progress_text", useUnmergedTree = true).assertCountEquals(1)
            assertEquals(before, label.getUnclippedBoundsInRoot())
            assertEquals("Bundled font must actually implement tnum", oldWidth, layout().size.width)
            assertEquals("tnum", layout().layoutInput.style.fontFeatureSettings)
        }
        rule.mainClock.autoAdvance = true
    }
}
