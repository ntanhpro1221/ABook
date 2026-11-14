package vn.abook.player

import android.content.Intent
import android.graphics.Bitmap
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.view.FrameMetrics
import android.view.MotionEvent
import android.view.Window
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.ui.NativeActivity
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.music.library.*
import vn.abook.player.ui.theme.AbookTheme
import java.io.ByteArrayOutputStream
import java.io.File
import java.security.MessageDigest
import java.util.Collections

/** Dedicated emulator only: synthetic catalog, verified cached images, no source requests/audio. */
class MusicArtOnDeviceTest {
    @Test fun offlineLibraryAndScrollFrames() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val out = File(context.getExternalFilesDir(null), "musicart").apply { mkdirs() }
        val cache = File(context.cacheDir, "music-art").apply { mkdirs() }
        val bitmap = Bitmap.createBitmap(96, 96, Bitmap.Config.ARGB_8888).apply { eraseColor(0xff497f7d.toInt()) }
        val data = ByteArrayOutputStream().also { bitmap.compress(Bitmap.CompressFormat.JPEG, 88, it) }.toByteArray()
        val sha = MessageDigest.getInstance("SHA-1").digest(data).joinToString("") { "%02x".format(it) }
        File(cache, "$sha.jpg").writeBytes(data)
        val tracks = (0 until 2387).map { at ->
            val info = JSONObject().put("title", "Artwork %04d".format(at)).put("creator", "ABook")
                .put("style", if (at % 2 == 0) "piano" else "ambient").put("arousal", (at % 200) / 100.0 - 1).put("duration", 180)
            if (at % 3 == 0) info.put("art", JSONObject().put("url", "https://artwork.invalid/$sha.jpg").put("sha1", sha).put("w",96).put("h",96))
            MusicLibrary.Track("https://music.example/$at.mp3", info)
        }
        val source = object : LibrarySource {
            override fun load() = LibraryIndex(tracks, emptyList(), emptyList(), emptyList())
            override fun downloaded(links: Collection<String>) = emptySet<String>()
            override fun saved() = emptyList<String>()
            override fun save(links: List<String>) {}
            override fun unsave(links: List<String>) {}
            override fun download(link: String, progress: (Long, Long?) -> Unit, cancelled: () -> Boolean) {}
            override fun forget(link: String) {}
            override fun partial(link: String) = 0L
            override fun metered() = false
            override fun online() = false
        }
        val preview = object : PreviewPlayer {
            override fun play(link: String, startSeconds: Double, volume: Float, onEnd: () -> Unit) {}
            override fun stop() {}
        }
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
        val state = LibraryState(source, scope, preview, pauseBook = {})
        val sheets = SheetHost()
        val frames = Collections.synchronizedList(ArrayList<Double>())
        val thread = HandlerThread("musicart-frames").apply { start() }
        val listener = Window.OnFrameMetricsAvailableListener { _, frame, _ -> frames.add(frame.getMetric(FrameMetrics.TOTAL_DURATION) / 1_000_000.0) }
        val intent = Intent(context, NativeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        ActivityScenario.launch<NativeActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                activity.window.addOnFrameMetricsAvailableListener(listener, Handler(thread.looper))
                activity.setContent { AbookTheme(false) {
                    Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                        MusicScreen(state, sheets, onMyMusic = {}, initialPart = MusicPart.Library)
                        SheetLayer(sheets)
                    }
                } }
            }
            val deadline = SystemClock.uptimeMillis() + 30000
            while (state.ui.value.shown.size != 2387 && SystemClock.uptimeMillis() < deadline) Thread.sleep(50)
            assertEquals(2387, state.ui.value.shown.size)
            val readyDeadline = SystemClock.uptimeMillis() + 15000
            while (tracks.take(4).any { !ArtImages.ready(MusicArtwork.seed(it.link, it.info), it.info.optJSONObject("art")?.optString("sha1") ?: "") }
                && SystemClock.uptimeMillis() < readyDeadline) Thread.sleep(50)
            instrumentation.waitForIdleSync()
            Thread.sleep(500)
            var screenshot = instrumentation.uiAutomation.takeScreenshot()
            repeat(30) {
                if (!hasCovers(screenshot)) { Thread.sleep(100); screenshot = instrumentation.uiAutomation.takeScreenshot() }
            }
            screenshot.compressTo(File(out, "android-library.png"))
            assertTrue("source and generated artwork must be rendered before timing", hasCovers(screenshot))
            frames.clear()
            val display = context.resources.displayMetrics
            repeat(12) {
                val start = SystemClock.uptimeMillis()
                for (step in 0..20) {
                    val action = if (step == 0) MotionEvent.ACTION_DOWN else if (step == 20) MotionEvent.ACTION_UP else MotionEvent.ACTION_MOVE
                    val event = MotionEvent.obtain(start, SystemClock.uptimeMillis(), action, display.widthPixels / 2f,
                        display.heightPixels * (.80f - .48f * step / 20), 0)
                    instrumentation.sendPointerSync(event); event.recycle()
                    Thread.sleep(16)
                }
            }
            Thread.sleep(500)
            scenario.onActivity { it.window.removeOnFrameMetricsAvailableListener(listener) }
            val sorted = synchronized(frames) { frames.toList().sorted() }
            assertTrue("no rendered frames", sorted.size > 30)
            val result = JSONObject().put("frames", sorted.size).put("p50Ms", sorted[sorted.size / 2])
                .put("p95Ms", sorted[(sorted.size * .95).toInt().coerceAtMost(sorted.lastIndex)])
                .put("over16_67Ms", sorted.count { it > 16.67 }).put("maxMs", sorted.last())
                .put("tracks", 2387).put("offline", true).put("cachedImageEvery", 3)
            File(out, "frames.json").writeText(result.toString(2))
            assertNotNull(runBlocking { ArtImages.real(cache, "https://artwork.invalid/$sha.jpg", sha) })
            File(out, "offline-cache.ok").writeText(sha)
            scenario.onActivity { sheets.show { dismiss -> TrackSheet(state, tracks.first().link, dismiss) } }
            Thread.sleep(1000)
            instrumentation.uiAutomation.takeScreenshot().compressTo(File(out, "android-detail.png"))
        }
        scope.cancel(); thread.quitSafely()
    }

    private fun Bitmap.compressTo(path: File) { path.outputStream().use { compress(Bitmap.CompressFormat.PNG, 100, it) } }

    private fun hasCovers(bitmap: Bitmap): Boolean {
        var teal = 0; var gold = 0
        for (y in 0 until bitmap.height step 3) for (x in 0 until bitmap.width step 3) {
            val pixel = bitmap.getPixel(x, y)
            val r = android.graphics.Color.red(pixel); val g = android.graphics.Color.green(pixel); val b = android.graphics.Color.blue(pixel)
            if (r in 70..80 && g in 120..132 && b in 120..132) teal++
            if (r in 140..235 && g in 120..205 && b in 80..145) gold++
        }
        return teal > 80 && gold > 80
    }
}
