package vn.abook.player.ui.data

import vn.abook.player.formatSize

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ListenPrefs
import java.io.File

/** Tầng dữ liệu Cài đặt native: cùng khoá / giá trị / mặc định với bản WebView (android/settings.ts) và kho native (ListenPrefs). */
class SettingsDataTest {
    /** JSON so được bất kể thứ tự khoá. */
    private fun canonical(json: JSONObject): Map<String, String> = json.keys().asSequence().associateWith { json.get(it).toString() }.toSortedMap()

    private fun repo(core: FakeSettingsCore) = SettingsRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined)

    @Test
    fun `defaults are the webview defaults`() {
        val d = AppSettings.from(JSONObject())
        assertEquals(ThemeMode.System, d.theme)
        assertEquals(ReadingSurface.Auto, d.readingSurface)
        assertEquals(10, d.sleepExtendMinutes)
        assertEquals(30, d.sleepFadeSeconds)
        assertEquals(2, d.safetyStopHours)
        assertTrue(d.shakeToExtend && d.headsetSkips && d.autoRewind && d.autoMusic && d.touchSounds && d.haptics)
        assertFalse(d.flipToPause)
        assertEquals(ShakeAction.Extend, d.shakeAction)
        assertEquals(ShakeSensitivity.Normal, d.shakeSensitivity)
        assertNull(d.schedule)
        assertEquals(0L, d.stamp)
    }

    @Test
    fun `a bad field falls back alone`() {
        val raw = JSONObject().put("theme", "neon").put("sleepFadeSeconds", 45).put("safetyStopHours", 3).put("autoRewind", "yes").put("haptics", false)
            .put("schedule", JSONObject().put("from", "25:00").put("to", "06:00").put("minutes", 30)).put("readingSurface", "ivory")
        val s = AppSettings.from(raw)
        assertEquals(ThemeMode.System, s.theme)
        assertEquals(30, s.sleepFadeSeconds)
        assertEquals(3, s.safetyStopHours)
        assertTrue(s.autoRewind)
        assertFalse(s.haptics)
        assertNull(s.schedule)
        assertEquals(ReadingSurface.Ivory, s.readingSurface)
        val night = AppSettings.from(JSONObject().put("schedule", JSONObject().put("from", "22:30").put("to", "06:00").put("minutes", 45.0)))
        assertEquals(SleepSchedule("22:30", "06:00", 45), night.schedule)
    }

    @Test
    fun `changes use the native keys and values that ListenPrefs keeps unchanged`() {
        val before = AppSettings.Default
        val after = before.copy(
            theme = ThemeMode.Dark, readingSurface = ReadingSurface.Night, touchSounds = false, haptics = false, autoRewind = false, headsetSkips = false,
            safetyStopHours = 0, schedule = SleepSchedule("23:00", "05:45", 60), shakeToExtend = false, shakeAction = ShakeAction.Reset,
            shakeSensitivity = ShakeSensitivity.Firm, flipToPause = true, sleepExtendMinutes = 15, sleepFadeSeconds = 60,
        )
        val changes = after.changesFrom(before)
        assertEquals("dark", changes.getString("theme"))
        assertEquals("night", changes.getString("readingSurface"))
        assertEquals("reset", changes.getString("shakeAction"))
        assertEquals("firm", changes.getString("shakeSensitivity"))
        assertEquals("23:00", changes.getJSONObject("schedule").getString("from"))
        // ListenPrefs.clean đưa về miền giá trị: thứ Cài đặt native ghi phải đi qua nguyên vẹn (cùng khoá, cùng giá trị với bản WebView).
        assertEquals(canonical(changes), canonical(ListenPrefs.clean(changes)))
        // Đọc lại từ kho cho đúng bản vừa ghi.
        assertEquals(after, AppSettings.from(changes))
        assertEquals(0, after.changesFrom(after).length())
        assertTrue(before.changesFrom(after).isNull("schedule"))
    }

    @Test
    fun `repo shows a change at once and writes only the diff with a newer stamp`() = runBlocking {
        val core = FakeSettingsCore(JSONObject().put("settingsStamp", 5L).put("autoMusic", false))
        val repo = repo(core)
        repo.load()
        assertTrue(repo.loaded.value)
        assertFalse(repo.state.value.autoMusic)
        repo.change { it.copy(autoRewind = false) }
        assertFalse(repo.state.value.autoRewind)
        assertEquals(1, core.saved.size)
        val write = core.saved.single()
        assertEquals(setOf("autoRewind", "settingsStamp"), write.keys().asSequence().toSet())
        assertTrue(write.getLong("settingsStamp") > 5L)
        repo.change { it.copy(autoRewind = false) }
        assertEquals(1, core.saved.size)
    }

    @Test
    fun `voices group like the webview and the chosen voice survives a removed one`() = runBlocking {
        val core = FakeSettingsCore()
        val repo = repo(core)
        repo.loadVoices()
        val list = repo.voices.value as VoiceList.Ready
        assertEquals(listOf("edge", "supertonic", "device"), list.groups.map { it.provider })
        assertEquals("Hoài My", list.groups[0].voices[0].name)
        assertEquals("Tiếng Việt", list.groups[2].voices[0].name)
        assertEquals("edge:vi-VN-HoaiMyNeural", list.chosen)
        repo.chooseVoice("supertonic:F1")
        assertEquals("supertonic:F1", core.default)
        assertEquals("edge:vi-VN-HoaiMyNeural", Voices.resolve(list.groups, "vieneu:gone"))
    }

    @Test
    fun `voice speed lines say what each voice uses`() {
        val state = VoiceSpeedText.state(FakeSettingsCore().voiceSpeed())
        assertEquals(VoiceSpeedChoice.Auto, state.choice)
        assertEquals(listOf("Giọng Supertonic - Đang dùng: Chất lượng cao nhất. Bản nhanh hơn cần tải thêm 48 MB."), state.lines)
        val quality = JSONObject().put("name", "G").put("tier", "quality").put("using", "quality").put("rtf", 0.4)
        assertEquals("G - Đang dùng: Chất lượng cao nhất (máy này đọc kịp tốc độ nghe).", VoiceSpeedText.line(quality, VoiceSpeedChoice.Auto))
        assertEquals("G - Đang dùng: Chất lượng cao nhất (bạn đã chọn).", VoiceSpeedText.line(quality, VoiceSpeedChoice.Quality))
    }

    @Test
    fun `sizes read like formatSize`() {
        assertEquals("1 KB", formatSize(10))
        assertEquals("100 KB", formatSize(100L * 1024))
        assertEquals("0,5 MB", formatSize(512L * 1024))
        assertEquals("1 MB", formatSize(1024L * 1024))
        assertEquals("9,9 MB", formatSize((9.9 * 1024 * 1024).toLong()))
        assertEquals("850 MB", formatSize(850L * 1024 * 1024))
        assertEquals("1.000 MB", formatSize(1000L * 1024 * 1024))
        assertEquals("3,2 GB", formatSize((3.2 * 1024 * 1024 * 1024).toLong()))
    }

    @Test
    fun `summaries and quarters`() {
        assertEquals("Tự lùi · nhạc tự chọn", SettingsSummary.listen(AppSettings.Default))
        assertEquals("Tự tắt sau 2 giờ", SettingsSummary.sleep(AppSettings.Default))
        assertEquals("Tắt", SettingsSummary.sleep(AppSettings.Default.copy(safetyStopHours = 0)))
        assertEquals("Lịch đêm 22:00–06:00", SettingsSummary.sleep(AppSettings.Default.copy(schedule = SleepSchedule.Default)))
        assertEquals(96, Quarters.ALL.size)
        assertEquals("23:45", Quarters.ALL.last())
        assertEquals(97, Quarters.around("22:10").size)
        assertTrue(Quarters.around("22:10").indexOf("22:10") == Quarters.ALL.indexOf("22:15"))
    }

    @Test
    fun `third party list drops the maintainer notes and joins wrapped lines`() {
        val parsed = ThirdParty.parse(FakeSettingsCore().thirdPartyText)
        assertEquals(listOf("", "Phông chữ"), parsed.map { it.title })
        assertEquals(ThirdPartyItem("**Be Vietnam Pro** (OFL)", true), parsed[1].items.single())
        assertEquals("Be Vietnam Pro (OFL)", ThirdParty.plain(parsed[1].items.single().text))
        val joined = ThirdParty.parse("## A\n\nmột dòng\nnối tiếp\n")
        assertEquals("một dòng nối tiếp", joined.single().items.single().text)
        // File thật gói vào bản -PnativeUi: đọc được, có mục, không lộ mục cho người bảo trì.
        val real = ThirdParty.parse(File("../../../docs/THIRD_PARTY.md").readText())
        assertTrue(real.size > 2)
        assertTrue(real.none { it.title == ThirdParty.MAINTAINER_SECTION })
    }
}
