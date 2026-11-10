package vn.abook.player

import android.os.Looper
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.ParameterizedRobolectricTestRunner
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode
import org.robolectric.annotation.LooperMode
import java.io.File
import java.time.Duration

/**
 * Real Playback clock -> MusicBed chapter selection. MusicBed reads the owner's music from the book's own `book.json` (Store.playableManifest)
 * and the mix constants from the packaged asset (MusicBed.init); only the codec players are [FakeExo]. Playback's ExoPlayer listener lives
 * inside PlaybackService.onCreate, so [voicePlaying]/[arrive] forward the same two events it forwards.
 *
 * Shared-JVM note: Conscrypt is off because these codec doubles need no TLS. Turning it on here once made two FastConnectTest cases fail
 * depending on suite order, so some TLS-provider state leaks across Robolectric suites (separate task, not fixed here).
 */
internal class ChapterMusicRig(music: Map<Int, JSONArray>) {
    val voice = FakeExo()
    val made = mutableListOf<FakeExo>()
    val root: File = BookEditsFixtures.tempDir("chapter-music")

    init {
        BookEditsFixtures.useStoreRoot(root)
        val dir = File(root, "books/matrix/music").also { it.mkdirs() }
        for (name in listOf("a", "b")) File(dir, "${name.repeat(40)}.mp3").writeBytes(byteArrayOf(1))
        writeMusic(music)
        MusicBed.init(RuntimeEnvironment.getApplication()) // mix constants from the packaged music_mix.json asset
        MusicBed.sync("", null, 0.0, false, stopNow = true) // no book yet: the first voice sync reads book.json like a fresh process
        MusicBed.testPlayerFactory = { FakeExo().also { it.duration = 200_000; it.notifyReady = true; made += it }.player }
        Playback.player = voice.player
        playbackField("appContext").set(Playback, RuntimeEnvironment.getApplication())
        playbackField("bookId").set(Playback, "matrix")
        playbackField("chapters").set(Playback, (1..3).map { Playback.Chapter(it, "Chapter $it", "$it.mp3", 100.0) })
        voice.items = (1..3).map { MediaItem.Builder().setMediaId("$it").build() }
        voice.playWhenReady = true; voice.duration = 100_000
        voicePlaying(true)
        advance(2500)
    }

    /** Quiet chapters have no manifest entry, as in the reported regression. */
    fun writeMusic(music: Map<Int, JSONArray>) {
        val chapters = JSONObject().also { out -> music.forEach { (id, cues) -> out.put("$id", cues) } }
        val tracks = JSONObject().put(track("a")!!, JSONObject()).put(track("b")!!, JSONObject())
        File(root, "books/matrix/book.json").writeText(JSONObject().put("id", "matrix").put("title", "Matrix")
            .put("music", JSONObject().put("tracks", tracks).put("chapters", chapters)).toString())
    }

    fun advance(ms: Long) = shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(ms))
    /** PlaybackService: onIsPlayingChanged -> Playback.onPlayingChanged. */
    fun voicePlaying(playing: Boolean) { voice.playing = playing; Playback.onPlayingChanged(playing) }
    /** PlaybackService: onMediaItemTransition -> Playback.onMediaTransition(manual = reason SEEK). */
    fun arrive(manual: Boolean) = Playback.onMediaTransition(voice.items[voice.index], manual)
    fun sounding() = made.filter { it.playing && it.volume > 0 }
    fun silent() = made.none { it.playing || it.playWhenReady }

    fun close() {
        MusicBed.stop(); MusicBed.testPlayerFactory = null
        MusicBed::class.java.getDeclaredField("context").also { it.isAccessible = true }.set(MusicBed, null)
        Playback.player = null
        playbackField("isPlaying").setBoolean(Playback, false)
        playbackField("ticking").setBoolean(Playback, false)
        playbackField("bookId").set(Playback, "")
        playbackField("chapters").set(Playback, emptyList<Playback.Chapter>())
        root.deleteRecursively()
    }

    companion object {
        fun track(name: String): String? = name.takeIf { it.isNotEmpty() }?.let { "music/${it.repeat(40)}.mp3" }
        fun cues(name: String, start: Int = 0): JSONArray = JSONArray().also {
            if (name.isNotEmpty()) it.put(JSONObject().put("start", start).put("end", 90).put("track", track(name)))
        }
        private fun playbackField(name: String) = Playback::class.java.getDeclaredField(name).also { it.isAccessible = true }
    }
}

