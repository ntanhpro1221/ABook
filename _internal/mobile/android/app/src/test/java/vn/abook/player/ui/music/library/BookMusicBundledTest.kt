package vn.abook.player.ui.music.library

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.MusicLibrary
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.snapshot.captureRoboImage
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/**
 * "Nhạc trong sách" với bài đi kèm sách (bookmusic2): gói chỉ có nhạc `local:` của người làm sách hiện đủ bài (tên + người sáng tác theo book.json,
 * "N đoạn", không "Lưu tất cả"), kể cả khi kho nhạc trực tuyến không tải được; gói trộn giữ đủ chức năng cho bài danh mục; gói không nhạc vẫn "Chưa có nhạc".
 * Chạm bài đi kèm sách mở sheet ở mức có dữ liệu (tên, người sáng tác, cảm xúc của đoạn đầu tiên dùng bài khi mốc có).
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class BookMusicBundledTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val sheets = SheetHost()
    private val source = FakeLibrarySource()
    private lateinit var state: LibraryState

    private val float = "local:" + "a".repeat(40)
    private val phantom = "local:" + "b".repeat(40)
    private val chaos = "local:" + "c".repeat(40)
    private val catalog = "https://music.example/5.mp3"

    private val packaged = listOf(
        MusicLibrary.BookTrack(float, 4, "1:0", "float flower (MONSTER)", "Kuniaki Haishima"),
        MusicLibrary.BookTrack(phantom, 2, "1:136729", "幻影の挽歌 (HUNTER×HUNTER (2011))", "Yoshihisa Hirano (平野義久)"),
        MusicLibrary.BookTrack(chaos, 1, "2:0", "Chaos mind (STEINS;GATE)", "Takeshi Abo (阿保剛)"),
    )

    private fun show(entries: List<MusicLibrary.BookTrack>, dark: Boolean = false, moods: Map<String, Map<String, Double>> = emptyMap()) {
        state = LibraryState(source, CoroutineScope(Dispatchers.Unconfined), SilentPreview(), pauseBook = {}, io = Dispatchers.Unconfined)
        rule.setContent {
            AbookTheme(dark) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    val rows = BookMusicSection(state, sheets, Result.success(entries), moods) {}
                    LazyColumn(Modifier.fillMaxSize(), content = rows)
                    SheetLayer(sheets)
                }
            }
        }
        rule.waitForIdle()
    }

    private fun count(tag: String) = rule.onAllNodesWithTag(tag, useUnmergedTree = true).fetchSemanticsNodes().size

    /** Hàng bài dựng trên Dispatchers.IO thật (BookMusicRows.build) - waitForIdle không đợi nó. */
    private fun awaitRow(tag: String) = rule.waitUntil(10_000) { count(tag) > 0 }

    private fun shot(name: String) {
        rule.waitForIdle()
        rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")
    }

    private fun packagedOnly(dark: Boolean) {
        source.failLoad = true // kho nhạc trực tuyến hỏng: bài đi kèm sách không cần nó
        show(packaged, dark)
        awaitRow("bundled_${chaos.hashCode()}")
        assertEquals(3, count("music_row_bundled"))
        assertEquals(0, count("book_music_empty"))
        assertEquals(0, count("book_music_error"))
        assertEquals(0, count("book_music_save_all"))
        assertEquals(0, count("preview_${float.hashCode()}"))
        rule.onNodeWithTag("bundled_${float.hashCode()}").assertIsDisplayed()
        shot("music_book_bundled_${if (dark) "dark" else "light"}")
    }

    @Test fun packagedOnlyLight() = packagedOnly(false)
    @Test fun packagedOnlyDark() = packagedOnly(true)

    @Test
    fun mixedBookKeepsCatalogFeaturesInListeningOrder() {
        show(listOf(packaged[0], MusicLibrary.BookTrack(catalog, 3, "1:60000", "Tên trong gói", ""), packaged[1]))
        awaitRow("track_${catalog.hashCode()}")
        awaitRow("bundled_${phantom.hashCode()}")
        val tops = listOf("bundled_${float.hashCode()}", "track_${catalog.hashCode()}", "bundled_${phantom.hashCode()}")
            .map { rule.onNodeWithTag(it).fetchSemanticsNode().boundsInRoot.top }
        assertEquals("thứ tự nghe", tops.sorted(), tops)
        rule.onNodeWithTag("preview_${catalog.hashCode()}").assertIsDisplayed()
        rule.onNodeWithTag("book_music_save_all").assertIsDisplayed()
        // Cột chữ và mũi tên thẳng hàng giữa dòng danh mục và dòng đi kèm sách.
        val titles = rule.onAllNodesWithTag("music_row_title", useUnmergedTree = true).fetchSemanticsNodes().map { it.boundsInRoot.left }
        assertEquals(1, titles.distinct().size)
        shot("music_book_mixed_light")
    }

    @Test
    fun aBookWithoutMusicStillSaysSo() {
        show(emptyList())
        rule.onNodeWithTag("book_music_empty").assertIsDisplayed()
        assertEquals(0, count("music_row_bundled"))
    }

    private fun sheet(dark: Boolean, name: String) {
        show(packaged, dark, moods = mapOf("1:0" to mapOf("sadness" to 0.8, "nostalgia" to 0.6, "tenderness" to 0.3, "fear" to 0.1)))
        awaitRow("bundled_${float.hashCode()}")
        rule.waitUntil(10_000) { state.ui.value.index != null }
        rule.onNodeWithTag("bundled_${float.hashCode()}").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("bundled_sheet").assertIsDisplayed()
        rule.onNodeWithTag("bundled_note").assertIsDisplayed()
        rule.onNodeWithTag("bundled_mood").assertIsDisplayed()
        assertEquals(3, listOf("sadness", "nostalgia", "tenderness", "fear").sumOf { count("scene_emotion_$it") })
        assertEquals(0, count("track_save"))
        shot(name)
    }

    @Test fun bundledSheetLight() = sheet(false, "music_book_bundled_sheet_light")
    @Test fun bundledSheetDark() = sheet(true, "music_book_bundled_sheet_dark")

    @Test
    @Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi", fontScale = 1.3f)
    fun bundledSheetLargeText() = sheet(false, "music_book_bundled_sheet_font130_light")

    @Test
    fun aSceneWithoutMoodShowsOnlyTheName() {
        show(packaged)
        awaitRow("bundled_${chaos.hashCode()}")
        rule.onNodeWithTag("bundled_${chaos.hashCode()}").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("track_title").assertIsDisplayed()
        assertEquals(0, count("bundled_mood"))
    }
}
