package vn.abook.player

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

/**
 * Bộ nhớ bài nhạc của danh mục không phình mãi (soát a47 mục 5): quá trần thì xoá bài lâu không dùng nhất ([MusicCatalog.prune]), giữ bài đang kêu; file tải dở bỏ quá 10 phút
 * cũng xoá; mảnh của phiên bản danh mục cũ bị dọn ([MusicCatalog.pruneRevisions]).
 */
class MusicCachePruneTest {
    private lateinit var root: File
    private var now = 10_000_000_000L

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-music-prune")
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    private fun catalog() = MusicCatalog(File(root, "cache"), "https://catalog/", clock = { now })

    /** Tạo file của bài `link` (đúng đường dẫn mà catalog tìm), cỡ `size`, dùng lần cuối `ago` ms trước. */
    private fun track(catalog: MusicCatalog, link: String, size: Int, ago: Long): File {
        val sha = java.security.MessageDigest.getInstance("SHA-1").digest(link.toByteArray()).joinToString("") { "%02x".format(it) }
        val file = File(File(root, "cache/files"), "$sha.mp3")
        file.parentFile!!.mkdirs()
        file.writeBytes(ByteArray(size))
        file.setLastModified(now - ago)
        return file
    }

    @Test
    fun overTheCapTheLeastRecentlyUsedTracksGoFirstAndKeptOnesStay() {
        val catalog = catalog()
        val old = track(catalog, "https://a/old.mp3", 400, ago = 5_000_000)
        val middle = track(catalog, "https://a/middle.mp3", 400, ago = 3_000_000)
        val playing = track(catalog, "https://a/playing.mp3", 400, ago = 9_000_000) // lâu nhất nhưng đang kêu
        val fresh = track(catalog, "https://a/fresh.mp3", 400, ago = 1_000)
        catalog.prune(keep = listOf("https://a/playing.mp3"), capBytes = 1_000)
        assertFalse("bài cũ nhất ngoài danh sách giữ bị xoá trước", old.exists())
        assertFalse("rồi tới bài kế", middle.exists())
        assertTrue(playing.exists())
        assertTrue(fresh.exists())
    }

    @Test
    fun underTheCapNothingIsDeletedAndStalePartialDownloadsAre() {
        val catalog = catalog()
        val one = track(catalog, "https://a/one.mp3", 100, ago = 99_000_000)
        val staleDir = File(root, "cache/files")
        val stale = File(staleDir, "x.123.part").apply { writeBytes(ByteArray(10)); setLastModified(now - 700_000) }
        val live = File(staleDir, "y.456.part").apply { writeBytes(ByteArray(10)); setLastModified(now - 1_000) }
        catalog.prune(capBytes = 10_000)
        assertTrue("dưới trần: bài lâu không nghe vẫn giữ", one.exists())
        assertFalse("tải dở quá 10 phút: xoá", stale.exists())
        assertTrue("tải dở đang chạy: giữ", live.exists())
    }

    @Test
    fun onlyDownloadedCatalogTracksAreEverPrunedNotImportedMusicNorTheBooksOwn() {
        // Cùng luật với máy tính (music_cache.py): nhạc người dùng nhập (MusicStore, thư mục riêng) và nhạc sách mang theo (music/ trong thư mục sách) nằm NGOÀI thư mục bài tải của danh mục.
        val catalog = catalog()
        val old = track(catalog, "https://a/old.mp3", 400, ago = 5_000_000)
        val imported = File(root, "mine/files/${"0".repeat(40)}.mp3").apply { parentFile!!.mkdirs(); writeBytes(ByteArray(400)); setLastModified(now - 99_000_000) }
        val ofBook = File(root, "books/b1/music/${"1".repeat(40)}.mp3").apply { parentFile!!.mkdirs(); writeBytes(ByteArray(400)); setLastModified(now - 99_000_000) }
        catalog.prune(capBytes = 100)
        assertFalse(old.exists())
        assertTrue(imported.exists())
        assertTrue(ofBook.exists())
    }

    @Test
    fun usingATrackRefreshesItsAgeOnlyOnceAnHour() {
        val catalog = catalog()
        val file = track(catalog, "https://a/used.mp3", 10, ago = 7_200_000)
        assertNotNull(catalog.use("https://a/used.mp3"))
        assertEquals("quá một giờ: ghi lần dùng mới", now, file.lastModified())
        file.setLastModified(now - 60_000)
        catalog.use("https://a/used.mp3")
        assertEquals("trong một giờ: không ghi lại", now - 60_000, file.lastModified())
        assertNull(catalog.use("https://a/missing.mp3"))
    }

    @Test
    fun foldersOfOldCatalogRevisionsAreDroppedButFilesAndTheCurrentRevisionStay() {
        val catalog = catalog()
        val cache = File(root, "cache")
        val keptTrack = track(catalog, "https://a/keep.mp3", 10, ago = 0)
        for (revision in listOf("r1", "r2", "r3")) File(cache, "$revision/tracks").mkdirs().also { File(cache, "$revision/tracks/ab.json").writeText("{}") }
        File(cache, "manifest.json").writeText("{}")
        catalog.pruneRevisions("r3")
        assertFalse(File(cache, "r1").exists())
        assertFalse(File(cache, "r2").exists())
        assertTrue(File(cache, "r3/tracks/ab.json").exists())
        assertTrue(keptTrack.exists())
        assertTrue(File(cache, "manifest.json").exists())
    }
}
