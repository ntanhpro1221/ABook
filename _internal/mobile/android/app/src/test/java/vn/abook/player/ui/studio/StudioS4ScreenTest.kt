package vn.abook.player.ui.studio

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import java.io.ByteArrayInputStream

/** Các màn của S4 trên JVM với nguồn giả: Xuất, Nhật ký, Sách mới, nút "Sách mới" ở danh sách, và ba mục mới trong "Thêm". */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class StudioS4ScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val never: suspend (Long) -> Unit = { awaitCancellation() }
    private val sheets = SheetHost()
    private val source = FakeStudioSource(listOf(studioBook()))
    private val hub = StudioHub(source, scope)

    private fun show(content: @Composable () -> Unit) {
        rule.setContent { AbookTheme(false) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { content(); SheetLayer(sheets) } } }
        rule.waitForIdle()
    }

    private fun tag(tag: String) = rule.onNodeWithTag(tag)
    private fun absent(tag: String) = assertEquals(0, rule.onAllNodesWithTag(tag).fetchSemanticsNodes().size)
    private fun project() = StudioProjectState(hub.session(""), "b1", StudioTab.Chapters, never)

    // ---- Xuất ----

    @Test fun exportingStartsOnceThenShowsProgressAndAConfirmedCancel() {
        val state = project()
        show { StudioExportScreen(state, sheets, {}, true) }
        tag("studio_export_kind_bookfile-job").assertIsDisplayed()
        tag("studio_export_lead").assertIsDisplayed()
        tag("studio_export_start").performClick()
        rule.waitForIdle()
        assertEquals(listOf(StudioExportKind.BookFile), source.exportStarts.map { it.first })
        tag("studio_export_busy").assertIsDisplayed()
        tag("studio_export_cancel").performClick()
        rule.waitForIdle()
        tag("studio_export_cancel_sheet").assertIsDisplayed()
        assertTrue(source.exportCancels.isEmpty())
        tag("studio_export_cancel_yes").performClick()
        rule.waitForIdle()
        assertEquals(listOf(StudioExportKind.BookFile), source.exportCancels)
    }

    @Test fun aMissingFfmpegIsExplainedWithNoDownloadButton() {
        source.exportOptionsView = StudioExportOptions(ffmpegReady = false)
        val state = project()
        show { StudioExportScreen(state, sheets, {}, true) }
        absent("studio_export_ffmpeg")
        tag("studio_export_kind_m4b-job").performClick()
        rule.waitForIdle()
        tag("studio_export_ffmpeg").assertIsDisplayed()
    }

    @Test fun aFinishedExportSaysWhichMachineHoldsTheFile() {
        source.exportJobs[StudioExportKind.BookFile] = studioExportJob("done", finishedAgo = 30.0, result = exportResult())
        val state = project()
        show { StudioExportScreen(state, sheets, {}, true) }
        tag("studio_export_done").assertIsDisplayed()
        tag("studio_export_done_line").assertIsDisplayed()
    }

    @Test fun aListenOnlyPhoneSeesThePermissionCardNotTheForm() {
        source.exportError = vn.abook.player.StudioError.ListenOnly()
        val state = project()
        show { StudioExportScreen(state, sheets, {}, true) }
        absent("studio_export_start")
    }

    // ---- Nhật ký ----

    @Test fun theLogShowsEachEntryAndTheTechnicalSwitchAsksAgain() {
        source.activityItems = listOf(StudioLogItem("1", 100.0, "info", "", "Bắt đầu"), StudioLogItem("2", 200.0, "error", "E1", "Hỏng"))
        val state = project()
        show { StudioActivityScreen(state, {}, true) }
        tag("studio_log_error").assertIsDisplayed()
        tag("studio_activity_technical").performClick()
        rule.waitForIdle()
        assertEquals(listOf(false, true), source.activityCalls)
    }

    // ---- Sách mới ----

    @Test fun theLimitIsStatedBeforeAnyFileIsPicked() {
        val state = StudioNewState(hub.session(""), "Tải lên")
        show { StudioNewScreen(state, {}, {}, true) }
        tag("studio_new_limit").assertIsDisplayed()
        tag("studio_new_pick").assertIsDisplayed()
        tag("studio_new_none").assertIsDisplayed()
    }

    @Test fun aSentFileOpensTheChapterStep() {
        source.scanView = ScanView(listOf(scannedChapter("c1", "Chương 1")), emptyList(), emptyList(), emptyList(), "Tắt đèn", emptyList())
        val state = StudioNewState(hub.session(""), "Tải lên")
        show { StudioNewScreen(state, {}, {}, true) }
        state.add(listOf(PickedFile("a.txt", 3) { ByteArrayInputStream("xyz".toByteArray()) }))
        rule.waitForIdle()
        tag("studio_new_row_0").assertIsDisplayed()
        tag("studio_new_next").performClick()
        rule.waitForIdle()
        tag("studio_new_chapters").assertIsDisplayed()
        tag("studio_new_totals").assertIsDisplayed()
    }

    @Test fun theNewBookButtonOnTheListOpensTheCreator() {
        var asked = 0
        val state = StudioHomeState(hub.session(""), never)
        show { StudioHomeScreen(state, {}, {}, true) { asked++ } }
        tag("studio_new").performClick()
        assertEquals(1, asked)
    }

    // ---- "Thêm" ----

    @Test fun theMoreMenuOffersExportCoverAndLog() {
        val opened = ArrayList<StudioSubKind>()
        val state = project()
        show { StudioProjectScreen(state, sheets, {}, {}, true) { opened += it } }
        tag("studio_more").performClick()
        rule.waitForIdle()
        tag("studio_more_export").assertIsDisplayed()
        tag("studio_more_cover").assertIsDisplayed()
        tag("studio_more_activity").performClick()
        rule.waitForIdle()
        assertEquals(listOf(StudioSubKind.Activity), opened)
    }
}
