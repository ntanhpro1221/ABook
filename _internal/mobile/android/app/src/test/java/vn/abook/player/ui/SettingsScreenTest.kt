package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.data.FakeSettingsCore
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.ThemeMode
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.screens.SettingsGroupScreen
import vn.abook.player.ui.screens.SettingsLinks
import vn.abook.player.ui.screens.SettingsScreen
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.ThemeReveal

/**
 * Màn Cài đặt native trên JVM: ảnh chụp (Roborazzi) trang gốc và từng nhóm, sáng / tối; kịch bản bấm thật - đổi tuỳ chọn ghi xuống lõi đúng khoá, chọn-một trượt
 * gạch chân, khối phụ mở / khép, bảng trượt.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class SettingsScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val sheets = SheetHost()
    private var opened: SettingsGroup? = null
    private var notifyOpened = 0
    private var shared = 0
    private var sourceOpened = 0
    private lateinit var core: FakeSettingsCore
    private lateinit var repo: SettingsRepo

    private fun env(scope: CoroutineScope) = SettingsEnv(
        repo,
        ThemeReveal(scope),
        SettingsLinks(openNotificationSettings = { notifyOpened++ }, shareLogs = { shared++ }, openSource = { sourceOpened++ }),
    )

    private fun prepare(stored: JSONObject, allowed: Boolean) {
        core = FakeSettingsCore(stored).also { it.allowed = allowed }
        repo = SettingsRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined)
        runBlocking { repo.load() }
    }

    private fun showRoot(dark: Boolean = false, stored: JSONObject = JSONObject()) {
        prepare(stored, allowed = true)
        rule.setContent {
            val scope = rememberCoroutineScope()
            val env = remember { env(scope) }
            AbookTheme(dark) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { SettingsScreen(env, onOpen = { opened = it }) }
            }
        }
        rule.waitForIdle()
    }

    private fun showGroup(group: SettingsGroup, dark: Boolean = false, stored: JSONObject = JSONObject(), allowed: Boolean = true) {
        prepare(stored, allowed)
        rule.setContent {
            val scope = rememberCoroutineScope()
            val env = remember { env(scope) }
            AbookTheme(dark) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    SettingsGroupScreen(group, env, sheets, onBack = {})
                    SheetLayer(sheets)
                }
            }
        }
        rule.waitForIdle()
    }

    private fun shot(name: String) = rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")

    // ---- trang gốc ----

    @Test
    fun rootLight() {
        showRoot()
        for (group in SettingsGroup.entries) rule.onNodeWithTag(group.tag).assertIsDisplayed()
        rule.onNodeWithText("Hoài My").assertIsDisplayed()
        rule.onNodeWithText("Tự lùi · nhạc tự chọn").assertIsDisplayed()
        rule.onNodeWithText("Phiên bản 0.4.146").assertIsDisplayed()
        shot("settings_root_light")
        rule.onNodeWithTag("settings_sleep").performClick()
        assertEquals(SettingsGroup.Sleep, opened)
    }

    @Test
    fun rootDark() {
        showRoot(dark = true, stored = JSONObject().put("theme", "dark").put("schedule", JSONObject().put("from", "22:30").put("to", "06:00").put("minutes", 30)))
        rule.onNodeWithText("Tối").assertIsDisplayed()
        rule.onNodeWithText("Lịch đêm 22:30–06:00").assertIsDisplayed()
        shot("settings_root_dark")
    }

    // ---- mỗi nhóm, sáng và tối ----

    /** Một nhóm ở một giao diện (mỗi test một setContent - quy tắc của ComposeTestRule). Thông báo đang tắt: dòng "Cho phép" của Nghe có trong ảnh. */
    private fun group(group: SettingsGroup, dark: Boolean) {
        showGroup(group, dark, allowed = false)
        rule.onNodeWithTag("${group.tag}_screen").assertIsDisplayed()
        shot("settings_${group.name.lowercase()}_${if (dark) "dark" else "light"}")
    }

    @Test fun voiceLight() = group(SettingsGroup.Voice, dark = false)
    @Test fun voiceDark() = group(SettingsGroup.Voice, dark = true)
    @Test fun listenLight() = group(SettingsGroup.Listen, dark = false)
    @Test fun listenDark() = group(SettingsGroup.Listen, dark = true)
    @Test fun sleepLight() = group(SettingsGroup.Sleep, dark = false)
    @Test fun sleepDark() = group(SettingsGroup.Sleep, dark = true)
    @Test fun lookLight() = group(SettingsGroup.Look, dark = false)
    @Test fun lookDark() = group(SettingsGroup.Look, dark = true)
    @Test fun devicesLight() = group(SettingsGroup.Devices, dark = false)
    @Test fun devicesDark() = group(SettingsGroup.Devices, dark = true)
    @Test fun advancedLight() = group(SettingsGroup.Advanced, dark = false)
    @Test fun advancedDark() = group(SettingsGroup.Advanced, dark = true)

    // ---- kịch bản ----

    @Test
    fun switchesWriteTheSameKeysAsTheWebView() {
        showGroup(SettingsGroup.Listen)
        rule.onNodeWithTag("notify_allow").assertDoesNotExist()
        rule.onNodeWithTag("auto_rewind").performClick()
        rule.onNodeWithTag("auto_music").performClick()
        assertFalse(repo.state.value.autoRewind)
        assertEquals(listOf("autoRewind", "autoMusic"), core.saved.map { write -> write.keys().asSequence().first { it != "settingsStamp" } })
        assertFalse(core.saved[0].getBoolean("autoRewind"))
        assertTrue(core.saved.all { it.getLong("settingsStamp") > 0 })
    }

    @Test
    fun notificationRowOpensTheSystemPage() {
        showGroup(SettingsGroup.Listen, allowed = false)
        rule.onNodeWithTag("notify_allow").performClick()
        assertEquals(1, notifyOpened)
    }

    @Test
    fun choiceUnderlineSlidesToTheNewOption() {
        showGroup(SettingsGroup.Sleep)
        rule.onNodeWithTag("safety_stop_2").assertIsSelected()
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("safety_stop_0").performClick()
        rule.mainClock.advanceTimeBy(110)
        shot("settings_choice_sliding_light")
        rule.mainClock.autoAdvance = true
        rule.waitForIdle()
        rule.onNodeWithTag("safety_stop_0").assertIsSelected()
        assertEquals(0, repo.state.value.safetyStopHours)
        assertEquals(0, core.saved.last().getInt("safetyStopHours"))
    }

    @Test
    fun nightScheduleOpensInPlaceAndTimesComeFromASheet() {
        showGroup(SettingsGroup.Sleep)
        rule.onNodeWithTag("schedule_editor").assertDoesNotExist()
        rule.onNodeWithTag("sleep_schedule").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("schedule_editor").assertIsDisplayed()
        assertEquals("22:00", core.saved.last().getJSONObject("schedule").getString("from"))
        rule.onNodeWithTag("schedule_from").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("time_sheet").assertIsDisplayed()
        shot("settings_sleep_time_sheet_light")
        rule.onNodeWithTag("time_22:30").performClick()
        rule.waitForIdle()
        assertEquals("22:30", repo.state.value.schedule?.from)
        rule.onNodeWithTag("sleep_schedule").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("schedule_editor").assertDoesNotExist()
        assertTrue(core.saved.last().isNull("schedule"))
    }

    @Test
    fun shakeOptionsCollapseWithTheSwitch() {
        showGroup(SettingsGroup.Sleep)
        rule.onNodeWithTag("shake_action").assertIsDisplayed()
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("shake").performScrollTo().performClick()
        rule.mainClock.advanceTimeBy(80)
        // Giữa chừng: khối đang khép (cao dần về 0), chưa biến mất cứng.
        val mid = rule.onNodeWithTag("shake_action").getUnclippedBoundsInRoot()
        assertTrue("khối phải còn đang khép, bounds=$mid", mid.bottom - mid.top > 0.dp)
        rule.mainClock.autoAdvance = true
        rule.waitForIdle()
        rule.onNodeWithTag("shake_action").assertDoesNotExist()
        assertFalse(core.saved.last().getBoolean("shakeToExtend"))
    }

    @Test
    fun themeChoiceChangesTheWholeApp() {
        showGroup(SettingsGroup.Look)
        rule.onNodeWithTag("theme_dark").performClick()
        rule.waitForIdle()
        assertEquals(ThemeMode.Dark, repo.state.value.theme)
        assertEquals("dark", core.saved.last().getString("theme"))
        rule.onNodeWithTag("theme_dark").assertIsSelected()
        rule.onNodeWithTag("reading_surface_ivory").performClick()
        assertEquals("ivory", core.saved.last().getString("readingSurface"))
    }

    @Test
    fun voiceListChoosesTheDefaultVoice() {
        showGroup(SettingsGroup.Voice)
        rule.onNodeWithTag("voice_current").assertIsDisplayed()
        rule.onNodeWithTag("voice_edge:vi-VN-HoaiMyNeural").assertIsSelected()
        rule.onNodeWithTag("voice_edge:vi-VN-NamMinhNeural").performClick()
        rule.waitForIdle()
        assertEquals("edge:vi-VN-NamMinhNeural", core.default)
        rule.onNodeWithText("Đang dùng: Nam Minh").assertIsDisplayed()
    }

    @Test
    fun advancedActionsReachTheCoreAndTheSystem() {
        showGroup(SettingsGroup.Advanced)
        rule.onNodeWithText("Bản đọc đã làm chiếm 12 MB trên máy này.").assertIsDisplayed()
        rule.onNodeWithTag("cache_clear").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("clear_sheet").assertIsDisplayed()
        shot("settings_clear_sheet_light")
        rule.onNodeWithTag("clear_confirm").performClick()
        rule.waitForIdle()
        rule.onNodeWithText("Chưa có bản đọc đã lưu.").assertIsDisplayed()
        rule.onNodeWithTag("logs_send").performScrollTo().performClick()
        assertEquals(1, shared)
        rule.onNodeWithTag("logs_clear").performScrollTo().performClick()
        assertEquals(1, core.logsCleared)
        rule.onNodeWithText("Đã xoá nhật ký.").assertIsDisplayed()
        rule.onNodeWithTag("source_open").performScrollTo().performClick()
        assertEquals(1, sourceOpened)
    }

    @Test
    fun logAndThirdPartySheets() {
        showGroup(SettingsGroup.Advanced, dark = true)
        rule.onNodeWithTag("logs_view").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("log_sheet").assertIsDisplayed()
        shot("settings_log_sheet_dark")
        rule.runOnUiThread { sheets.dismiss() }
        rule.waitForIdle()
        rule.onNodeWithTag("third_party").performScrollTo().performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("third_party_sheet").assertIsDisplayed()
        rule.onNodeWithText("Phông chữ").assertIsDisplayed()
        rule.onNodeWithText("không hiện").assertDoesNotExist()
        shot("settings_third_party_dark")
    }
}
