package vn.abook.player

import android.os.Handler
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Soát a77 #6: tuỳ chọn nghe mà Kotlin cần lúc KHỞI ĐỘNG không có giao diện (nút tai nghe, tự lùi, lắc / úp, lịch ngủ, số phút thêm, dừng an toàn) nằm ở kho native, nạp lại khi
 * tiến trình dậy; hẹn giờ ngủ đang chạy được khôi phục theo mốc kết thúc tuyệt đối nếu chưa quá.
 */
class ListenPrefsTest {
    private fun sleep(name: String) = SleepTimer::class.java.getDeclaredField(name).also { it.isAccessible = true }

    private fun defaults() {
        Playback.headsetSkips = true
        SleepTimer.extendMinutes = 10
        SleepTimer.fadeMs = 30_000L
        SleepTimer.shakeEnabled = true
        SleepTimer.shakeThresholdG = 2.2
        SleepTimer.schedule = null
        Motion.flipEnabled = false
        sleep("mode").set(SleepTimer, SleepTimer.Mode.OFF)
        sleep("automaticReason").set(SleepTimer, "")
        sleep("ownerBook").set(SleepTimer, "test-book")
        sleep("ownerRecord").set(SleepTimer, "test-record")
        sleep("remainingMs").setLong(SleepTimer, 0L)
        sleep("runningSinceMs").setLong(SleepTimer, 0L)
        sleep("minutes").setInt(SleepTimer, 0)
    }

