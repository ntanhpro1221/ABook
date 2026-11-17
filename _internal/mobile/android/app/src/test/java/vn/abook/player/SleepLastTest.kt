package vn.abook.player

import android.os.Handler
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.abook.player.ui.components.ValueSpecs
import vn.abook.player.ui.nowplaying.SleepText
import java.io.File

/**
 * Chủ sách 17-11: mốc mặc định của hẹn giờ ngủ là lần đặt cuối, không cố định 30 phút. Lõi nhớ lần hẹn người nghe tự đặt ở `listen-prefs.json`
 * (khoá `lastSleep`) và nạp lại khi tiến trình dậy ([ListenPrefs.load]) - "mở lại app" ở đây là xoá trạng thái trong bộ nhớ rồi nạp lại từ đĩa.
 */
class SleepLastTest {
    private val voice = FakeExo()
    private lateinit var fixture: ColdStoreFixture
    private lateinit var root: File
    private val table: JSONObject = JSONObject(BookEditsFixtures.file("../settings/ranges.json").readText(Charsets.UTF_8)).getJSONObject("lastSleep")
    private fun field(name: String) = SleepTimer::class.java.getDeclaredField(name).also { it.isAccessible = true }
    private fun reset() {
        field("mode").set(SleepTimer, SleepTimer.Mode.OFF)
        field("selectedMode").set(SleepTimer, SleepTimer.Mode.OFF)
        field("retained").setBoolean(SleepTimer, false)
        field("automaticReason").set(SleepTimer, "")
        field("stoppedAtMs").setLong(SleepTimer, 0)
        field("ticking").setBoolean(SleepTimer, false)
        SleepTimer.last = LastSleep()
    }

    @Before fun setup() {
        Handler.reset(); reset()
        fixture = ColdStoreFixture()
        root = BookEditsFixtures.tempDir("sleep-last")
        BookEditsFixtures.useStoreRoot(root)
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

    /** Tắt app rồi mở lại: hẹn giờ đang chạy tắt hẳn, mọi thứ trong bộ nhớ về như tiến trình mới, rồi nạp lại từ đĩa. */
    private fun reopen() {
        SleepTimer.cancel()
        assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
        reset()
        ListenPrefs.load()
    }

    @Test fun theContractMatchesTheSharedFixture() {
        fun of(json: JSONObject) = LastSleep(json.getString("kind"), json.getInt("minutes"), json.getInt("chapters"))
        assertEquals(LastSleep(), of(table.getJSONObject("default")))
        assertEquals(table.getJSONObject("minutes").getInt("max").toDouble(), ValueSpecs.sleepMinutes.max, 0.0)
        assertEquals(table.getJSONObject("chapters").getInt("max").toDouble(), ValueSpecs.sleepChapters.max, 0.0)
        val cases = table.getJSONArray("cases")
        assertTrue(cases.length() > 10)
        for (index in 0 until cases.length()) {
            val pair = cases.getJSONArray(index)
            val given = pair.get(0)
            val parsed = LastSleep.parse(given)
            if (pair.isNull(1)) assertNull("$given", parsed)
            else assertEquals("$given", of(pair.getJSONObject(1)), parsed)
        }
    }

    @Test fun neverSetMeansThirtyMinutes() {
        ListenPrefs.load()
        assertEquals(LastSleep(LastSleep.MINUTES, 30, 1), SleepTimer.last)
        assertEquals("Bật lại 30 phút", SleepText.restart(SleepTimer.last))
    }

    @Test fun fortyFiveMinutesSurvivesAReopen() {
        SleepTimer.setMinutes(45, feedback = false)
        SleepTimer.cancel() // tắt hẹn giờ không phải một lần đặt
        reopen()
        assertEquals(LastSleep(LastSleep.MINUTES, 45, 1), SleepTimer.last)
        assertEquals("Bật lại 45 phút", SleepText.restart(SleepTimer.last))
        SleepTimer.restartLast()
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals(45, SleepTimer.describe().getInt("minutes"))
    }

    @Test fun twoChaptersSurvivesAReopenAndKeepsTheLastMinutes() {
        SleepTimer.setMinutes(45, feedback = false)
        SleepTimer.setEndOfChapter(2)
        reopen()
        assertEquals(LastSleep(LastSleep.CHAPTER, 45, 2), SleepTimer.last)
        assertEquals("Bật lại hết 2 chương", SleepText.restart(SleepTimer.last))
        assertEquals("Bật lại hết chương này", SleepText.restart(LastSleep(LastSleep.CHAPTER, 45, 1)))
        SleepTimer.restartLast()
        assertEquals(SleepTimer.Mode.CHAPTER, SleepTimer.mode)
        assertEquals(2, SleepTimer.chapters)
    }

    @Test fun theNightScheduleDoesNotChangeTheLastChoice() {
        SleepTimer.setMinutes(45, feedback = false)
        SleepTimer.setMinutes(30, "schedule")
        assertEquals(45, SleepTimer.last.minutes)
    }

    @Test fun aBrokenStoredValueFallsBackToThirtyWithoutCrashing() {
        val broken = listOf("""{"kind":"minutes","minutes":999,"chapters":1}""", """{"kind":"chapter","minutes":30,"chapters":0}""",
            """{"kind":"off","minutes":30,"chapters":1}""", """{"kind":"minutes","minutes":"45","chapters":1}""", """{"kind":"minutes"}""",
            "\"45\"", "45", "[45]", "null", "true")
        for (value in broken) {
            File(root, "listen-prefs.json").writeText("""{"lastSleep":$value,"sleepExtendMinutes":15}""", Charsets.UTF_8)
            SleepTimer.last = LastSleep(LastSleep.CHAPTER, 7, 7)
            ListenPrefs.load()
            assertEquals(value, LastSleep(), SleepTimer.last)
            assertEquals("trường khác không bị ảnh hưởng", 15, SleepTimer.extendMinutes)
        }
        File(root, "listen-prefs.json").writeText("{không phải json", Charsets.UTF_8)
        SleepTimer.last = LastSleep(LastSleep.CHAPTER, 7, 7)
        ListenPrefs.load()
        assertEquals(LastSleep(), SleepTimer.last)
        SleepTimer.extendMinutes = 10
    }
}