/**
 * Same mode names on all three players (Qt MusicTests::chapterMusicMatrix, web chapterMusic.dom.test.tsx):
 * continuous = the voice runs into the next chapter; manual = next(); jump = jumpTo(n, 0); seek = jumpTo(n, 40), then seek inside the
 * chapter past the cue end and back across it; resume = pause, next(), play; buffering = jumpTo(n, 0) while the voice stalls (Android cues
 * are local, so there is no cue answer to hold). The step into chapter 3 repeats the cell's mode.
 */
@RunWith(ParameterizedRobolectricTestRunner::class)
@Config(sdk = [35])
@ConscryptMode(ConscryptMode.Mode.OFF)
@LooperMode(LooperMode.Mode.PAUSED)
class ChapterMusicTest(private val from: String, private val to: String, private val mode: String) {
    companion object {
        @JvmStatic @ParameterizedRobolectricTestRunner.Parameters(name = "{0}->{1}/{2}")
        fun cases(): List<Array<String>> = listOf("" to "", "" to "a", "a" to "", "a" to "b", "a" to "a").flatMap { (from, to) ->
            listOf("continuous", "manual", "jump", "seek", "resume", "buffering").map { arrayOf(from, to, it) }
        }
    }
    private lateinit var rig: ChapterMusicRig
    private fun track(name: String) = ChapterMusicRig.track(name)

    @Before fun setup() {
        rig = ChapterMusicRig(buildMap {
            if (from.isNotEmpty()) put(1, ChapterMusicRig.cues(from))
            if (to.isNotEmpty()) put(2, ChapterMusicRig.cues(to))
            put(3, ChapterMusicRig.cues("a"))
        })
    }
    @After fun cleanup() = rig.close()

    /** Move to chapter `target` (2 or 3) the way this cell's mode does. */
    private fun go(target: Int) = with(rig) {
        when (mode) {
            "continuous" -> { voice.index = target - 1; voice.position = 0; arrive(false) }
            "manual" -> { Playback.next(); arrive(true) }
            "jump", "seek" -> { Playback.jumpTo(target, if (mode == "seek") 40.0 else 0.0); arrive(true) }
            "resume" -> {
                Playback.pause(); voicePlaying(false)
                Playback.next(); arrive(true)
                advance(3000)
                assertTrue("paused voice keeps the music paused", silent())
                Playback.play(); voicePlaying(true)
            }
            "buffering" -> {
                Playback.jumpTo(target, 0.0); arrive(true)
                voice.state = Player.STATE_BUFFERING; voicePlaying(false); Playback.onWantsChanged()
            }
        }
        advance(3000)
        if (mode == "seek") {
            assertEquals(40_000L, voice.position)
            Playback.seekTo(95.0) // past the cue end inside the chapter
            advance(3000)
            assertNull(MusicBed.activeTrack)
            Playback.seekTo(40.0) // back across the cue edge
            advance(3000)
        }
        // The voice moves on once the stream has data; a voice standing still past voiceStallMs is a real stall and hushes the music.
        if (mode == "buffering") { voice.state = Player.STATE_READY; voice.position += 1_000; voicePlaying(true); advance(3000) }
    }

    @Test fun chapterTransitionKeepsTheMusicClockAlive() = with(rig) {
        assertEquals(track(from), MusicBed.activeTrack)
        voice.position = 20_000
        advance(500)
        made.forEach { it.position = 55_000 } // a reused old player would still stand here
        go(2)
        assertEquals(2, Playback.currentChapter?.id)
        assertEquals(track(to), MusicBed.activeTrack)
        assertEquals(if (to.isEmpty()) 0 else 1, sounding().size)
        if (to.isNotEmpty()) assertEquals(if (mode == "seek") 40_000L else 0L, sounding().single().position)
        // A quiet middle chapter must not disable the voice clock for chapter three.
        go(3)
        assertEquals(3, Playback.currentChapter?.id)
        assertEquals(track("a"), MusicBed.activeTrack)
        assertEquals(1, sounding().size)
        assertEquals(if (mode == "seek") 40_000L else 0L, sounding().single().position)
    }
}