    @Before fun setup() {
        Handler.reset()
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("listen-prefs"))
        defaults()
    }

    @After fun cleanup() {
        assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
        defaults()
        Handler.reset()
    }

    private fun chosen() = JSONObject(
        """{"headsetSkips":false,"sleepExtendMinutes":15,"sleepFadeSeconds":10,"shakeToExtend":false,
            "shakeSensitivity":"firm","flipToPause":false,"schedule":{"from":"23:00","to":"06:30","minutes":45},"readAloudVoice":"edge:x"}""",
    )

    @Test fun theChoicesSurviveTheProcessDyingBeforeTheUiPushesThemAgain() {
        ListenPrefs.apply(chosen())
        assertFalse(Playback.headsetSkips)
        assertEquals(15, SleepTimer.extendMinutes)
        defaults() // tiến trình chết, dậy lại từ tai nghe / widget / xe: chưa có giao diện
        assertTrue(Playback.headsetSkips)
        ListenPrefs.load()
        assertFalse("nút tai nghe chuyển chương vẫn là lựa chọn của bạn", Playback.headsetSkips)
        assertEquals(15, SleepTimer.extendMinutes)
        assertEquals(10_000L, SleepTimer.fadeMs)
        assertFalse(SleepTimer.shakeEnabled)
        assertEquals(2.8, SleepTimer.shakeThresholdG, 0.0)
        assertEquals(Triple(23 * 60, 6 * 60 + 30, 45), SleepTimer.schedule)
    }

    @Test fun aPartialPushKeepsTheOthersAndALaterNullScheduleClearsIt() {
        ListenPrefs.apply(chosen())
        ListenPrefs.apply(JSONObject("""{"sleepExtendMinutes":5,"readAloudVoice":"edge:y"}"""))
        defaults()
        ListenPrefs.load()
        assertEquals(5, SleepTimer.extendMinutes)
        assertFalse(Playback.headsetSkips)
        assertNotNull(SleepTimer.schedule)
        ListenPrefs.apply(JSONObject("""{"schedule":null}"""))
        defaults()
        ListenPrefs.load()
        assertNull(SleepTimer.schedule)
        assertFalse(Playback.headsetSkips)
    }

    @Test fun theInterfaceCanReadBackWhatNativeRememberedWithItsStamp() {
        assertEquals("chưa có file thì không có gì", 0, ListenPrefs.stored().length())
        ListenPrefs.apply(JSONObject("""{"headsetSkips":false,"sleepFadeSeconds":60,"schedule":null,"settingsStamp":1700000000123,"readAloudVoice":"edge:x"}"""))
        sleep("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        sleep("remainingMs").setLong(SleepTimer, 10 * 60_000L)
        SleepTimer.persist(1_000_000_000L)
        val stored = ListenPrefs.stored()
        assertEquals(false, stored.getBoolean("headsetSkips"))
        assertEquals(60, stored.getInt("sleepFadeSeconds"))
        assertEquals(1700000000123L, stored.getLong("settingsStamp"))
        assertFalse("hẹn giờ đang chạy không phải tuỳ chọn", stored.has("timer"))
        assertFalse("giọng đọc có đường riêng", stored.has("readAloudVoice"))
        ListenPrefs.apply(JSONObject("""{"headsetSkips":true,"settingsStamp":1700000000999}"""))
        assertEquals("bản sau gộp vào bản trước", 60, ListenPrefs.stored().getInt("sleepFadeSeconds"))
        assertEquals(1700000000999L, ListenPrefs.stored().getLong("settingsStamp"))
    }

    @Test fun aRunningSleepTimerComesBackUntilItsAbsoluteEnd() {
        val now = 1_000_000_000L
        sleep("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        sleep("minutes").setInt(SleepTimer, 30)
        sleep("remainingMs").setLong(SleepTimer, 30 * 60_000L)
        sleep("runningSinceMs").setLong(SleepTimer, now - 5 * 60_000L) // đang phát, đã chạy 5 phút
        SleepTimer.persist(now)
        defaults() // tiến trình chết
        ListenPrefs.load(now + 2 * 60_000L) // dậy 2 phút sau
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals("còn 30 - 5 - 2 = 23 phút", 23 * 60.0, SleepTimer.describe(now + 2 * 60_000L).getDouble("remaining"), 1.0)
        assertFalse("chưa phát nên đồng hồ chưa chạy", SleepTimer.describe(now).getBoolean("counting"))
    }

    @Test fun anExpiredTimerIsNotBroughtBack() {
        val now = 1_000_000_000L
        sleep("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        sleep("minutes").setInt(SleepTimer, 10)
        sleep("remainingMs").setLong(SleepTimer, 10 * 60_000L)
        sleep("runningSinceMs").setLong(SleepTimer, now)
        SleepTimer.persist(now)
        defaults()
        ListenPrefs.load(now + 11 * 60_000L)
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
        ListenPrefs.load(now + 1000) // đã bỏ khỏi kho, không sống lại ở lần nạp sau
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
    }

    @Test fun aPausedTimerKeepsItsRemainingTimeNotAnEndTime() {
        val now = 1_000_000_000L
        sleep("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        sleep("minutes").setInt(SleepTimer, 30)
        sleep("remainingMs").setLong(SleepTimer, 12 * 60_000L)
        sleep("runningSinceMs").setLong(SleepTimer, 0L) // đang tạm dừng: đồng hồ đứng
        SleepTimer.persist(now)
        defaults()
        ListenPrefs.load(now + 10 * 60_000L) // still within the paused timer lifetime
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals(12 * 60.0, SleepTimer.describe(now).getDouble("remaining"), 1.0)
    }

    @Test fun orderedTimerAndPreferenceWritesKeepTheNewestValues() {
        ListenPrefs.saveTimer(JSONObject().put("minutes", 30))
        ListenPrefs.apply(JSONObject().put("sleepExtendMinutes", 15))
        ListenPrefs.saveTimer(null)
        assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
        val saved = JSONObject(java.io.File(Store.root, "listen-prefs.json").readText())
        assertFalse(saved.has("timer"))
        assertEquals(15, saved.getInt("sleepExtendMinutes"))
    }

    @Test fun cancellingTheTimerForgetsItToo() {
        val now = 1_000_000_000L
        sleep("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        sleep("remainingMs").setLong(SleepTimer, 10 * 60_000L)
        SleepTimer.persist(now)
        sleep("mode").set(SleepTimer, SleepTimer.Mode.OFF)
        sleep("automaticReason").set(SleepTimer, "")
        sleep("ownerBook").set(SleepTimer, "test-book")
        sleep("ownerRecord").set(SleepTimer, "test-record")
        SleepTimer.persist(now)
        defaults()
        ListenPrefs.load(now)
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
    }
    @Test fun staleUnownedAndAutomaticSnapshotsCannotRestoreATimer() {
        val now = 1_000_000_000L
        val valid = JSONObject().put("source", "manual").put("bookId", "a").put("recordId", "r")
            .put("savedAt", now).put("minutes", 30).put("remainingMs", 600_000L)
        for (bad in listOf(
            JSONObject().put("endsAt", now + 60_000L),
            JSONObject(valid.toString()).put("source", "schedule"),
            JSONObject(valid.toString()).put("savedAt", now - 25 * 3_600_000L),
            JSONObject(valid.toString()).put("bookId", ""),
            JSONObject(valid.toString()).put("remainingMs", 31 * 60_000L),
        )) {
            defaults()
            SleepTimer.restore(bad, now)
            assertEquals(bad.toString(), SleepTimer.Mode.OFF, SleepTimer.mode)
        }
    }

    @Test fun automaticCountdownIsNeverPersistedAsAManualTimer() {
        sleep("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        sleep("automaticReason").set(SleepTimer, "schedule")
        sleep("remainingMs").setLong(SleepTimer, 60_000L)
        SleepTimer.persist(1_000_000_000L)
        defaults()
        ListenPrefs.load(1_000_000_100L)
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
    }

}
