package vn.abook.player.ui.music

import android.content.Intent
import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
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
import vn.abook.player.ui.data.Passage
import vn.abook.player.ui.nowplaying.FakeNowPlayingModel
import vn.abook.player.ui.nowplaying.NowPlayingLayer
import vn.abook.player.ui.nowplaying.NowPlayingWindowState
import vn.abook.player.ui.nowplaying.PlayerSheet
import vn.abook.player.ui.nowplaying.rememberNowPlayingWindowState
import vn.abook.player.ui.screens.BookMenuSheet
import vn.abook.player.ui.screens.BookScreenActions
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/**
 * Nhạc nền ở hai chỗ của giao diện native: tấm "Nhạc nền" của trình phát (từ "Tuỳ chọn", Back về lại Tuỳ chọn) và trang "Nhạc nền" trong bảng "Thêm" của trang sách.
 * Ảnh sáng + tối của từng chỗ.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class MusicScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val demo = FakeNowPlayingModel.demoState().bookId
    private val source = FakeMusicSource().apply {
        books[demo] = BookMusic(MusicKind.Playlist, playlist = MusicText.SCENE, playlistAuto = true)
        books["b1"] = BookMusic(MusicKind.Packaged, levelDb = -18.0)
        menu = menu.copy(mine = 3)
    }
    private val music = MusicState(source, CoroutineScope(Dispatchers.Unconfined))
    private val credit = MusicCredit(
        "Rainy Night", "Kevin MacLeod", "\"Rainy Night\" Kevin MacLeod (incompetech.com)", "https://incompetech.com/music/", "by",
        "https://creativecommons.org/licenses/by/4.0/",
    )
    private lateinit var window: NowPlayingWindowState

    private fun shot(name: String) = rule.onRoot().captureRoboImage("src/test/snapshots/music_$name.png")

    private fun back() {
        rule.runOnUiThread { rule.activity.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
    }

    private fun showPlayer(dark: Boolean = false, playerMusic: PlayerMusic = PlayerMusic(credit, scene = true)) {
        val model = FakeNowPlayingModel(FakeNowPlayingModel.demoState().copy(music = playerMusic), music = music)
        rule.setContent {
            AbookTheme(dark) {
                window = rememberNowPlayingWindowState()
                LaunchedEffect(Unit) {
                    window.open()
                    window.openSheet(PlayerSheet.More)
                }
                NowPlayingLayer(model, window, sampleClock = false) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) }
            }
        }
        rule.waitForIdle()
    }

    private val actions = BookScreenActions(back = {}, playBook = {}, toggle = {}, playChapter = { _, _, _ -> }, deleted = {}, readAlong = {}, edit = {})

    private object NoBook : BookSource {
        override suspend fun detail(id: String): BookDetail? = null
        override suspend fun passages(id: String, chapter: ChapterLine): List<Passage>? = null
        override suspend fun setFinished(id: String, finished: Boolean) {}
        override suspend fun setChapterDone(id: String, chapterId: Int, done: Boolean) {}
        override suspend fun delete(id: String): String? = null
        override suspend fun share(id: String): Intent? = null
    }

    private fun showBookMenu(dark: Boolean = false, id: String = "b1") {
        val chapter = JSONObject().put("id", 1).put("fullTitle", "Chương 1").put("file", "audio/1.m4a").put("available", true).put("duration", 900.0)
        val manifest = JSONObject().put("id", id).put("title", "Dế Mèn phiêu lưu ký").put("author", "Tô Hoài").put("chapters", JSONArray(listOf(chapter)))
        val detail = BookDetail.of(manifest, null, { null })
        val sheets = SheetHost()
        rule.setContent {
            AbookTheme(dark) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    LaunchedEffect(Unit) { sheets.show { dismiss -> BookMenuSheet(detail.book, detail, NoBook, actions, dismiss, music) } }
                    SheetLayer(sheets)
                }
            }
        }
        rule.waitForIdle()
    }

    private fun playerMusicSheet(dark: Boolean) {
        showPlayer(dark)
        rule.onNodeWithText("Theo cảnh").assertIsDisplayed()
        rule.onNodeWithText("Nhạc nền").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("player_sheet_music").assertIsDisplayed()
        rule.onNodeWithTag("music_option_auto").assertIsDisplayed()
        shot("player_choices_${if (dark) "dark" else "light"}")
        rule.onNodeWithTag("music_panel").performScrollToNode(hasTestTag("music_credit_toggle"))
        rule.onNodeWithTag("music_credit_toggle").performClick()
        rule.waitForIdle()
        rule.onNodeWithText("CC BY 4.0").assertIsDisplayed()
        shot("player_credit_${if (dark) "dark" else "light"}")
    }

    @Test fun playerMusicSheetLight() = playerMusicSheet(dark = false)

    @Test fun playerMusicSheetDark() = playerMusicSheet(dark = true)

    @Test
    fun choosingInThePlayerSavesForThisBookAndBackReturnsToOptions() {
        showPlayer()
        rule.onNodeWithText("Nhạc nền").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("music_option_night_rain").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("music_panel").performScrollToNode(hasTestTag("music_level_-24"))
        rule.onNodeWithTag("music_level_-24").performClick()
        rule.waitForIdle()
        assertEquals(listOf("choose $demo night_rain", "level $demo -24.0"), source.calls)
        back()
        rule.onNodeWithTag("player_sheet_more").assertIsDisplayed()
        rule.onNodeWithText("Đêm mưa").assertIsDisplayed()
        back()
        assertTrue(!window.sheetOpen)
    }

    @Test
    fun aBookWithoutMusicHasNoMusicRow() {
        source.books.remove(demo)
        showPlayer(playerMusic = PlayerMusic.None)
        rule.onNodeWithTag("player_sheet_more").assertIsDisplayed()
        rule.onNodeWithText("Giọng").assertIsDisplayed()
        assertTrue(rule.onAllNodesWithText("Nhạc nền").fetchSemanticsNodes().isEmpty())
    }

    private fun bookMenuMusic(dark: Boolean) {
        showBookMenu(dark)
        rule.onNodeWithTag("menu_music_value", useUnmergedTree = true).assertIsDisplayed()
        shot("book_menu_${if (dark) "dark" else "light"}")
        rule.onNodeWithTag("menu_music", useUnmergedTree = true).captureRoboImage("src/test/snapshots/music_book_menu_row_${if (dark) "dark" else "light"}.png")
        rule.onNodeWithTag("menu_music").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("music_enabled").assertIsDisplayed()
        rule.onNodeWithText("Của sách").assertIsDisplayed()
        shot("book_page_${if (dark) "dark" else "light"}")
    }

    @Test fun bookMenuMusicLight() = bookMenuMusic(dark = false)

    @Test fun bookMenuMusicDark() = bookMenuMusic(dark = true)

    @Test
    fun theBookPageTurnsPackagedMusicOffAndBackGoesToTheMenu() {
        showBookMenu()
        rule.onNodeWithTag("menu_music").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("music_enabled").performClick()
        rule.waitForIdle()
        assertEquals(listOf("enable b1 false"), source.calls)
        back()
        rule.onNodeWithTag("menu_music").assertIsDisplayed()
        rule.onNodeWithText("Tắt").assertIsDisplayed()
    }
}
