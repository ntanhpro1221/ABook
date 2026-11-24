package vn.abook.player

import java.io.File
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import vn.abook.player.ui.music.library.BookMusicRows
import vn.abook.player.ui.music.library.Label
import vn.abook.player.ui.music.library.LibraryIndex

/**
 * "Nhạc trong sách" (bookmusic2): cuốn đóng gói chỉ có nhạc riêng của người làm sách (`local:<sha1>` trong `music.tracks`) từng hiện
 * "Chưa có nhạc" dù đang phát nhạc - các dòng chỉ giữ bài có trong kho nhạc. Mọi bài cuốn dùng phải có dòng, theo thứ tự nghe, tên lấy từ book.json.
 */
class BookTrackNamesTest {
    private lateinit var root: File
    private val id = "f-0123456789abcdef0123bm02"
    private val first = "local:" + "a".repeat(40)
    private val second = "local:" + "b".repeat(40)
    private val catalog = "https://music.example/1.mp3"

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-bookmusic2")
        BookEditsFixtures.useStoreRoot(root)
    }

    private fun track(link: String, title: String, creator: String) =
        JSONObject().put("file", "music/${link.takeLast(6)}.opus").put("link", link).put("title", title).put("creator", creator)

    /** Gói như "Brunhild the Dragon Slayer.abook": chương 1 hai mốc, chương 2 quay lại bài đầu (+ một bài danh mục khi `mixed`). */
    private fun packagedBook(mixed: Boolean) {
        val dir = Store.bookDir(id).apply { mkdirs() }
        val tracks = JSONObject().put("music/a.opus", track(first, "float flower (MONSTER)", "Kuniaki Haishima"))
            .put("music/b.opus", track(second, "幻影の挽歌 (HUNTER×HUNTER (2011))", "Yoshihisa Hirano (平野義久)"))
        if (mixed) tracks.put("music/c.mp3", track(catalog, "Tên trong gói", "Người trong gói"))
        val one = JSONArray().put(JSONObject().put("start", 0.0).put("end", 136.3).put("track", "music/a.opus"))
            .put(JSONObject().put("start", 136.7).put("end", 221.1).put("track", "music/b.opus"))
        val two = JSONArray().put(JSONObject().put("start", 0.0).put("end", 90.0).put("track", "music/a.opus"))
        if (mixed) two.put(JSONObject().put("start", 90.0).put("end", 180.0).put("track", "music/c.mp3"))
        File(dir, "book.json").writeText(JSONObject().put("format", "abook-book/1").put("title", "Brunhild").put("package", JSONObject())
            .put("chapters", JSONArray().put(JSONObject().put("id", 1).put("title", "Một")).put(JSONObject().put("id", 2).put("title", "Hai")))
            .put("music", JSONObject().put("levelDb", -20.0).put("tracks", tracks).put("chapters", JSONObject().put("1", one).put("2", two))).toString())
        Store.rememberChapters(id, JSONObject(), imported = true)
    }

    private fun index() = LibraryIndex(MusicLibrary.tracksOf(mapOf(catalog to JSONObject().put("title", "Tên trong kho").put("creator", "Kevin MacLeod").put("bytes", 4096))),
        emptyList(), emptyList<Label>(), emptyList<Label>())

    @Test
    fun aBookOfPackagedTracksListsEveryTrackInListeningOrderWithItsName() {
        packagedBook(mixed = false)
        val entries = MusicLibrary.bookTracks(LocalStudio.bookScenes(id), LocalStudio.bookTrackNames(id))
        assertEquals(listOf(first to 2, second to 1), entries.map { it.link to it.scenes })
        assertEquals("float flower (MONSTER)", entries[0].title)
        assertEquals("Yoshihisa Hirano (平野義久)", entries[1].creator)
        // Không cần (và không chờ) kho nhạc: mọi dòng là bài đi kèm sách, không có gì để "Lưu tất cả".
        val rows = BookMusicRows.build(entries, null, emptyList(), emptySet())
        assertEquals(listOf(first, second), rows.tracks.map { it.first.link })
        assertEquals(setOf(first, second), rows.bundled)
        assertEquals("float flower (MONSTER)", rows.tracks[0].first.title)
        assertEquals(emptyList<String>(), rows.unsaved)
        assertEquals(0L, rows.missingBytes)
    }

    @Test
    fun aMixedBookKeepsCatalogRowsAndSavesOnlyThem() {
        packagedBook(mixed = true)
        val entries = MusicLibrary.bookTracks(LocalStudio.bookScenes(id), LocalStudio.bookTrackNames(id))
        assertEquals(listOf(first, second, catalog), entries.map { it.link })
        val rows = BookMusicRows.build(entries, index(), emptyList(), emptySet())
        assertEquals(listOf(first, second, catalog), rows.tracks.map { it.first.link })
        assertEquals(setOf(first, second), rows.bundled)
        assertEquals("bài danh mục dùng tên của kho", "Tên trong kho", rows.tracks[2].first.title)
        assertEquals(listOf(catalog), rows.unsaved)
        assertEquals(4096L, rows.missingBytes)
        // Bài danh mục kho không biết vẫn có dòng (tên theo gói), không lưu được.
        val unknown = BookMusicRows.build(entries, LibraryIndex(emptyList(), emptyList(), emptyList(), emptyList()), emptyList(), emptySet())
        assertEquals(setOf(first, second, catalog), unknown.bundled)
        assertEquals("Tên trong gói", unknown.tracks[2].first.title)
        assertEquals(emptyList<String>(), unknown.unsaved)
    }

    @Test
    fun aBookWithoutMusicHasNoRows() {
        val dir = Store.bookDir(id).apply { mkdirs() }
        File(dir, "book.json").writeText(JSONObject().put("format", "abook-book/1").put("title", "Không nhạc").put("package", JSONObject())
            .put("chapters", JSONArray().put(JSONObject().put("id", 1))).toString())
        Store.rememberChapters(id, JSONObject(), imported = true)
        assertEquals(emptyList<MusicLibrary.BookTrack>(), MusicLibrary.bookTracks(LocalStudio.bookScenes(id), LocalStudio.bookTrackNames(id)))
        assertEquals(emptyMap<String, MusicLibrary.TrackName>(), LocalStudio.bookTrackNames(id))
    }
}
