package vn.abook.player.ui

import android.content.Intent
import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasAnyAncestor
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.performTextReplacement
import com.github.takahirom.roborazzi.captureRoboImage
import org.json.JSONArray
import org.json.JSONObject
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
import vn.abook.player.ui.data.BookDetail
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.ChapterLine
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.Passage
import vn.abook.player.ui.data.PlayerClock
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.screens.BookScreen
import vn.abook.player.ui.screens.BookScreenActions
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Trang sách trên JVM: ảnh chụp (Roborazzi) sáng / tối cho từng dáng và kịch bản bấm thật qua cây semantics. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class BookScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    /** Nguồn giả: trang sách dựng từ JSON thật qua [BookDetail.of]; ghi lại mọi việc được nhờ. */
    private class FakeSource(var detail: BookDetail?, val texts: Map<Int, List<Passage>> = emptyMap()) : BookSource {
        val calls = ArrayList<String>()
        override suspend fun detail(id: String) = detail
        override suspend fun passages(id: String, chapter: ChapterLine) = texts[chapter.id]
        override suspend fun setFinished(id: String, finished: Boolean) { calls += "finished $finished" }
        override suspend fun setChapterDone(id: String, chapterId: Int, done: Boolean) { calls += "done $chapterId $done" }
        override suspend fun rename(id: String, title: String): String? { calls += "rename $title"; return null }
        override suspend fun setAuthor(id: String, author: String): String? { calls += "author $author"; return null }
        override suspend fun delete(id: String): String? { calls += "delete $id"; return null }
        override suspend fun share(id: String): Intent? = null
    }

    private val played = ArrayList<String>()
    private var toggles = 0
    private var deleted = 0
    private val actions = BookScreenActions(
        back = {},
        playBook = { played += "book $it" },
        toggle = { toggles++ },
        playChapter = { book, chapter, seconds -> played += "chapter $book $chapter $seconds" },
        deleted = { deleted++ },
        readAlong = { played += "read $it" },
    )

    private fun chapter(id: Int, duration: Double = 1500.0) = JSONObject().put("id", id).put("fullTitle", "Chương $id: Một cái tên chương khá dài để xuống dòng")
        .put("file", "audio/$id.m4a").put("available", true).put("duration", duration)

    private fun manifest(chapters: Int = 12, complete: Boolean = true, title: String = "Dế Mèn phiêu lưu ký · Tập 2") = JSONObject()
        .put("id", "b1").put("title", title).put("author", "Tô Hoài").put("narrator", "Hoài My").put("complete", complete)
        .put("chaptersTotal", chapters + if (complete) 0 else 3)
        .put("chapters", JSONArray((1..chapters).map { chapter(it) } + JSONObject().put("id", chapters + 1).put("fullTitle", "Chương ${chapters + 1}").put("available", false)))

    /** Đã nghe xong chương 1-2, chương 3 dở 40 %, chỗ nghe cuối ở chương 3. */
    private fun listening() = JSONObject()
        .put("chapters", JSONObject()
            .put("1", JSONObject().put("heard", 1500.0).put("done", true))
            .put("2", JSONObject().put("heard", 1500.0).put("done", true))
            .put("3", JSONObject().put("heard", 600.0).put("done", false)))
        .put("last", JSONObject().put("chapterId", 3).put("seconds", 600.0).put("at", 1_760_000_000.0))

    private fun finished() = JSONObject().put("finished", true)
        .put("chapters", JSONObject().apply { for (id in 1..12) put("$id", JSONObject().put("heard", 1500.0).put("done", true)) })
        .put("last", JSONObject().put("chapterId", 12).put("seconds", 1499.0).put("at", 1_760_000_000.0))

    private lateinit var source: FakeSource
    private val sheets = SheetHost()

    private fun show(detail: BookDetail?, dark: Boolean = false, player: PlayerState = PlayerState.Empty, texts: Map<Int, List<Passage>> = emptyMap()) {
        source = FakeSource(detail, texts)
        val book = detail?.book ?: BookDetail.of(manifest(), null, { null }).book
        rule.setContent {
            AbookTheme(dark) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    BookScreen(book, LibraryState.Ready(listOf(book)), player, PlayerClock(), CoverLoader(1 shl 20), source, sheets, actions)
                    SheetLayer(sheets)
                }
            }
        }
        rule.waitForIdle()
    }

    private fun shot(name: String) = rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")

    private fun detail(state: JSONObject? = null, complete: Boolean = true) = BookDetail.of(manifest(complete = complete), state, { null }, canShare = true)

    // ---- ảnh chụp ----

    @Test
    fun freshLight() {
        show(detail())
        rule.onNodeWithTag("book_title").assertIsDisplayed()
        rule.onNodeWithText("Tập 2").assertIsDisplayed()
        rule.onNodeWithText("Nghe").assertIsDisplayed()
        shot("book_fresh_light")
    }

    @Test
    fun freshDark() {
        show(detail(), dark = true)
        shot("book_fresh_dark")
    }

    @Test
    fun listeningLight() {
        show(detail(listening()))
        rule.onNodeWithText("Nghe tiếp").assertIsDisplayed()
        rule.onNode(hasText("Chương 3: Một cái tên chương khá dài để xuống dòng") and hasAnyAncestor(hasTestTag("book_primary")), useUnmergedTree = true)
            .assertIsDisplayed()
        rule.onNodeWithTag("chapter_3").assertIsSelected()
        shot("book_listening_light")
    }

    @Test
    fun openingNeverScrollsPastThePrimaryAndOffersAJumpToTheCurrentChapter() {
        val deep = JSONObject().put("last", JSONObject().put("chapterId", 11).put("seconds", 600.0).put("at", 1_760_000_000.0))
        show(detail(deep))
        rule.onNodeWithTag("book_primary").assertIsDisplayed()
        rule.onNodeWithTag("book_jump_current").assertIsDisplayed().performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("chapter_11").assertIsDisplayed()
    }

    /** Một luật căn cho cả hàng: biểu tượng trạng thái và nút "…" cùng tâm với dòng đầu của tên, kể cả khi tên xuống dòng. */
    @Test
    fun chapterRowIconsShareTheFirstLineCenter() {
        show(detail(listening()))
        val status = rule.onAllNodesWithTag("chapter_status", useUnmergedTree = true)
        val more = rule.onAllNodesWithTag("chapter_more", useUnmergedTree = true)
        for (i in 0 until 3) {
            val a = status[i].getUnclippedBoundsInRoot()
            val b = more[i].getUnclippedBoundsInRoot()
            val ca = (a.top + a.bottom) / 2
            val cb = (b.top + b.bottom) / 2
            assert((ca - cb).value in -0.5f..0.5f) { "hàng $i: tâm trạng thái $ca, tâm nút … $cb" }
        }
    }

    @Test
    fun noJumpWhenTheCurrentChapterIsAlreadyOnScreen() {
        show(detail(listening()))
        rule.onNodeWithTag("book_primary").assertIsDisplayed()
        rule.onNodeWithTag("book_jump_current").assertDoesNotExist()
    }

    @Test
    fun listeningDark() {
        show(detail(listening()), dark = true)
        shot("book_listening_dark")
    }

    @Test
    fun playingHereLight() {
        val player = PlayerState(bookId = "b1", chapterId = 3, chapterTitle = "Chương 3", playing = true, durationMs = 1_500_000)
        show(detail(listening()), player = player)
        rule.onNodeWithText("Tạm dừng").assertIsDisplayed()
        shot("book_playing_light")
    }

    @Test
    fun finishedDark() {
        show(detail(finished()), dark = true)
        rule.onNodeWithText("Nghe lại từ đầu").assertIsDisplayed()
        shot("book_finished_dark")
    }

    @Test
    fun partialBookLight() {
        show(detail(complete = false))
        rule.onNodeWithText("Sách này có 12/15 chương đã thu - các chương sau chưa có audio").assertIsDisplayed()
        shot("book_partial_light")
    }

    @Test
    fun beforeTheDetailIsReadTheHeadIsAlreadyThere() {
        show(null)
        rule.onNodeWithTag("book_title").assertIsDisplayed()
        shot("book_loading_light")
    }

    // ---- kịch bản bấm ----

    @Test
    fun primaryPlaysTheBookAtItsResumePoint() {
        show(detail(listening()))
        rule.onNodeWithTag("book_primary").performClick()
        assertEquals(listOf("book b1"), played)
    }

    @Test
    fun primaryTogglesWhenTheBookIsInThePlayer() {
        show(detail(listening()), player = PlayerState(bookId = "b1", chapterId = 3, playing = true))
        rule.onNodeWithTag("book_primary").performClick()
        assertEquals(1, toggles)
        assertTrue(played.isEmpty())
    }

    @Test
    fun finishedPrimaryRestartsFromTheFirstChapter() {
        show(detail(finished()))
        rule.onNodeWithTag("book_primary").performClick()
        assertEquals(listOf("chapter b1 1 0.0"), played)
    }

    @Test
    fun tappingAChapterPlaysItFromWhereItWasLeft() {
        show(detail(listening()))
        rule.onNodeWithTag("chapter_3").performClick()
        rule.onNodeWithTag("book_list").performScrollToNode(hasTestTag("chapter_5"))
        rule.onNodeWithTag("chapter_5").performClick()
        assertEquals(listOf("chapter b1 3 600.0", "chapter b1 5 0.0"), played)
    }

    @Test
    fun restartPlaysTheFirstChapter() {
        show(detail(listening()))
        rule.onNodeWithTag("book_restart").performClick()
        assertEquals(listOf("chapter b1 1 0.0"), played)
    }

    @Test
    fun menuLight() {
        show(detail(listening()))
        rule.onNodeWithTag("book_more").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("menu_edit").assertIsDisplayed()
        rule.onNodeWithTag("menu_share").assertIsDisplayed()
        rule.onNodeWithTag("menu_read").assertIsDisplayed()
        shot("book_menu_light")
    }

    @Test
    fun readAlongInTheMenuClosesTheSheetAndAsksForTheBook() {
        show(detail(listening()))
        rule.onNodeWithTag("book_more").performClick()
        rule.waitForIdle()
        rule.onNode(hasText("Sắp có") and hasAnyAncestor(hasTestTag("menu_read"))).assertDoesNotExist()
        rule.onNodeWithTag("menu_read").performClick()
        rule.waitForIdle()
        assertEquals(listOf("read b1"), played)
        rule.onNodeWithTag("book_menu").assertDoesNotExist()
    }

    @Test
    fun readAlongIsOffWithoutAnyTextToFollowAndSaysNothingAboutSoon() {
        show(BookDetail.of(manifest(chapters = 0), null, { null }))
        rule.onNodeWithTag("book_more").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("menu_read").assertIsDisplayed()
        rule.onNodeWithTag("menu_read").performClick()
        assertTrue(played.isEmpty())
        // "Sắp có" còn lại đúng một chỗ: Xuất MP3 / M4B, việc native chưa làm.
        rule.onAllNodesWithText("Sắp có").assertCountEquals(1)
    }

    @Test
    fun deleteAsksInsideTheSheetFirst() {
        show(detail(listening()))
        rule.onNodeWithTag("book_more").performClick()
        rule.onNodeWithTag("menu_delete").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("delete_confirm").assertIsDisplayed()
        shot("book_delete_light")
        assertTrue(source.calls.isEmpty())
        // "Giữ lại" về danh sách việc, không xoá gì.
        rule.onNodeWithTag("delete_keep").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("menu_delete").performClick()
        rule.onNodeWithTag("delete_yes").performClick()
        rule.waitForIdle()
        assertEquals(listOf("delete b1"), source.calls)
        assertEquals(1, deleted)
    }

    @Test
    fun deleteConfirmDark() {
        show(detail(listening()), dark = true)
        rule.onNodeWithTag("book_more").performClick()
        rule.onNodeWithTag("menu_delete").performClick()
        rule.waitForIdle()
        shot("book_delete_dark")
    }

    @Test
    fun editSavesOnlyWhatChanged() {
        show(detail(listening()))
        rule.onNodeWithTag("book_more").performClick()
        rule.onNodeWithTag("menu_edit").performClick()
        rule.waitForIdle()
        shot("book_edit_light")
        rule.onNodeWithTag("edit_author").performTextReplacement("Tô  Hoài ")
        rule.onNodeWithTag("edit_save").performClick()
        rule.waitForIdle()
        // Tác giả chỉ khác khoảng trắng: không lưu gì; tên không đổi: không lưu tên.
        assertEquals(emptyList<String>(), source.calls)
        rule.onNodeWithTag("book_more").performClick()
        rule.onNodeWithTag("menu_edit").performClick()
        rule.onNodeWithTag("edit_title").performTextReplacement("Tên mới")
        rule.onNodeWithTag("edit_save").performClick()
        rule.waitForIdle()
        assertEquals(listOf("rename Tên mới"), source.calls)
    }

    @Test
    fun markFinishedFromTheMenu() {
        show(detail(listening()))
        rule.onNodeWithTag("book_more").performClick()
        rule.onNodeWithTag("menu_finished").performClick()
        rule.waitForIdle()
        assertEquals(listOf("finished true"), source.calls)
    }

    @Test
    fun chapterSheetMarksAChapter() {
        show(detail(listening()))
        rule.onAllNodesWithTag("chapter_more")[0].performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("chapter_sheet").assertIsDisplayed()
        rule.onNodeWithTag("chapter_done").performClick()
        rule.waitForIdle()
        assertEquals(listOf("done 1 false"), source.calls)
    }

    @Test
    fun findPlaysFromTheSentenceFound() {
        val texts = mapOf(
            2 to listOf(Passage("Dế Mèn gặp chị Cốc ở bờ ao.", 61.5)),
            4 to listOf(Passage("Chưa gặp ai.", 1.0), Passage("Lại gặp chị Cốc.", 130.0)),
        )
        show(detail(listening()), texts = texts)
        rule.onNodeWithTag("book_find").performClick()
        rule.onNodeWithTag("find_field").performTextInput("chi coc")
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("find_hit").fetchSemanticsNodes().size == 2 }
        shot("book_find_light")
        rule.onAllNodesWithTag("find_hit")[1].performClick()
        assertEquals(listOf("chapter b1 4 130.0"), played)
    }
}
