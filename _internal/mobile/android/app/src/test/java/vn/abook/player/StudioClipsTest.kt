package vn.abook.player

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.voice.SamplePlayer
import java.io.File
import java.io.FileNotFoundException
import java.io.IOException
import java.nio.file.Files

/** Nghe thử trong Studio: tải cả chương MỘT lần vào cache, phát đúng đoạn của từng câu, bấm lại thì dừng, lượt cũ không phát chen vào lượt mới. */
class StudioClipsTest {
    private class Player : SamplePlayer {
        val ranges = ArrayList<Triple<String, Int, Int>>()
        var stops = 0
        var ended: (() -> Unit)? = null
        var failed: (() -> Unit)? = null

        override fun play(path: String, onEnded: () -> Unit, onFailed: () -> Unit) = playRange(path, 0, 0, onEnded, onFailed)

        override fun playRange(path: String, startMs: Int, endMs: Int, onEnded: () -> Unit, onFailed: () -> Unit) {
            ranges += Triple(File(path).name, startMs, endMs)
            ended = onEnded
            failed = onFailed
        }

        override fun stop() {
            stops++
        }
    }

    private val dir: File = Files.createTempDirectory("studio_clips").toFile()
    private val player = Player()
    private val fetched = ArrayList<String>()
    private var gate: CompletableDeferred<Unit>? = null
    private var failure: Throwable? = null
    private val clips = StudioClips(
        dir,
        { _, path, partial ->
            fetched += path
            gate?.await()
            failure?.let { throw it }
            partial.writeBytes(ByteArray(10))
        },
        player, CoroutineScope(Dispatchers.Unconfined), limitBytes = 25,
    )

    @After fun cleanUp() {
        dir.deleteRecursively()
    }

    private fun until(what: String, condition: () -> Boolean) {
        val end = System.currentTimeMillis() + 5_000
        while (!condition()) {
            if (System.currentTimeMillis() > end) throw AssertionError("Hết giờ chờ: $what")
            Thread.sleep(5)
        }
    }

    private val chapter = "/media/books/b1/chapters/1/audio"

    @Test fun aChapterIsDownloadedOnceAndEachSentencePlaysItsOwnWindow() {
        clips.toggle("a", ClipSpec("", chapter, 1000, 2500))
        until("câu đầu phát") { clips.state.value.playing == "a" }
        clips.toggle("b", ClipSpec("", chapter, 4000, 5200))
        until("câu hai phát") { clips.state.value.playing == "b" }
        assertEquals(listOf(chapter), fetched)
        assertEquals(listOf(1000 to 2500, 4000 to 5200), player.ranges.map { it.second to it.third })
        assertEquals(1, player.ranges.map { it.first }.distinct().size)
    }

    @Test fun tappingTheSameClipAgainStopsIt() {
        clips.toggle("a", ClipSpec("", chapter))
        until("phát") { clips.state.value.playing == "a" }
        clips.toggle("a", ClipSpec("", chapter))
        assertNull(clips.state.value.playing)
        assertTrue(player.stops > 0)
    }

    @Test fun finishingFiresTheCallbackAndClearsTheState() {
        var ended = 0
        clips.toggle("a", ClipSpec("", chapter)) { ended++ }
        until("phát") { clips.state.value.playing == "a" }
        player.ended!!.invoke()
        assertEquals(1, ended)
        assertEquals(ClipState(), clips.state.value)
    }

    @Test fun stoppingNeverFiresTheEndedCallback() {
        var ended = 0
        clips.toggle("a", ClipSpec("", chapter)) { ended++ }
        until("phát") { clips.state.value.playing == "a" }
        clips.stop()
        player.ended!!.invoke()
        assertEquals(0, ended)
    }

    @Test fun aClipTappedWhileAnotherIsStillDownloadingReplacesIt() = runBlocking {
        gate = CompletableDeferred()
        clips.toggle("a", ClipSpec("", "/media/books/b1/chapters/1/audio"))
        assertEquals("a", clips.state.value.loading)
        clips.toggle("b", ClipSpec("", "/media/books/b1/chapters/2/audio"))
        assertEquals("b", clips.state.value.loading)
        gate!!.complete(Unit)
        until("b phát") { clips.state.value.playing == "b" }
        Thread.sleep(50)
        assertEquals(1, player.ranges.size)
        assertEquals("b", clips.state.value.playing)
    }

    @Test fun aDroppedConnectionIsOfflineAndAMissingFileIsMissing() {
        failure = IOException("rớt mạng")
        clips.toggle("a", ClipSpec("", chapter))
        until("hỏng") { clips.state.value.failure != null }
        assertEquals(ClipFailure.Offline, clips.state.value.failure)
        failure = FileNotFoundException("404")
        clips.toggle("a", ClipSpec("", chapter))
        until("hỏng lại") { clips.state.value.failure == ClipFailure.Missing }
        assertTrue(player.ranges.isEmpty())
    }

    @Test fun theCacheDropsTheOldestFilesFirstAndNeverTheOneInUse() {
        val old = File(dir, "old.clip").also { it.writeBytes(ByteArray(10)); it.setLastModified(1_000) }
        val mid = File(dir, "mid.clip").also { it.writeBytes(ByteArray(10)); it.setLastModified(2_000) }
        val current = File(dir, "now.clip").also { it.writeBytes(ByteArray(10)) }
        clips.trim(keep = current)
        assertFalse(old.exists())
        assertTrue(mid.exists())
        assertTrue(current.exists())
    }

    @Test fun cacheNamesNeverContainTheSourcePath() {
        val name = StudioClips.name(ClipSpec("m", "/media/../x"))
        assertTrue(name.endsWith(".clip"))
        assertFalse(name.contains("/") || name.contains(".."))
        assertEquals(name, StudioClips.name(ClipSpec("m", "/media/../x", 5, 9)))
    }
}
