package vn.abook.player

import android.os.Handler
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.lang.reflect.Proxy

/**
 * Móc đo của [MusicBed] (SPEC_loop_p3w_bed.md §1): null / 0 thì không đổi hành vi, khác null thì dòng sự kiện phát đúng chỗ (open/plan/attach/pos/item/audiotrack cần ExoPlayer thật:
 * androidTest MusicBedSeamOnDeviceTest; ở đây kiểm định dạng ([SeamEvents]) và các chỗ phát được trên bản giả: demote, vol).
 */
class MusicSeamHooksTest {
    private class Fake {
        var volume = 0f
        var state = Player.STATE_READY
        val player: ExoPlayer = Proxy.newProxyInstance(ExoPlayer::class.java.classLoader, arrayOf(ExoPlayer::class.java)) { proxy, method, args ->
            when (method.name) {
                "getPlaybackState" -> state
                "getVolume" -> volume
                "setVolume" -> { volume = args!![0] as Float; null }
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

    private val events = mutableListOf<String>()
    private fun field(name: String) = MusicBed::class.java.getDeclaredField(name).also { it.isAccessible = true }
    private fun bedClass() = Class.forName("vn.abook.player.MusicBed\$Bed")
    private fun bed(fake: Fake): Any = bedClass().declaredConstructors.single().also { it.isAccessible = true }.newInstance("music/a.mp3", fake.player, 0.1f, 0.0025f, null, 2000L)
    private fun setBedField(bed: Any, name: String, value: Any?) = bedClass().getDeclaredField(name).also { it.isAccessible = true }.set(bed, value)

    private fun seam() = LoopSeam.Seam(File("a.mp3"), File("a.wav"), 10 * 1152L, 100 * 1152L, 1000 * 1152L, 40 * 1152, 48000, 2, 1152, 0, 3)

    @Before fun setup() {
        Handler.reset()
        MusicCues.mix = MusicMix.parse(File("../../../abook/webui/assets/music_mix.json").readText())
        MusicBed.stop()
        field("fadingTicker").setBoolean(MusicBed, false)
        events.clear()
    }

    @After fun cleanup() {
        MusicBed.testEvents = null
        MusicBed.testAudioProcessor = null
        MusicBed.testRenderDelayMs = 0L
        MusicBed.testPlayerSeq = 0
        field("context").set(MusicBed, null)
        MusicBed.stop()
        Handler.reset()
    }

    private fun demote(bed: Any, reason: DemoteReason) {
        val m = MusicBed::class.java.getDeclaredMethod("demote", android.content.Context::class.java, bedClass(), DemoteReason::class.java, java.lang.Boolean.TYPE)
        m.isAccessible = true
        m.invoke(MusicBed, null, bed, reason, false)
    }

    @Test fun hooksAreOffByDefault() {
        assertNull(MusicBed.testEvents)
        assertNull(MusicBed.testAudioProcessor)
        assertEquals(0L, MusicBed.testRenderDelayMs)
        assertEquals(false, MusicBed.musicSeamP3)
    }

    @Test fun formatsMatchTheSpec() {
        val s = seam()
        assertEquals("open 2 p3 music/a.mp3", SeamEvents.open(2, true, "music/a.mp3"))
        assertEquals("open 0 a87 music/a.mp3", SeamEvents.open(0, false, "music/a.mp3"))
        assertEquals("plan 1 48000 2 0.240000 2.400000 24.000000 46080", SeamEvents.plan(1, s))
        val built = SeamPicker.Built(s, MusicCues.Loop(0.24, 24.0, 20.0, true, 2.4, 24.0), 25.0, "k").also { it.buildMs = 312; it.source = "built" }
        assertEquals("attach 1 5 312 built", SeamEvents.attach(1, 5, built))
        assertEquals("demote 1 late", SeamEvents.demote(1, DemoteReason.LATE))
        assertEquals("demote 1 fail", SeamEvents.demote(1, DemoteReason.FAIL))
        assertEquals("demote 1 seek", SeamEvents.demote(1, DemoteReason.SEEK))
        assertEquals("demote 1 error", SeamEvents.demote(1, DemoteReason.ERROR))
        assertEquals("seek 0 21.500 1 seam 1000", SeamEvents.seek(0, 21.5, SeamClock.Target(1, 1000)))
        assertEquals("seek 0 0.000 0 clip0 0", SeamEvents.seek(0, 0.0, SeamClock.Target(0, 0)))
        assertEquals("seek 0 40.000 2 clip 5000", SeamEvents.seek(0, 40.0, SeamClock.Target(2, 5000)))
        assertEquals("pos 0 3.360000 3.340000", SeamEvents.pos(0, 3.36, 3.34))
        assertEquals("item 0 2 1 clip", SeamEvents.item(0, 2, 1, SeamEvents.kindOf(2)))
        assertEquals("audiotrack 0 44100 2", SeamEvents.audioTrack(0, 44100, 2))
        assertEquals("vol 3 0.002500", SeamEvents.volume(3, 0.0025f))
        assertEquals("promote 2 loop", SeamEvents.promote(2))
    }

    @Test fun demoteReasonFollowsTheGateOutcome() {
        // Các ca của SeamClock.gate: dựng hỏng -> fail; hết hạn chót khi còn dựng -> late
        assertEquals(DemoteReason.FAIL, SeamClock.demoteReason(SeamPicker.State.DEAD))
        assertEquals(SeamClock.Gate.DEMOTE, SeamClock.gate(SeamPicker.State.DEAD, false, 60_000))
        assertEquals(DemoteReason.LATE, SeamClock.demoteReason(SeamPicker.State.BUILDING))
        assertEquals(SeamClock.Gate.DEMOTE, SeamClock.gate(SeamPicker.State.BUILDING, false, SeamClock.DEADLINE_MS))
    }

    @Test fun demoteEmitsItsReasonWhenTheHookIsSet() {
        val fake = Fake()
        val b = bed(fake)
        setBedField(b, "built", SeamPicker.Built(seam(), MusicCues.Loop(0.24, 24.0, 20.0, true, 2.4, 24.0), 25.0, "k"))
        setBedField(b, "testK", 3)
        field("current").set(MusicBed, b)
        MusicBed.testEvents = { events += it }
        demote(b, DemoteReason.SEEK)
        assertEquals(listOf("demote 3 seek"), events)
        assertNull(MusicBed.activeTrack) // bài P3 đã rời khỏi `current` (a87 mở lại ở lần sync kế khi có context)
    }

    @Test fun demoteWithoutHookIsSilentButStillFallsBack() {
        val fake = Fake()
        val b = bed(fake)
        setBedField(b, "built", SeamPicker.Built(seam(), MusicCues.Loop(0.24, 24.0, 20.0, true, 2.4, 24.0), 25.0, "k"))
        field("current").set(MusicBed, b)
        demote(b, DemoteReason.LATE)
        assertTrue(events.isEmpty())
        assertNull(MusicBed.activeTrack)
    }

    @Test fun everyVolumeStepIsReportedWhenTheHookIsSetAndNotOtherwise() {
        for (hooked in listOf(false, true)) {
            events.clear()
            MusicBed.stop()
            field("fadingTicker").setBoolean(MusicBed, false)
            val fake = Fake()
            val b = bed(fake)
            setBedField(b, "testK", 7)
            field("current").set(MusicBed, b)
            MusicBed.testEvents = if (hooked) ({ events += it }) else null
            MusicBed.javaClass.getDeclaredMethod("startFade").also { it.isAccessible = true }.invoke(MusicBed)
            Handler.advance(150)
            assertTrue("âm lượng vẫn nhích như cũ", fake.volume > 0f)
            if (hooked) {
                assertTrue(events.size >= 2)
                assertTrue(events.all { it.startsWith("vol 7 ") })
                assertEquals(SeamEvents.volume(7, fake.volume), events.last())
            } else {
                assertTrue(events.isEmpty())
            }
        }
    }
}
