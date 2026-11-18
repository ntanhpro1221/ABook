package vn.abook.player

import android.os.Build
import android.os.SystemClock
import android.view.InputDevice
import android.view.MotionEvent
import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.music.library.LibraryIndex
import vn.abook.player.ui.music.library.LibrarySource
import vn.abook.player.ui.music.library.LibraryState
import vn.abook.player.ui.music.library.MusicPart
import vn.abook.player.ui.music.library.MusicScreen
import vn.abook.player.ui.music.library.PreviewPlayer
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/**
 * Ảnh của chủ sách 17-11 (OPPO, Nhạc > Kho nhạc): bấm thanh "Đang nghe thử" thì cú bấm lọt xuống dòng bài nằm dưới. Trên emulator, cú chạm đi qua đường
 * nhập THẬT của hệ thống (UiAutomation.injectInputEvent tại toạ độ màn hình): chạm thân thanh mở chi tiết của chính bài đang nghe thử, chạm chỗ chừa đáy
 * dưới thanh không mở dòng nào. Từ chối chạy trên máy thật.
 */
@RunWith(AndroidJUnit4::class)
class PreviewBarTapOnDeviceTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private class Source : LibrarySource {
        private val raw = (0 until 40).associate { index ->
            "https://music.example/$index.mp3" to JSONObject().put("title", "Bài %02d".format(index)).put("creator", "Người %d".format(index % 4))
                .put("duration", 60 + index).put("bpm", 90).put("style", "piano").put("bytes", 2_000_000).put("lufs", -16).put("audibleStart", 0.0)
                .put("license", "cc0").put("emotions", JSONObject().put("joy", 0.5))
        }
        override fun load() = LibraryIndex(MusicLibrary.tracksOf(raw), emptyList(), emptyList(), emptyList())
        override fun downloaded(links: Collection<String>) = emptySet<String>()
        override fun saved() = emptyList<String>()
        override fun save(links: List<String>) {}
        override fun unsave(links: List<String>) {}
        override fun download(link: String, progress: (Long, Long?) -> Unit, cancelled: () -> Boolean) {}
        override fun forget(link: String) {}
        override fun partial(link: String) = 0L
        override fun metered() = false
        override fun online() = true
    }

    private class Silent : PreviewPlayer {
        override fun play(link: String, startSeconds: Double, volume: Float, onEnd: () -> Unit, onPlaying: (Boolean) -> Unit, onError: (String) -> Unit) = onPlaying(true)
        override fun stop() {}
    }

    /** Một cú chạm thật vào màn hình tại (x, y) px của cửa sổ. */
    private fun tap(x: Float, y: Float) {
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        val location = IntArray(2)
        rule.runOnUiThread { rule.activity.window.decorView.getLocationOnScreen(location) }
        val sx = x + location[0]
        val sy = y + location[1]
        val down = SystemClock.uptimeMillis()
        for ((action, at) in listOf(MotionEvent.ACTION_DOWN to down, MotionEvent.ACTION_UP to down + 60)) {
            val event = MotionEvent.obtain(down, at, action, sx, sy, 0).apply { source = InputDevice.SOURCE_TOUCHSCREEN }
            assertTrue(automation.injectInputEvent(event, true))
            event.recycle()
        }
        rule.waitForIdle()
        SystemClock.sleep(400)
        rule.waitForIdle()
    }

    private fun rowUnder(x: Float, y: Float) = rule.onAllNodes(SemanticsMatcher("track row") {
        it.config.getOrNull(SemanticsProperties.TestTag)?.matches(Regex("track_-?\\d+")) == true
    }).fetchSemanticsNodes().any { it.boundsInRoot.contains(androidx.compose.ui.geometry.Offset(x, y)) }

    private fun sheetTitle(): String? = rule.onAllNodesWithTag("track_title").fetchSemanticsNodes().firstOrNull()
        ?.config?.getOrNull(SemanticsProperties.Text)?.joinToString { it.text }

    @Test
    fun barTapOpensThePreviewingTrackAndNothingLeaks() {
        assumeTrue("emulator only: máy thật (OPPO) bỏ qua, không đỏ", Build.FINGERPRINT.contains("generic") || Build.HARDWARE.contains("ranchu") || Build.PRODUCT.contains("sdk"))
        val sheets = SheetHost()
        val state = LibraryState(Source(), CoroutineScope(Dispatchers.Unconfined), Silent(), pauseBook = {}, io = Dispatchers.Unconfined)
        rule.setContent {
            AbookTheme(false) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    MusicScreen(state, sheets, initialPart = MusicPart.Library)
                    SheetLayer(sheets)
                }
            }
        }
        rule.waitForIdle()
        rule.runOnUiThread { state.togglePreview("https://music.example/3.mp3") }
        rule.waitForIdle()
        val node = rule.onNodeWithTag("preview_bar").fetchSemanticsNode()
        val bar = node.boundsInRoot
        val shift = node.boundsInWindow.topLeft - bar.topLeft   // gốc Compose -> cửa sổ (thanh trạng thái)
        assertTrue("a row lies under the bar", rowUnder(bar.center.x, bar.center.y))
        tap(bar.center.x + shift.x, bar.center.y + shift.y)
        assertEquals("Bài 03", sheetTitle())
        rule.runOnUiThread { sheets.dismiss() }
        rule.waitForIdle()
        SystemClock.sleep(600)
        val below = androidx.compose.ui.geometry.Offset(bar.center.x, bar.bottom + 6f)
        assertTrue("a row lies under the bar's bottom clearance", rowUnder(below.x, below.y))
        tap(below.x + shift.x, below.y + shift.y)
        assertEquals("tap under the bar leaked to a row", null, sheetTitle())
        assertEquals("https://music.example/3.mp3", state.ui.value.previewing)
    }
}
