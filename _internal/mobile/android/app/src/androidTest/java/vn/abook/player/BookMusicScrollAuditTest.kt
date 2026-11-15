package vn.abook.player

import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.view.FrameMetrics
import androidx.activity.ComponentActivity
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performScrollToIndex
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipeUp
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.data.BookDetail
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.PlayerClock
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.music.library.BookMusicFor
import vn.abook.player.ui.music.library.LibraryIndex
import vn.abook.player.ui.music.library.LibrarySource
import vn.abook.player.ui.music.library.LibraryState
import vn.abook.player.ui.music.library.PreviewPlayer
import vn.abook.player.ui.screens.BookScreen
import vn.abook.player.ui.screens.BookScreenActions
import vn.abook.player.ui.theme.AbookTheme
import java.io.File
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicBoolean

/** Original generated data only. Opt in on the dedicated emulator with -e bookMusicAudit true. */
class BookMusicScrollAuditTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun scrollToBookEnd() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("bookMusicAudit") == "true")
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val root = File(context.cacheDir, "bookmusic-audit").apply { mkdirs() }
        val catalog = File(root, "catalog.json")
        catalog.writeText(JSONArray((1..2400).map { n -> JSONObject().put("link", "https://example.invalid/$n.mp3")
            .put("title", "Audit track $n").put("creator", "Fixture composer").put("bytes", 1048576).put("duration", 180) }).toString())
        val sceneFile = File(root, "scenes.json")
        sceneFile.writeText(JSONArray((1..12000).map { n -> JSONObject().put("key", "scene-$n").put("link", "https://example.invalid/${n % 64 + 1}.mp3") }).toString())
        val calls = CopyOnWriteArrayList<String>()
        val source = object : LibrarySource {
            override fun load(): LibraryIndex {
                calls += "catalog:${Thread.currentThread().name}"
                val raw = JSONArray(catalog.readText())
                return LibraryIndex((0 until raw.length()).map { raw.getJSONObject(it).let { row -> MusicLibrary.Track(row.getString("link"), row) } }, emptyList(), emptyList(), emptyList())
            }
            override fun downloaded(links: Collection<String>): Set<String> {
                calls += "file-size:${Thread.currentThread().name}"
                return links.filter { File(root, it.substringAfterLast('/')).let { file -> file.isFile && file.length() > 0 } }.toSet()
            }
            override fun saved() = emptyList<String>()
            override fun save(links: List<String>) {}
            override fun unsave(links: List<String>) {}
            override fun download(link: String, progress: (Long, Long?) -> Unit, cancelled: () -> Boolean) {}
            override fun forget(link: String) {}
            override fun partial(link: String) = 0L
            override fun metered() = false
            override fun online() = false
        }
        val manifest = JSONObject().put("id", "scroll-audit").put("title", "Scroll fixture").put("complete", true)
            .put("chaptersTotal", 300).put("chapters", JSONArray((1..300).map { n -> JSONObject().put("id", n)
                .put("fullTitle", "Audit chapter $n").put("file", "audio/$n.mp3").put("available", true).put("duration", 360) }))
        val detail = BookDetail.of(manifest, null, { null })
        val bookSource = object : BookSource by BookSource.None { override suspend fun detail(id: String) = detail }
        rule.setContent {
            AbookTheme(false) {
                val scope = rememberCoroutineScope()
                val library = remember { LibraryState(source, scope, object : PreviewPlayer {
                    override fun play(link: String, startSeconds: Double, volume: Float, onEnd: () -> Unit, onPlaying: (Boolean) -> Unit, onError: (String) -> Unit) {}
                    override fun stop() {}
                }) }
                val sheets = remember { SheetHost() }
                BookScreen(detail.book, vn.abook.player.ui.data.LibraryState.Ready(listOf(detail.book)), PlayerState.Empty,
                    PlayerClock(), CoverLoader(1 shl 20), bookSource, sheets,
                    BookScreenActions(back = {}, playBook = {}, toggle = {}, playChapter = { _, _, _ -> }, deleted = {}, readAlong = {}, edit = {}),
                    bookMusic = { id -> BookMusicFor(library, sheets, id) {
                        calls += "scenes:${Thread.currentThread().name}"
                        val raw = JSONArray(sceneFile.readText())
                        (0 until raw.length()).map { raw.getJSONObject(it).let { row -> row.getString("key") to row.getString("link") } }
                    } })
            }
        }
        rule.waitForIdle()
        rule.onNodeWithTag("book_list").performScrollToIndex(290)
        rule.waitForIdle()
        val frames = CopyOnWriteArrayList<Long>()
        val samples = CopyOnWriteArrayList<String>()
        val running = AtomicBoolean(true)
        val main = Looper.getMainLooper().thread
        val sampler = Thread {
            while (running.get()) {
                val stack = main.stackTrace
                stack.firstOrNull { it.className.contains("MusicLibrary") || it.className.contains("BookMusicSection") || it.className.contains("LibraryState") }
                    ?.let { samples += it.toString() }
                Thread.sleep(2)
            }
        }.apply { start() }
        val collector = HandlerThread("bookmusic-frames").apply { start() }
        val listener = android.view.Window.OnFrameMetricsAvailableListener { _, frame, _ -> frames += frame.getMetric(FrameMetrics.TOTAL_DURATION) }
        rule.activity.window.addOnFrameMetricsAvailableListener(listener, Handler(collector.looper))
        try {
            repeat(12) { rule.onNodeWithTag("book_list").performTouchInput { swipeUp(durationMillis = 350) }; Thread.sleep(150) }
            rule.waitForIdle()
            Thread.sleep(1200)
        } finally {
            running.set(false); sampler.join()
            rule.activity.window.removeOnFrameMetricsAvailableListener(listener)
            collector.quitSafely()
        }
        val period = 1_000_000_000.0 / rule.activity.display!!.refreshRate
        val ordered = frames.sorted()
        val report = JSONObject().put("frames", JSONArray(frames)).put("frameCount", frames.size)
            .put("overBudget", frames.count { it > period }).put("missedVsyncSlots", frames.sumOf { (kotlin.math.ceil(it / period).toLong() - 1).coerceAtLeast(0) })
            .put("p95Ms", ordered.getOrNull((ordered.size * .95).toInt())?.div(1e6)).put("maxMs", ordered.lastOrNull()?.div(1e6))
            .put("periodMs", period / 1e6).put("calls", JSONArray(calls)).put("mainMusicSamples", JSONArray(samples))
        File(context.getExternalFilesDir(null), "bookmusic-scroll.json").writeText(report.toString(2))
        check(calls.none { it.endsWith(":main") }) { calls.toString() }
    }
}
