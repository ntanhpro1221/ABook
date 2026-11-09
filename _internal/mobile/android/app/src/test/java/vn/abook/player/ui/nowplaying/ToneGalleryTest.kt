package vn.abook.player.ui.nowplaying

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.test.*
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.AudioFx
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk=[35],qualifiers="w360dp-h780dp-xxhdpi")
class ToneGalleryTest {
    @get:Rule val rule=createAndroidComposeRule<ComponentActivity>()
    private fun show(dark: Boolean) {
        rule.runOnUiThread { AudioFx.init(rule.activity);AudioFx.selectBook("tone-gallery");AudioFx.changeTone { it.select("clear") } }
        rule.setContent {
            AbookTheme(dark) {
                val density=LocalDensity.current
                CompositionLocalProvider(LocalDensity provides Density(density.density,1.3f)) {
                    Box(Modifier.fillMaxSize().background(Abook.colors.panel).padding(horizontal=20.dp)) { TonePage({}) }
                }
            }
        }
        rule.waitForIdle()
    }
    private fun gallery(dark: Boolean) {
        show(dark);val theme=if(dark)"dark" else "light"
        rule.onNodeWithTag("tone_clear").assertIsSelected()
        rule.onRoot().captureRoboImage("src/test/snapshots/tone_360_130_${theme}_list.png")
        rule.onNodeWithTag("tone_scope").performScrollTo()
        rule.onRoot().captureRoboImage("src/test/snapshots/tone_360_130_${theme}_bands.png")
        rule.onNodeWithTag("tone_band_1 kHz").performSemanticsAction(androidx.compose.ui.semantics.SemanticsActions.SetProgress) { it(5f) }
        rule.onNodeWithTag("tone_save").assertExists()
    }
    @Test fun light130(){gallery(false)}
    @Test fun dark130(){gallery(true)}
    @Test fun deleteShowsUndoInTheViewportAndRestoresThePreset() {
        show(false)
        var id=""
        rule.runOnIdle { AudioFx.changeTone { id=it.save("Undo")!! } }
        rule.onNodeWithTag("tone_delete").performScrollTo().performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("tone_undo").assertIsDisplayed().performClick()
        rule.runOnIdle { org.junit.Assert.assertTrue(AudioFx.tones.mine.any { it.id==id });org.junit.Assert.assertEquals(id,AudioFx.tones.selected.id) }
    }
}