/** Cells a listener meets that the from/to matrix does not: changing chapter mid-fade, a cue that starts late in the chapter, a late answer while paused, rate change mid-fade. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
@ConscryptMode(ConscryptMode.Mode.OFF)
@LooperMode(LooperMode.Mode.PAUSED)
class ChapterMusicEdgeTest {
    private var rig: ChapterMusicRig? = null
    private fun rig(music: Map<Int, JSONArray>) = ChapterMusicRig(music).also { rig = it }
    @After fun cleanup() { rig?.close() }

    @Test fun nextThenPreviousInsideTheFadeLeavesOneTrackAndReleasesTheRest() = with(rig(mapOf(1 to ChapterMusicRig.cues("a"), 2 to ChapterMusicRig.cues("b")))) {
        assertEquals(ChapterMusicRig.track("a"), MusicBed.activeTrack)
        Playback.next(); arrive(true)
        advance(1000) // a -> b crossfade is half way (fadeSeconds = 2)
        Playback.previous(); arrive(true)
        assertEquals(1, Playback.currentChapter?.id)
        advance(3000)
        assertEquals(ChapterMusicRig.track("a"), MusicBed.activeTrack)
        val live = sounding()
        assertEquals(1, live.size)
        assertTrue("every other music player is released", made.filter { it !== live.single() }.all { it.released })
    }

    @Test fun cueStartingAtThirtySecondsComesInOnTheVoiceClock() = with(rig(mapOf(2 to ChapterMusicRig.cues("a", start = 30)))) {
        assertNull(MusicBed.activeTrack)
        voice.index = 1; voice.position = 0; arrive(false)
        advance(3000)
        assertNull(MusicBed.activeTrack)
        assertTrue(silent())
        voice.position = 31_000 // no event: only the ticker can notice the cue
        advance(3000)
        assertEquals(ChapterMusicRig.track("a"), MusicBed.activeTrack)
        assertEquals(1, sounding().size)
        assertEquals(1_000L, sounding().single().position)
    }

    @Test fun lateMusicWhilePausedInTheNextChapterStaysSilentUntilPlay() = with(rig(mapOf(1 to ChapterMusicRig.cues("a")))) {
        assertEquals(ChapterMusicRig.track("a"), MusicBed.activeTrack)
        Playback.pause(); voicePlaying(false)
        Playback.next(); arrive(true)
        advance(3000)
        // Android cues are local: the late answer is the book's music arriving for chapter 2 (sync/edit) while paused.
        writeMusic(mapOf(1 to ChapterMusicRig.cues("a"), 2 to ChapterMusicRig.cues("b")))
        MusicBed.invalidate("matrix")
        Playback.onWantsChanged()
        advance(3000)
        assertTrue("checked after the late answer: still silent", silent())
        assertNotEquals(ChapterMusicRig.track("a"), MusicBed.activeTrack)
        Playback.play(); voicePlaying(true)
        advance(3000)
        assertEquals(ChapterMusicRig.track("b"), MusicBed.activeTrack)
        assertEquals(1, sounding().size)
    }

    @Test fun pausedInAQuietChapterThenNextStaysSilentUntilPlay() = with(rig(mapOf(1 to ChapterMusicRig.cues("a"), 3 to ChapterMusicRig.cues("b")))) {
        // The quiet chapter is reached while playing; only the pause inside it tells the bed the voice stopped.
        Playback.jumpTo(2, 0.0); arrive(true)
        advance(3000)
        assertNull(MusicBed.activeTrack)
        Playback.pause(); voicePlaying(false)
        Playback.next(); arrive(true)
        advance(3000)
        assertEquals(3, Playback.currentChapter?.id)
        assertTrue(silent())
        Playback.play(); voicePlaying(true)
        advance(3000)
        assertEquals(ChapterMusicRig.track("b"), MusicBed.activeTrack)
        assertEquals(1, sounding().size)
    }

    @Test fun rateChangeInsideTheFadeKeepsOneTrack() = with(rig(mapOf(1 to ChapterMusicRig.cues("a"), 2 to ChapterMusicRig.cues("b")))) {
        Playback.next(); arrive(true)
        advance(1000)
        Playback.setRate(1.5)
        advance(3000)
        assertEquals(ChapterMusicRig.track("b"), MusicBed.activeTrack)
        assertEquals(1, sounding().size)
    }
}
