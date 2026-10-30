package vn.abook.player.ui.studio

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.hasAnyAncestor
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
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
import vn.abook.player.StudioError
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Hai màn Studio trên JVM với nguồn giả: danh sách theo nhóm, thẻ quyền, một nút chính theo trạng thái, Dừng sau xác nhận, và chỉ hỏi khi màn đang hiện. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class StudioScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val never: suspend (Long) -> Unit = { awaitCancellation() }
    private val sheets = SheetHost()
    private val source = FakeStudioSource()
    private val hub = StudioHub(source, scope)
    private var backs = 0
    private var listened = 0
    private val opened = ArrayList<String>()

    private fun show(content: @androidx.compose.runtime.Composable () -> Unit) {
        rule.setContent { AbookTheme(false) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { content(); SheetLayer(sheets) } } }
        rule.waitForIdle()
    }

    private fun home(active: Boolean = true) = StudioHomeState(hub.session(""), never).also { state ->
        show { StudioHomeScreen(state, { backs++ }, { opened += it.id }, active) }
    }

    private fun project(id: String = "b1", active: Boolean = true, tab: StudioTab = StudioTab.Chapters) = StudioProjectState(hub.session(""), id, tab, never).also { state ->
        show { StudioProjectScreen(state, sheets, { backs++ }, { listened++ }, active) }
    }

    private fun tag(tag: String) = rule.onNodeWithTag(tag)
    private fun absent(tag: String) = assertEquals(0, rule.onAllNodesWithTag(tag).fetchSemanticsNodes().size)

    // ---- danh sách ----

    @Test fun theListGroupsProjectsByWhatNeedsYou() {
        source.books = listOf(
            studioBook("a", title = "Đang chạy", running = true, canPause = true), studioBook("b", title = "Chờ duyệt", phase = "casting", precastHeld = true),
            studioBook("c", title = "Xong rồi", phase = "done", statusLabel = "Đã xong", chaptersCompleted = 10),
        )
        home()
        tag("studio_group_Working").assertIsDisplayed()
        tag("studio_group_Review").assertIsDisplayed()
        tag("studio_group_Rest").assertIsDisplayed()
        tag("studio_book_a").assertIsDisplayed()
        tag("studio_book_b").assertIsDisplayed()
        tag("studio_book_c").assertIsDisplayed()
        tag("studio_book_c").performClick()
        assertEquals(listOf("c"), opened)
    }

    @Test fun anEmptyMachineSaysSoWithoutAComingSoonRow() {
        home()
        tag("studio_empty").assertIsDisplayed()
        absent("studio_group_Working")
    }

    @Test fun listenOnlyReplacesTheWholeListWithOneCardAndRetryAsksAgain() {
        source.error = StudioError.ListenOnly()
        val state = home()
        tag("studio_permission").assertIsDisplayed()
        tag("studio_permission_line").assertTextEquals("Bật “Cho phép điều khiển sản xuất” trên máy bàn rồi quay lại.")
        absent("studio_list")
        source.error = null
        source.books = listOf(studioBook("a"))
        tag("studio_permission_retry").performClick()
        rule.waitForIdle()
        tag("studio_book_a").assertIsDisplayed()
        absent("studio_permission")
        assertTrue(state.poll.value.error == null)
    }

    @Test fun anOfflineFirstLoadOffersRetry() {
        source.error = StudioError.Offline()
        home()
        tag("studio_home_problem").assertIsDisplayed()
    }

    @Test fun aScreenCoveredByAnotherAsksNothing() {
        source.books = listOf(studioBook("a"))
        home(active = false)
        assertEquals(0, source.libraryCalls.size)
    }

    @Test fun aVisibleScreenAsksOnce() {
        source.books = listOf(studioBook("a"))
        home(active = true)
        assertEquals(1, source.libraryCalls.size)
    }

    // ---- dự án ----

    private fun withBook(book: StudioBook, chapters: List<StudioChapter> = listOf(studioChapter(1), studioChapter(2, redo = true, statusLabel = "Chờ thu lại"))) {
        source.books = listOf(book)
        source.chapters = mapOf(book.id to chapters)
    }

    @Test fun oneButtonNamedByTheStateAndNeverAComingSoonRow() {
        withBook(studioBook(running = true, canPause = true))
        project()
        tag("studio_primary").assertIsDisplayed()
        tag("studio_primary").assertTextEquals("Tạm dừng")
        assertEquals(1, rule.onAllNodesWithTag("studio_primary").fetchSemanticsNodes().size)
        tag("studio_status").assertTextEquals("Đang thu âm")
        tag("studio_progress").assertIsDisplayed()
        tag("studio_percent").assertTextEquals("40%")
    }

    @Test fun pressingPauseSendsPauseAndReadsAgain() {
        withBook(studioBook(running = true, canPause = true))
        project()
        tag("studio_primary").performClick()
        rule.waitForIdle()
        assertEquals(listOf("b1" to StudioCommand.Pause(true)), source.commands)
        assertTrue(source.bookCalls.size >= 2)
    }

    @Test fun startingAndStoppingAreOnlyStatusNotButtons() {
        withBook(studioBook(starting = true))
        project()
        // Nút nhạt đi khi chỉ báo trạng thái: chữ nằm ở con của nó.
        tag("studio_primary").assertIsNotEnabled()
        rule.onNode(hasText("Đang khởi động") and hasAnyAncestor(hasTestTag("studio_primary"))).assertIsDisplayed()
    }

    @Test fun stopHidesBehindMoreAndAConfirmWithPauseFirstDuringAnalysis() {
        withBook(studioBook(phase = "analysis", statusLabel = "Đang phân tích", running = true, canPause = true))
        project()
        tag("studio_more").assertIsDisplayed()
        tag("studio_more").performClick()
        rule.waitForIdle()
        tag("studio_more_stop").performClick()
        rule.waitForIdle()
        tag("studio_stop").assertIsDisplayed()
        tag("studio_stop_pause").assertIsDisplayed()
        tag("studio_stop_confirm").assertIsDisplayed()
        // Chưa gửi lệnh nào cho tới khi xác nhận.
        assertTrue(source.commands.isEmpty())
        tag("studio_stop_confirm").performClick()
        rule.waitForIdle()
        assertEquals(listOf("b1" to StudioCommand.Stop), source.commands)
    }

    @Test fun keepingItRunningSendsNothing() {
        withBook(studioBook(running = true, canPause = true))
        project()
        tag("studio_more").performClick()
        rule.waitForIdle()
        tag("studio_more_stop").performClick()
        rule.waitForIdle()
        tag("studio_stop_keep").performClick()
        rule.waitForIdle()
        assertTrue(source.commands.isEmpty())
    }

    @Test fun resumingACutAnalysisAsksFirst() {
        withBook(studioBook(phase = "analysis", analysisInterrupted = true))
        project()
        tag("studio_primary").assertTextEquals("Tiếp tục")
        tag("studio_primary").performClick()
        rule.waitForIdle()
        tag("studio_resume").assertIsDisplayed()
        assertTrue(source.commands.isEmpty())
        tag("studio_resume_confirm").performClick()
        rule.waitForIdle()
        assertEquals(listOf("b1" to StudioCommand.Start), source.commands)
    }

    @Test fun aFinishedBookWithEditsAsksBeforeApplying() {
        withBook(studioBook(phase = "done", statusLabel = "Đã xong", pendingChanges = 2))
        project()
        tag("studio_primary").assertTextEquals("Áp dụng 2 thay đổi")
        tag("studio_primary").performClick()
        rule.waitForIdle()
        tag("studio_apply").assertIsDisplayed()
        tag("studio_apply_confirm").performClick()
        rule.waitForIdle()
        assertEquals(listOf("b1" to StudioCommand.Start), source.commands)
    }

    @Test fun listeningGoesToTheLibrary() {
        withBook(studioBook(phase = "done", statusLabel = "Đã xong"))
        project()
        tag("studio_primary").assertTextEquals("Nghe trong Thư viện")
        tag("studio_primary").performClick()
        assertEquals(1, listened)
        assertTrue(source.commands.isEmpty())
    }

    @Test fun aQueuedBookCanLeaveTheQueueButNotBeStopped() {
        withBook(studioBook(queuePosition = 2, chaptersCompleted = 0))
        project()
        tag("studio_primary").assertTextEquals("Bỏ xếp hàng")
        tag("studio_action_note").assertIsDisplayed()
        tag("studio_primary").performClick()
        rule.waitForIdle()
        assertEquals(listOf("b1" to StudioCommand.Dequeue), source.commands)
    }

    @Test fun chaptersShowOnlyWhatDeviatesAndMusicHasItsOwnTab() {
        withBook(studioBook(phase = "done", statusLabel = "Đã xong"), listOf(studioChapter(1), studioChapter(2, redo = true, statusLabel = "Chờ thu lại")))
        val state = project()
        tag("studio_chapter_1").assertIsDisplayed()
        tag("studio_chapter_2").assertIsDisplayed()
        rule.runOnIdle { state.tab = StudioTab.Music }
        rule.waitForIdle()
        tag("studio_music_settings").assertExists()
        absent("studio_chapter_1")
    }

    @Test fun listenOnlyOnAProjectIsTheSameSingleCard() {
        source.error = StudioError.ListenOnly()
        project()
        tag("studio_permission").assertIsDisplayed()
        absent("studio_primary")
        absent("studio_more")
    }

    @Test fun aMissingProjectOnlyOffersTheWayBack() {
        project("zzz")
        tag("studio_gone").assertIsDisplayed()
        tag("studio_gone_back").performClick()
        assertEquals(1, backs)
        absent("studio_primary")
    }

    @Test fun anOfflineMachineKeepsThePageAndSaysSo() {
        withBook(studioBook(running = true, canPause = true))
        val state = project()
        tag("studio_primary").assertIsDisplayed()
        source.error = StudioError.Offline()
        rule.runOnIdle { kotlinx.coroutines.runBlocking { state.refresh() } }
        rule.waitForIdle()
        tag("studio_link").assertIsDisplayed()
        tag("studio_primary").assertIsDisplayed()
    }

    @Test fun aFailedCommandShowsItsReasonUnderTheButton() {
        withBook(studioBook(running = true, canPause = true))
        source.commandError = StudioError.Busy("Máy đang bận việc khác")
        project()
        tag("studio_primary").performClick()
        rule.waitForIdle()
        tag("studio_problem").assertIsDisplayed()
        tag("studio_primary").assertIsEnabled()
    }

    @Test fun aCoveredProjectAsksNothing() {
        withBook(studioBook(running = true, canPause = true))
        project(active = false)
        assertEquals(0, source.bookCalls.size)
    }
}
