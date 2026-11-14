package vn.abook.player.ui.music.library

import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.MusicLibrary
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.data.BookDetail
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.PlayerClock
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.screens.BookScreen
import vn.abook.player.ui.screens.BookScreenActions
import vn.abook.player.ui.theme.AbookTheme
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class BookMusicPlacementTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val gate = CountDownLatch(1)
    private val sceneReads = AtomicInteger()
    private val catalogReads = AtomicInteger()
    private lateinit var state: LibraryState
    @After fun unblock() { gate.countDown() }

    private fun show(block: Boolean = false, failFirst: Boolean = false) {
        val detail = BookDetail.of(JSONObject().put("id", "music-fixture").put("title", "Audit book").put("complete", true)
            .put("chaptersTotal", 300).put("chapters", JSONArray((1..300).map { n -> JSONObject().put("id", n)
                .put("fullTitle", "Audit chapter $n").put("file", "audio/$n.mp3").put("available", true).put("duration", 360) })), null, { null })
        val source = object : BookSource by BookSource.None { override suspend fun detail(id: String) = detail }
        val library = object : LibrarySource {
            override fun load(): LibraryIndex {
                check(Looper.myLooper() != Looper.getMainLooper())
                catalogReads.incrementAndGet()
                return LibraryIndex((1..200).map { n -> MusicLibrary.Track("https://example.invalid/$n.mp3", JSONObject().put("title", "Audit track $n").put("bytes", 1024)) }, emptyList(), emptyList(), emptyList())
            }
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
        rule.setContent {
            val scope = rememberCoroutineScope()
            state = remember { LibraryState(library, scope, object : PreviewPlayer {
                override fun play(link: String, startSeconds: Double, volume: Float, onEnd: () -> Unit) {}
                override fun stop() {}
            }) }
            val sheets = remember { SheetHost() }
            AbookTheme(false) {
                BookScreen(detail.book, vn.abook.player.ui.data.LibraryState.Ready(listOf(detail.book)), PlayerState.Empty,
                    PlayerClock(), CoverLoader(1 shl 20), source, sheets,
                    BookScreenActions(back = {}, playBook = {}, toggle = {}, playChapter = { _, _, _ -> }, deleted = {}, edit = {}),
                    bookMusic = { id -> BookMusicFor(state, sheets, id) {
                        check(Looper.myLooper() != Looper.getMainLooper())
                        val attempt = sceneReads.incrementAndGet()
                        if (block) check(gate.await(20, TimeUnit.SECONDS))
                        if (failFirst && attempt == 1) throw IOException("fixture read error")
                        (1..12000).map { n -> "scene-$n" to "https://example.invalid/${n % 64 + 1}.mp3" }
                    } })
            }
        }
        rule.waitForIdle()
    }

    @Test fun chapterEndHasNoMusicAndDoesNotLoadIt() {
        show()
        rule.onNodeWithTag("book_list").performScrollToNode(hasTestTag("chapter_300"))
        rule.onNodeWithTag("chapter_300").assertIsDisplayed()
        assertEquals(0, sceneReads.get())
        assertEquals(0, catalogReads.get())
        rule.onNodeWithTag("book_music_heading").assertDoesNotExist()
    }

    @Test fun canLeaveMusicWhileItsIoIsBlocked() {
        show(block = true)
        rule.onNodeWithTag("book_tab_music").performClick()
        rule.waitUntil(10000) { sceneReads.get() > 0 }
        rule.onNodeWithTag("book_music_loading").assertIsDisplayed()
        rule.onNodeWithTag("book_tab_chapters").performClick()
        rule.onNodeWithTag("chapter_1").assertIsDisplayed()
        assertEquals(0, catalogReads.get())
        gate.countDown()
    }

    @Test fun musicRowsLoadInBackgroundAndKeepSceneAndByteTotals() {
        show()
        rule.onNodeWithTag("book_tab_music").performClick()
        rule.waitUntil(10000) { state.ui.value.index != null && rule.onAllNodesWithTag("book_music_loading").fetchSemanticsNodes().isEmpty() }
        rule.onNodeWithTag("book_list").performScrollToNode(hasTestTag("book_music_save_all"))
        rule.onNodeWithTag("book_music_save_all").assertIsDisplayed()
        val rows = BookMusicRows.build(MusicLibrary.bookTracks((1..12000).map { n -> "scene-$n" to "https://example.invalid/${n % 64 + 1}.mp3" }), state.ui.value.index!!, emptyList(), emptySet())
        assertEquals(64, rows.tracks.size)
        assertEquals(12000, rows.tracks.sumOf { it.second.scenes })
        assertEquals(64 * 1024L, rows.missingBytes)
        assertEquals(1, catalogReads.get())
        state.setOnline(true)
        rule.runOnUiThread { state.togglePreview(rows.tracks.first().first.link) }
        assertTrue(state.ui.value.previewing != null)
        rule.onNodeWithTag("book_list").performScrollToNode(hasTestTag("book_tab_chapters"))
        rule.onNodeWithTag("book_tab_chapters").performClick()
        rule.waitForIdle()
        assertEquals(null, state.ui.value.previewing)
    }

    @Test fun failedSceneReadCanBeRetried() {
        show(failFirst = true)
        rule.onNodeWithTag("book_tab_music").performClick()
        rule.waitUntil(10000) { rule.onAllNodesWithTag("book_music_retry").fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithTag("book_music_retry").performClick()
        rule.waitUntil(10000) { state.ui.value.index != null }
        assertTrue(sceneReads.get() >= 2)
        rule.onNodeWithTag("book_music_error").assertDoesNotExist()
    }
}
