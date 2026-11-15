package vn.abook.player

import android.graphics.Bitmap
import android.os.Build
import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.data.FakeSettingsCore
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.nowplaying.*
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.screens.SettingsGroupScreen
import vn.abook.player.ui.theme.ThemeReveal
import vn.abook.player.ui.snapshot.UiTree
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Real Compose semantics and pixels; no models, network, or owner's data. */
@RunWith(AndroidJUnit4::class)
class AffordanceOnDeviceTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private data class Scene(val name: String, val dark: Boolean, val group: SettingsGroup? = null, val sheet: PlayerSheet? = null, val reading: Boolean = false)

    @Test fun captureMainScreensAndEveryPlayerSheet() {
        check(Build.HARDWARE in setOf("ranchu", "goldfish")) { "Emulator only" }
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val out = File(context.getExternalFilesDir(null), "affordance").apply { mkdirs() }
        val scenes = listOf(false, true).flatMap { dark ->
            val theme = if (dark) "dark" else "light"
            SettingsGroup.entries.map { Scene("settings_${it.name.lowercase()}_$theme", dark, group = it) } +
                PlayerSheet.entries.map { Scene("player_${it.name.lowercase()}_$theme", dark, sheet = it, reading = true) } +
                listOf(Scene("player_listen_$theme", dark), Scene("player_reading_$theme", dark, reading = true))
        }
        var scene by mutableStateOf(scenes.first())
        rule.setContent {
            key(scene.name) {
                AbookTheme(scene.dark) {
                    val scope = rememberCoroutineScope()
                    val repo = remember { SettingsRepo(FakeSettingsCore(), scope, Dispatchers.Unconfined).also { runBlocking { it.load() } } }
                    val sheets = remember { SheetHost() }
                    val env = remember { SettingsEnv(repo, ThemeReveal(scope)) }
                    Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                        if (scene.group != null) {
                            SettingsGroupScreen(scene.group!!, env, sheets, {})
                            SheetLayer(sheets)
                        } else {
                            val model = remember { FakeNowPlayingModel(FakeNowPlayingModel.demoState().copy(
                                voices = List(6) { PlayerVoice("device:test$it", "Tiếng Việt ${it + 1}") }, voiceId = "device:test0")) }
                            val window = rememberNowPlayingWindowState()
                            LaunchedEffect(Unit) {
                                window.voiceSettings = {}; window.bookPage = {}
                                window.reading = scene.reading; window.open()
                                scene.sheet?.let(window::openSheet)
                            }
                            NowPlayingLayer(model, window, sampleClock = false) { Box(Modifier.fillMaxSize()) }
                        }
                    }
                }
            }
        }
        for (next in scenes) {
            rule.runOnIdle { scene = next }
            rule.waitForIdle()
            val root = rule.onRoot()
            val file = File(out, next.name + ".png")
            file.outputStream().use { root.captureToImage().asAndroidBitmap().compress(Bitmap.CompressFormat.PNG, 100, it) }
            val tree = UiTree.describe(root.fetchSemanticsNode(), file.name)
            tree.put("image_sha256", MessageDigest.getInstance("SHA-256").digest(file.readBytes()).joinToString("") { "%02x".format(it) })
            File(out, next.name + ".tree.json").writeText(tree.toString())
            if (next.sheet == PlayerSheet.Voice) {
                rule.onNodeWithTag("voice_add").assertHasClickAction().assertIsDisplayed()
                rule.onNodeWithTag("voice_choice_device:test1").assertHasClickAction()
            }
        }
    }
}
