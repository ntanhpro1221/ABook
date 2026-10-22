package vn.abook.player

import android.os.Handler
import androidx.media3.common.Player
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.io.File
import java.lang.reflect.Proxy

/** Exercise MusicBed's real scheduled fade and release with a delayed ExoPlayer double.
 * Reflection installs the private Bed, avoiding codecs, network and production test hooks. */
class MusicBedIntegrationTest {
    private class FakePlayer {
        var state = Player.STATE_IDLE
        var volume = 0f
        var playing = true
        var released = 0
        var buffered = ByteArray(8192)
        var position = 10_000L
        var seeks = 0
        var item: MediaItem? = null
        val listeners = mutableListOf<Player.Listener>()
        val player: ExoPlayer = Proxy.newProxyInstance(ExoPlayer::class.java.classLoader, arrayOf(ExoPlayer::class.java)) { proxy, method, args ->
            when (method.name) {
                "prepare" -> { state = Player.STATE_BUFFERING; null }
                "getPlaybackState" -> state
                "getVolume" -> volume
                "setVolume" -> { volume = args!![0] as Float; null }
                "getDuration" -> 200_000L
                "getCurrentPosition" -> position
                "getCurrentMediaItem" -> item
                "seekTo" -> { seeks++; position = args!!.last() as Long; null }
                "isPlaying" -> playing
                "play" -> { playing = true; null }
                "pause" -> { playing = false; null }
                "addListener" -> { listeners.add(args!![0] as Player.Listener); null }
                "removeListener" -> { listeners.remove(args!![0] as Player.Listener); null }
                "release" -> { check(listeners.isEmpty()) { "listeners must be removed before release" }; released++; buffered = byteArrayOf(); null }
                "equals" -> args!![0] === proxy
                "hashCode" -> System.identityHashCode(this)
                "toString" -> "FakeMusicPlayer"
                else -> when (method.returnType) {
                    java.lang.Boolean.TYPE -> false
                    java.lang.Integer.TYPE -> 0
                    java.lang.Long.TYPE -> 0L
                    java.lang.Float.TYPE -> 0f
                    else -> null
                }
            }
        } as ExoPlayer
    }

    private fun field(name: String) = MusicBed::class.java.getDeclaredField(name).also { it.isAccessible = true }
    private fun invoke(name: String) = MusicBed::class.java.getDeclaredMethod(name).also { it.isAccessible = true }.invoke(MusicBed)
    private fun bed(fake: FakePlayer, cue: MusicCues.Cue? = null): Any {
        val type = Class.forName("vn.abook.player.MusicBed\$Bed")
        return type.declaredConstructors.single().also { it.isAccessible = true }
            .newInstance("music/a.mp3", fake.player, 0.1f, 0.0025f, cue, 2000L)
    }

    @Before fun setup() {
        Handler.reset()
        MusicCues.mix = MusicMix.parse(File("../../../abook/webui/assets/music_mix.json").readText())
        MusicBed.stop()
        field("fadingTicker").setBoolean(MusicBed, false)
    }
    @After fun cleanup() { field("context").set(MusicBed, null); MusicBed.stop(); Playback.player = null; Handler.reset() }

    @Test fun prepareLongerThanFadeStillFadesFromSilenceToTheGoal() {
        val fake = FakePlayer()
        fake.player.prepare()
        val current = bed(fake)
        field("current").set(MusicBed, current)
        invoke("startFade")
        Handler.advance(10_000) // 5x the fade duration, still preparing
        assertEquals(0f, fake.volume, 0f)
        assertTrue(current.javaClass.getDeclaredField("entering").also { it.isAccessible = true }.getBoolean(current))
        fake.state = Player.STATE_READY
        Handler.advance(50)
        assertEquals("first audible tick must not jump", 0.0025f, fake.volume, 1e-6f)
        Handler.advance(950)
        assertEquals(0.05f, fake.volume, 1e-5f)
        Handler.advance(1000)
        assertEquals("must not get stuck at zero", 0.1f, fake.volume, 1e-6f)
        assertFalse(current.javaClass.getDeclaredField("entering").also { it.isAccessible = true }.getBoolean(current))
    }

