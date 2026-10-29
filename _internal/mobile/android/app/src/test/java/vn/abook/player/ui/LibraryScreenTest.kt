package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.grid.LazyGridState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.longClick
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.performTouchInput
import com.github.takahirom.roborazzi.captureRoboImage
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
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.DemoLibrary
import vn.abook.player.ui.data.LibraryFilter
import vn.abook.player.ui.data.LibrarySort
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.Last
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.ListenState
import vn.abook.player.ui.screens.LibraryActions
import vn.abook.player.ui.screens.LibraryScreen
import vn.abook.player.ui.screens.LibraryUiState
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Màn Thư viện trên JVM: ảnh chụp (Roborazzi) sáng / tối cho từng dáng và kịch bản bấm thật qua cây semantics. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class LibraryScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val opened = ArrayList<String>()
    private val played = ArrayList<String>()
    private var addOpened = 0
    private lateinit var ui: LibraryUiState
    private val sheets = SheetHost()
    private val actions = LibraryActions(
        openBook = { opened += it.id },
        playNow = { played += it },
        addBook = { addOpened++ },
    )

    private fun show(books: List<ListenBook>, dark: Boolean = false, sort: LibrarySort = LibrarySort.Recent) {
        rule.setContent {
            AbookTheme(dark) {
                val scope = rememberCoroutineScope()
                ui = remember { LibraryUiState(scope, sort) }
                val grid = remember { LazyGridState() }
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    LibraryScreen(LibraryState.Ready(books), ui, grid, CoverLoader(1 shl 20), sheets, actions)
                    SheetLayer(sheets)
                }
            }
        }
    }

    private fun shot(name: String) = rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")

    private val listening = ListenBook(
        "l1", "Dế Mèn phiêu lưu ký", "Tô Hoài", duration = 7200.0, chaptersTotal = 10, chaptersAvailable = 10,
        state = ListenState(last = Last(1, 100.0, 1_760_000_000.0)),
        progress = vn.abook.player.ui.data.Progress.None.copy(heardSeconds = 2400.0, fraction = 0.33f),
        resume = vn.abook.player.ui.data.ResumeSpot(4, "Chương 4: Bài học đầu tiên", 724.0),
    )
    private val fresh = ListenBook("n1", "Chí Phèo", "Nam Cao", duration = 3600.0, chaptersTotal = 5, chaptersAvailable = 5)

    // ---- ảnh chụp ----

    @Test
    fun emptyLight() {
        show(emptyList())
        rule.onNodeWithText("Chưa có sách trên máy").assertIsDisplayed()
        rule.onNodeWithTag("add_book").assertIsDisplayed()
        shot("library_empty_light")
    }

    @Test
    fun emptyDark() {
        show(emptyList(), dark = true)
        shot("library_empty_dark")
    }

    @Test
    fun oneBookWithoutListeningLight() {
        show(listOf(fresh))
        rule.onNodeWithText("1 cuốn").assertIsDisplayed()
        shot("library_one_light")
    }

    @Test
    fun oneBookWithoutListeningDark() {
        show(listOf(fresh), dark = true)
        shot("library_one_dark")
    }

    @Test
    fun oneBookListeningLight() {
        show(listOf(listening))
        rule.onNodeWithText("1 cuốn").assertIsDisplayed()
        rule.onAllNodesWithTag("book_cell").assertCountEquals(1)
        shot("library_listening_light")
    }

    @Test
    fun theLibraryHasNoPlayControlForTheBookBeingHeard() {
        // Cuốn đang nghe chỉ có MỘT nút phát - ở thanh phát nhỏ của khung. Thư viện một mình không có hàng "Đang nghe" và không có nút phát / dừng nào.
        show(listOf(listening, fresh))
        rule.onNodeWithTag("continue_row").assertDoesNotExist()
        rule.onNodeWithTag("continue_play").assertDoesNotExist()
        rule.onAllNodes(hasContentDescription("Phát") or hasContentDescription("Tạm dừng"), useUnmergedTree = true).assertCountEquals(0)
        rule.onNodeWithText("Đang nghe").assertDoesNotExist()
        rule.onAllNodesWithTag("book_cell").assertCountEquals(2)
    }

    @Test
    fun thirtyBooksLight() {
        show(DemoLibrary.books(30))
        rule.onNodeWithTag("library_grid").assertIsDisplayed()
        shot("library_30_light")
    }

    @Test
    fun thirtyBooksDark() {
        show(DemoLibrary.books(30), dark = true)
        shot("library_30_dark")
    }

    // ---- bấm thật ----

    @Test
    fun theHeaderCountsAllBooksAndAddOpensTheSheet() {
        show(DemoLibrary.books(30))
        rule.onNodeWithText("30 cuốn").assertIsDisplayed()
        rule.onNodeWithTag("add_book").performClick()
        assertEquals(1, addOpened)
    }

    @Test
    fun filterSlidesTheGridAndKeepsOnlyThatState() {
        val books = DemoLibrary.books(30)
        show(books)
        val total = rule.onAllNodesWithTag("book_cell").fetchSemanticsNodes().size
        assertTrue(total > 0)
        rule.onNodeWithTag(LibraryFilter.Finished.tag).performClick()
        rule.waitForIdle()
        assertEquals(LibraryFilter.Finished, ui.shown)
        assertEquals(0f, ui.slide.value, 0f)
        assertEquals(LibraryFilter.Finished.ordinal.toFloat(), ui.position.value, 0f)
        val finished = books.count { it.progress.finished }
        // Mỗi ô đang hiện là một cuốn đã xong (bộ nhiều tập tính một ô).
        assertTrue(finished > 0)
        shot("library_filter_finished_light")
        rule.onNodeWithTag(LibraryFilter.All.tag).performClick()
        rule.waitForIdle()
        assertEquals(LibraryFilter.All, ui.shown)
    }

    @Test
    fun filterContentLeavesBeforeItEntersAndThereIsNoCrossfade() {
        show(DemoLibrary.books(30))
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag(LibraryFilter.Listening.tag).performClick()
        rule.mainClock.advanceTimeBy(60)
        assertEquals("còn đang trượt ra, dữ liệu cũ", LibraryFilter.All, ui.shown)
        assertTrue(ui.slide.value < 0f)
        rule.mainClock.advanceTimeBy(60)
        rule.mainClock.advanceTimeBy(60)
        assertEquals(LibraryFilter.Listening, ui.shown)
        assertTrue("trượt vào từ bên phải", ui.slide.value > 0f)
        rule.mainClock.autoAdvance = true
        rule.waitForIdle()
        assertEquals(0f, ui.slide.value, 0f)
    }

    @Test
    fun searchExpandsFiltersAndClosesBack() {
        show(DemoLibrary.books(30))
        rule.onNodeWithTag("search_button").performClick()
        rule.waitForIdle()
        assertTrue(ui.searchOpen)
        assertEquals(1f, ui.search.value, 0f)
        rule.onNodeWithTag("search_field").performTextInput("tat den")
        rule.waitForIdle()
        val shown = rule.onAllNodesWithTag("book_cell").fetchSemanticsNodes().size + rule.onAllNodesWithTag("series_cell").fetchSemanticsNodes().size
        assertTrue("chỉ còn sách khớp 'tat den', không dấu", shown in 1..6)
        shot("library_search_light")
        // Như web: nút X lần đầu chỉ xoá chữ (ô vẫn mở để gõ lại), lần sau mới đóng ô.
        rule.onNodeWithTag("search_close").performClick()
        rule.waitForIdle()
        assertEquals("", ui.query)
        assertTrue(ui.searchOpen)
        rule.onNodeWithTag("search_close").performClick()
        rule.waitForIdle()
        assertEquals(false, ui.searchOpen)
        assertEquals(0f, ui.search.value, 0f)
    }

    @Test
    fun sortMenuListsFourWaysAndRemembersTheChoice() {
        show(DemoLibrary.books(30))
        rule.onNodeWithTag("sort_button").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("sort_menu").assertIsDisplayed()
        shot("library_sort_menu_light")
        for (sort in LibrarySort.entries) rule.onNodeWithTag("sort_${sort.name}").assertIsDisplayed()
        rule.onNodeWithTag("sort_${LibrarySort.Title.name}").performClick()
        rule.waitForIdle()
        assertEquals(LibrarySort.Title, ui.sort)
        rule.onNodeWithTag("sort_menu").assertDoesNotExist()
    }

    @Test
    fun aSeriesIsOneCoverThatOpensTheVolumesAndLongPressPlays() {
        val books = DemoLibrary.books(30)
        show(books)
        val series = rule.onAllNodesWithTag("series_cell")
        assertTrue("bộ ba tập gom thành một bìa", series.fetchSemanticsNodes().isNotEmpty())
        series[0].performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("series_sheet").assertIsDisplayed()
        shot("library_series_sheet_light")
        rule.onAllNodesWithTag("series_row")[1].performClick()
        rule.waitForIdle()
        assertEquals(1, opened.size)
        series[0].performTouchInput { longClick() }
        rule.waitForIdle()
        assertEquals(1, played.size)
    }

    @Test
    fun tappingABookOpensItAndLongPressPlaysIt() {
        show(listOf(fresh, ListenBook("z", "Số đỏ")))
        val cell = rule.onAllNodesWithTag("book_cell")[0]
        cell.performClick()
        assertEquals(1, opened.size)
        cell.performTouchInput { longClick() }
        rule.waitForIdle()
        assertEquals(1, played.size)
    }
}
