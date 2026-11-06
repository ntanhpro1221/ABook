package vn.abook.player.ui.music

import androidx.activity.ComponentActivity
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performSemanticsAction
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35])
class LevelMeterSaveTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun savingBlocksInputAndResetAfterAckSendsTheOriginalLevel() {
        val level = mutableStateOf(-20.0)
        val busy = mutableStateOf(false)
        val calls = mutableListOf<Double>()
        rule.setContent {
            AbookTheme {
                LevelMeter(level.value, enabled = !busy.value, onPick = { calls += it; busy.value = true })
            }
        }
        rule.onNodeWithTag("music_level_slider").performSemanticsAction(SemanticsActions.SetProgress) { it(-19f) }
        rule.onNodeWithTag("music_level_slider").assertIsNotEnabled()
        rule.onNodeWithTag("music_level_slider").performSemanticsAction(SemanticsActions.SetProgress) { it(-20f) }
        rule.runOnIdle { assertEquals(listOf(-19.0), calls); level.value = -19.0; busy.value = false }
        rule.onNodeWithTag("music_level_reset").performClick()
        rule.runOnIdle { assertEquals(listOf(-19.0, -20.0), calls) }
    }
}