    @Test fun closingReleasesCurrentAndFadingPlayersAndTheirBuffers() {
        val players = listOf(FakePlayer(), FakePlayer())
        val beds = players.map { bed(it) }
        val listener = object : Player.Listener {}
        for ((index, current) in beds.withIndex()) {
            @Suppress("UNCHECKED_CAST")
            val registered = current.javaClass.getDeclaredField("listeners").also { it.isAccessible = true }.get(current) as MutableList<Player.Listener>
            registered.add(listener)
            players[index].player.addListener(listener)
        }
        field("book").set(MusicBed, "closed-book")
        field("current").set(MusicBed, beds[0])
        @Suppress("UNCHECKED_CAST")
        (field("fading").get(MusicBed) as MutableList<Any>).add(beds[1])
        invoke("startFade")
        // PlayerPlugin.release (the close button) calls this lifecycle entry.
        MusicBed.release()
        assertNull(MusicBed.activeTrack)
        assertEquals("closed-book", field("closedBook").get(MusicBed))
        for (fake in players) { assertEquals(1, fake.released); assertEquals(0, fake.buffered.size); assertTrue(fake.listeners.isEmpty()) }
        Handler.advance(10_000) // queued fade must not revive or release the players twice
        assertEquals(listOf(1, 1), players.map { it.released })
        assertTrue((field("fading").get(MusicBed) as List<*>).isEmpty())
    }

    @Test fun smallSeeksThroughPlaybackDoNotSeekTheMusicOrRestartItsFade() {
        val voice = FakePlayer().also { it.state = Player.STATE_READY; it.item = MediaItem.Builder().setMediaId("1").build() }
        val music = FakePlayer().also { it.state = Player.STATE_READY; it.volume = 0.1f; it.position = 50_000 }
        val cue = MusicCues.Cue(0.0, 100.0, "music/a.mp3", -20.0)
        field("book").set(MusicBed, "seek-book")
        field("closedBook").set(MusicBed, "")
        field("chapter").setInt(MusicBed, 1)
        field("cues").set(MusicBed, listOf(cue))
        field("lastSeconds").setDouble(MusicBed, 10.0)
        val current = bed(music, cue)
        current.javaClass.getDeclaredField("entering").also { it.isAccessible = true }.setBoolean(current, false)
        field("current").set(MusicBed, current)
        // Context is only a presence check on this already-open, already-cached path.
        val unsafeClass = Class.forName("sun.misc.Unsafe")
        val unsafe = unsafeClass.getDeclaredField("theUnsafe").also { it.isAccessible = true }.get(null)
        field("context").set(MusicBed, unsafeClass.getMethod("allocateInstance", Class::class.java).invoke(unsafe, android.content.ContextWrapper::class.java))
        Playback.player = voice.player
        Playback::class.java.getDeclaredField("bookId").also { it.isAccessible = true }.set(Playback, "seek-book")
        Playback::class.java.getDeclaredField("chapters").also { it.isAccessible = true }.set(Playback, listOf(Playback.Chapter(1, "Chapter", "1.mp3", 100.0)))
        val sync = Playback::class.java.getDeclaredMethod("syncMusic", Boolean::class.javaPrimitiveType).also { it.isAccessible = true }
        for (seconds in listOf(13.0, 10.0, 10.5)) {
            Playback.seekTo(seconds)
            sync.invoke(Playback, true) // same callback used by Playback's voice ticker
            assertEquals(0, music.seeks)
            assertEquals(50_000L, music.position)
            assertEquals(0.1f, music.volume, 1e-6f)
            assertEquals(0, music.released)
        }
        Playback.seekTo(15.0) // positive control: > 3 s must realign the music
        sync.invoke(Playback, true)
        assertEquals(1, music.seeks)
        assertEquals(15_000L, music.position)
    }
}
