package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.grid.LazyGridState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
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
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.Last
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.ListenState
import vn.abook.player.ui.data.NightEvent
import vn.abook.player.ui.data.NightSession
import vn.abook.player.ui.data.NightSource
import vn.abook.player.ui.data.NightState
import vn.abook.player.ui.nowplaying.ReadParagraph
import vn.abook.player.ui.screens.LibraryActions
import vn.abook.player.ui.screens.LibraryScreen
import vn.abook.player.ui.screens.LibraryUiState
import vn.abook.player.ui.screens.MorningRecap
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Thẻ "Tối qua" ở Thư viện và nút "Nối máy" của thư viện trống. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class MorningRecapTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val now = 1_800_000_000.0
    private val night = NightSession(
        "b1", "Truyện đêm", now - 3 * 3600, now - 2 * 3600, false,
        listOf(
            NightEvent("timer", now - 3 * 3600, "", 4, "Chương 4", 100.0),
            NightEvent("touch", now - 3 * 3600 + 600, "shake", 4, "Chương 4", 700.0),
            NightEvent("still", now - 3 * 3600 + 1200, "", 4, "Chương 4", 1300.0),
            NightEvent("stopped", now - 2 * 3600, "", 4, "Chương 4", 2000.0),
        ),
    )

    private class FakeNight(val night: NightSession?, val dismissed: MutableList<Boolean>) : NightSource {
        override suspend fun latest() = night
        override suspend fun dismiss() { dismissed += true }
        override suspend fun paragraphs(bookId: String, chapterId: Int, title: String) = listOf(
            ReadParagraph(0, "Câu đầu tiên của đêm.", 0, 600_000, true),
            ReadParagraph(1, "Đoạn bạn còn nhớ cuối cùng.", 1_000_000, 1_400_000, true),
            ReadParagraph(2, "Đoạn sau khi đã ngủ.", 1_900_000, 2_100_000, true),
        )
    }

    private val played = ArrayList<String>()
    private val dismissed = ArrayList<Boolean>()

    private fun book(lastAt: Double? = null) = ListenBook("b1", "Truyện đêm", chaptersTotal = 5, chaptersAvailable = 5,
        state = ListenState(last = lastAt?.let { Last(4, 2000.0, it) }))

    private fun show(book: ListenBook = book(), session: NightSession? = night, dark: Boolean = false, connect: Boolean = false, books: List<ListenBook> = listOf(book)) {
        val state = NightState(FakeNight(session, dismissed), CoroutineScope(Dispatchers.Unconfined), clockMs = { (now * 1000).toLong() })
        state.load()
        rule.setContent {
            AbookTheme(dark) {
                val scope = rememberCoroutineScope()
                val ui = remember { LibraryUiState(scope, vn.abook.player.ui.data.LibrarySort.Recent) }
                val grid = remember { LazyGridState() }
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    LibraryScreen(LibraryState.Ready(books), ui, grid, CoverLoader(1 shl 20), SheetHost(),
                        LibraryActions({ }, { }, { }, if (connect) ({ played += "connect" }) else null),
                        recap = { list -> MorningRecap(state, list, { id, chapter, seconds -> played += "$id/$chapter/$seconds" }, Modifier, nowMs = { (now * 1000).toLong() }) })
                }
            }
        }
    }

    @Test
    fun recapOffersTheMarkersAndResumesFromTheSuggestedOne() {
        show()
        rule.onNodeWithText("Nghe tới đâu rồi thiếp đi?").assertIsDisplayed()
        rule.onNodeWithText("Hẹn giờ ngủ").assertIsDisplayed()
        rule.onNodeWithText("Lần cuối chạm máy").assertIsDisplayed()
        rule.onNodeWithText("Máy bắt đầu nằm yên").assertIsDisplayed()
        rule.onNodeWithText("Tự dừng").assertIsDisplayed()
        rule.onNodeWithText("“Đoạn bạn còn nhớ cuối cùng.”").assertIsDisplayed()
        rule.onRoot().captureRoboImage("src/test/snapshots/recap_light.png")
        rule.onNodeWithTag("recap_resume").performClick()
        // Mốc gợi ý là "máy bắt đầu nằm yên": 1300 giây trừ 2 phút.
        assertEquals(listOf("b1/4/1180.0"), played)
        rule.waitForIdle()
        assertEquals(listOf(true), dismissed)
    }

    @Test
    fun recapScrubLetsYouPickTheLastSentenceYouRemember() {
        show(dark = true)
        rule.onNodeWithText("Tìm đúng câu").performClick()
        rule.onNodeWithText("Chọn câu cuối cùng còn nhớ:").assertIsDisplayed()
        rule.onRoot().captureRoboImage("src/test/snapshots/recap_scrub_dark.png")
        rule.onNodeWithTag("recap_line_4_1").performClick()
        assertEquals(listOf("b1/4/1000.0"), played)
    }

    @Test
    fun recapHidesWhenDismissedOrWhenYouListenedAfterTheNight() {
        show(book = book(lastAt = now - 3600))
        rule.onNodeWithTag("morning_recap").assertDoesNotExist()
    }

    @Test
    fun recapCanBeHidden() {
        show()
        rule.onNodeWithContentDescription("Ẩn thẻ này").performClick()
        rule.waitForIdle()
        assertTrue(dismissed.isNotEmpty())
    }

    @Test
    fun noRecapWithoutTheBookOrWithoutANight() {
        show(books = emptyList())
        rule.onNodeWithTag("morning_recap").assertDoesNotExist()
    }

    @Test
    fun emptyLibraryOffersToConnectAComputer() {
        show(books = emptyList(), connect = true)
        rule.onNodeWithText("Nối máy").assertIsDisplayed().performClick()
        assertEquals(listOf("connect"), played)
    }
}
