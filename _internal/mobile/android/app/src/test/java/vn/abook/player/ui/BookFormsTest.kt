package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.addbook.*
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.editbook.*
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.nav.NavState
import vn.abook.player.ui.shell.ScreenStack
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class BookFormsTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val preview = ImportPreview("Chuyến phà cuối ngày", "Nguyễn Nhật Ánh", listOf(ImportChapter(1, "Chương 1")),
        suggestions = listOf(Suggestion(1, "Dịch: Nhóm Lục Bình"), Suggestion(1, "Nguồn: Thư viện của bạn")))
    private val longTitle = "Chuyến phà cuối ngày và những câu chuyện về một người khách lạ trở về ngôi làng bên kia dòng sông vào buổi chiều mùa thu"
    private val edit = EditSnapshot("b", "Chuyến phà cuối ngày", "Nguyễn Nhật Ánh", listOf(EditChapter(1, "Chương 1")),
        sendable = true, pending = 2)

    private fun show(dark: Boolean = false, content: @Composable () -> Unit) {
        rule.setContent { AbookTheme(dark) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { content() } } }
    }
    private fun shot(name: String) = rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")
    private fun add(state: ImportState, dark: Boolean, name: String) {
        show(dark) { AddBookScreen(state, {}, {}, {}, {}, {}, {}) }
        shot(name)
    }
    private fun review(dark: Boolean, name: String) {
        var state by mutableStateOf(ImportState(currentId = 1, preview = preview, choices = ImportLogic.defaults(preview)))
        show(dark) { ImportReviewScreen(state, {}, { state = state.copy(choices = it(state.choices)) }, {}, {}, {}) }
        shot(name)
    }
    private fun edit(dark: Boolean, name: String, title: String = edit.title) {
        val book = edit.copy(title = title)
        show(dark) { EditBookScreen(EditState(book, EditLogic.draft(book), loading = false, note = "Đã lưu"), CoverLoader(), {}, {}, {}, {}, {}, {}, {}) }
        shot(name)
    }

    @Test fun emptyAddLight() = add(ImportState(), false, "add_empty_light")
    @Test fun emptyAddDark() = add(ImportState(), true, "add_empty_dark")
    private val queue = ImportState(items = listOf(
        ImportItem(1, "a", "Chuyến phà cuối ngày.epub", stage = ImportStage.Added),
        ImportItem(2, "b", "Người khách lạ.txt", stage = ImportStage.Reading),
        ImportItem(3, "c", "Những ngày thơ ấu.docx"),
    ))
    @Test fun queueProgressLight() = add(queue, false, "add_queue_light")
    @Test fun queueProgressDark() = add(queue, true, "add_queue_dark")
    private val error = ImportState(items = listOf(ImportItem(1, "bad", "Sách tải dở.epub", stage = ImportStage.Error,
        problem = "File EPUB hỏng hoặc sai định dạng. Bạn hãy tải lại rồi thử lại.")))
    @Test fun errorLight() = add(error, false, "add_error_light")
    @Test fun errorDark() = add(error, true, "add_error_dark")
    @Test fun suggestionsLight() = review(false, "add_suggestions_light")
    @Test fun suggestionsDark() = review(true, "add_suggestions_dark")
    @Test fun editLight() = edit(false, "edit_book_light")
    @Test fun editDark() = edit(true, "edit_book_dark")
    @Test fun longTitleLight() = edit(false, "edit_long_title_light", longTitle)
    @Test fun longTitleDark() = edit(true, "edit_long_title_dark", longTitle)

    @Test fun queueRowsStayInOrderWithStableIdentity() {
        add(queue, false, "add_queue_order_light")
        val rows = (1L..3L).map { rule.onNodeWithTag("import_$it").fetchSemanticsNode().boundsInRoot.top }
        assertTrue(rows.zipWithNext().all { it.first < it.second })
    }

    @Test fun suggestionOnlyChangesWhenTheUserAcceptsAndCanBeReversed() {
        val source = FakeImportSource(preview)
        val queue = ImportQueue(source, CoroutineScope(Dispatchers.Main.immediate))
        show {
            val state by queue.state.collectAsState()
            ImportReviewScreen(state, {}, queue::choose, queue::revise, queue::add, queue::skip)
        }
        rule.runOnIdle { queue.enqueue(listOf("a")) }
        rule.onNodeWithTag("suggestion_Dịch: Nhóm Lục Bình").assertIsDisplayed()
        assertTrue(queue.state.value.choices.skipped.isEmpty())
        assertEquals(0, source.adds)
        rule.onNodeWithTag("suggestion_Dịch: Nhóm Lục Bình").performClick()
        assertEquals(setOf("Dịch: Nhóm Lục Bình"), queue.state.value.choices.skipped)
        assertEquals(0, source.adds)
        rule.onNodeWithTag("confirm_import").performClick()
        assertEquals(1, source.adds)
        assertEquals(setOf("Dịch: Nhóm Lục Bình"), source.addedChoices?.skipped)
    }

    @Test fun metadataTypingAndBackSavesWithoutAConfirmButton() {
        val source = FakeEditSource(edit)
        lateinit var editor: BookEditor
        show {
            val scope = rememberCoroutineScope()
            editor = remember { BookEditor("b", source, scope) }
            val state by editor.state.collectAsState()
            EditBookScreen(state, CoverLoader(), {}, editor::change, {}, {}, {}, editor::send, editor::retry)
        }
        rule.onNodeWithTag("edit_author").performTextReplacement("")
        rule.mainClock.advanceTimeBy(1000)
        rule.waitForIdle()
        rule.runOnIdle { assertEquals("", editor.state.value.draft?.author) }
        rule.onAllNodesWithText("Lưu").assertCountEquals(0)
    }

    @Test fun backClosesExactlyOneLayerAndKeepsQueueChoices() {
        lateinit var nav: NavState
        show {
            val scope = rememberCoroutineScope()
            nav = remember { NavState(scope) }
            androidx.activity.compose.BackHandler(nav.canPop) { nav.pop() }
            ScreenStack(nav, root = { AddBookScreen(ImportState(), {}, {}, {}, {}, {}, {}) }) { destination ->
                when (destination) {
                    is Destination.ImportReview -> ImportReviewScreen(ImportState(preview = preview, choices = ImportLogic.defaults(preview)), nav::pop, {}, {}, {}, {})
                    else -> BookForm("Chú thích", nav::pop, "nested") { }
                }
            }
        }
        rule.runOnIdle { nav.push(Destination.ImportReview(1)) }
        rule.waitForIdle()
        rule.runOnIdle { nav.push(Destination.AddBook) }
        rule.waitForIdle()
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        rule.runOnIdle { assertEquals(1, nav.stack.size) }
        rule.onNodeWithTag("import_review_screen").assertIsDisplayed()
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        rule.runOnIdle { assertEquals(0, nav.stack.size) }
        rule.onNodeWithTag("add_book_screen").assertIsDisplayed()
    }
}
