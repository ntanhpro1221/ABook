package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import com.github.takahirom.roborazzi.captureRoboImage
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.data.BookDetail
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.Cast
import vn.abook.player.ui.data.CastView
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.PlayerClock
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.screens.BookScreen
import vn.abook.player.ui.screens.BookScreenActions
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Trang sách: ba mục (Chương / Lịch sử / Nhân vật), chip hồ sơ, bảng một người, trang "không tìm thấy". Ảnh chuẩn ở src/test/snapshots (ghi: -Proborazzi.test.record=true; so: verifyRoborazziDebug). */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class BookTabsScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private class Source(var detail: BookDetail?, val cast: CastView?) : BookSource by BookSource.None {
        override suspend fun detail(id: String) = detail
        override suspend fun cast(id: String) = cast
    }

    private val sheets = SheetHost()
    private val actions = BookScreenActions(back = {}, playBook = {}, toggle = {}, playChapter = { _, _, _ -> }, deleted = {}, readAlong = {}, edit = {})

    private fun title(id: Int) = "Chương $id: Một cái tên chương khá dài để xuống dòng"

    private fun manifest(): JSONObject {
        val chapters = (1..12).map {
            JSONObject().put("id", it).put("fullTitle", title(it)).put("file", "audio/$it.m4a").put("available", true).put("duration", 1500.0)
        }
        return JSONObject().put("id", "b1").put("title", "Dế Mèn phiêu lưu ký").put("author", "Tô Hoài").put("narrator", "Hoài My")
            .put("complete", true).put("chaptersTotal", 12).put("chapters", JSONArray(chapters))
    }

    private fun state(): JSONObject {
        val now = System.currentTimeMillis() / 1000.0
        val session = JSONObject().put("id", "s1").put("startedAt", now - 3600).put("endedAt", now - 3000).put("listened", 600.0)
            .put("from", JSONObject().put("chapterId", 2).put("seconds", 10.0)).put("to", JSONObject().put("chapterId", 3).put("seconds", 600.0))
        return JSONObject()
            .put("chapters", JSONObject().put("3", JSONObject().put("heard", 600.0).put("done", false)))
            .put("last", JSONObject().put("chapterId", 3).put("seconds", 600.0).put("at", now - 3000))
            .put("sessions", JSONArray(listOf(session)))
    }

    private fun records(count: Int) = JSONArray((1..count).map {
        JSONObject().put("id", "r$it").put("name", if (it == 1) "Mặc định" else "Lần nghe $it").put("updatedAt", 1_760_000_000.0 + it).put("active", it == 1)
    })

    private fun cast() = Cast.parse(
        JSONObject()
            .put("narrator", JSONObject().put("voice", "Hoài My").put("lines", 120).put("seconds", 900.0))
            .put("characters", JSONArray(listOf(person("An", "Nữ", 40, title(1)), person("Bình", "Nam", 25, title(9)))))
            .put("extras", JSONArray())
            .toString(),
    )

    private fun person(name: String, gender: String, lines: Int, first: String) = JSONObject().put("name", name).put("displayName", name).put("gender", gender)
        .put("lines", lines).put("seconds", lines * 8.0).put("firstChapter", first).put("sampleId", 1)
        .put("voice", JSONObject().put("key", "k$name").put("preset", "p$name").put("label", "Giọng $name").put("tone", ""))

    private fun show(detail: BookDetail?, cast: CastView? = cast(), others: List<ListenBook> = emptyList(), dark: Boolean = false) {
        val book = BookDetail.of(manifest(), null, { null }).book
        val source = Source(detail, cast)
        rule.setContent {
            AbookTheme(dark) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    BookScreen(book, LibraryState.Ready(if (detail == null) others else listOf(book) + others), PlayerState.Empty, PlayerClock(), CoverLoader(1 shl 20), source, sheets, actions)
                    SheetLayer(sheets)
                }
            }
        }
        rule.waitForIdle()
    }

    private fun detail(records: Int = 2) = BookDetail.of(manifest(), state(), { null }, canShare = true, records = records(records))

    private fun snap(name: String) {
        rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")
    }

    private fun open(tag: String) {
        rule.onNodeWithTag(tag).performClick()
        rule.waitForIdle()
    }

    @Test
    fun historyTabListsTheDaysAndAWeekLine() {
        show(detail())
        rule.onNodeWithTag("book_tabs").assertIsDisplayed()
        open("book_tab_history")
        rule.onNodeWithTag("history_week").assertIsDisplayed()
        snap("book_history_light")
    }

    @Test
    fun castTabShowsTheNarratorAndPeopleWhoHaveSpokenSoFar() {
        show(detail())
        open("book_tab_cast")
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("person_row").fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithTag("cast_narrator").assertIsDisplayed()
        // Bình lần đầu nói ở chương 9, chưa nghe tới: chỉ An hiện, dưới có lối "Hiện chương sau".
        assertEquals(1, rule.onAllNodesWithTag("person_row").fetchSemanticsNodes().size)
        rule.onNodeWithTag("book_list").performScrollToNode(hasText("Hiện chương sau · 1 người"))
        rule.onNodeWithText("Hiện chương sau · 1 người").assertIsDisplayed()
        snap("book_cast_light")
        rule.onNodeWithText("Hiện chương sau · 1 người").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("book_list").performScrollToNode(hasText("Ẩn chương sau · 1 người"))
        assertEquals(2, rule.onAllNodesWithTag("person_row").fetchSemanticsNodes().size)
        rule.onNodeWithText("Ẩn chương sau · 1 người").assertIsDisplayed()
    }

    @Test
    fun aPersonSheetOffersRenameGenderAndMerge() {
        show(detail())
        open("book_tab_cast")
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("person_more").fetchSemanticsNodes().isNotEmpty() }
        rule.onAllNodesWithTag("person_more").onFirst().performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("person_rename").assertIsDisplayed()
        rule.onNodeWithTag("person_gender").assertIsDisplayed()
        rule.onNodeWithTag("person_merge").assertIsDisplayed()
        snap("book_person_sheet_light")
    }

    @Test
    fun theRecordChipOpensTheProfileSheetOnlyWhenThereAreSeveral() {
        show(detail(records = 2))
        rule.onNodeWithTag("book_record_chip").assertIsDisplayed()
        snap("book_head_light")
        open("book_record_chip")
        rule.onNodeWithTag("record_sheet").assertIsDisplayed()
        rule.onNodeWithTag("record_create").assertIsDisplayed()
        snap("book_records_light")
    }

    @Test
    fun aSingleRecordHasNoChip() {
        show(detail(records = 1))
        assertEquals(0, rule.onAllNodesWithTag("book_record_chip").fetchSemanticsNodes().size)
    }

    @Test
    fun aBookGoneFromTheShelfSaysSoAndOffersTheLibrary() {
        show(null)
        rule.onNodeWithTag("book_gone").assertIsDisplayed()
        rule.onNodeWithText("Không tìm thấy sách này").assertIsDisplayed()
        rule.onNodeWithTag("book_gone_back").assertIsDisplayed()
        snap("book_gone_light")
    }

    @Test
    fun darkTabs() {
        show(detail(), dark = true)
        open("book_tab_cast")
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("person_row").fetchSemanticsNodes().isNotEmpty() }
        snap("book_cast_dark")
    }
}
