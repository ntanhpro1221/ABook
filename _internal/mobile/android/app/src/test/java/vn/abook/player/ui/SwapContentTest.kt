package vn.abook.player.ui

import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class SwapContentTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun nullableBranchRetainsItsSnapshot() = retains(false)
    @Test fun scaleZeroStillKeepsARealFade() = retains(true)

    private fun retains(reduced: Boolean) {
        val resolver = RuntimeEnvironment.getApplication().contentResolver
        Settings.Global.putFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, if (reduced) 0f else 1f)
        var value by mutableStateOf<String?>("Lan")
        val alive = mutableSetOf<String?>()
        rule.setContent {
            AbookTheme(false) {
                SwapContent(value, contentKey = { it != null }) { held ->
                    DisposableEffect(held) {
                        alive.add(held)
                        onDispose { alive.remove(held) }
                    }
                    if (held != null) BasicText(held) else BasicText("Empty")
                }
            }
        }
        rule.waitForIdle()
        rule.mainClock.autoAdvance = false
        rule.runOnUiThread { value = null }
        rule.mainClock.advanceTimeByFrame()
        rule.mainClock.advanceTimeBy(32)
        rule.runOnUiThread { assertTrue("Outgoing non-null value survives intermediate frames", "Lan" in alive) }
        rule.mainClock.advanceTimeBy(500)
        rule.mainClock.autoAdvance = true
        rule.waitForIdle()
        rule.runOnUiThread { assertEquals(setOf<String?>(null), alive) }
        Settings.Global.putFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
    }
}
