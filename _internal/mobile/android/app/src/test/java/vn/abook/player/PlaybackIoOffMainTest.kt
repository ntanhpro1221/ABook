package vn.abook.player

import android.os.Handler
import androidx.media3.common.MediaItem
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Player events (pause, seek while paused, chapter change) arrive on the main looper. While another thread holds
 * Store's monitor - a slow disk write - those events must still return at once, and the place lands on disk afterwards.
 */
class PlaybackIoOffMainTest {
    private val voice = FakeExo()

    private fun field(name: String) = Playback::class.java.getDeclaredField(name).also { it.isAccessible = true }

    /** Only a presence check on these paths: nothing reaches a real Android service. */
    private val context: android.content.Context = Class.forName("sun.misc.Unsafe").let { unsafeClass ->
        val unsafe = unsafeClass.getDeclaredField("theUnsafe").also { it.isAccessible = true }.get(null)
        unsafeClass.getMethod("allocateInstance", Class::class.java).invoke(unsafe, android.content.ContextWrapper::class.java) as android.content.Context
    }

    @Before fun setup() {
        Handler.reset()
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("io-off-main"))
        voice.item = MediaItem.Builder().setMediaId("1").setTag(Playback.BookTag("io-book")).build()
        voice.duration = 3_600_000
        voice.position = 1_800_000
        voice.state = androidx.media3.common.Player.STATE_READY
        Playback.player = voice.player
        field("appContext").set(Playback, context) // the paused place is pushed to the holder after it is written
        field("bookId").set(Playback, "io-book")
        field("chapters").set(Playback, listOf(Playback.Chapter(1, "Một", "1.mp3", 3600.0)))
        field("savedPlace").set(Playback, 1 to 1_800_000L)
        Store.progress("io-book", 1, 1800.0, 3600.0)
    }

    @After fun cleanup() {
        SleepTimer.cancel()
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        field("sessionFrom").set(Playback, null)
        field("bookId").set(Playback, "")
        field("recordId").set(Playback, "")
        field("chapters").set(Playback, emptyList<Playback.Chapter>())
        field("savedPlace").set(Playback, null)
        Playback.player = null
        Handler.reset()
    }

    /** Runs [event] as the main looper would while the disk is busy; true when it returned without waiting for the disk. */
    private fun returnsWhileDiskIsBusy(event: () -> Unit): Boolean {
        val holding = CountDownLatch(1)
        val release = CountDownLatch(1)
        val disk = Thread { synchronized(Store) { holding.countDown(); release.await() } }.apply { start() }
        assertTrue(holding.await(TestTime.seconds(5), TimeUnit.SECONDS))
        val done = CountDownLatch(1)
        val caller = Thread { event(); done.countDown() }.apply { start() }
        try {
            // An event that waits for Store never returns while the disk thread holds it: any limit tells the two apart.
            return done.await(TestTime.seconds(2), TimeUnit.SECONDS)
        } finally {
            release.countDown()
            caller.join(TestTime.ms(5_000))
            disk.join(TestTime.ms(5_000))
        }
    }

    /**
     * The place on disk once the place writer has drained. The event handed its snapshot to the writer before it
     * returned, so the writer's own "nothing left" signal is the moment to read - no polling of the file.
     */
    private fun savedSeconds(): Double {
        assertTrue("the place was not written after the disk was released", Playback.flushSaves(TestTime.ms(2_000)))
        return Store.state("io-book").getJSONObject("last").getDouble("seconds")
    }

    @Test fun aSeekWhilePausedDoesNotWaitForTheDiskAndStillSaves() {
        assertTrue("seek on the main looper waited for Store", returnsWhileDiskIsBusy { Playback.seekTo(600.0) })
        assertEquals(600.0, savedSeconds(), 0.001)
    }

    @Test fun aPauseEventDoesNotWaitForTheDiskAndStillSaves() {
        voice.position = 900_000
        assertTrue("pause on the main looper waited for Store", returnsWhileDiskIsBusy { Playback.onPlayingChanged(false) })
        assertEquals(900.0, savedSeconds(), 0.001)
    }

    @Test fun aPauseWithATimerAnOpenSessionAndANightDoesNotWaitForDisk() {
        val record = Store.activeRecord("io-book")
        field("recordId").set(Playback, record)
        val now = System.currentTimeMillis()
        SleepTimer.restore(JSONObject().put("source", "manual").put("bookId", "io-book").put("recordId", record)
            .put("minutes", 30).put("remainingMs", 20 * 60_000L).put("savedAt", now), now)
        field("sessionFrom").set(Playback, JSONObject().put("chapterId", 1).put("seconds", 800.0))
        field("sessionBook").set(Playback, "io-book")
        field("sessionRecord").set(Playback, record)
        field("sessionStartMs").setLong(Playback, now - 25_000L)
        field("sessionMarkMs").setLong(Playback, now - 25_000L)
        field("sessionListenedMs").setLong(Playback, 0L)
        Bedtime.timerSet(30)
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        voice.position = 900_000L
        assertTrue("pause with timer/session waited for Store", returnsWhileDiskIsBusy {
            Bedtime.interaction("pause")
            Playback.onPlayingChanged(false)
        })
        assertEquals(900.0, savedSeconds(), 0.001)
        val sessions = Store.state("io-book").getJSONArray("sessions")
        assertEquals(1, sessions.length())
        assertTrue(sessions.getJSONObject(0).getDouble("listened") >= 20.0)
        val prefs = JSONObject(java.io.File(Store.root, "listen-prefs.json").readText())
        assertEquals(20 * 60_000L, prefs.getJSONObject("timer").getLong("remainingMs"))
        val events = Bedtime.all().single().getJSONArray("events")
        assertEquals("pause", events.getJSONObject(events.length() - 1).getString("action"))
    }

    @Test fun aChapterTransitionDoesNotReadTheManifestOnTheCaller() {
        assertTrue("keepScript read book.json on the main looper",
            returnsWhileDiskIsBusy { Streaming.keepScript(context, "io-book", 1L) })
    }
}
