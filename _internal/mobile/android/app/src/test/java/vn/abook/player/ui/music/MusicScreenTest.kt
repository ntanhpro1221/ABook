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
import vn.abook.player.ui.voice.FakeVoiceSource
import vn.abook.player.ui.voice.MineImports
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
 * Nhạc nền ở hai chỗ của giao diện native: tấm "Nhạc nền" của trình phát (từ "Thêm tuỳ chọn", Back về lại tấm ấy) và trang "Nhạc nền" trong bảng "Thêm" của trang sách.
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
        books["b1"] = BookMusic(
            MusicKind.Packaged, levelDb = -18.0,
            cues = listOf(
                MusicCue("1:0", 1, "Chương 1", 0.0, 95.0, "Rainy Night", "Kevin MacLeod"),
                MusicCue("1:95000", 1, "Chương 1", 95.0, 260.0, "Wallpaper", "Kevin MacLeod", silenced = true),
                MusicCue("2:0", 2, "Chương 2: Bắt đầu cuộc phiêu lưu", 0.0, 184.0, "Mưa đầu mùa", "Tôi", pinned = true),
                MusicCue("2:184000", 2, "Chương 2: Bắt đầu cuộc phiêu lưu", 184.0, 412.0, "Peaceful Desolation", "Kevin MacLeod"),
            ),
        )
        menu = menu.copy(mine = 3)
        mine += MineTrack("local:a", "Mưa đầu mùa", "Tôi", 184.0, analysed = true)
        mine += MineTrack("local:b", "Ru con", "Hà Anh", 151.0, analysed = true, vocalsLikely = true)
        mine += MineTrack("local:c", "Sóng", "", 95.0, analysed = false)
    }
    private val music = CoroutineScope(Dispatchers.Unconfined).let { MusicState(source, MineImports(FakeVoiceSource(), it), it) }
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
        rule.onNodeWithTag("music_panel").performScrollToNode(hasTestTag("music_levels"))
        rule.waitForIdle()
        rule.onNodeWithTag("music_levels").captureRoboImage("src/test/snapshots/music_player_levels_${if (dark) "dark" else "light"}.png")
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
        rule.onNodeWithText("Giọng đọc").assertIsDisplayed()
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
        rule.onNodeWithText("-18 dB (của sách)").assertIsDisplayed()
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

    private fun packagedCues(dark: Boolean) {
        val mode = if (dark) "dark" else "light"
        showBookMenu(dark)
        rule.onNodeWithTag("menu_music").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("music_panel").performScrollToNode(hasTestTag("music_cue_3"))
        rule.waitForIdle()
        rule.onNodeWithText("Chương 2: Bắt đầu cuộc phiêu lưu · 0:00 – 3:04 · Tôi · bài của bạn").assertIsDisplayed()
        shot("book_cues_$mode")
        rule.onNodeWithTag("music_cue_2").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("music_cue_page").assertIsDisplayed()
        rule.onNodeWithText("Về bài gốc").assertIsDisplayed()
        shot("cue_page_$mode")
        rule.onNodeWithTag("music_cue_swap").performClick()
        rule.waitForIdle()
        rule.onNodeWithText("Có vẻ có lời - máy không tự chọn bài này").assertIsDisplayed()
        shot("cue_swap_$mode")
    }

    @Test fun packagedCuesLight() = packagedCues(dark = false)

    @Test fun packagedCuesDark() = packagedCues(dark = true)

    @Test
    fun aCueIsSilencedSwappedAndBackLeavesItsPageOneStepAtATime() {
        showBookMenu()
        rule.onNodeWithTag("menu_music").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("music_panel").performScrollToNode(hasTestTag("music_cue_1"))
        rule.onNodeWithTag("music_cue_1").performClick()
        rule.waitForIdle()
        rule.onNodeWithText("Có nhạc").performClick()
        rule.waitForIdle()
        rule.onNodeWithText("Im lặng").assertIsDisplayed()
        rule.onNodeWithTag("music_cue_swap").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("music_mine_2").performClick()
        rule.waitForIdle()
        assertEquals(listOf("silence b1 1:95000 false", "alternatives b1 1:95000", "pin b1 1:95000 local:c"), source.calls)
        rule.onNodeWithText("Về bài gốc").assertIsDisplayed()
        rule.onNodeWithTag("music_cue_swap").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("music_swap").assertIsDisplayed()
        back()
        assertTrue("Back khép Đổi bài trước", rule.onAllNodes(hasTestTag("music_swap")).fetchSemanticsNodes().isEmpty())
        rule.onNodeWithTag("music_cue_page").assertIsDisplayed()
        back()
        rule.onNodeWithTag("music_enabled").assertIsDisplayed()
        back()
        rule.onNodeWithTag("menu_music").assertIsDisplayed()
    }

    @Test
    fun anEmptyStoreOffersToAddMusicRightThere() {
        source.mine.clear()
        showBookMenu()
        rule.onNodeWithTag("menu_music").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("music_panel").performScrollToNode(hasTestTag("music_cue_0"))
        rule.onNodeWithTag("music_cue_0").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("music_cue_swap").performClick()
        rule.waitForIdle()
        rule.onNodeWithText(MusicText.NO_MINE).assertIsDisplayed()
        rule.onNodeWithText(MusicText.ADD_LABEL).assertIsDisplayed()
    }
}
