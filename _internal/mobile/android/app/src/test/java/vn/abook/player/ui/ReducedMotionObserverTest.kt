package vn.abook.player.ui

import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.rememberReducedMotion
import vn.abook.player.ui.theme.AbookTheme

/**
 * A book page holds dozens of SwapContent / Reveal. Each used to register its own settings observer: one Binder call per
 * item entering and another per item leaving, 10-20 ms in the frame that closed the page. One shared observer remains.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ReducedMotionObserverTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    private val resolver get() = RuntimeEnvironment.getApplication().contentResolver
    private val uri = Settings.Global.getUriFor(Settings.Global.ANIMATOR_DURATION_SCALE)
    private fun observers() = shadowOf(resolver).getContentObservers(uri).size

    @Test fun manyCallSitesShareOneObserverAndLeavingRegistersNothing() {
        var shown by mutableStateOf(true)
        var reduced = emptyList<Boolean>()
        rule.setContent {
            AbookTheme(false) {
                if (shown) Column {
                    repeat(40) { index ->
                        SwapContent(index, contentKey = { it }) { BasicText("row $it") }
                        Reveal(true) { BasicText("hint $index") }
                    }
                    reduced = List(3) { rememberReducedMotion() }
                }
            }
        }
        rule.waitForIdle()
        assertEquals(listOf(false, false, false), reduced)
        assertEquals(1, observers())
        rule.runOnUiThread { shown = false }
        rule.waitForIdle()
        rule.runOnUiThread { shown = true }
        rule.waitForIdle()
        assertEquals(1, observers())
    }

    @Test fun theSharedObserverStillFollowsTheSettingLive() {
        Settings.Global.putFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
        var reduced = false
        rule.setContent { AbookTheme(false) { reduced = rememberReducedMotion() } }
        rule.waitForIdle()
        assertTrue(!reduced)
        rule.runOnUiThread {
            Settings.Global.putFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 0f)
            resolver.notifyChange(uri, null)
        }
        rule.waitForIdle()
        try {
            assertTrue(reduced)
        } finally {
            Settings.Global.putFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
        }
    }
}
