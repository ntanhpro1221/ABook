package vn.abook.player

import java.io.File
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class CastCloseTest {
    @Test fun closingDuringAPollStopsAndReleasesTheDeviceExactlyOnce() {
        val folder = Files.createTempDirectory("cast-close").toFile()
        val entered = CountDownLatch(1)
        val unblockPoll = CountDownLatch(1)
        val closeStarted = CountDownLatch(1)
        val closeSaved = CountDownLatch(1)
        val pollBlocked = AtomicBoolean(false)
        val calls = java.util.Collections.synchronizedList(mutableListOf<String>())
        var track: CastTrack? = null
        val backend = object : CastBackend {
            override fun load(value: CastTrack, seconds: Double): Double { track = value; return seconds }
            override fun play() {}
            override fun pause() = false
            override fun seek(seconds: Double) {}
            override fun stop(timeoutMs: Int) { calls += "stop" }
            override fun close(release: Boolean) { calls += "close:$release" }
            override fun status(): CastStatus {
                if (pollBlocked.get()) {
                    entered.countDown()
                    check(unblockPoll.await(TestTime.seconds(5), TimeUnit.SECONDS))
                }
                return CastStatus("PLAYING", 6.0, 300.0, track!!.url)
            }
        }
        val book = DlnaPlayers.Book("Fixture", listOf(DlnaPlayers.Chapter(1, "One", 300.0,
            File(folder, "1.mp3").apply { writeBytes(ByteArray(100)) })))
        val players = DlnaPlayers(
            book = { book },
            save = { _, _, _, _, _ -> if (Thread.currentThread().name == "test-cast-close") closeSaved.countDown() },
            media = Dlna.Media("127.0.0.1"),
            find = { listOf("speaker" to "127.0.0.1") },
            read = { id, host -> Dlna.Renderer(id, "Fixture speaker", "speaker", host) },
            backend = { backend },
        ).apply { playingPollMs = 10; idlePollMs = 10 }
        var closing: Thread? = null
        try {
            players.scan()
            val deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(TestTime.ms(5_000))
            while (!players.owns("speaker") && System.nanoTime() < deadline) Thread.yield()
            assertTrue(players.owns("speaker"))
            players.send("speaker", JSONObject().put("action", "load").put("bookId", "book").put("chapterId", 1))
            pollBlocked.set(true)
            assertTrue(entered.await(TestTime.seconds(5), TimeUnit.SECONDS))
            closing = Thread({ closeStarted.countDown(); players.close() }, "test-cast-close").apply { start() }
            assertTrue(closeStarted.await(TestTime.seconds(5), TimeUnit.SECONDS))
            // Closing must not mark/save an ended session while an in-flight poll still owns it.
            assertFalse(closeSaved.await(TestTime.ms(250), TimeUnit.MILLISECONDS))
            unblockPoll.countDown()
            closing.join(TestTime.ms(5_000))
            assertFalse(closing.isAlive)
            assertEquals(listOf("stop", "close:true"), calls.toList())
        } finally {
            unblockPoll.countDown()
            closing?.join(TestTime.ms(5_000))
            players.close()
            folder.deleteRecursively()
        }
    }
}
