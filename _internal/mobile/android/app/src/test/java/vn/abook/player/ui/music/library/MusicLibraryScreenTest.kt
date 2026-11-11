package vn.abook.player.ui.music.library

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performTextReplacement
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.text.TextLayoutResult
import vn.abook.player.ui.snapshot.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.MusicLibrary
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.components.hasOrphanLastLine
import vn.abook.player.ui.components.separatorsAtLineEnd
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import java.io.IOException

/** Kho nhạc giả: 48 bài như phòng trưng bày web (tên dài ngắn lẫn lộn), vài bài đã lưu / đã tải, tải giả chạy tức thì hay treo ở 44 %. */
class FakeLibrarySource : LibrarySource {
    private val styles = listOf("eastern_ancient" to "Cổ phong phương Đông", "orchestral_epic" to "Giao hưởng hùng tráng", "piano" to "Piano", "ambient" to "Ambient / không gian", "dark" to "U tối / kinh dị")
    private val emotions = listOf(
        "peacefulness" to "bình yên", "tenderness" to "dịu dàng", "nostalgia" to "hoài niệm", "sadness" to "buồn", "joy" to "vui tươi", "playful" to "tinh nghịch",
        "power" to "hào hùng", "wonder" to "kỳ vĩ", "tension" to "căng thẳng", "fear" to "rùng rợn", "anger" to "giận dữ", "mystery" to "bí ẩn", "moved" to "xúc động",
    )
    private val titles = listOf(
        "Ghostpocalypse - 5 Apotheosis", "Air Prelude", "Mưa trên phố cổ", "Bản tình ca của những người lữ hành trong đêm dài không trăng", "Clean Soul", "Đồi gió",
        "Hành khúc đêm", "Long Road Ahead", "Lantern Festival", "Moonlight Hall", "Sương mù", "Thunder Dreams",
    )
    private val creators = listOf("Kevin MacLeod", "Scott Buckley", "Shane Ivers", "Nhóm nhạc rất dài tên để kiểm chữ xuống dòng ở người sáng tác")
    val raw: Map<String, JSONObject> = (0 until 48).associate { index ->
        "https://music.example/$index.mp3" to JSONObject()
            .put("title", titles[index % titles.size] + if (index >= titles.size) " ${index / titles.size + 1}" else "")
            .put("creator", creators[index % creators.size]).put("duration", 45 + (index * 53) % 420).put("bpm", 60 + (index * 17) % 110)
            .put("style", styles[index % styles.size].first).put("bytes", 2_400_000 + index * 91_000).put("lufs", -16 - index % 6).put("audibleStart", 0.4)
            .put("arousal", ((index * 29) % 200) / 100.0 - 1).put("vocals", if (index % 5 == 0) 0.8 else 0.1)
            .put("license", if (index % 4 == 3) "cc0" else "by")
            .put("attribution", if (index % 4 == 3) "" else "\"${titles[index % titles.size]}\" ${creators[index % creators.size]}, Licensed under Creative Commons: By Attribution 4.0")
            .put("landing", "https://incompetech.com/music/royalty-free/")
            .put("emotions", JSONObject(emotions.mapIndexed { at, (id, _) -> id to ((index * 37 + at * 53) % 100) / 100.0 }.toMap()))
    }
    private val links = raw.keys.toList()
    val saved = links.filterIndexed { at, _ -> at % 7 == 0 }.toMutableList()
    val onDisk = saved.toMutableSet()
    var failLoad = false
    var metered = false
    var online = true
    /** Tải giả: null = xong ngay; số = treo ở phần trăm ấy (ảnh "đang tải"). */
    var stallAt: Int? = null
    val downloads = ArrayList<String>()

    override fun load(): LibraryIndex {
        if (failLoad) throw IOException("Chưa tải được danh mục nhạc nền - cần mạng ở lần đầu.")
        val playlists = listOf(
            LibraryPlaylist("fantasy_adventure", "Kỳ ảo phiêu lưu", links.filterIndexed { at, _ -> at % 3 == 0 }),
            LibraryPlaylist("calm_reading", "Đọc êm", links.filterIndexed { at, _ -> at % 4 == 1 }),
        )
        return LibraryIndex(MusicLibrary.tracksOf(raw), playlists, styles.map { Label(it.first, it.second) }, emotions.map { Label(it.first, it.second) })
    }

