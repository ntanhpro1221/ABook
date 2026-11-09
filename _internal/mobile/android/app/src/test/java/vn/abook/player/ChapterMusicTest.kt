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
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.ConscryptMode
import org.robolectric.annotation.LooperMode
import java.io.File
import java.time.Duration

/** Full Playback clock -> MusicBed chapter selection; only the codec players are doubles. */
@RunWith(ParameterizedRobolectricTestRunner::class)
@Config(sdk = [35])
@ConscryptMode(ConscryptMode.Mode.OFF) // This codec-double test needs no TLS provider changes in the shared JVM.
@LooperMode(LooperMode.Mode.PAUSED)
class ChapterMusicTest(private val from: String, private val to: String, private val mode: String) {
    companion object {
        @JvmStatic @ParameterizedRobolectricTestRunner.Parameters(name = "{0}->{1}/{2}")
        fun cases(): List<Array<String>> = listOf("" to "", "" to "a", "a" to "", "a" to "b", "a" to "a").flatMap { (from, to) ->
            listOf("continuous", "manual", "seek", "resume", "buffering").map { arrayOf(from, to, it) }
        }
    }
    private val voice = FakeExo()
    private val made = mutableListOf<FakeExo>()
    private lateinit var root: File
    private fun bedField(name: String) = MusicBed::class.java.getDeclaredField(name).also { it.isAccessible = true }
    private fun playbackField(name: String) = Playback::class.java.getDeclaredField(name).also { it.isAccessible = true }
    private fun advance(ms: Long) = shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(ms))
    private fun track(name: String): String? = name.takeIf { it.isNotEmpty() }?.let { "music/${it.repeat(40)}.mp3" }
    private fun cues(name: String): JSONArray = JSONArray().also {
        if (name.isNotEmpty()) it.put(JSONObject().put("start", 0).put("end", 90).put("track", track(name)))
    }
    @Before fun setup() {
        root = BookEditsFixtures.tempDir("chapter-music")
        BookEditsFixtures.useStoreRoot(root)
        val dir = File(root, "books/matrix/music").also { it.mkdirs() }
        for (name in listOf("a", "b")) File(dir, "${name.repeat(40)}.mp3").writeBytes(byteArrayOf(1))
        MusicBed.stop()
        bedField("context").set(MusicBed, RuntimeEnvironment.getApplication())
        bedField("closedBook").set(MusicBed, "")
        bedField("book").set(MusicBed, "matrix")
        val chapterMusic = JSONObject().put("3", cues("a"))
        if (from.isNotEmpty()) chapterMusic.put("1", cues(from))
        if (to.isNotEmpty()) chapterMusic.put("2", cues(to))
        bedField("music").set(MusicBed, JSONObject().put("tracks", JSONObject().put(track("a")!!, JSONObject()).put(track("b")!!, JSONObject()))
            .put("chapters", chapterMusic)) // quiet chapters have no manifest entry, as in the reported regression
        bedField("chapter").setInt(MusicBed, Int.MIN_VALUE)
        bedField("sceneMode").setBoolean(MusicBed, false)
        MusicCues.mix = MusicMix.parse(File("../../../abook/webui/assets/music_mix.json").readText())
        MusicBed.testPlayerFactory = { FakeExo().also { it.duration = 200_000; it.notifyReady = true; made += it }.player }
        Playback.player = voice.player
        playbackField("appContext").set(Playback, RuntimeEnvironment.getApplication())
        playbackField("bookId").set(Playback, "matrix")
        playbackField("chapters").set(Playback, (1..3).map { Playback.Chapter(it, "Chapter $it", "$it.mp3", 100.0) })
        voice.items = (1..3).map { MediaItem.Builder().setMediaId("$it").build() }
        voice.playing = true; voice.playWhenReady = true; voice.duration = 100_000
        Playback.onPlayingChanged(true)
        advance(2500)
    }
    @After fun cleanup() {
        MusicBed.stop(); MusicBed.testPlayerFactory = null
        bedField("context").set(MusicBed, null)
        Playback.player = null
        playbackField("isPlaying").setBoolean(Playback, false)
        playbackField("ticking").setBoolean(Playback, false)
        playbackField("bookId").set(Playback, "")
        playbackField("chapters").set(Playback, emptyList<Playback.Chapter>())
        root.deleteRecursively()
    }
    @Test fun chapterTransitionKeepsTheMusicClockAlive() {
        assertEquals(track(from), MusicBed.activeTrack)
        voice.position = 20_000
        advance(500)
        made.forEach { it.position = 55_000 }
        if (mode == "resume") { voice.playing = false; voice.playWhenReady = false; Playback.onPlayingChanged(false) }
        if (mode == "manual" || mode == "seek") Playback.jumpTo(2, if (mode == "seek") 40.0 else 0.0)
        else { voice.index = 1; voice.position = 0 }
        if (mode == "buffering") { voice.state = Player.STATE_BUFFERING; voice.playing = false; Playback.onPlayingChanged(false) }
        Playback.onMediaTransition(voice.items[1], mode != "continuous")
        if (mode == "resume") {
            assertTrue(made.none { it.playing || it.playWhenReady })
            voice.playing = true; voice.playWhenReady = true; Playback.onPlayingChanged(true)
        }
        advance(3000)
        assertEquals(track(to), MusicBed.activeTrack)
        assertEquals(if (to.isEmpty()) 0 else 1, made.count { it.playing && it.volume > 0 })
        if (to.isNotEmpty()) assertEquals(if (mode == "seek") 40_000L else 0L, made.last().position)
        // A quiet middle chapter must not disable the voice clock for chapter three.
        voice.index = 2; voice.position = 0
        Playback.onMediaTransition(voice.items[2])
        advance(3000)
        assertEquals(track("a"), MusicBed.activeTrack)
        assertEquals(1, made.count { it.playing && it.volume > 0 })
    }
}
