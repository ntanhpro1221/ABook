package vn.abook.player

import android.os.Handler
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import vn.abook.player.ui.nowplaying.SleepText

class SleepKeepTest {
    private val voice = FakeExo()
    private lateinit var fixture: ColdStoreFixture
    private fun field(name: String) = SleepTimer::class.java.getDeclaredField(name).also { it.isAccessible = true }
    private fun reset() {
        field("mode").set(SleepTimer, SleepTimer.Mode.OFF)
        field("selectedMode").set(SleepTimer, SleepTimer.Mode.OFF)
        field("retained").setBoolean(SleepTimer, false)
        field("automaticReason").set(SleepTimer, "")
        field("stoppedAtMs").setLong(SleepTimer, 0)
        field("ticking").setBoolean(SleepTimer, false)
        SleepTimer.activityResets = true
    }
    @Before fun setup() {
        Handler.reset(); reset()
        fixture = ColdStoreFixture()
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("sleep-keep"))
        Playback::class.java.getDeclaredField("appContext").also { it.isAccessible = true }.set(Playback, fixture.context)
        Motion::class.java.getDeclaredField("running").also { it.isAccessible = true }.setBoolean(Motion, true)
        Playback.player = voice.player
        Playback::class.java.getDeclaredField("bookId").also { it.isAccessible = true }.set(Playback, "sleep-book")
        Playback::class.java.getDeclaredField("recordId").also { it.isAccessible = true }.set(Playback, "reader")
        voice.playing = true
    }
    @After fun cleanup() {
        Bedtime.timerOff()
        assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
        reset(); Playback.player = null; Handler.reset(); fixture.restore()
        Motion::class.java.getDeclaredField("running").also { it.isAccessible = true }.setBoolean(Motion, false)
    }
    private fun expire() {
        field("remainingMs").setLong(SleepTimer, 0)
        field("runningSinceMs").setLong(SleepTimer, 0)
        voice.playing = true
        SleepTimer.onPlaying(true)
        Handler.advance(0)
    }
    @Test fun expiryRetainsTheSelectionAndTheNextPlaybackCountsAgain() {
        SleepTimer.setMinutes(1)
        expire()
        assertFalse(voice.playWhenReady)
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals(60.0, SleepTimer.describe().getDouble("remaining"), 0.01)
        assertTrue(SleepTimer.describe().getDouble("stoppedAt") > 0)
        voice.playing = true
        SleepTimer.onPlaying(true)
        assertTrue(SleepTimer.describe().getBoolean("counting"))
        expire()
        assertEquals(60.0, SleepTimer.describe().getDouble("remaining"), 0.01)
        SleepTimer.cancel()
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
    }
    @Test fun processRecreationRestoresAFullPausedCycleEvenTheNextDay() {
        SleepTimer.setMinutes(10)
        SleepTimer.persist()
        assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
        reset()
        ListenPrefs.load(System.currentTimeMillis() + 24 * 3_600_000L)
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals(600.0, SleepTimer.describe().getDouble("remaining"), 0.01)
        assertFalse(SleepTimer.describe().getBoolean("counting"))
    }
    @Test fun explicitExtensionOfAParkedChapterTimerOnlyChangesThisCycle() {
        SleepTimer.setEndOfChapter(1)
        SleepTimer.onPausedAtChapterEnd()
        SleepTimer.extend(feedback = false)
        SleepTimer.onUserActivity("play")
        voice.playing = true
        SleepTimer.onPlaying(true)
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        expire()
        assertEquals(SleepTimer.Mode.CHAPTER, SleepTimer.mode)
        assertEquals(1, SleepTimer.chapters)
    }
    @Test fun everyDeliberateSourceResetsTheFullCycleAndRestoresVolume() {
        for (source in listOf("resume", "touch", "screen-on", "screen-off", "unlock", "media-button", "widget", "auto", "bluetooth", "shake")) {
            SleepTimer.setMinutes(10)
            field("remainingMs").setLong(SleepTimer, 240_000)
            field("runningSinceMs").setLong(SleepTimer, 0)
            Playback.applyVolume(0.1f)
            SleepTimer.onUserActivity(source)
            assertEquals(source, 600.0, SleepTimer.describe().getDouble("remaining"), 1.0)
            assertEquals(1f, voice.volume, 0.001f)
        }
    }
    @Test fun disablingActivityResetKeepsTheCurrentCountdown() {
        SleepTimer.setMinutes(10)
        SleepTimer.activityResets = false
        field("remainingMs").setLong(SleepTimer, 240_000)
        field("runningSinceMs").setLong(SleepTimer, 0)
        SleepTimer.onUserActivity("touch")
        assertEquals(240.0, SleepTimer.describe().getDouble("remaining"), 0.01)
    }
    @Test fun screenTimeoutIsNotDeliberateButAnEarlyPowerPressIs() {
        assertTrue(ListenerActivity.isDeliberateScreenOff(15_000, 10_000, 30_000))
        assertFalse(ListenerActivity.isDeliberateScreenOff(40_000, 10_000, 30_000))
    }
    @Test fun chapterPicksAndMinutePicksDoNotFabricateAnEnd() {
        for (count in listOf(2, 1, 2, 3, 2, 1, 2)) {
            SleepTimer.setEndOfChapter(count)
            assertEquals(count, SleepTimer.chapters)
            assertEquals(0.0, SleepTimer.describe().optDouble("stoppedAt", 0.0), 0.0)
        }
        SleepTimer.setEndOfChapter(2)
        SleepTimer.onChapterChanged()
        assertEquals(1, SleepTimer.chapters)
        SleepTimer.onPausedAtChapterEnd()
        assertEquals(SleepTimer.Mode.CHAPTER, SleepTimer.mode)
        assertEquals(2, SleepTimer.chapters)
        SleepTimer.onPlaying(true)
        SleepTimer.onChapterChanged()
        assertEquals(1, SleepTimer.chapters)
        for (count in listOf(2, 1, 2, 1, 2)) {
            SleepTimer.setMinutes(count)
            assertEquals(count, SleepTimer.describe().getInt("minutes"))
        }
        assertEquals("Đang tạm dừng - đồng hồ cũng dừng.", SleepText.pausedNote)
    }
}
