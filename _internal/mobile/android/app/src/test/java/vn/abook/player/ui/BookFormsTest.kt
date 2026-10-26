package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
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
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
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
    private val chapters = listOf(
        ImportChapter(1, "Lời nói đầu", included = false, note = "Ngắn"),
        ImportChapter(2, "Chương 1"),
        ImportChapter(3, "Chương 2: Một tên chương khá dài để thử xuống dòng trong hàng"),
    )
    private val preview = ImportPreview("Chuyến phà cuối ngày", "Nguyễn Nhật Ánh", chapters,
        suggestions = listOf(Suggestion(2, "Dịch: Nhóm Lục Bình"), Suggestion(3, "Dịch: Nhóm Lục Bình"), Suggestion(2, "Nguồn: Thư viện của bạn")))
    private val longTitle = "Chuyến phà cuối ngày và những câu chuyện về một người khách lạ trở về ngôi làng bên kia dòng sông vào buổi chiều mùa thu"
    private val edit = EditSnapshot("b", "Chuyến phà cuối ngày", "Nguyễn Nhật Ánh",
        listOf(EditChapter(1, "Chương 1"), EditChapter(2, "Khách qua sông", original = "Chương 2"), EditChapter(3, "Chương 3: Một tên chương khá dài để xuống dòng")),
        sendable = true, pending = 2)

    private fun show(dark: Boolean = false, content: @Composable () -> Unit) {
        rule.setContent { AbookTheme(dark) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { content() } } }
    }
    private fun shot(name: String) {
        rule.assertIconLedTextColumns()
        rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")
    }
    private fun add(state: ImportState, dark: Boolean, name: String?) {
        show(dark) { AddBookScreen(state, {}, {}, {}, {}, {}, {}) }
        if (name != null) shot(name)
    }
    private fun review(dark: Boolean, name: String?, picked: ImportPreview = preview, names: Map<Int, String> = mapOf(3 to "Khách qua sông")) {
        var state by mutableStateOf(ImportState(currentId = 1, preview = picked, choices = ImportLogic.defaults(picked).copy(names = names)))
        show(dark) { ImportReviewScreen(state, {}, { state = state.copy(choices = it(state.choices)) }, {}, {}, {}) }
        if (name != null) shot(name)
    }
    private fun edit(dark: Boolean, name: String, title: String = edit.title, state: (EditSnapshot) -> EditState = { EditState(it, EditLogic.draft(it), loading = false) }) {
        val book = edit.copy(title = title)
        show(dark) { EditBookScreen(state(book), CoverLoader(), {}, {}, {}, {}, {}, {}) }
        shot(name)
    }

    // --- Thêm sách: chưa chọn gì ---
    @Test fun emptyAddLight() = add(ImportState(), false, "add_empty_light")
    @Test fun emptyAddDark() = add(ImportState(), true, "add_empty_dark")

    @Test fun emptyAddIsOneCaptionAndTwoActions() {
        add(ImportState(), false, "add_empty_light")
        // Cùng chữ với lời đầu hộp Thêm sách của web (listen/AddBook.tsx); không câu thứ hai.
        rule.onNodeWithText("EPUB, DOCX, PDF có chữ, TXT hoặc file .abook. Chọn được nhiều file.").assertIsDisplayed()
        rule.onAllNodesWithText("Chọn sách từ máy bạn").assertCountEquals(0)
        rule.onNodeWithText("Chọn file sách").assertIsDisplayed()
        rule.onNodeWithText("Chọn thư mục TXT").assertIsDisplayed()
        // Không còn tiêu đề giả của một biểu mẫu, không còn câu hướng dẫn.
        rule.onAllNodesWithText("Sách của bạn").assertCountEquals(0)
        rule.onAllNodesWithText("Hàng đợi nhập").assertCountEquals(0)
    }

    // --- Hàng đợi ---
    private val queue = ImportState(items = listOf(
        ImportItem(1, "a", "Chuyến phà cuối ngày.epub", stage = ImportStage.Added, bookId = "a"),
        ImportItem(2, "b", "Người khách lạ và những câu chuyện bên kia dòng sông dài.txt", stage = ImportStage.Reading),
        ImportItem(3, "c", "Những ngày thơ ấu.docx", stage = ImportStage.Review),
        ImportItem(4, "d", "Truyện ngắn", folder = true, stage = ImportStage.Waiting),
        ImportItem(5, "e", "Sách tải dở.epub", stage = ImportStage.Error, problem = "File EPUB hỏng hoặc sai định dạng. Bạn hãy tải lại rồi thử lại."),
    ))
    @Test fun queueLight() = add(queue, false, "add_queue_light")
    @Test fun queueDark() = add(queue, true, "add_queue_dark")
    private val error = ImportState(items = listOf(ImportItem(1, "bad", "Sách tải dở.epub", stage = ImportStage.Error,
        problem = "File EPUB hỏng hoặc sai định dạng. Bạn hãy tải lại rồi thử lại.")))
    @Test fun errorLight() = add(error, false, "add_error_light")
    @Test fun errorDark() = add(error, true, "add_error_dark")

    @Test fun queueRowsStayInOrderWithStableIdentity() {
        add(queue, false, null)
        val rows = (1L..4L).map { rule.onNodeWithTag("import_$it").fetchSemanticsNode().boundsInRoot.top }
        assertTrue(rows.zipWithNext().all { it.first < it.second })
    }

    @Test fun finishedAndReviewRowsAreTheTapTargetsAndFailedRowRetries() {
        val opened = mutableListOf<String>()
        val reviewed = mutableListOf<Long>()
        val retried = mutableListOf<Long>()
        show { AddBookScreen(queue, {}, {}, {}, { reviewed += it }, { retried += it }, { opened += it }) }
        // Không còn liên kết "Mở sách" / "Xem trước" tách rời: chạm chính hàng.
        rule.onAllNodesWithText("Mở sách").assertCountEquals(0)
        rule.onAllNodesWithText("Xem trước").assertCountEquals(0)
        rule.onNodeWithTag("open_1").performClick()
        rule.onNodeWithTag("review_3").performClick()
        rule.onNodeWithTag("retry_5").performClick()
        assertEquals(listOf("a"), opened)
        assertEquals(listOf(3L), reviewed)
        assertEquals(listOf(5L), retried)
        // Hàng đang đọc / đang chờ không chạm được.
        rule.onNodeWithTag("open_2").assertHasNoClickAction()
        rule.onNodeWithTag("open_4").assertHasNoClickAction()
    }

    @Test fun queueRowsShareTheFirstLineCenterOnBothSides() {
        add(queue, false, null)
        for (row in listOf("import_1", "import_2", "import_3", "import_4", "import_5")) {
            sharesFirstLine(row, "row_leading")
        }
        sharesFirstLine("import_1", "row_trailing")
        sharesFirstLine("import_3", "row_trailing")
        sharesFirstLine("import_5", "row_trailing")
    }

    /** Tâm của biểu tượng / nút ở một bên hàng trùng tâm dòng chữ đầu (đỉnh tên + 12). Đúng cả khi tên xuống nhiều dòng. */
    private fun sharesFirstLine(row: String, side: String) {
        val title = rule.onNode(hasTestTag("row_title") and hasAnyAncestor(hasTestTag(row)), useUnmergedTree = true).getUnclippedBoundsInRoot()
        val edge = rule.onNode(hasTestTag(side) and hasAnyAncestor(hasTestTag(row)), useUnmergedTree = true).getUnclippedBoundsInRoot()
        val first = title.top + 12.dp
        val center = (edge.top + edge.bottom) / 2
        assertTrue("$row/$side: tâm dòng đầu $first, tâm biểu tượng $center", (first - center).value in -0.6f..0.6f)
    }

    // --- Xem trước ---
    @Test fun reviewLight() = review(false, "add_review_light")
    @Test fun reviewDark() = review(true, "add_review_dark")

    @Test fun reviewHasNoInstructionsNoGlyphCheckboxesAndAHeaderGap() {
        review(false, "add_review_light")
        for (gone in listOf("Bạn chọn dòng cần bỏ đọc", "Chương trong sách", "Tên chương")) rule.onAllNodesWithText(gone, substring = true).assertCountEquals(0)
        rule.onAllNodesWithText("□").assertCountEquals(0)
        rule.onAllNodesWithText("✓").assertCountEquals(0)
        rule.onNodeWithTag("import_meta").assertTextEquals("Nguyễn Nhật Ánh · 2 / 3 chương")
        rule.onAllNodesWithText("Bỏ đọc dòng").assertCountEquals(2)
        // Không hai khối dính nhau: dòng thông tin và tiêu đề "Gợi ý phần đọc" cách ≥ 16.
        val meta = rule.onNodeWithTag("import_meta").getUnclippedBoundsInRoot()
        val next = rule.onNodeWithText("Gợi ý phần đọc").getUnclippedBoundsInRoot()
        assertTrue("khoảng ${next.top - meta.bottom}", (next.top - meta.bottom).value >= 16f)
    }

    @Test fun aBookAlreadyInTheLibrarySaysWhichOneAndSkipIsThePrimaryAction() {
        val known = preview.copy(existingId = "old", existingTitle = "Chuyến phà cuối ngày")
        var skipped = 0
        show { ImportReviewScreen(ImportState(currentId = 1, preview = known, choices = ImportLogic.defaults(known)), {}, {}, {}, {}, { skipped++ }) }
        rule.onNodeWithText("Cuốn này đã có trong thư viện: “Chuyến phà cuối ngày”.").assertIsDisplayed()
        // Nút chính là "Bỏ cuốn này" (như hàng nhiều file của web), không lặp ở cuối danh sách.
        rule.onAllNodesWithText("Bỏ cuốn này").assertCountEquals(1)
        rule.onAllNodesWithTag("skip_book").assertCountEquals(0)
    }

    @Test fun reviewTitleCountsTheBooksWhenSeveralFilesWerePicked() {
        val items = listOf(ImportItem(1, "a", "Một.epub", stage = ImportStage.Review), ImportItem(2, "b", "Hai.epub"))
        show { ImportReviewScreen(ImportState(items = items, currentId = 1, preview = preview, choices = ImportLogic.defaults(preview)), {}, {}, {}, {}, {}) }
        rule.onNodeWithText("Sách 1/2 · Xem trước").assertIsDisplayed()
        rule.onNodeWithText("Thêm vào thư viện").assertIsDisplayed()
    }

    @Test fun chapterRowsHaveASwitchAndOpenTheNameScreenFromTheTitle() {
        var state by mutableStateOf(ImportState(currentId = 1, preview = preview, choices = ImportLogic.defaults(preview)))
        val opened = mutableListOf<Int>()
        show { ImportReviewScreen(state, {}, { state = state.copy(choices = it(state.choices)) }, {}, {}, {}, { opened += it }) }
        rule.onNodeWithTag("import_review").performScrollToNode(hasTestTag("import_chapter_1"))
        assertFalse(1 in state.choices.picked)
        rule.onNodeWithTag("import_chapter_1_keep").performClick()
        assertTrue(1 in state.choices.picked)
        rule.onNodeWithTag("import_chapter_1_keep").performClick()
        assertFalse(1 in state.choices.picked)
        // Chạm tên mở màn đặt tên, không đổi giữ / bỏ.
        rule.onNodeWithTag("import_chapter_2_name").performClick()
        assertEquals(listOf(2), opened)
        assertTrue(2 in state.choices.picked)
    }

    @Test fun chapterRowsShareTheFirstLineCenterOnBothSides() {
        review(false, null)
        rule.onNodeWithTag("import_review").performScrollToNode(hasTestTag("import_chapter_3"))
        for (row in listOf("import_chapter_1", "import_chapter_2", "import_chapter_3")) {
            rule.onNodeWithTag("import_review").performScrollToNode(hasTestTag(row))
            val title = rule.onNode(hasTestTag("row_title") and hasAnyAncestor(hasTestTag(row)), useUnmergedTree = true).getUnclippedBoundsInRoot()
            val keep = rule.onNodeWithTag("${row}_keep", useUnmergedTree = true).getUnclippedBoundsInRoot()
            val chevron = rule.onNode(hasTestTag("row_trailing") and hasAnyAncestor(hasTestTag(row)), useUnmergedTree = true).getUnclippedBoundsInRoot()
            val first = title.top + 12.dp
            assertEquals("$row công tắc", first.value, ((keep.top + keep.bottom) / 2).value, 0.6f)
            assertEquals("$row mũi tên", first.value, ((chevron.top + chevron.bottom) / 2).value, 0.6f)
        }
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
        rule.onNodeWithTag("suggestion_Dịch: Nhóm Lục Bình").performClick()
        assertTrue(queue.state.value.choices.skipped.isEmpty())
        rule.onNodeWithTag("suggestion_Dịch: Nhóm Lục Bình").performClick()
        rule.onNodeWithTag("confirm_import").performClick()
        assertEquals(1, source.adds)
        assertEquals(setOf("Dịch: Nhóm Lục Bình"), source.addedChoices?.skipped)
    }

    // --- Chọn hết / bỏ chọn hết chương ---
    @Test fun pickAllAndNoneSetEveryChapterAndNothingPickedBlocksAdding() {
        var state by mutableStateOf(ImportState(currentId = 1, preview = preview, choices = ImportLogic.defaults(preview)))
        show { ImportReviewScreen(state, {}, { state = state.copy(choices = it(state.choices)) }, {}, {}, {}) }
        rule.onNodeWithTag("import_review").performScrollToNode(hasTestTag("pick_all_chapters"))
        rule.onNodeWithTag("pick_all_chapters").performClick()
        assertEquals(setOf(1, 2, 3), state.choices.picked)
        rule.onAllNodesWithText(ImportLogic.NOTHING_PICKED).assertCountEquals(0)
        rule.onNodeWithTag("confirm_import").assertIsEnabled()
        rule.onNodeWithTag("pick_no_chapters").performClick()
        assertTrue(state.choices.picked.isEmpty())
        // Không chương nào: nói ngay ở chân màn, "Thêm sách" không bấm được.
        rule.onNodeWithText(ImportLogic.NOTHING_PICKED).assertIsDisplayed()
        rule.onNodeWithTag("confirm_import").assertIsNotEnabled()
        rule.onNodeWithTag("import_chapter_2_keep").performClick()
        rule.onAllNodesWithText(ImportLogic.NOTHING_PICKED).assertCountEquals(0)
        rule.onNodeWithTag("confirm_import").assertIsEnabled()
    }

    @Test fun oneChapterHasNoPickAllActions() {
        val single = preview.copy(chapters = listOf(ImportChapter(1, "Chương 1")), suggestions = emptyList())
        review(false, null, single, emptyMap())
        rule.onAllNodesWithTag("pick_all_chapters").assertCountEquals(0)
        rule.onAllNodesWithTag("pick_no_chapters").assertCountEquals(0)
    }

    @Test fun pickAllRowSharesTheChapterHeading() {
        review(false, null)
        rule.onNodeWithTag("import_review").performScrollToNode(hasTestTag("pick_all_chapters"))
        val heading = rule.onNodeWithText("Chương").getUnclippedBoundsInRoot()
        for (tag in listOf("pick_all_chapters", "pick_no_chapters")) {
            val action = rule.onNodeWithTag(tag).getUnclippedBoundsInRoot()
            assertEquals(tag, ((heading.top + heading.bottom) / 2).value, ((action.top + action.bottom) / 2).value, 1f)
        }
    }

    // --- Đóng Thêm sách giữa hàng ---
    private val waiting = ImportState(items = listOf(
        ImportItem(1, "a", "Chuyến phà cuối ngày.epub", stage = ImportStage.Added, bookId = "a"),
        ImportItem(2, "b", "Những ngày thơ ấu.docx", stage = ImportStage.Review),
        ImportItem(3, "c", "Truyện ngắn", folder = true, stage = ImportStage.Waiting),
        ImportItem(4, "d", "Số đỏ.txt", stage = ImportStage.Waiting),
    ), currentId = 2)

    private fun leaving(dark: Boolean, name: String) {
        show(dark) { AddBookScreen(waiting, {}, {}, {}, {}, {}, {}, leaving = 3) }
        rule.onNodeWithText("Còn 3 cuốn chưa thêm vào thư viện. Đóng bây giờ thì các cuốn ấy sẽ không được thêm.").assertIsDisplayed()
        rule.onNodeWithTag("leave_stay").assertIsDisplayed()
        rule.onNodeWithTag("leave_drop").assertIsDisplayed()
        rule.onAllNodesWithTag("pick_books").assertCountEquals(0)
        shot(name)
    }
    @Test fun leavingLight() = leaving(false, "add_leaving_light")
    @Test fun leavingDark() = leaving(true, "add_leaving_dark")

    private fun back() = rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }

    @Test fun backWithSeveralBooksLeftAsksFirstAndBackAgainKeepsAdding() {
        val source = FakeImportSource(preview)
        val queue = ImportQueue(source, CoroutineScope(Dispatchers.Main.immediate))
        var left = 0
        show { AddBookRoute(queue, { left++ }, {}, {}) }
        rule.runOnIdle { queue.enqueue(listOf("one", "two", "three")) }
        rule.waitForIdle()
        back()
        rule.waitForIdle()
        rule.onNodeWithTag("leave_confirm").assertIsDisplayed()
        assertEquals(0, left)
        // Back lần nữa = "Quay lại thêm sách": lời hỏi khép, hàng còn nguyên.
        back()
        rule.waitForIdle()
        rule.onAllNodesWithTag("leave_confirm").assertCountEquals(0)
        rule.onNodeWithTag("pick_books").assertIsDisplayed()
        assertEquals(3, queue.state.value.items.size)
        assertEquals(0, left)
        // Nút ← hỏi y như Back; "Quay lại thêm sách" cũng khép lời hỏi.
        rule.onNodeWithContentDescription("Quay lại").performClick()
        rule.onNodeWithTag("leave_stay").performClick()
        rule.waitForIdle()
        rule.onAllNodesWithTag("leave_confirm").assertCountEquals(0)
        assertEquals(0, left)
        // "Bỏ phần còn lại": bản tạm của cuốn đang xem bị bỏ, hàng trống, màn đóng.
        back()
        rule.waitForIdle()
        rule.onNodeWithTag("leave_drop").performClick()
        rule.waitForIdle()
        assertEquals(1, left)
        assertTrue(queue.state.value.items.isEmpty())
        assertEquals(listOf("ref1"), source.discarded)
    }

    @Test fun backWithOneBookLeftClosesWithoutAsking() {
        val source = FakeImportSource(preview)
        val queue = ImportQueue(source, CoroutineScope(Dispatchers.Main.immediate))
        var left = 0
        show { AddBookRoute(queue, { left++ }, {}, {}) }
        rule.runOnIdle { queue.enqueue(listOf("one")) }
        rule.waitForIdle()
        rule.onNodeWithContentDescription("Quay lại").performClick()
        rule.waitForIdle()
        assertEquals(1, left)
        rule.onAllNodesWithTag("leave_confirm").assertCountEquals(0)
        // Một cuốn: hàng giữ nguyên như trước (Back không huỷ việc nhập).
        assertEquals(1, queue.state.value.items.size)
    }

    // --- Màn tên chương của xem trước ---
    private fun importName(dark: Boolean, name: String, names: Map<Int, String>) {
        var state by mutableStateOf(ImportState(currentId = 1, preview = preview, choices = ImportLogic.defaults(preview).copy(names = names)))
        show(dark) { ImportChapterScreen(state, 3, {}) { state = state.copy(choices = it(state.choices)) } }
        shot(name)
    }
    @Test fun importNameLight() = importName(false, "add_chapter_name_light", mapOf(3 to "Khách qua sông"))
    @Test fun importNameDark() = importName(true, "add_chapter_name_dark", mapOf(3 to "Khách qua sông"))

    @Test fun revertAppearsOnlyWhenTheNameDiffersAndRestoresTheOriginal() {
        var state by mutableStateOf(ImportState(currentId = 1, preview = preview, choices = ImportLogic.defaults(preview)))
        show { ImportChapterScreen(state, 3, {}) { state = state.copy(choices = it(state.choices)) } }
        rule.onAllNodesWithTag("chapter_revert").assertCountEquals(0)
        rule.onNodeWithTag("chapter_title").performTextReplacement("Khách qua sông")
        rule.onNodeWithTag("chapter_revert").assertIsDisplayed()
        assertEquals("Khách qua sông", state.choices.names[3])
        rule.onNodeWithTag("chapter_revert").performClick()
        assertNull(state.choices.names[3])
        rule.onAllNodesWithTag("chapter_revert").assertCountEquals(0)
        // Gõ lại đúng tên gốc (khác khoảng trắng) cũng không có "Về tên gốc".
        rule.onNodeWithTag("chapter_title").performTextReplacement("  Chương 2:   Một tên chương khá dài để thử xuống dòng trong hàng ")
        rule.onAllNodesWithTag("chapter_revert").assertCountEquals(0)
    }

    // --- Chú thích ---
    private val noted = ImportPreview("Chuyến phà cuối ngày", chapters = listOf(ImportChapter(1, "Chương 1")),
        footnoteCount = 12, footnoteMarks = 12, footnoteExample = "hàng cây²\nLời chú về cây bên sông.")
    @Test fun footnotesLight() = footnotes(false, "add_footnotes_light")
    @Test fun footnotesDark() = footnotes(true, "add_footnotes_dark")
    private fun footnotes(dark: Boolean, name: String) {
        var state by mutableStateOf(ImportState(preview = noted, choices = ImportLogic.defaults(noted)))
        val revised = mutableListOf<String>()
        show(dark) { ImportReviewScreen(state, {}, {}, { change ->
            state = state.copy(choices = change(state.choices)); revised += state.choices.notes
        }, {}, {}) }
        rule.onNodeWithTag("footnote_count").assertTextEquals("12 chú thích trong file")
        rule.onNodeWithTag("footnote_example").assertIsDisplayed()
        rule.onNodeWithText("Bỏ số gọi").performClick()
        assertTrue(state.choices.hideMarks)
        rule.onNodeWithText("Bỏ số gọi").performClick()
        assertFalse(state.choices.hideMarks)
        // Lời chú loại trừ nhau (một giá trị trong lõi): chọn một thì bỏ cái kia.
        rule.onNodeWithTag("footnote_notes_end").performClick()
        assertEquals("end", state.choices.notes)
        rule.onNodeWithTag("footnote_notes_drop").performClick()
        assertEquals("drop", state.choices.notes)
        rule.onNodeWithTag("footnote_notes_keep").performClick()
        assertEquals("", state.choices.notes)
        rule.onAllNodesWithText("Bạn chọn mới đổi phần đọc.").assertCountEquals(0)
        shot(name)
    }

    // --- Sửa sách ---
    @Test fun editLight() = edit(false, "edit_book_light")
    @Test fun editDark() = edit(true, "edit_book_dark")
    @Test fun longTitleLight() = edit(false, "edit_long_title_light", longTitle)
    @Test fun longTitleDark() = edit(true, "edit_long_title_dark", longTitle)

    @Test fun editSavesSilentlyAndShowsOnlyFailures() {
        edit(false, "edit_book_light")
        rule.onAllNodesWithText("Đã lưu").assertCountEquals(0)
        rule.onAllNodesWithText("Đang lưu").assertCountEquals(0)
        rule.onAllNodesWithText("Bạn sửa là tự lưu", substring = true).assertCountEquals(0)
        rule.onAllNodesWithTag("edit_problem").assertCountEquals(0)
        rule.onAllNodesWithText("Chọn ảnh bìa").assertCountEquals(0)
        // Cùng chữ với dòng tình trạng "Gửi về máy tính" của web (SendEdits.tsx, shared/editsSync.ts).
        rule.onNodeWithText("2 thay đổi đang chờ gửi về máy tính").assertIsDisplayed()
        rule.onNodeWithText("Tự gửi khi tới được máy tính; bấm “Gửi về máy tính” để gửi ngay.").assertIsDisplayed()
        rule.onNodeWithText("Gửi về máy tính").assertIsDisplayed()
    }

    @Test fun editShowsAFailureInlineWithRetry() {
        var retried = 0
        var sent = 0
        val book = edit
        show {
            EditBookScreen(EditState(book, EditLogic.draft(book), loading = false, problem = "Không ghi được file.", sendProblem = "Chưa gửi được về máy tính. Phần sửa vẫn nằm trên máy này."),
                CoverLoader(), {}, {}, {}, {}, { sent++ }, { retried++ })
        }
        rule.onNodeWithText("Không ghi được file.").assertIsDisplayed()
        rule.onNodeWithTag("edit_problem-retry").performClick()
        rule.onNodeWithTag("send_problem-retry").performClick()
        assertEquals(1, retried)
        assertEquals(1, sent)
        shot("edit_failed_light")
    }

    /** "Thử lại" thẳng dòng đầu của câu lỗi, kể cả khi câu lỗi xuống hai dòng (không đứng giữa khối). */
    @Test fun retryStaysOnTheFirstLineOfAWrappedProblem() {
        val book = edit
        show {
            EditBookScreen(EditState(book, EditLogic.draft(book), loading = false, sendProblem = "Chưa gửi được về máy tính. Phần sửa vẫn nằm trên máy này."),
                CoverLoader(), {}, {}, {}, {}, {}, {})
        }
        val text = rule.onNodeWithText("Chưa gửi được về máy tính. Phần sửa vẫn nằm trên máy này.").getUnclippedBoundsInRoot()
        val retry = rule.onNodeWithTag("send_problem-retry").getUnclippedBoundsInRoot()
        assertTrue("câu lỗi phải xuống dòng", (text.bottom - text.top).value > 30f)
        val first = text.top + 10.5.dp
        assertTrue("dòng đầu $first, tâm nút ${(retry.top + retry.bottom) / 2}", (first - (retry.top + retry.bottom) / 2).value in -1.5f..1.5f)
    }

    @Test fun pendingRowOnlyExistsWhenThereIsSomethingToSend() {
        val clean = edit.copy(pending = 0)
        show { EditBookScreen(EditState(clean, EditLogic.draft(clean), loading = false), CoverLoader(), {}, {}, {}, {}, {}, {}) }
        rule.onAllNodesWithTag("send_edits").assertCountEquals(0)
    }

    @Test fun chapterRowsShowTheOriginalNameOnlyWhenRenamed() {
        edit(false, "edit_book_light")
        rule.onNodeWithTag("edit_book_list").performScrollToNode(hasTestTag("edit_chapter_3"))
        rule.onNodeWithText("Tên gốc: Chương 2").assertIsDisplayed()
        rule.onAllNodesWithText("Tên gốc:", substring = true).assertCountEquals(1)
    }

    @Test fun editRowsShareTheFirstLineCenterOnBothSides() {
        edit(false, "edit_book_light")
        rule.onNodeWithTag("edit_book_list").performScrollToNode(hasTestTag("edit_chapter_3"))
        for (row in listOf("edit_chapter_1", "edit_chapter_2", "edit_chapter_3")) sharesFirstLine(row, "row_trailing")
    }

    @Test fun theCoverIsTheControl() {
        var opened = 0
        val book = edit
        show { EditBookScreen(EditState(book, EditLogic.draft(book), loading = false), CoverLoader(), {}, {}, { opened++ }, {}, {}, {}) }
        rule.onNodeWithTag("edit_cover").performClick()
        assertEquals(1, opened)
    }

    private fun coverSheet(dark: Boolean, name: String, hasCover: Boolean) {
        val sheets = SheetHost()
        show(dark) { SheetLayer(sheets) }
        rule.runOnIdle { sheets.show { dismiss -> CoverSheet(hasCover, dismiss, dismiss) } }
        rule.mainClock.advanceTimeBy(600)
        rule.waitForIdle()
        shot(name)
        rule.onNodeWithTag("cover_pick").assertIsDisplayed()
        rule.onNodeWithTag("cover_find").assertIsDisplayed()
        if (hasCover) rule.onNodeWithTag("cover_remove").assertIsDisplayed() else rule.onAllNodesWithTag("cover_remove").assertCountEquals(0)
    }

    @Test fun coverSheetFindOpensTheSearch() {
        val sheets = SheetHost()
        var found = 0
        show { SheetLayer(sheets) }
        rule.runOnIdle { sheets.show { dismiss -> CoverSheet(true, dismiss, dismiss, onFind = { dismiss(); found++ }) } }
        rule.waitForIdle()
        rule.onNodeWithText("Tìm bìa").performClick()
        rule.waitForIdle()
        assertEquals(1, found)
        rule.onAllNodesWithTag("cover_sheet").assertCountEquals(0)
    }

    // --- Cách đọc tên / Bỏ mọi thay đổi ---
    private fun editorScreen(snapshot: EditSnapshot, source: FakeEditSource = FakeEditSource(snapshot), dark: Boolean = false, discard: () -> Unit = {}): FakeEditSource {
        show(dark) {
            val scope = rememberCoroutineScope()
            val editor = remember { BookEditor("b", source, scope) }
            val state by editor.state.collectAsState()
            val readings by editor.readings.collectAsState()
            EditBookScreen(state, CoverLoader(), {}, editor::change, {}, {}, editor::send, editor::retry,
                readings = readings, loadReadings = editor::loadReadings, setReading = editor::setReading, discard = discard)
        }
        // Sách đã đọc xong trước khi test đổi nguồn giả (vd cho nó hỏng).
        rule.waitForIdle()
        return source
    }

    private fun openReadings() {
        rule.onNodeWithTag("edit_book_list").performScrollToNode(hasTestTag("edit_readings"))
        rule.onNodeWithTag("edit_readings").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("edit_book_list").performScrollToNode(hasTestTag("readings_section"))
    }

    @Test fun readingsFoldListsTaughtWordsAndEditsOneInPlace() {
        val source = FakeEditSource(edit)
        source.words["Haruto"] = "Ha-ru-tô"
        editorScreen(edit, source)
        rule.onAllNodesWithTag("readings_section").assertCountEquals(0)
        openReadings()
        rule.onNodeWithText(ReadingText.HINT).assertIsDisplayed()
        rule.onNodeWithText("đọc là “Ha-ru-tô”").assertIsDisplayed()
        rule.onNodeWithContentDescription("Sửa cách đọc Haruto").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("edit_book_list").performScrollToNode(hasTestTag("reading_save"))
        // Chưa đổi gì: "Lưu cho cả cuốn" chưa bấm được; từ đã có cách đọc riêng thì có "Đọc như chữ trong sách".
        rule.onNodeWithTag("reading_save").assertIsNotEnabled()
        rule.onNodeWithTag("edit_book_list").performScrollToNode(hasTestTag("reading_plain"))
        rule.onNodeWithText("Đọc như chữ trong sách").assertIsDisplayed()
        rule.onNodeWithTag("reading_field").performTextReplacement("Ha-ru-to")
        rule.onNodeWithTag("reading_save").assertIsEnabled().performClick()
        rule.waitForIdle()
        assertEquals("Haruto" to "Ha-ru-to", source.readingCalls.last())
        rule.onAllNodesWithTag("reading_form").assertCountEquals(0)
        rule.onNodeWithText("“Haruto” sẽ đọc là “Ha-ru-to” từ đoạn sau").assertExists()
        rule.onNodeWithContentDescription("Bỏ cách đọc Haruto").performClick()
        rule.waitForIdle()
        assertEquals("Haruto" to "", source.readingCalls.last())
        // Hàng cuối trượt ra hết rồi mới tới dòng "Chưa có từ nào." (không đổi cứng).
        rule.mainClock.advanceTimeBy(1000)
        rule.waitForIdle()
        rule.onNodeWithText("Chưa có từ nào.").assertExists()
    }

    @Test fun readingsThatCannotLoadSayHowToRetry() {
        val source = FakeEditSource(edit)
        editorScreen(edit, source)
        source.fail = true
        openReadings()
        rule.onNodeWithText("Bạn hãy thử tải lại danh sách cách đọc.").assertIsDisplayed()
        source.fail = false
        rule.onNodeWithTag("readings_problem-retry").performClick()
        rule.waitForIdle()
        rule.onNodeWithText("Chưa có từ nào.").assertExists()
    }

    @Test fun audiobooksHaveNoReadingsFold() {
        editorScreen(edit.copy(textOnly = false))
        rule.onAllNodesWithTag("edit_readings").assertCountEquals(0)
    }

    private fun readingsShot(dark: Boolean, name: String) {
        val source = FakeEditSource(edit)
        source.words["Haruto"] = "Ha-ru-tô"
        source.words["Hạ Vy"] = "Hạ Vi"
        editorScreen(edit, source, dark)
        openReadings()
        rule.onNodeWithContentDescription("Sửa cách đọc Haruto").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("edit_book_list").performScrollToNode(hasTestTag("reading_save"))
        shot(name)
    }
    @Test @Config(sdk = [35], qualifiers = "w360dp-h1100dp-xxhdpi") fun readingsLight() = readingsShot(false, "edit_readings_light")
    @Test @Config(sdk = [35], qualifiers = "w360dp-h1100dp-xxhdpi") fun readingsDark() = readingsShot(true, "edit_readings_dark")

    @Test fun discardRowOnlyWithChangesAndAsksBeforeDiscarding() {
        var asked = 0
        editorScreen(edit.copy(edits = 3), discard = { asked++ })
        rule.onNodeWithTag("edit_book_list").performScrollToNode(hasTestTag("discard_edits"))
        rule.onNodeWithText("Bỏ mọi thay đổi (3)").assertIsDisplayed()
        rule.onNodeWithText(ReadingText.DISCARD_HINT).assertIsDisplayed()
        rule.onNodeWithTag("discard_edits").performClick()
        assertEquals(1, asked)
    }

    @Test fun noChangesNoDiscardRow() {
        editorScreen(edit.copy(edits = 0))
        rule.onAllNodesWithTag("discard_edits").assertCountEquals(0)
    }

    private fun discardSheet(dark: Boolean, name: String?, fail: Boolean = false): Pair<FakeEditSource, BookEditor> {
        val sheets = SheetHost()
        val source = FakeEditSource(edit.copy(title = "Tên đã sửa", edits = 2))
        source.original = edit
        lateinit var editor: BookEditor
        show(dark) {
            val scope = rememberCoroutineScope()
            editor = remember { BookEditor("b", source, scope) }
            SheetLayer(sheets)
        }
        rule.waitForIdle()
        source.fail = fail
        rule.runOnIdle { sheets.show { dismiss -> DiscardSheet(editor::discardAll, dismiss) } }
        rule.mainClock.advanceTimeBy(600)
        rule.waitForIdle()
        if (name != null) shot(name)
        return source to editor
    }
    @Test fun discardSheetLight() { discardSheet(false, "edit_discard_light") }
    @Test fun discardSheetDark() { discardSheet(true, "edit_discard_dark") }

    @Test fun discardSheetBringsThePackagedBookBackOrKeepsAskingOnFailure() {
        val (source, editor) = discardSheet(false, null, fail = true)
        rule.onNodeWithTag("discard_yes").performClick()
        rule.waitForIdle()
        rule.onNodeWithText("Chưa bỏ được thay đổi").assertIsDisplayed()
        assertEquals("Tên đã sửa", editor.state.value.saved?.title)
        source.fail = false
        rule.onNodeWithTag("discard_yes").performClick()
        rule.waitForIdle()
        assertEquals(1, source.discards)
        assertEquals(edit.title, editor.state.value.saved?.title)
        rule.onAllNodesWithTag("discard_confirm").assertCountEquals(0)
    }

    @Test fun discardSheetThoiClosesWithoutDiscarding() {
        val (source, _) = discardSheet(false, null)
        rule.onNodeWithText("Thôi").performClick()
        rule.waitForIdle()
        assertEquals(0, source.discards)
        rule.onAllNodesWithTag("discard_confirm").assertCountEquals(0)
    }

    // --- Tìm ảnh bìa ---
    private val found = listOf(
        FoundCover("Open Library", "Chuyến phà cuối ngày", "Nguyễn Nhật Ánh", "https://covers.openlibrary.org/b/id/1-M.jpg", "https://covers.openlibrary.org/b/id/1-L.jpg"),
        FoundCover("Google Books", "Chuyến phà cuối ngày (bản in lại có minh hoạ)", "", "https://books.google.com/t2", "https://books.google.com/f2"),
        FoundCover("iTunes", "Chuyến phà", "", "https://is1-ssl.mzstatic.com/t3", "https://is1-ssl.mzstatic.com/f3"),
    )

    private fun coverSearch(source: FakeEditSource, dark: Boolean = false, left: () -> Unit = {}, cropped: (String) -> Unit = {}) {
        show(dark) {
            val scope = rememberCoroutineScope()
            val editor = remember { BookEditor("b", source, scope) }
            CoverSearchRoute(editor, source.snapshot.title, left, cropped)
        }
        rule.waitForIdle()
    }

    private fun coverResults(dark: Boolean, name: String) {
        val source = FakeEditSource(edit)
        source.covers = CoverResults("", found)
        coverSearch(source, dark)
        assertEquals(listOf("Chuyến phà cuối ngày"), source.queries)
        rule.onNodeWithText("Tìm ảnh bìa").assertIsDisplayed()
        rule.onNodeWithText("Bạn chọn ảnh từ các nguồn sách hoặc trên máy.").assertIsDisplayed()
        rule.onNodeWithTag("cover_found_${found[0].url}").assertIsDisplayed()
        shot(name)
    }
    @Test fun coverSearchLight() = coverResults(false, "edit_cover_search_light")
    @Test fun coverSearchDark() = coverResults(true, "edit_cover_search_dark")

    @Test fun coverSearchSearchesAVolumeByItsSeriesName() {
        val source = FakeEditSource(edit.copy(title = "Throne of Magical Arcana · Tập 16"))
        coverSearch(source)
        assertEquals(listOf("Throne of Magical Arcana"), source.queries)
    }

    @Test fun choosingAFoundCoverSetsItAndLeavesOnce() {
        val source = FakeEditSource(edit)
        source.covers = CoverResults("", found)
        var left = 0
        coverSearch(source, left = { left++ })
        rule.onNodeWithTag("cover_found_${found[1].url}").performClick()
        rule.waitForIdle()
        assertEquals(listOf(found[1].url), source.chosen)
        assertEquals(1, left)
    }

    @Test fun aFailedChoiceSaysSoAndRetriesTheSameCover() {
        val source = FakeEditSource(edit)
        source.covers = CoverResults("", found)
        var left = 0
        coverSearch(source, left = { left++ })
        source.coverFail = true
        rule.onNodeWithTag("cover_found_${found[0].url}").performClick()
        rule.waitForIdle()
        rule.onNodeWithText("Bạn hãy kiểm tra kết nối rồi đặt lại ảnh bìa.").assertIsDisplayed()
        assertEquals(0, left)
        source.coverFail = false
        rule.onNodeWithTag("cover_choose_problem-retry").performClick()
        rule.waitForIdle()
        assertEquals(listOf(found[0].url), source.chosen)
        assertEquals(1, left)
    }

    private fun coverNothing(dark: Boolean, name: String?) {
        val source = FakeEditSource(edit)
        coverSearch(source, dark)
        rule.onNodeWithText("Bạn hãy chọn ảnh trên máy").assertIsDisplayed()
        rule.onNodeWithTag("cover_pick_file").assertIsDisplayed()
        if (name != null) shot(name)
    }
    @Test fun coverNothingLight() = coverNothing(false, "edit_cover_search_none_light")
    @Test fun coverNothingDark() = coverNothing(true, "edit_cover_search_none_dark")

    @Test fun offlineSearchAndMissingSourcesBothOfferARetry() {
        val source = FakeEditSource(edit)
        source.coverFail = true
        coverSearch(source)
        rule.onNodeWithText("Bạn hãy kiểm tra kết nối rồi tìm lại ảnh bìa.").assertIsDisplayed()
        source.coverFail = false
        source.covers = CoverResults("", found.take(1), failed = listOf("google_books"))
        rule.onNodeWithTag("cover_search_problem-retry").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("cover_found_${found[0].url}").assertIsDisplayed()
        rule.onNodeWithText("Bạn hãy kiểm tra kết nối rồi tìm lại các nguồn bìa.").assertIsDisplayed()
        assertEquals(2, source.queries.size)
    }

    @Test fun typingANewNameAndTappingTimSearchesAgain() {
        val source = FakeEditSource(edit)
        coverSearch(source)
        rule.onNodeWithTag("cover_query").performTextReplacement("The last ferry")
        rule.onNodeWithTag("cover_search_go").performClick()
        rule.waitForIdle()
        assertEquals("The last ferry", source.queries.last())
    }
    @Test fun coverSheetLight() = coverSheet(false, "edit_cover_sheet_light", true)
    @Test fun coverSheetDark() = coverSheet(true, "edit_cover_sheet_dark", true)
    @Test fun coverSheetWithoutACoverHasNoRemoveRow() = coverSheet(false, "edit_cover_sheet_none_light", false)

    @Test fun metadataTypingAndBackSavesWithoutAConfirmButton() {
        val source = FakeEditSource(edit)
        lateinit var editor: BookEditor
        show {
            val scope = rememberCoroutineScope()
            editor = remember { BookEditor("b", source, scope) }
            val state by editor.state.collectAsState()
            EditBookScreen(state, CoverLoader(), {}, editor::change, {}, {}, editor::send, editor::retry)
        }
        rule.onNodeWithTag("edit_author").performTextReplacement("")
        rule.mainClock.advanceTimeBy(1000)
        rule.waitForIdle()
        rule.runOnIdle { assertEquals("", editor.state.value.draft?.author) }
        rule.onAllNodesWithText("Lưu").assertCountEquals(0)
        rule.onAllNodesWithText("Đã lưu").assertCountEquals(0)
    }

    // --- Màn tên chương của Sửa sách ---
    private fun editName(dark: Boolean, name: String, text: Boolean) {
        val snapshot = edit.copy(textOnly = text)
        show(dark) {
            val scope = rememberCoroutineScope()
            val editor = remember { BookEditor("b", FakeEditSource(snapshot), scope) }
            EditChapterRoute(editor, 2) {}
        }
        rule.onNodeWithTag("chapter_title").assertIsDisplayed()
        shot(name)
    }
    @Test fun editNameLight() = editName(false, "edit_chapter_light", true)
    @Test fun editNameDark() = editName(true, "edit_chapter_dark", true)
    @Test fun editNameWithSubtitleLight() = editName(false, "edit_chapter_audio_light", false)

    @Test fun editNameHasNoSavedNoteAndRevertOnlyWhenRenamed() {
        show {
            val scope = rememberCoroutineScope()
            val editor = remember { BookEditor("b", FakeEditSource(edit), scope) }
            Box { EditChapterRoute(editor, 1) {} }
        }
        rule.onAllNodesWithText("Đã lưu").assertCountEquals(0)
        // Chương 1 chưa đổi tên: không có "Về tên gốc".
        rule.onAllNodesWithTag("chapter_revert").assertCountEquals(0)
    }

    @Test fun editNameOfARenamedChapterOffersTheOriginal() {
        show {
            val scope = rememberCoroutineScope()
            val editor = remember { BookEditor("b", FakeEditSource(edit), scope) }
            EditChapterRoute(editor, 2) {}
        }
        rule.onNodeWithTag("chapter_revert").assertIsDisplayed()
        rule.onNodeWithText("Tên gốc: Chương 2").assertIsDisplayed()
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
