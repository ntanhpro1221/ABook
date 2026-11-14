package vn.abook.player.ui.nowplaying

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.unit.dp
import org.junit.Rule
import org.junit.Test
import org.junit.Assert.assertThrows
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.theme.AbookTheme

/** Rotation can leave the reading region smaller than its jump dock for a layout pass. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w800dp-h360dp-mdpi")
class ReadAlongSmallViewportTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun originalViewportFormulaReproducesTheReportedException() {
        assertThrows(IllegalArgumentException::class.java) {
            PaddingValues(bottom = ((24.dp - 48.dp) / 3) * 2)
        }
    }

    @Test fun shrinkingPastDockHeightDoesNotCreateNegativePadding() {
        val height = mutableIntStateOf(96)
        val position = object : PlayerPosition {
            override val milliseconds: State<Long> = mutableLongStateOf(0L)
            override val sleepRemainingMs: State<Long> = mutableLongStateOf(0L)
            override fun sample() {}
        }
        val state = ReadAlongState("viewport-test", 1, listOf(ReadParagraph(0, "Dòng chữ kiểm tra màn hình nhỏ.", 0L, 1000L, true, emptyList())))
        rule.setContent {
            AbookTheme(false) {
                Box(Modifier.fillMaxWidth().height(height.intValue.dp)) {
                    ReadAlongPane(state, position, Modifier.fillMaxWidth().height(height.intValue.dp))
                }
            }
        }
        for (value in listOf(48, 47, 24, 1, 0, 200, 320)) {
            rule.runOnIdle { height.intValue = value }
            rule.waitForIdle()
            rule.onNodeWithTag("read_along_text").assertExists()
        }
    }
}
