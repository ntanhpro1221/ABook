package vn.abook.player.ui.nowplaying

import android.speech.tts.Voice
import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import com.github.takahirom.roborazzi.RoborazziOptions
import com.github.takahirom.roborazzi.RoborazziTaskType
import java.io.File
import java.util.Locale
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.readaloud.DeviceVoiceNames
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.snapshot.captureRoboImage
import vn.abook.player.ui.snapshot.UiTree
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.dp
import java.security.MessageDigest
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.voice.*

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class DeviceVoiceSheetTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    private fun check(dark: Boolean) {
        fun voices(engine: String, label: String, vararg ids: String) = DeviceVoiceNames.describe(engine, label,
            ids.map { Voice(it, Locale.forLanguageTag("vi-VN"), Voice.QUALITY_HIGH, Voice.LATENCY_NORMAL, false, emptySet()) })
        val listed = voices("com.google.android.tts", "", "vi-vn-x-gft-local", "vi-vn-x-vie-local", "vi-vn-x-vif-local") +
            voices("com.samsung.SMT", "", "samsung-vi") + voices("oem.reader", "OPPO", "oem-vi")
        val source = FakeVoiceSource()
        val scope = CoroutineScope(Dispatchers.Unconfined)
        val sampling = VoiceState(source, scope, FakeSamplePlayer(), imports = MineImports(source, scope))
        val state = FakeNowPlayingModel.demoState().copy(voices = listed.map { PlayerVoice(it.id, it.name) }, voiceId = listed.first().id)
        val fake = FakeNowPlayingModel(state)
        var canSample by mutableStateOf(true)
        val model = object : NowPlayingModel by fake { override val voice get() = if (canSample) sampling else null }
        rule.setContent {
            AbookTheme(dark) {
                val window = rememberNowPlayingWindowState()
                LaunchedEffect(Unit) { window.openSheet(PlayerSheet.Voice) }
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { PlayerSheets(state, model, window) }
            }
        }
        rule.waitForIdle()
        rule.onNodeWithTag("voice_choice_${listed.first().id}").assertIsSelected()
        rule.onNodeWithTag("voice_choice_${listed.last().id}").assertIsNotSelected()
        rule.onNodeWithText("Đang chọn").assertDoesNotExist()
        for (voice in listed) {
            rule.onNodeWithText(voice.name).assertIsDisplayed()
            val nameBounds = rule.onNodeWithText(voice.name).getUnclippedBoundsInRoot()
            val tryBounds = rule.onNodeWithTag("voice_try_${voice.id}").getUnclippedBoundsInRoot()
            assertTrue("Preview must be at least 12 dp from the name", tryBounds.left - nameBounds.right >= 12.dp)
            val layouts = mutableListOf<TextLayoutResult>()
            rule.onNodeWithText(voice.name).performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
            assertEquals(1, layouts.single().lineCount)
            assertTrue(rule.onNodeWithTag("voice_try_${voice.id}").fetchSemanticsNode().config[SemanticsProperties.ContentDescription].single().contains(voice.name))
            rule.onNodeWithTag("voice_try_${voice.id}").assertIsDisplayed().performClick()
            rule.waitForIdle()
            assertEquals(voice.id, source.sampled.last().first)
            rule.onNodeWithTag("voice_try_${voice.id}").performClick()
        }
        rule.runOnIdle { canSample = false }
        rule.waitForIdle()
        rule.onAllNodesWithTag("voice_try_${listed.first().id}").assertCountEquals(0)
        rule.onNodeWithTag("voice_choice_${listed.first().id}").assertIsSelected()
        rule.onNodeWithText("Đang chọn").assertDoesNotExist()
        rule.runOnIdle { canSample = true }
        rule.waitForIdle()
        rule.onNodeWithTag("voice_try_${listed.first().id}").assertIsDisplayed()
        // Export review frames only when requested; evidence stays outside the checkout.
        System.getenv("DEVVOICE_EVIDENCE")?.let { directory ->
            val name = if (dark) "android-dark.png" else "android-light.png"
            val frame = File(directory, "build/icon_probe/$name").apply { parentFile?.mkdirs() }.path
            rule.onRoot().captureRoboImage(frame, RoborazziOptions(taskType = RoborazziTaskType.Record))
            val png = File(frame)
            val tree = UiTree.describe(rule.onRoot().fetchSemanticsNode(), png.name)
            tree.put("image_sha256", MessageDigest.getInstance("SHA-256").digest(png.readBytes()).joinToString("") { "%02x".format(it) })
            png.resolveSibling(png.nameWithoutExtension + ".tree.json").writeText(tree.toString())
        }
        rule.onNodeWithTag("voice_choice_${listed.last().id}").performClick()
        assertEquals(listed.last().id, fake.state.value.voiceId)
    }
    @Test fun light() = check(false)
    @Test fun dark() = check(true)
}