    override fun downloaded(links: Collection<String>) = links.filterTo(HashSet()) { it in onDisk }
    override fun saved() = saved.toList()
    override fun save(links: List<String>) {
        saved.removeAll(links.toSet())
        saved.addAll(links)
    }

    override fun unsave(links: List<String>) {
        saved.removeAll(links.toSet())
        onDisk.removeAll(links.toSet())
    }

    override fun download(link: String, progress: (Long, Long?) -> Unit, cancelled: () -> Boolean) {
        downloads += link
        val stall = stallAt
        if (stall != null) {
            progress(stall * 10_000L, 1_000_000L)
            throw IOException("treo")
        }
        onDisk += link
    }

    override fun forget(link: String) {
        onDisk -= link
    }

    override fun partial(link: String) = 0L
    override fun metered() = metered
    override fun online() = online
}

class SilentPreview : PreviewPlayer {
    val played = ArrayList<String>()
    var stops = 0
    override fun play(link: String, startSeconds: Double, volume: Float, onEnd: () -> Unit) {
        played += link
    }

    override fun stop() {
        stops++
    }
}

/**
 * Màn Nhạc của điện thoại trên JVM với kho giả: ảnh chụp (Roborazzi) sáng / tối ở 360 dp, chữ 130 %, chế độ chọn, chi tiết bài, đang tải; cộng kịch bản
 * bấm thật (tìm, chip lọc, lưu qua mạng tính phí, dùng bài ở chế độ chọn, nghe thử dừng sách).
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class MusicLibraryScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val sheets = SheetHost()
    private val source = FakeLibrarySource()
    private val preview = SilentPreview()
    private var paused = 0
    private val used = ArrayList<String>()
    private lateinit var state: LibraryState

    private fun show(dark: Boolean = false, part: MusicPart = MusicPart.Library, pick: Boolean = false) {
        state = LibraryState(source, CoroutineScope(Dispatchers.Unconfined), preview, pauseBook = { paused++ }, io = Dispatchers.Unconfined)
        val target = if (pick) PickTarget({ used += it }, { used += "ban:$it" }) else null
        rule.setContent {
            AbookTheme(dark) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    MusicScreen(state, sheets, pick = target, onBack = if (pick) ({}) else null, onMyMusic = {}, initialPart = part)
                    SheetLayer(sheets)
                }
            }
        }
        rule.waitForIdle()
    }

    private fun theme(dark: Boolean) = if (dark) "dark" else "light"

    private fun shot(name: String) {
        rule.waitForIdle()
        rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")
    }

    private fun tap(tag: String) {
        rule.onNodeWithTag(tag).performClick()
        rule.waitForIdle()
    }

    private fun link(index: Int) = "https://music.example/$index.mp3"

    // ---- Ảnh chụp ----

    private fun library(dark: Boolean) {
        show(dark)
        rule.onNodeWithTag("music_count").assertIsDisplayed()
        shot("music_library_${theme(dark)}")
    }

    @Test fun libraryLight() = library(false)
    @Test fun libraryDark() = library(true)

    private fun saved(dark: Boolean) {
        show(dark, MusicPart.Saved)
        rule.onNodeWithTag("music_saved_summary").assertIsDisplayed()
        shot("music_saved_${theme(dark)}")
    }

    @Test fun savedLight() = saved(false)
    @Test fun savedDark() = saved(true)

    @Test
    @Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi", fontScale = 1.3f)
    fun libraryLargeText() {
        show()
        checkRowText()
        shot("music_library_font130_light")
    }

    /** Inspect the real TextWrap layouts rather than inferring line breaks from screenshots. */
    private fun checkRowText() {
        for ((tag, maxLines) in listOf("music_row_title" to 2, "music_row_creator" to 1, "music_row_duration" to 1)) {
            val nodes = rule.onAllNodesWithTag(tag, useUnmergedTree = true).fetchSemanticsNodes()
            assertTrue("no measured $tag", nodes.isNotEmpty())
            for (node in nodes) {
                val measured = ArrayList<TextLayoutResult>()
                node.config[SemanticsActions.GetTextLayoutResult].action!!.invoke(measured)
                val layout = measured.single()
                assertTrue("$tag: ${layout.layoutInput.text}", layout.lineCount <= maxLines)
                if (tag != "music_row_title") {
                    val text = layout.layoutInput.text.text
                    val ends = (0 until layout.lineCount).map { layout.getLineEnd(it) }
                    assertTrue("separator at a metadata break: $text", separatorsAtLineEnd(text, ends).isEmpty())
                    assertTrue("orphan in metadata: $text", !hasOrphanLastLine(listOf(text)))
                }
            }
        }
        val columns = rule.onAllNodesWithTag("music_row_duration", useUnmergedTree = true).fetchSemanticsNodes()
        assertTrue("metadata must be measured", columns.isNotEmpty())
        val downloads = rule.onAllNodes(SemanticsMatcher("download column") {
            it.config.getOrNull(SemanticsProperties.TestTag)?.startsWith("download_") == true
        }, useUnmergedTree = true).fetchSemanticsNodes()
        assertTrue("every measured row has a download status", downloads.size >= columns.size)
        val right = downloads.filter { it.boundsInRoot.width > 0f && it.boundsInRoot.height > 0f }.map { it.boundsInRoot.right }
        assertTrue("no visible download statuses", right.isNotEmpty())
        assertTrue("download column moved: $right", right.max() - right.min() < 1f)
        println("MUSIC_ROW_TEXT: measured ${columns.size} metadata rows; creator/duration <= 1 line; title <= 2 lines; separator detector clean; download column spread=${right.max() - right.min()} px")
    }

    @Test fun rowTextAt360dp100Percent() { show(); checkRowText() }

    @Test
    fun rowDownloadsAndCancellationUseTheExistingQueue() {
        show()
        rule.onNodeWithTag("music_list").performScrollToNode(hasTestTag("download_${link(1).hashCode()}"))
        tap("download_${link(1).hashCode()}")
        assertTrue(link(1) in state.ui.value.downloaded)
        rule.runOnUiThread { stateWithActive(link(1), 44) }
        tap("download_${link(1).hashCode()}")
        assertTrue(link(1) !in state.ui.value.active)
    }

    private fun pick(dark: Boolean) {
        show(dark, pick = true)
        shot("music_pick_${theme(dark)}")
    }

    @Test fun pickLight() = pick(false)
    @Test fun pickDark() = pick(true)

    private fun detail(dark: Boolean) {
        show(dark)
        rule.runOnUiThread { openTrack(sheets, state, link(5), null, scene = mapOf("joy" to 0.8, "power" to 0.6, "peacefulness" to 0.3)) }
        rule.waitForIdle()
        rule.onNodeWithTag("track_title").assertIsDisplayed()
        rule.onNodeWithTag("track_fit").assertIsDisplayed()
        shot("music_track_${theme(dark)}")
        rule.onNodeWithTag("emotion_anger").performScrollTo()
        shot("music_track_middle_${theme(dark)}")
        rule.onNodeWithTag("track_source").performScrollTo()
        rule.onNodeWithTag("track_credit").assertIsDisplayed()
        shot("music_track_bottom_${theme(dark)}")
    }

    @Test fun detailLight() = detail(false)
    @Test fun detailDark() = detail(true)

    private fun downloading(dark: Boolean) {
        source.stallAt = 44
        show(dark)
        rule.runOnUiThread { state.save(listOf(link(1))) }
        rule.waitForIdle()
        // Tải giả treo rồi hỏng: dòng ấy hiện "chưa tải xong"; một bài khác đang tải giữa chừng thì hiện phần trăm.
        rule.runOnUiThread { stateWithActive(link(2), 44) }
        shot("music_library_downloading_${theme(dark)}")
    }

    private fun stateWithActive(link: String, percent: Int) {
        val field = LibraryState::class.java.getDeclaredField("flow").apply { isAccessible = true }
        @Suppress("UNCHECKED_CAST")
        val flow = field.get(state) as kotlinx.coroutines.flow.MutableStateFlow<LibraryUi>
        flow.value = flow.value.copy(active = flow.value.active + (link to Loading(percent * 10_000L, 1_000_000L)))
    }

    @Test fun downloadingLight() = downloading(false)
    @Test fun downloadingDark() = downloading(true)

    // ---- Kịch bản ----

    @Test
    fun searchIgnoresMarksAndChipsFilter() {
        show()
        val all = state.ui.value.shown.size
        assertEquals(48, all)
        rule.onNodeWithTag("music_search").performTextReplacement("MUA TREN")
        rule.waitForIdle()
        assertTrue(state.ui.value.shown.isNotEmpty())
        assertTrue(state.ui.value.shown.all { "Mưa trên" in it.title })
        rule.onNodeWithTag("music_search").performTextReplacement("")
        tap("chip_style")
        tap("option_piano")
        assertTrue(state.ui.value.shown.all { it.style == "piano" })
        // Chip "Đã tải" nằm ngoài khung 360 dp của hàng chip cuộn ngang: cuộn tới rồi mới bấm
        rule.onNodeWithTag("chip_downloaded").performScrollTo()
        tap("chip_downloaded")
        assertTrue(state.ui.value.filters.downloaded)
        assertTrue(state.ui.value.shown.all { it.link in source.onDisk })
        tap("music_clear")
        assertEquals(48, state.ui.value.shown.size)
        assertTrue("lọc 48 bài phải tức thì: ${state.ui.value.filterMs} ms", state.ui.value.filterMs < 50)
    }

    @Test
    fun savingOnMeteredNetworkAsksFirst() {
        source.metered = true
        show()
        rule.runOnUiThread { state.save(listOf(link(3))) }
        rule.waitForIdle()
        rule.onNodeWithTag("music_metered").assertIsDisplayed()
        assertTrue(source.downloads.isEmpty())
        tap("metered_go")
        assertEquals(listOf(link(3)), source.downloads)
        assertTrue(link(3) in source.saved)
        assertTrue(link(3) in state.ui.value.downloaded)
    }

    @Test
    fun unsavingRemovesTheDownload() {
        show(part = MusicPart.Saved)
        assertTrue(link(7) in state.ui.value.downloaded)
        rule.runOnUiThread { state.unsave(listOf(link(7))) }
        rule.waitForIdle()
        assertTrue(link(7) !in source.saved)
        assertTrue(link(7) !in source.onDisk)
    }

    @Test
    fun previewPausesTheBookAndStopsWhenLeaving() {
        show()
        // Danh sách ảo hoá xếp theo tên: bài 0 có thể chưa được dựng - cuộn tới trước
        rule.onNodeWithTag("music_list").performScrollToNode(hasTestTag("preview_${link(0).hashCode()}"))
        tap("preview_${link(0).hashCode()}")
        assertEquals(listOf(link(0)), preview.played)
        assertEquals(1, paused)
        rule.onNodeWithTag("preview_bar").assertIsDisplayed()
        tap("preview_stop")
        assertEquals(null, state.ui.value.previewing)
    }

    @Test
    fun offlinePreviewOnlyForDownloadedTracks() {
        source.online = false
        show()
        rule.runOnUiThread { state.togglePreview(link(1)) }
        assertEquals(emptyList<String>(), preview.played)
        rule.runOnUiThread { state.togglePreview(link(0)) } // bài 0 đã tải
        assertEquals(listOf(link(0)), preview.played)
    }

    @Test
    fun pickModeUsesTheTrack() {
        show(pick = true)
        rule.onNodeWithTag("music_list").performScrollToNode(hasTestTag("use_${link(4).hashCode()}"))
        tap("use_${link(4).hashCode()}")
        assertEquals(listOf(link(4)), used)
    }

    @Test
    fun brokenCatalogueShowsTheReasonAndRetries() {
        source.failLoad = true
        show()
        rule.onNodeWithTag("music_error").assertIsDisplayed()
        source.failLoad = false
        rule.runOnUiThread { state.open() }
        rule.waitForIdle()
        rule.onNodeWithTag("music_count").assertIsDisplayed()
    }
}
