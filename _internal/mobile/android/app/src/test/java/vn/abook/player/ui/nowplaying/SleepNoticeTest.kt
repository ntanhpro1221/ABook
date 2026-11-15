package vn.abook.player.ui.nowplaying

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class SleepNoticeTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    @Test fun continuingAScheduledStopKeepsTheTimerAndStartsPlayback() {
        val state = FakeNowPlayingModel.demoState().copy(playing = false,
            sleep = PlayerSleep(SleepKind.Minutes, 30, false, automaticReason = "schedule"))
        val model = FakeNowPlayingModel(state)
        rule.setContent { AbookTheme(false) { SleepNotice(state, model) } }
        rule.onNodeWithTag("sleep_continue").performClick()
        rule.runOnIdle {
            assertEquals(SleepKind.Minutes, model.state.value.sleep.kind)
            assertTrue(model.state.value.playing)
        }
    }
}
