package vn.abook.player.ui.export

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.assertNoTextOverflow
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/**
 * Màn Xuất trên JVM với nguồn giả: ảnh chụp sáng / tối từng trạng thái (chọn MP3, chọn M4B, sách chữ, đang làm, xong M4B, xong MP3, dừng, lỗi) và kịch bản
 * bấm thật - bắt đầu gọi lõi đúng tuỳ chọn, tiến độ hiện, Dừng tới lõi, xong thì Mở / Gửi, lỗi hiện chữ, rời màn rồi quay lại vẫn thấy việc đang chạy.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class ExportScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val source = FakeExportSource()
    private lateinit var exports: ExportState
    private var backs = 0
    private var settings = 0
    private val shared = ArrayList<Pair<String, String>>()
    private var visible by mutableStateOf(true)

    private val book = ListenBook("b1", "Dế Mèn phiêu lưu ký · Tập 2", author = "Tô Hoài", chaptersTotal = 12, chaptersAvailable = 12, duration = 8 * 3600.0 + 1500)
    private val text = ListenBook("t1", "Tắt đèn", chaptersTotal = 12, textOnly = true)

    private fun show(target: ListenBook = book, dark: Boolean = false) {
        exports = ExportState(
            source, CoroutineScope(Dispatchers.Unconfined),
            ExportLinks(
                pickFolder = { result -> result("content://tree/Music") },
                createFile = { _, result -> result("content://doc/Truyen.m4b") },
                share = { uri, name -> shared += uri to name; true },
                openAppSettings = { settings++ },
            ),
        )
        rule.setContent {
            AbookTheme(dark) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    if (visible) ExportScreen(target, exports, onBack = { backs++ })
                }
            }
        }
        rule.waitForIdle()
    }

    private fun ui(block: () -> Unit) {
        rule.runOnUiThread(block)
        rule.waitForIdle()
    }

    private fun emit(event: ExportEvent) = ui { source.events.tryEmit(event) }

    private fun event(kind: ExportKind = ExportKind.Mp3, bookId: String = "b1", block: ExportEvent.() -> ExportEvent = { this }) =
        ExportEvent(kind, bookId, "run-1").block()

    private fun tap(tag: String) {
        rule.onNodeWithTag(tag).performClick()
        rule.waitForIdle()
    }

    private fun shot(name: String, dark: Boolean) = rule.onRoot().captureRoboImage("src/test/snapshots/export_${name}_${if (dark) "dark" else "light"}.png")

    private val past = PastExport(ExportKind.Mp3, "content://tree/Music/De%20Men", listOf(3, 4))

    // ---- ảnh chụp: chọn ----

    private fun optionsMp3(dark: Boolean) {
        source.folder = "Music"
        source.music = ExportMusic(available = true, enabled = true)
        source.history = listOf(past, PastExport(ExportKind.M4b, "content://doc/De%20Men.m4b", emptyList()))
        source.background = BackgroundView("OPPO", allowed = false)
        show(dark = dark)
        rule.onNodeWithTag("export_format_mp3").assertIsSelected()
        rule.onNodeWithTag("export_folder").assertIsDisplayed()
        rule.onNodeWithTag("export_scope").assertIsDisplayed()
        rule.onNodeWithTag("export_music").assertIsDisplayed()
        rule.onNodeWithTag("export_background").assertIsDisplayed()
        rule.onNodeWithTag("export_start").assertIsEnabled()
        shot("options_mp3", dark)
    }

    @Test fun optionsMp3Light() = optionsMp3(false)
    @Test fun optionsMp3Dark() = optionsMp3(true)

    private fun optionsPast(dark: Boolean) {
        source.folder = "Music"
        source.history = listOf(past, PastExport(ExportKind.M4b, "content://doc/De%20Men.m4b", emptyList()))
        source.background = BackgroundView("OPPO", allowed = false)
        show(dark = dark)
        rule.onNodeWithTag("export_options").performScrollToNode(hasTestTag("export_past"))
        rule.waitForIdle()
        shot("options_past", dark)
    }

    @Test fun optionsPastLight() = optionsPast(false)
    @Test fun optionsPastDark() = optionsPast(true)

    private fun optionsFresh(dark: Boolean) {
        show(dark = dark)
        rule.onNodeWithTag("export_folder").assertIsDisplayed()
        rule.onNodeWithTag("export_start").assertIsEnabled()
        shot("options_fresh", dark)
    }

    @Test fun optionsFreshLight() = optionsFresh(false)
    @Test fun optionsFreshDark() = optionsFresh(true)

    private fun optionsM4b(dark: Boolean) {
        source.music = ExportMusic(available = true, enabled = false)
        show(dark = dark)
        tap("export_format_m4b")
        rule.onNodeWithTag("export_format_m4b").assertIsSelected()
        rule.onNodeWithTag("export_place").assertIsDisplayed()
        shot("options_m4b", dark)
    }

    @Test fun optionsM4bLight() = optionsM4b(false)
    @Test fun optionsM4bDark() = optionsM4b(true)

    private fun optionsText(dark: Boolean) {
        source.plan = source.plan.copy(readyChapters = 4, readySeconds = 3 * 3600, music = ExportMusic(available = true, enabled = true), rereads = 3)
        show(text, dark)
        rule.onNodeWithTag("export_voice").assertIsDisplayed()
        rule.onNodeWithTag("export_plan").assertIsDisplayed()
        rule.onNodeWithTag("export_start").assertIsEnabled()
        shot("options_text", dark)
    }

    @Test fun optionsTextLight() = optionsText(false)
    @Test fun optionsTextDark() = optionsText(true)

    private fun optionsNoVoice(dark: Boolean) {
        source.voice = null
        show(text, dark)
        rule.onNodeWithTag("export_no_voice").assertIsDisplayed()
        rule.onNodeWithTag("export_start").assertIsNotEnabled()
        shot("options_no_voice", dark)
    }

    @Test fun optionsNoVoiceLight() = optionsNoVoice(false)
    @Test fun optionsNoVoiceDark() = optionsNoVoice(true)

    // ---- ảnh chụp: làm, kết quả ----

    private fun running(dark: Boolean) {
        source.folder = "Music"
        show(dark = dark)
        tap("export_start")
        emit(event { copy(done = 5, total = 12) })
        rule.onNodeWithTag("export_running").assertIsDisplayed()
        rule.onNodeWithTag("export_progress_text").assertTextEquals("5/12 chương")
        rule.onNodeWithTag("export_progress_folder").assertTextEquals("Vào Music/Dế Mèn phiêu lưu ký · Tập 2")
        rule.onNodeWithTag("export_stop").assertIsDisplayed()
        shot("running", dark)
    }

    @Test fun runningLight() = running(false)
    @Test fun runningDark() = running(true)

    private fun doneM4b(dark: Boolean) {
        show(dark = dark)
        tap("export_format_m4b")
        tap("export_start")
        emit(event(ExportKind.M4b) { copy(finished = true, name = "De Men.m4b", size = 310L * 1024 * 1024, uri = "content://doc/Truyen.m4b", chapters = 12, files = 12) })
        rule.onNodeWithTag("export_result_title").assertTextEquals("Đã xuất M4B")
        rule.onNodeWithTag("export_open").assertIsDisplayed()
        rule.onNodeWithTag("export_share").assertIsDisplayed()
        shot("done_m4b", dark)
    }

    @Test fun doneM4bLight() = doneM4b(false)
    @Test fun doneM4bDark() = doneM4b(true)

    private fun doneMp3(dark: Boolean) {
        source.folder = "Music"
        show(dark = dark)
        tap("export_start")
        emit(event { copy(finished = true, files = 9, chaptersTotal = 12, folder = "Music/Dế Mèn phiêu lưu ký · Tập 2", uri = "content://tree/Music", musicMissing = 2) })
        rule.onNodeWithTag("export_result_title").assertTextEquals("Đã xuất 9 chương")
        rule.onNodeWithTag("export_open_folder").assertIsDisplayed()
        shot("done_mp3", dark)
    }

    @Test fun doneMp3Light() = doneMp3(false)
    @Test fun doneMp3Dark() = doneMp3(true)

    private fun stopped(dark: Boolean) {
        source.folder = "Music"
        show(dark = dark)
        tap("export_start")
        emit(event { copy(stopped = true, files = 4) })
        rule.onNodeWithTag("export_result_title").assertTextEquals("Đã dừng xuất")
        rule.onNodeWithTag("export_retry").assertIsDisplayed()
        shot("stopped", dark)
    }

    @Test fun stoppedLight() = stopped(false)
    @Test fun stoppedDark() = stopped(true)

    private fun failed(dark: Boolean) {
        source.folder = "Music"
        show(dark = dark)
        tap("export_start")
        emit(event { copy(error = "Hết chỗ trống trên điện thoại hoặc ở nơi lưu - dọn bớt rồi xuất lại") })
        rule.onNodeWithTag("export_error").assertIsDisplayed()
        rule.onNodeWithTag("export_retry").assertIsDisplayed()
        shot("failed", dark)
    }

    @Test fun failedLight() = failed(false)
    @Test fun failedDark() = failed(true)

    private fun notStarted(dark: Boolean) {
        source.folder = "Music"
        source.startError = "Không mở được thư mục đã chọn - chọn lại nơi lưu"
        show(dark = dark)
        tap("export_start")
        rule.onNodeWithTag("export_problem").assertIsDisplayed()
        rule.onNodeWithTag("export_start").assertIsEnabled()
        shot("not_started", dark)
    }

    @Test fun notStartedLight() = notStarted(false)
    @Test fun notStartedDark() = notStarted(true)

    // ---- kịch bản bấm thật ----

    @Test
    fun theMp3MusicNoteAppearsOnlyWithMusicOnAndOnlyForMp3() {
        source.folder = "Music"
        source.music = ExportMusic(available = true, enabled = true)
        show()
        rule.onNodeWithTag("export_mp3_music").assertIsDisplayed().assertTextEquals(ExportText.MP3_MUSIC_NOTE)
        tap("export_music")
        rule.onNodeWithTag("export_mp3_music").assertDoesNotExist()
        tap("export_music")
        tap("export_format_m4b")
        rule.onNodeWithTag("export_mp3_music").assertDoesNotExist()
    }

    @Test
    fun startSendsTheChosenOptionsToTheCore() {
        source.music = ExportMusic(available = true, enabled = false)
        show()
        tap("export_format_m4b")
        tap("export_music")
        tap("export_start")
        val start = source.starts.single()
        assertEquals(ExportKind.M4b, start.kind)
        assertTrue("ô nhạc bật thì lõi nhận nhạc", start.music)
        assertEquals("content://doc/Truyen.m4b", start.file)
        rule.onNodeWithTag("export_running").assertIsDisplayed()
    }

    @Test
    fun mp3WithoutAFolderAsksTheSystemFirstThenStarts() {
        show()
        rule.onNodeWithTag("export_folder").assertIsDisplayed()
        tap("export_start")
        assertEquals(listOf("content://tree/Music"), source.keptFolders)
        assertEquals(ExportKind.Mp3, source.starts.single().kind)
    }

    @Test
    fun progressWordsFollowTheCore() {
        source.folder = "Music"
        show()
        tap("export_start")
        emit(event { copy(done = 3, total = 12) })
        rule.onNodeWithTag("export_progress_text").assertTextEquals("3/12 chương")
        emit(event { copy(done = 6, total = 12, percent = 52) })
        rule.onNodeWithTag("export_progress_text").assertTextEquals("6/12 chương · 52%")
    }

    @Test
    fun stopReachesTheCoreAndTheButtonSaysSo() {
        source.folder = "Music"
        show()
        tap("export_start")
        tap("export_stop")
        assertEquals(listOf(ExportKind.Mp3 to "b1"), source.cancels)
        rule.onNodeWithTag("export_stop").assertTextEquals("Đang dừng")
        emit(event { copy(stopped = true, files = 2) })
        rule.onNodeWithTag("export_result_title").assertTextEquals("Đã dừng xuất")
    }

    @Test
    fun aFinishedFileCanBeOpenedAndShared() {
        show()
        tap("export_format_m4b")
        tap("export_start")
        emit(event(ExportKind.M4b) { copy(finished = true, name = "De Men.m4b", size = 1L shl 28, uri = "content://doc/Truyen.m4b") })
        tap("export_open")
        assertEquals(listOf("content://doc/Truyen.m4b"), source.opened)
        tap("export_share")
        assertEquals(listOf("content://doc/Truyen.m4b" to book.title), shared)
    }

    @Test
    fun aFinishedFolderCanBeOpenedButNotShared() {
        source.folder = "Music"
        show()
        tap("export_start")
        emit(event { copy(finished = true, files = 12, chaptersTotal = 12, uri = "content://tree/Music") })
        tap("export_open_folder")
        assertEquals(listOf("content://tree/Music"), source.openedFolders)
        count("export_share", 0)
    }

    @Test
    fun anErrorFromTheCoreIsShownAndTryAgainStartsAgain() {
        source.folder = "Music"
        show()
        tap("export_start")
        emit(event { copy(error = "Hết chỗ trống") })
        rule.onNodeWithTag("export_error").assertTextEquals("Hết chỗ trống")
        source.run = "run-2"
        tap("export_retry")
        assertEquals(2, source.starts.size)
        rule.onNodeWithTag("export_running").assertIsDisplayed()
    }

    @Test
    fun leavingTheScreenKeepsTheRunAndComingBackShowsIt() {
        source.folder = "Music"
        show()
        tap("export_start")
        emit(event { copy(done = 4, total = 12) })
        ui { visible = false }
        count("export_screen", 0)
        emit(event { copy(done = 7, total = 12) })
        ui { visible = true }
        rule.onNodeWithTag("export_running").assertIsDisplayed()
        rule.onNodeWithTag("export_progress_text").assertTextEquals("7/12 chương")
        assertEquals("lượt chạy không bị khởi động lại", 1, source.starts.size)
    }

    @Test
    fun aRunThatFinishedWhileAwayShowsItsResultOnce() {
        source.folder = "Music"
        show()
        tap("export_start")
        ui { visible = false }
        emit(event { copy(finished = true, files = 12, chaptersTotal = 12, uri = "content://tree/Music") })
        ui { visible = true }
        rule.onNodeWithTag("export_result_title").assertTextEquals("Đã xuất 12 chương")
        ui { visible = false }
        ui { visible = true }
        rule.onNodeWithTag("export_options").assertIsDisplayed()
    }

    @Test
    fun theBackgroundRowOpensTheSettingsOfTheApp() {
        source.background = BackgroundView("OPPO", allowed = false)
        show()
        tap("export_background")
        assertEquals(1, settings)
    }

    @Test
    fun theBackgroundRowIsHiddenWhenTheAppMayRunInTheBackground() {
        show()
        count("export_background", 0)
    }

    @Test
    fun theStartButtonSitsAtTheFootOfTheScreenAndWithinThumbReach() {
        source.folder = "Music"
        show()
        val root = rule.onRoot().getUnclippedBoundsInRoot()
        val start = rule.onNodeWithTag("export_start").getUnclippedBoundsInRoot()
        assertTrue("nút Bắt đầu phải ở nửa dưới màn: $start / $root", start.top > (root.bottom - root.top) / 2)
        assertTrue("nút Bắt đầu vượt mép dưới: $start / $root", start.bottom <= root.bottom)
        assertTrue("nút Bắt đầu phải cao ít nhất 48dp", start.bottom - start.top >= 48.dp)
    }

    @Test
    fun everyRowHintOnThePageIsDrawnInOneStyle() {
        source.folder = "Music"
        source.music = ExportMusic(available = true, enabled = true)
        source.history = listOf(past)
        source.background = BackgroundView("OPPO", allowed = false)
        show()
        val hints = listOf("Music", ExportText.MUSIC_MIX_HINT, "Bản MP3 bạn xuất trước đây", "Xuất sách dài khi tắt màn hình")
        fun sizeOf(text: String): androidx.compose.ui.unit.TextUnit {
            val layouts = mutableListOf<TextLayoutResult>()
            rule.onNode(hasText(text, substring = true), useUnmergedTree = true).fetchSemanticsNode().config[SemanticsActions.GetTextLayoutResult].action!!(layouts)
            return layouts.single().layoutInput.style.fontSize
        }
        val sizes = hints.map(::sizeOf)
        // Mục "Đã xuất" nằm cuối danh sách: cuộn tới nó rồi đo cùng thước.
        rule.onNodeWithTag("export_options").performScrollToNode(hasTestTag("export_past"))
        rule.waitForIdle()
        val all = sizes + sizeOf("2 chương đã đổi từ lần xuất này")
        assertEquals("dòng mô tả các hàng của màn Xuất phải cùng cỡ chữ: $hints -> $all", 1, all.distinct().size)
    }

    @Test
    @Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi", fontScale = 1.3f)
    fun nothingIsCutAtLargeFontScale() {
        source.folder = "Music"
        source.music = ExportMusic(available = true, enabled = true)
        source.history = listOf(past)
        source.background = BackgroundView("OPPO", allowed = false)
        show()
        assertTrue(rule.assertNoTextOverflow() > 4)
    }

    @Test
    fun backIsForwardedToTheShell() {
        show()
        rule.onNodeWithContentDescription("Quay lại").performClick()
        rule.waitForIdle()
        assertEquals(1, backs)
    }

    private fun count(tag: String, n: Int) = rule.onAllNodesWithTag(tag).assertCountEquals(n)
}
