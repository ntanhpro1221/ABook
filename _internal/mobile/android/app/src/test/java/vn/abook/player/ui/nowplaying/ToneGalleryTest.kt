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
import vn.abook.player.ui.snapshot.captureRoboImage
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.AudioFx
import vn.abook.player.S
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk=[35],qualifiers="w360dp-h780dp-xxhdpi")
class ToneGalleryTest {
    @get:Rule val rule=createAndroidComposeRule<ComponentActivity>()
    private fun show(dark: Boolean, mine: Boolean = false) {
        rule.runOnUiThread { AudioFx.init(rule.activity);AudioFx.selectBook("tone-gallery");AudioFx.changeTone { it.select("clear") } }
        rule.runOnUiThread { AudioFx.changeTone { lib->lib.mine.toList().forEach { lib.delete(it.id) };lib.select("clear") } }
        if(mine)rule.runOnUiThread { AudioFx.changeTone { it.select("warm");it.edit(4,-5.0);it.save("Đêm khuya");it.select("soft");it.save("Tai nghe cũ");it.select("clear") } }
        rule.setContent {
            AbookTheme(dark) {
                val density=LocalDensity.current
                CompositionLocalProvider(LocalDensity provides Density(density.density,1.3f)) {
                    // Như trong tấm thật: đầu tấm (← + tên) rồi trang.
                    Column(Modifier.fillMaxSize().background(Abook.colors.panel).padding(horizontal=20.dp)) { SheetTitle(S.s_am_sac_8c2f4e1a) {};TonePage({}) }
                }
            }
        }
        rule.waitForIdle()
    }
    private fun gallery(dark: Boolean) {
        show(dark,mine=true);val theme=if(dark)"dark" else "light"
        rule.onNodeWithTag("tone_clear").assertIsSelected()
        rule.onNodeWithTag("sheet_back").assertIsDisplayed()
        rule.onNodeWithText("−4 dB").assertExists()
        rule.onRoot().captureRoboImage("src/test/snapshots/tone_360_130_${theme}_top.png")
        rule.onNodeWithTag("tone_more_1").performScrollTo()
        rule.onRoot().captureRoboImage("src/test/snapshots/tone_360_130_${theme}_presets.png")
        rule.onNodeWithTag("tone_more_0").performScrollTo().performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("tone_scope").performScrollTo()
        rule.onNodeWithTag("tone_rename").assertIsDisplayed()
        rule.onRoot().captureRoboImage("src/test/snapshots/tone_360_130_${theme}_mine.png")
        rule.onNodeWithTag("tone_band_1 kHz").performSemanticsAction(androidx.compose.ui.semantics.SemanticsActions.SetProgress) { it(5f) }
        rule.onNodeWithTag("tone_save").assertExists()
    }
    @Test fun light130(){gallery(false)}
    @Test fun dark130(){gallery(true)}
    /** "Tạo âm sắc" ở cuối nhóm Của tôi lưu đường cong đang nghe thành một dòng mới, tên gợi ý sẵn. */
    @Test fun addCreatesANamedToneFromTheCurrentCurve() {
        show(false)
        var before=0
        rule.runOnIdle { before=AudioFx.tones.mine.size }
        rule.onNodeWithTag("tone_add").performScrollTo().performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("tone_confirm").performScrollTo().performClick()
        rule.runOnIdle {
            val mine=AudioFx.tones.mine
            org.junit.Assert.assertEquals(before+1,mine.size)
            org.junit.Assert.assertEquals("Của tôi ${before+1}",mine.last().name)
            org.junit.Assert.assertEquals(vn.abook.player.ToneCatalog.presets.first { it.id=="clear" }.bands,mine.last().bands)
        }
    }
    @Test fun deleteShowsUndoInTheViewportAndRestoresThePreset() {
        show(false)
        var id=""
        rule.runOnIdle { AudioFx.changeTone { id=it.save("Undo")!! } }
        rule.onNodeWithTag("tone_more_0").performScrollTo().performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("tone_delete").performScrollTo().performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("tone_undo").assertIsDisplayed().performClick()
        rule.runOnIdle { org.junit.Assert.assertTrue(AudioFx.tones.mine.any { it.id==id });org.junit.Assert.assertEquals(id,AudioFx.tones.selected.id) }
    }
}
