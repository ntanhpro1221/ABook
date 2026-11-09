package vn.abook.player

import android.content.Context
import android.os.Handler
import android.view.View
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class FeedbackTest {
    private val original = Feedback.output
    private val calls = mutableListOf<String>()
    private val voice = FakeExo()
    private fun field(name: String) = SleepTimer::class.java.getDeclaredField(name).apply { isAccessible = true }

    @Before fun setup() {
        Handler.reset()
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("feedback"))
        Playback.player = voice.player
        Feedback.sounds = true; Feedback.haptics = true
        Feedback.output = object : Feedback.Output {
            override fun sound(notes: List<Feedback.Note>, context: Context?) { calls += "sound:${notes.map { it.pitch }}" }
            override fun haptic(effect: String, view: View?, context: Context?) { calls += "haptic:$effect" }
        }
        field("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        field("minutes").setInt(SleepTimer, 10)
        field("remainingMs").setLong(SleepTimer, 120_000L)
        field("runningSinceMs").setLong(SleepTimer, 0L)
        field("automaticReason").set(SleepTimer, "")
        field("warned").setBoolean(SleepTimer, false)
        field("ticking").setBoolean(SleepTimer, false)
        SleepTimer.shakeEnabled = true
    }

    @After fun cleanup() {
        Feedback.output = original
        Feedback.sounds = true; Feedback.haptics = true
        Playback.player = null
        field("mode").set(SleepTimer, SleepTimer.Mode.OFF)
        field("warned").setBoolean(SleepTimer, false)
        Handler.reset()
    }

    @Test fun shakeDispatchesOneSoundAndOneMatchingHapticBeforeReturningWhilePlaying() {
        voice.playing = true
        SleepTimer.onShake()
        assertEquals(listOf("sound:[1046.5, 1318.5]", "haptic:CONFIRM"), calls)
        assertEquals(600.0, SleepTimer.describe().getDouble("remaining"), 1.0)
    }

    @Test fun buttonAndShakeUseExactlyTheSameFeedbackWithoutDoubling() {
        SleepTimer.extend()
        val button = calls.toList(); calls.clear()
        SleepTimer.onShake()
        assertEquals(button, calls)
        assertEquals(2, calls.size)
    }

    @Test fun disabledShakeAndOffTimerDoNotProduceFeedback() {
        SleepTimer.shakeEnabled = false; SleepTimer.onShake()
        SleepTimer.shakeEnabled = true
        field("mode").set(SleepTimer, SleepTimer.Mode.OFF)
        field("stoppedAtMs").setLong(SleepTimer, 0L)
        SleepTimer.onShake(); SleepTimer.extend()
        assertTrue(calls.isEmpty())
    }

    @Test fun switchesAreIndependentAndApplyEvenWithoutAnActivity() {
        ListenPrefs.apply(JSONObject().put("touchSounds", false), startup = true)
        SleepTimer.onShake()
        assertEquals(listOf("haptic:CONFIRM"), calls); calls.clear()
        ListenPrefs.apply(JSONObject().put("touchSounds", true).put("haptics", false), startup = true)
        SleepTimer.onShake()
        assertEquals(listOf("sound:[1046.5, 1318.5]"), calls); calls.clear()
        ListenPrefs.apply(JSONObject().put("touchSounds", false).put("haptics", false), startup = true)
        SleepTimer.onShake(); SleepTimer.warning(20_000L)
        assertTrue(calls.isEmpty())
    }

    @Test fun savedSoundSwitchSurvivesAColdPreferenceLoad() {
        ListenPrefs.apply(JSONObject().put("touchSounds", false).put("haptics", false))
        Feedback.sounds = true; Feedback.haptics = true
        ListenPrefs.load()
        SleepTimer.onShake()
        assertTrue(calls.isEmpty())
    }

    @Test fun ordinaryHapticsRemainSilentDuringPlaybackButWarningAndExtensionAreAudible() {
        voice.playing = true
        listOf("tap", "playPause", "longPress", "reject", "tick", "toggle", "confirm", "done").forEach { Feedback.play(it) }
        assertTrue(calls.none { it.startsWith("sound:") }); calls.clear()
        Feedback.play("sleepWarn"); Feedback.play("sleepExtend")
        assertEquals(listOf("sound:[220.0]", "sound:[1046.5, 1318.5]", "haptic:CONFIRM"), calls)
    }

    @Test fun warningIsOnceAtThirtySecondsAndNotRepeatedThroughoutFadeOrAtExpiry() {
        SleepTimer.warning(31_000L); SleepTimer.warning(30_000L)
        SleepTimer.warning(25_000L); SleepTimer.warning(1L); SleepTimer.warning(0L)
        Feedback.play("sleepExpired")
        assertEquals(listOf("sound:[220.0]"), calls)
        SleepTimer.extend(); calls.clear()
        SleepTimer.warning(30_000L)
        assertEquals(listOf("sound:[220.0]"), calls)
    }

    @Test fun soundFailureDoesNotPreventHapticOrResettingTheTimer() {
        Feedback.output = object : Feedback.Output {
            override fun sound(notes: List<Feedback.Note>, context: Context?) { error("output unavailable") }
            override fun haptic(effect: String, view: View?, context: Context?) { calls += effect }
        }
        SleepTimer.onShake()
        assertEquals(listOf("CONFIRM"), calls)
        assertEquals(600.0, SleepTimer.describe().getDouble("remaining"), 1.0)
    }

    @Test fun realTimerTickWarnsOnceAndFinishesWithoutSoundOrVibration() {
        voice.playing = true
        field("remainingMs").setLong(SleepTimer, 25_000L)
        SleepTimer::class.java.getDeclaredMethod("tick").apply { isAccessible = true }.invoke(SleepTimer)
        Handler.advance(500L)
        assertEquals(listOf("sound:[220.0]"), calls)
        assertTrue(Playback.fadeLevel < 1f)
        field("remainingMs").setLong(SleepTimer, 0L)
        Handler.advance(250L)
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
        assertFalse(voice.playing)
        assertEquals(listOf("sound:[220.0]"), calls)
    }

    @Test fun generatedNotesAreShortQuietAndHaveNoHardOnset() {
        assertEquals(Feedback.notes("confirm"), Feedback.notes("sleepExtend"))
        for (kind in listOf("toggle", "tick", "confirm", "done", "sleepExtend", "sleepWarn")) {
            val pcm = Feedback.pcm(Feedback.notes(kind))
            assertTrue(pcm.size <= 12_000)
            assertEquals(0, pcm.first().toInt())
            assertTrue(pcm.maxOf { kotlin.math.abs(it.toInt()) } in 10..3500)
            assertTrue(kotlin.math.abs(pcm.last().toInt()) < 8)
        }
    }
}
