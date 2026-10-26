package vn.abook.player.ui.voice

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.hasAnyAncestor
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
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
import vn.abook.player.ui.music.MusicText
import vn.abook.player.ui.data.FakeSettingsCore
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.VoiceOption
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.screens.SettingsGroupScreen
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.ThemeReveal

/**
 * Giọng đọc làm thêm trên JVM với nguồn giả: ảnh chụp (Roborazzi) từng trạng thái sáng / tối - giọng trên máy (chưa có, đang tải, lỗi, đã có, đề nghị, máy không dùng được),
 * nghe thử (đang lấy, đang phát, lỗi), khóa (chưa có, đã lưu, bảng nhập, đồng ý), Nhạc của tôi (trống, có bài, đang thêm) - kịch bản bấm thật, và luật căn hàng: nút / biểu
 * tượng đầu hàng và phần cuối hàng cùng thẳng dòng đầu của tên.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class VoiceScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val sheets = SheetHost()
    private val source = FakeVoiceSource()
    private val player = FakeSamplePlayer()
    private val core = FakeSettingsCore()
    private val repo = SettingsRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined).also { runBlocking { it.load() } }
    private val voice = CoroutineScope(Dispatchers.Unconfined).let { VoiceState(source, it, player, { repo.loadVoices() }, 3_600_000, MineImports(source, it)) }
    private var opened: VoicePage? = null
    private val viet = ModuleKind.Vieneu
    private val sieu = ModuleKind.Supertonic

    private fun show(dark: Boolean = false, content: @Composable (SettingsEnv) -> Unit) {
        rule.setContent {
            val scope = rememberCoroutineScope()
            val env = remember { SettingsEnv(repo, ThemeReveal(scope), voice = voice) }
            AbookTheme(dark) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    content(env)
                    SheetLayer(sheets)
                }
            }
        }
        rule.waitForIdle()
    }

    private fun showVoice(dark: Boolean = false) = show(dark) { env -> SettingsGroupScreen(SettingsGroup.Voice, env, sheets, onBack = {}, openVoice = { opened = it }) }
    private fun showListen(dark: Boolean = false) = show(dark) { env -> SettingsGroupScreen(SettingsGroup.Listen, env, sheets, onBack = {}, openVoice = { opened = it }) }
    private fun showKeys(dark: Boolean = false) = show(dark) { KeysScreen(voice, sheets, onBack = {}) }
    private fun showMusic(dark: Boolean = false) = show(dark) { MyMusicScreen(voice, sheets, onBack = {}) }

    private fun shot(name: String) = rule.onRoot().captureRoboImage("src/test/snapshots/voice_$name.png")

    private fun theme(dark: Boolean) = if (dark) "dark" else "light"

    private fun tap(tag: String, unmerged: Boolean = false) {
        rule.onNodeWithTag(tag, useUnmergedTree = unmerged).performClick()
        rule.waitForIdle()
    }

    private fun ui(block: () -> Unit) {
        rule.runOnUiThread(block)
        rule.waitForIdle()
    }

    /** Cuộn danh sách giọng tới một mục (danh sách lười: mục ngoài màn chưa được dựng). */
    private fun scrollTo(tag: String) {
        rule.onNodeWithTag("settings_voice_screen").performScrollToNode(hasTestTag(tag))
        rule.waitForIdle()
    }

    // ---- giọng tải về máy: ảnh chụp ----

    private fun modulesMissing(dark: Boolean) {
        showVoice(dark)
        scrollTo("voice_keys")
        rule.onNodeWithTag("module_vieneu_turbo").assertIsDisplayed()
        rule.onNodeWithText("Tải 198 MB").assertIsDisplayed()
        rule.onNodeWithTag("voice_keys").assertIsDisplayed()
        shot("modules_missing_${theme(dark)}")
    }

    @Test fun modulesMissingLight() = modulesMissing(false)
    @Test fun modulesMissingDark() = modulesMissing(true)

    private fun modulesDownloading(dark: Boolean) {
        source.modules[viet] = Fixtures.downloading(viet, 40)
        showVoice(dark)
        scrollTo("voice_keys")
        rule.onNodeWithTag("module_vieneu_turbo_cancel", useUnmergedTree = true).assertIsDisplayed()
        rule.onNodeWithText("Đang tải 198 MB · 40%").assertIsDisplayed()
        shot("modules_downloading_${theme(dark)}")
    }

    @Test fun modulesDownloadingLight() = modulesDownloading(false)
    @Test fun modulesDownloadingDark() = modulesDownloading(true)

    private fun modulesFailed(dark: Boolean) {
        source.modules[viet] = Fixtures.failed(viet)
        showVoice(dark)
        scrollTo("voice_keys")
        rule.onNodeWithTag("module_vieneu_turbo_retry", useUnmergedTree = true).assertIsDisplayed()
        shot("modules_failed_${theme(dark)}")
    }

    @Test fun modulesFailedLight() = modulesFailed(false)
    @Test fun modulesFailedDark() = modulesFailed(true)

    private fun modulesInstalled(dark: Boolean) {
        source.modules[viet] = Fixtures.ready(viet, mapOf("turbo" to ModuleBench(0.5, 900)))
        source.modules[sieu] = Fixtures.outdated(sieu)
        showVoice(dark)
        scrollTo("voice_keys")
        rule.onNodeWithText("Đọc trực tiếp được · nhanh gấp 2,0 lần").assertIsDisplayed()
        rule.onNodeWithText("Có bản mới · 12 MB").assertIsDisplayed()
        shot("modules_installed_${theme(dark)}")
    }

    @Test fun modulesInstalledLight() = modulesInstalled(false)
    @Test fun modulesInstalledDark() = modulesInstalled(true)

    private fun modulesSuggestion(dark: Boolean) {
        source.modules[viet] = Fixtures.ready(viet, mapOf("turbo" to ModuleBench(1.4, 3000)), ModuleSuggestion("turbo", 1.4, "nano", installed = false))
        source.modules[sieu] = Fixtures.unsupported(sieu)
        showVoice(dark)
        scrollTo("voice_keys")
        rule.onNodeWithTag("suggestion_vieneu").assertIsDisplayed()
        rule.onNodeWithText("Tải giọng VieNeu Nano").assertIsDisplayed()
        rule.onNodeWithText("Máy này chưa dùng được: thiếu bộ nhớ trống.").assertIsDisplayed()
        shot("modules_suggestion_${theme(dark)}")
    }

    @Test fun modulesSuggestionLight() = modulesSuggestion(false)
    @Test fun modulesSuggestionDark() = modulesSuggestion(true)

    // ---- giọng tải về máy: bấm thật ----

    @Test
    fun downloadStartsForThatChoiceAndCancelStopsIt() {
        showVoice()
        scrollTo("voice_keys")
        tap("module_vieneu_nano_action", unmerged = true)
        assertEquals(listOf(viet to listOf("nano")), source.started)
        source.modules[viet] = Fixtures.downloading(viet, 10)
        ui { voice.openVoice() }
        tap("module_vieneu_nano_cancel", unmerged = true)
        assertEquals(listOf(viet), source.cancels)
        rule.onNodeWithTag("module_vieneu_nano_action", useUnmergedTree = true).assertIsDisplayed()
    }

    @Test
    fun meteredDataAsksBeforeDownloading() {
        source.modules[viet] = Fixtures.missing(viet, metered = true)
        showVoice()
        scrollTo("voice_keys")
        tap("module_vieneu_turbo_action", unmerged = true)
        assertTrue(source.started.isEmpty())
        rule.onNodeWithTag("metered_confirm").assertIsDisplayed()
        shot("metered_sheet_light")
        tap("metered_go")
        assertEquals(listOf(viet to listOf("turbo")), source.started)
    }

    @Test
    fun anInstalledVoiceOpensItsSheetAndRemovingAsksFirst() {
        source.modules[viet] = Fixtures.ready(viet, mapOf("turbo" to ModuleBench(0.5, 900)))
        showVoice()
        scrollTo("voice_keys")
        tap("module_vieneu_turbo")
        rule.onNodeWithTag("module_sheet").assertIsDisplayed()
        rule.onNodeWithTag("module_benchmark").assertIsDisplayed()
        shot("module_sheet_light")
        tap("module_remove")
        rule.onNodeWithTag("module_remove_confirm").assertIsDisplayed()
        assertTrue(source.removed.isEmpty())
        shot("module_remove_light")
        tap("module_remove_yes")
        assertEquals(listOf(viet to "turbo"), source.removed)
    }

    @Test
    fun keepingTheVoiceRemovesNothing() {
        source.modules[viet] = Fixtures.ready(viet)
        showVoice(dark = true)
        scrollTo("voice_keys")
        tap("module_vieneu_turbo")
        tap("module_remove")
        shot("module_remove_dark")
        tap("module_remove_keep")
        rule.onNodeWithTag("module_remove").assertIsDisplayed()
        assertTrue(source.removed.isEmpty())
    }

    @Test
    fun leftoversOfACancelledDownloadCanBeClearedFromTheRow() {
        source.modules[viet] = Fixtures.leftover(viet)
        showVoice()
        scrollTo("voice_keys")
        tap("module_vieneu_turbo")
        rule.onNodeWithText("Xoá phần đã tải").assertIsDisplayed()
        tap("module_remove")
        tap("module_remove_yes")
        assertEquals(listOf(viet to "turbo"), source.removed)
    }

    @Test
    fun theSuggestionDownloadsTheLightVoiceOnlyWhenPressed() {
        source.modules[viet] = Fixtures.ready(viet, mapOf("turbo" to ModuleBench(1.4, 3000)), ModuleSuggestion("turbo", 1.4, "nano", installed = false))
        showVoice()
        scrollTo("voice_keys")
        assertTrue(source.started.isEmpty())
        tap("suggestion_vieneu_action", unmerged = true)
        assertEquals(listOf(viet to listOf("nano")), source.started)
    }

    @Test
    fun finishingADownloadPutsTheNewVoiceInTheList() {
        source.modules[viet] = Fixtures.downloading(viet, 50)
        showVoice()
        rule.onNodeWithTag("voice_vieneu:turbo/binh").assertDoesNotExist()
        core.installed = listOf(VoiceOption("vieneu:turbo/binh", "Bình (VieNeu)", "vieneu", false))
        source.modules[viet] = Fixtures.ready(viet)
        ui { voice.openVoice() }
        scrollTo("voice_vieneu:turbo/binh")
        rule.onNodeWithTag("voice_vieneu:turbo/binh").assertIsDisplayed()
    }

    // ---- nghe thử ----

    @Test
    fun everyVoiceRowHasASampleButtonAtItsEnd() {
        showVoice()
        for (id in listOf("edge:vi-VN-HoaiMyNeural", "edge:vi-VN-NamMinhNeural", "supertonic:F1", "device:vi-vn-x-gft-local")) {
            rule.onNodeWithTag("sample_$id", useUnmergedTree = true).assertIsDisplayed()
        }
    }

    private fun samplePlaying(dark: Boolean) {
        showVoice(dark)
        tap("sample_edge:vi-VN-NamMinhNeural", unmerged = true)
        assertEquals("edge:vi-VN-NamMinhNeural" to VoiceText.SAMPLE, source.sampled.single())
        assertEquals(listOf("/cache/edge:vi-VN-NamMinhNeural.mp3"), player.played)
        rule.onNodeWithTag("voice_edge:vi-VN-HoaiMyNeural").assertIsSelected()
        shot("sample_playing_${theme(dark)}")
    }

    @Test fun samplePlayingLight() = samplePlaying(false)
    @Test fun samplePlayingDark() = samplePlaying(true)

    private fun sampleLoading(dark: Boolean) {
        source.sampleGate = CompletableDeferred()
        showVoice(dark)
        rule.mainClock.autoAdvance = false
        tap("sample_edge:vi-VN-NamMinhNeural", unmerged = true)
        rule.mainClock.advanceTimeBy(3000)
        rule.onNodeWithText("Đang lấy giọng").assertIsDisplayed()
        shot("sample_loading_${theme(dark)}")
        rule.mainClock.autoAdvance = true
        source.sampleGate!!.complete(Unit)
        rule.waitForIdle()
    }

    @Test fun sampleLoadingLight() = sampleLoading(false)
    @Test fun sampleLoadingDark() = sampleLoading(true)

    private fun sampleFailed(dark: Boolean) {
        source.sampleError = VoiceFailure("Chưa có mạng để lấy giọng này.")
        showVoice(dark)
        tap("sample_edge:vi-VN-NamMinhNeural", unmerged = true)
        rule.onNodeWithText("Chưa có mạng để lấy giọng này.").assertIsDisplayed()
        rule.onNodeWithTag("sample_retry_edge:vi-VN-NamMinhNeural", useUnmergedTree = true).assertIsDisplayed()
        shot("sample_failed_${theme(dark)}")
    }

    @Test fun sampleFailedLight() = sampleFailed(false)
    @Test fun sampleFailedDark() = sampleFailed(true)

    @Test
    fun tappingAnotherSampleSwitchesAndLeavingTheScreenStops() {
        showVoice()
        tap("sample_edge:vi-VN-NamMinhNeural", unmerged = true)
        tap("sample_supertonic:F1", unmerged = true)
        assertEquals(listOf("/cache/edge:vi-VN-NamMinhNeural.mp3", "/cache/supertonic:F1.mp3"), player.played)
        assertEquals("supertonic:F1", voice.sample.value.playing)
        val stops = player.stops
        ui { voice.stopSample() }
        assertEquals(SampleUi(), voice.sample.value)
        assertTrue(player.stops > stops)
    }

    // ---- đồng ý khi chọn giọng trực tuyến ----

    private fun consentSheet(dark: Boolean) {
        showVoice(dark)
        tap("voice_edge:vi-VN-NamMinhNeural")
        rule.onNodeWithTag("consent_confirm").assertIsDisplayed()
        assertEquals("edge:vi-VN-HoaiMyNeural", core.default)
        shot("consent_sheet_${theme(dark)}")
    }

    @Test fun consentSheetLight() = consentSheet(false)
    @Test fun consentSheetDark() = consentSheet(true)

    @Test
    fun agreeingRemembersTheProviderAndChoosesTheVoice() {
        showVoice()
        tap("voice_edge:vi-VN-NamMinhNeural")
        tap("consent_yes")
        assertEquals(setOf("edge"), source.allowed)
        assertEquals("edge:vi-VN-NamMinhNeural", core.default)
        tap("voice_edge:vi-VN-HoaiMyNeural")
        assertEquals("đã đồng ý thì không hỏi lại", "edge:vi-VN-HoaiMyNeural", core.default)
    }

    @Test
    fun decliningKeepsTheOldVoiceAndSendsNothing() {
        showVoice()
        tap("voice_edge:vi-VN-NamMinhNeural")
        tap("consent_no")
        assertEquals("edge:vi-VN-HoaiMyNeural", core.default)
        assertTrue(source.allowed.isEmpty())
    }

    @Test
    fun aVoiceOnThisPhoneNeverAsks() {
        showVoice()
        tap("voice_supertonic:F1")
        assertEquals("supertonic:F1", core.default)
        assertFalse(source.allowed.contains("supertonic"))
    }

    // ---- khóa giọng trực tuyến ----

    private fun keysNone(dark: Boolean) {
        showKeys(dark)
        for (id in VoiceText.KEYED.keys) rule.onNodeWithTag("key_$id").assertIsDisplayed()
        rule.onNodeWithText("Miễn phí 500.000 ký tự mỗi tháng").assertIsDisplayed()
        shot("keys_none_${theme(dark)}")
    }

    @Test fun keysNoneLight() = keysNone(false)
    @Test fun keysNoneDark() = keysNone(true)

    private fun keysSaved(dark: Boolean) {
        source.keys = mutableListOf(
            Fixtures.provider("azure", "Azure Speech", hasKey = true, valid = true, region = "southeastasia"),
            Fixtures.provider("google", "Google Cloud", hasKey = true),
            Fixtures.provider("fpt", "FPT.AI"),
            Fixtures.provider("viettel", "Viettel AI"),
        )
        showKeys(dark)
        rule.onNodeWithText("••••WXYZ · Dùng được · 4 giọng").assertIsDisplayed()
        rule.onNodeWithText("••••WXYZ · Chưa dùng được").assertIsDisplayed()
        shot("keys_saved_${theme(dark)}")
    }

    @Test fun keysSavedLight() = keysSaved(false)
    @Test fun keysSavedDark() = keysSaved(true)

    @Test
    fun theKeysRowOnTheVoicePageSummarisesAndOpensTheKeysScreen() {
        source.keys = source.keys.map { if (it.id == "fpt") it.copy(hasKey = true, masked = "••••1234") else it }.toMutableList()
        showVoice()
        scrollTo("voice_keys")
        rule.onNodeWithText("FPT.AI").assertIsDisplayed()
        tap("voice_keys")
        assertEquals(VoicePage.Keys, opened)
    }

    private fun keySheet(dark: Boolean) {
        showKeys(dark)
        tap("key_azure")
        rule.onNodeWithTag("key_sheet").assertIsDisplayed()
        rule.onNodeWithTag("key_field").performTextInput("secret-key-0001-WXYZ")
        rule.onNodeWithTag("key_region").performTextInput("southeastasia")
        rule.waitForIdle()
        rule.onNodeWithTag("key_reveal", useUnmergedTree = true).assertIsDisplayed()
        shot("key_sheet_${theme(dark)}")
    }

    @Test fun keySheetLight() = keySheet(false)
    @Test fun keySheetDark() = keySheet(true)

    @Test
    fun savingSendsTheKeyDownOnceAndClosesTheSheet() {
        showKeys()
        tap("key_azure")
        rule.onNodeWithTag("key_field").performTextInput("secret-key-0001-WXYZ")
        rule.onNodeWithTag("key_region").performTextInput("southeastasia")
        rule.waitForIdle()
        tap("key_save")
        assertEquals(Triple("azure", "secret-key-0001-WXYZ", "southeastasia"), source.savedKeys.single())
        rule.onNodeWithTag("key_sheet").assertDoesNotExist()
        rule.onNodeWithText("••••WXYZ · Chưa dùng được").assertIsDisplayed()
    }

    @Test
    fun saveStaysOffUntilThereIsSomethingToSave() {
        showKeys()
        tap("key_google")
        tap("key_save")
        assertTrue(source.savedKeys.isEmpty())
    }

    @Test
    fun aBadRegionIsShownInPlaceAndNothingIsClosed() {
        source.saveError = VoiceFailure("Vùng Azure chưa đúng (ví dụ: southeastasia)")
        showKeys()
        tap("key_azure")
        rule.onNodeWithTag("key_field").performTextInput("k")
        rule.waitForIdle()
        tap("key_save")
        rule.onNodeWithText("Vùng Azure chưa đúng (ví dụ: southeastasia)").assertIsDisplayed()
        rule.onNodeWithTag("key_sheet").assertIsDisplayed()
        shot("key_problem_light")
    }

    @Test
    fun theFirstCheckAsksForConsentThenChecks() {
        showKeys()
        tap("key_google")
        rule.onNodeWithTag("key_field").performTextInput("google-key-9999")
        rule.waitForIdle()
        tap("key_check")
        rule.onNodeWithTag("consent_confirm").assertIsDisplayed()
        assertTrue(source.checked.isEmpty())
        shot("key_consent_light")
        tap("consent_yes")
        assertEquals(setOf("google"), source.allowed)
        assertEquals(listOf("google"), source.checked)
        rule.onNodeWithTag("key_verdict").assertIsDisplayed()
        rule.onNodeWithText("Dùng được · 4 giọng tiếng Việt").assertIsDisplayed()
        shot("key_verdict_light")
    }

    @Test
    fun decliningTheConsentSendsNothingToTheService() {
        showKeys()
        tap("key_google")
        rule.onNodeWithTag("key_field").performTextInput("google-key-9999")
        rule.waitForIdle()
        tap("key_check")
        tap("consent_no")
        assertTrue(source.checked.isEmpty())
        rule.onNodeWithTag("key_field").assertIsDisplayed()
    }

    @Test
    fun aRefusedKeySaysSoInTheDangerColourAndCheckWithoutAKeyAsksForOne() {
        source.allowed += "fpt"
        source.checkResult = { KeyResult(false, "Khóa FPT.AI bị từ chối (401).") }
        showKeys(dark = true)
        tap("key_fpt")
        tap("key_check")
        rule.onNodeWithText("Dán khóa trước đã.").assertIsDisplayed()
        rule.onNodeWithTag("key_field").performTextInput("bad-key-0000")
        rule.waitForIdle()
        tap("key_check")
        rule.onNodeWithText("Khóa FPT.AI bị từ chối (401).").assertIsDisplayed()
        shot("key_refused_dark")
    }

    @Test
    fun removingAKeyAsksFirst() {
        source.keys = source.keys.map { if (it.id == "viettel") it.copy(hasKey = true, masked = "••••9999") else it }.toMutableList()
        showKeys(dark = true)
        tap("key_viettel")
        tap("key_remove")
        rule.onNodeWithTag("key_remove_confirm").assertIsDisplayed()
        assertTrue(source.removedKeys.isEmpty())
        shot("key_remove_dark")
        tap("key_remove_yes")
        assertEquals(listOf("viettel"), source.removedKeys)
        rule.onNodeWithText("••••9999 · Chưa dùng được").assertDoesNotExist()
    }

    // ---- Nhạc của tôi ----

    private fun musicEmpty(dark: Boolean) {
        showMusic(dark)
        rule.onNodeWithTag("music_add").assertIsDisplayed()
        rule.onNodeWithTag("music_empty").assertIsDisplayed()
        shot("music_empty_${theme(dark)}")
    }

    @Test fun musicEmptyLight() = musicEmpty(false)
    @Test fun musicEmptyDark() = musicEmpty(true)

    private fun musicFiles(dark: Boolean) {
        source.tracks = listOf(
            Fixtures.track("Buổi sáng yên tĩnh", creator = "Kevin MacLeod", duration = 187.0),
            Fixtures.track("Một bản nhạc có tên rất dài để xem hàng xuống dòng mà không bị cắt chữ ở đâu cả", bytes = 12_400_000, creator = "", duration = 3725.0),
            Fixtures.track("track03.mp3", bytes = 900_000, creator = "Bạn", duration = 0.0, analysed = false),
        )
        showMusic(dark)
        rule.onNodeWithText("Buổi sáng yên tĩnh").assertIsDisplayed()
        rule.onNodeWithText("Kevin MacLeod · 3:07").assertIsDisplayed()
        rule.onNodeWithTag("music_intro").assertIsDisplayed()
        rule.onAllNodesWithText(MusicText.UNANALYSED).assertCountEquals(1)
        shot("music_files_${theme(dark)}")
    }

    @Test fun musicFilesLight() = musicFiles(false)
    @Test fun musicFilesDark() = musicFiles(true)

    private fun musicImporting(dark: Boolean) {
        source.tracks = listOf(Fixtures.track("Buổi sáng yên tĩnh"))
        source.importGate = CompletableDeferred()
        showMusic(dark)
        rule.mainClock.autoAdvance = false
        ui { voice.importMusic(listOf("content://a", "content://b", "content://c")) }
        rule.mainClock.advanceTimeBy(1000)
        rule.onNodeWithText("Đang thêm 3/3").assertIsDisplayed()
        shot("music_importing_${theme(dark)}")
        rule.mainClock.autoAdvance = true
        source.importGate!!.complete(Unit)
        rule.waitForIdle()
    }

    @Test fun musicImportingLight() = musicImporting(false)
    @Test fun musicImportingDark() = musicImporting(true)

    @Test
    fun anImportShowsItsSummaryAndTheFilesThatFailed() {
        source.importResult = { uris -> MusicImportResult(uris.map { Fixtures.track(it) }, 2, 1, listOf("“ghi chu.txt”: không phải file nhạc.")) }
        showMusic()
        ui { voice.importMusic(listOf("content://a", "content://b", "content://c")) }
        rule.onNodeWithText("Đã thêm: 2 bài mới, 1 bài đã có từ trước").assertIsDisplayed()
        rule.onNodeWithText("“ghi chu.txt”: không phải file nhạc.").assertIsDisplayed()
        shot("music_imported_light")
    }

    @Test
    fun removingATrackAsksFirstAndTakesItOffTheList() {
        val keep = Fixtures.track("Bản A")
        val drop = Fixtures.track("Bản B")
        source.tracks = listOf(keep, drop)
        showMusic()
        tap(trackTag(drop))
        rule.onNodeWithTag("track_confirm").assertIsDisplayed()
        shot("music_remove_light")
        assertTrue(source.removedTracks.isEmpty())
        tap("track_yes")
        assertEquals(listOf(drop.link), source.removedTracks)
        rule.onNodeWithText("Bản A").assertIsDisplayed()
    }

    @Test
    fun keepingATrackChangesNothing() {
        val drop = Fixtures.track("Bỏ đi")
        source.tracks = listOf(drop)
        showMusic(dark = true)
        tap(trackTag(drop))
        shot("music_remove_dark")
        tap("track_keep")
        assertTrue(source.removedTracks.isEmpty())
    }

    @Test
    fun theListenPageShowsMyMusicWithItsCountAndOpensIt() {
        source.tracks = listOf(Fixtures.track("Một"), Fixtures.track("Hai"), Fixtures.track("Ba"))
        showListen()
        rule.onNodeWithText("3 bài").assertIsDisplayed()
        tap("my_music")
        assertEquals(VoicePage.Music, opened)
        shot("listen_my_music_light")
    }

    // ---- căn hàng: nút / biểu tượng đầu hàng và phần cuối hàng cùng thẳng dòng đầu của tên ----

    /** Tâm của `row_leading` / `row_trailing` trong hàng `tag` trùng tâm dòng chữ đầu của tên (đỉnh tên + 12), kể cả khi tên xuống dòng. */
    private fun assertFirstLine(tag: String, leading: Boolean = false, trailing: Boolean = false) {
        val title = rule.onNode(hasTestTag("row_title") and hasAnyAncestor(hasTestTag(tag)), useUnmergedTree = true).getUnclippedBoundsInRoot()
        val sides = listOfNotNull("row_leading".takeIf { leading }, "row_trailing".takeIf { trailing })
        assertTrue("$tag: không có bên nào để kiểm", sides.isNotEmpty())
        for (side in sides) {
            val edge = rule.onNode(hasTestTag(side) and hasAnyAncestor(hasTestTag(tag)), useUnmergedTree = true).getUnclippedBoundsInRoot()
            val center = (edge.top + edge.bottom) / 2
            assertTrue("$tag/$side: tâm dòng đầu ${title.top + 12.dp}, tâm $center", ((title.top + 12.dp) - center).value in -0.6f..0.6f)
        }
    }

    @Test
    fun voiceRowsShareTheFirstLineWithTheTickAndTheSampleButton() {
        showVoice()
        assertFirstLine("voice_edge:vi-VN-HoaiMyNeural", leading = true, trailing = true)
        assertFirstLine("voice_supertonic:F1", leading = true, trailing = true)
        source.sampleError = VoiceFailure("Chưa có mạng để lấy giọng này, bạn thử lại sau ít phút nhé, hoặc chọn một giọng khác.")
        tap("sample_edge:vi-VN-NamMinhNeural", unmerged = true)
        assertFirstLine("voice_edge:vi-VN-NamMinhNeural", leading = true, trailing = true)
    }

    @Test
    fun theSampleButtonAndTheLoadingBarKeepTheirPlace() {
        source.sampleGate = CompletableDeferred()
        showVoice()
        rule.mainClock.autoAdvance = false
        tap("sample_edge:vi-VN-NamMinhNeural", unmerged = true)
        rule.mainClock.advanceTimeBy(500)
        assertFirstLine("voice_edge:vi-VN-NamMinhNeural", leading = true, trailing = true)
        val row = rule.onNodeWithTag("voice_edge:vi-VN-NamMinhNeural", useUnmergedTree = true).getUnclippedBoundsInRoot()
        val bar = rule.onNode(hasTestTag("row_below") and hasAnyAncestor(hasTestTag("voice_edge:vi-VN-NamMinhNeural")), useUnmergedTree = true).getUnclippedBoundsInRoot()
        assertTrue("thanh tới mép phải hàng", (row.right - bar.right).value in -0.6f..0.6f)
        rule.mainClock.autoAdvance = true
        source.sampleGate!!.complete(Unit)
        rule.waitForIdle()
    }

    @Test
    fun moduleRowsShareTheFirstLineInEveryState() {
        source.modules[viet] = Fixtures.downloading(viet, 40)
        source.modules[sieu] = Fixtures.ready(sieu, mapOf("supertonic" to ModuleBench(0.5, 900)))
        showVoice()
        scrollTo("voice_keys")
        assertFirstLine("module_vieneu_turbo", trailing = true)
        assertFirstLine("module_supertonic_supertonic", trailing = true)
        val row = rule.onNodeWithTag("module_vieneu_turbo", useUnmergedTree = true).getUnclippedBoundsInRoot()
        val bar = rule.onNode(hasTestTag("row_below") and hasAnyAncestor(hasTestTag("module_vieneu_turbo")), useUnmergedTree = true).getUnclippedBoundsInRoot()
        assertTrue("thanh tiến độ tới mép phải hàng", (row.right - bar.right).value in -0.6f..0.6f)
    }

    @Test
    fun moduleDownloadAndRetryActionsShareTheFirstLine() {
        source.modules[viet] = Fixtures.failed(viet)
        showVoice()
        scrollTo("voice_keys")
        assertFirstLine("module_vieneu_turbo", trailing = true)
        assertFirstLine("module_vieneu_nano", trailing = true)
    }

    @Test
    fun keyRowsShareTheFirstLineWithTheChevron() {
        source.keys = source.keys.map { if (it.id == "google") it.copy(hasKey = true, masked = "••••WXYZ") else it }.toMutableList()
        showKeys()
        for (id in VoiceText.KEYED.keys) assertFirstLine("key_$id", trailing = true)
    }

    @Test
    fun trackRowsShareTheFirstLineWithTheSizeEvenWhenTheNameWraps() {
        val long = Fixtures.track("Một bản nhạc có tên rất dài để xem hàng xuống dòng mà không bị cắt chữ ở đâu cả", bytes = 12_400_000)
        source.tracks = listOf(long, Fixtures.track("Ngắn"))
        showMusic()
        assertFirstLine(trackTag(long), trailing = true)
        assertFirstLine(trackTag(source.tracks[1]), trailing = true)
    }

    @Test
    fun theAddMusicRowKeepsItsPlusOnTheFirstLine() {
        showMusic()
        assertFirstLine("music_add", leading = true)
    }
}
