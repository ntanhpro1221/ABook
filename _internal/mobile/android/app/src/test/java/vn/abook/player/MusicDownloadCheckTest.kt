package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.File
import java.security.MessageDigest

/**
 * Bài nhạc tải về phải đúng `bytes` / `sha1` của danh mục (FINDINGS_music B1: bài cụt hay bị đổi không được cất như bài tốt, bộ nhớ đệm hỏng được xoá và tải lại),
 * và bài phải ghi công mà thiếu tên tác giả không bao giờ được dùng (A2) - cùng luật với tests/test_music_credit_required.py.
 */
class MusicDownloadCheckTest {
    private lateinit var root: File
    private val good = ByteArray(5000) { (it % 251).toByte() }
    private val link = "https://x/calm.mp3"
    private val twin = "https://x/calm2.mp3"

    private fun sha1(bytes: ByteArray) = MessageDigest.getInstance("SHA-1").digest(bytes).joinToString("") { "%02x".format(it) }

    private fun info(bytes: ByteArray = good, mirrors: List<String> = emptyList()) =
        JSONObject().put("bytes", bytes.size).put("sha1", sha1(bytes)).put("mirrors", JSONArray(mirrors))

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-music-download-check")
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    private fun catalog(open: (String) -> java.io.InputStream, source: String = "https://catalog/") =
        MusicCatalog(File(root, "cache"), source, open = open, publicKey = CatalogSigning.publicKey)

    @Test
    fun theOriginalDownloadMustMatchTheCatalogBytesAndSha1() {
        val changed = good.copyOf().also { it[10] = 99 }
        var served: ByteArray = changed
        val catalog = catalog({ ByteArrayInputStream(served) })
        assertNull("bài khác sha1 danh mục không được cất", catalog.download(link, info()))
        assertNull(catalog.cached(link))
        served = good.copyOf(4000)
        assertNull("bài cụt (đủ HTTP 200 nhưng thiếu byte) không được cất", catalog.download(link, info()))
        assertNull(catalog.cached(link))
        served = good
        assertEquals(good.size.toLong(), catalog.download(link, info())!!.length())
    }

    @Test
    fun aStreamThatEndsBeforeItsContentLengthIsANetworkFailureNotAGoodTrack() {
        val catalog = catalog({ MusicCatalog.Sized(ByteArrayInputStream(good.copyOf(1000)), good.size.toLong()) })
        val error = runCatching { catalog.download(link, null) }.exceptionOrNull()
        assertTrue("tải đứt giữa chừng: lỗi mạng, bài vẫn tốt - $error", error is MusicCatalog.Offline)
        assertNull("không có file cụt để lần sau tưởng là bài tốt", catalog.cached(link))
    }

    @Test
    fun truncatedAndEmptyResponsesAreNotCachedAndTheNextDownloadRetries() {
        for ((name, body, length) in listOf(
            Triple("truncated", good.copyOf(1000), good.size.toLong()),
            Triple("empty-sized", byteArrayOf(), 0L),
            Triple("empty-unknown", byteArrayOf(), -1L),
        )) {
            var now = 1_000_000L
            var calls = 0
            val catalog = MusicCatalog(File(root, name), "https://catalog/", clock = { now }, open = {
                calls++
                val bytes = if (calls == 1) body else good
                if (calls == 1 && length >= 0) MusicCatalog.Sized(ByteArrayInputStream(bytes), length)
                else ByteArrayInputStream(bytes)
            }, publicKey = CatalogSigning.publicKey)
            val first = runCatching { catalog.download(link, null) }
            assertTrue("$name: không nhận file hỏng", first.getOrNull() == null)
            assertNull("$name: cache không có bài hỏng", catalog.cached(link))
            assertTrue("$name: không giữ file hay .part", File(root, "$name/files").listFiles().orEmpty().isEmpty())
            now += MusicCatalog.HOST_REST_MS + 1
            assertEquals("$name: tải lại đủ bài", good.size.toLong(), catalog.download(link, null)!!.length())
            assertEquals("$name: phải gọi nguồn lại", 2, calls)
        }
    }

    @Test
    fun aMirrorIsUsedWhenTheOriginalIsWrong() {
        val mirror = "https://mirror/calm.mp3"
        val catalog = catalog({ url -> ByteArrayInputStream(if (url == link) good.copyOf(100) else good) })
        val file = catalog.download(link, info(mirrors = listOf(mirror)))
        assertNotNull(file)
        assertEquals(good.size.toLong(), file!!.length())
    }

    @Test
    fun aCutFileInTheCacheIsDeletedAndDownloadedAgain() {
        val catalog = catalog({ ByteArrayInputStream(good) })
        val info = info()
        val file = catalog.download(link, info)!!
        file.writeBytes(good.copyOf(300)) // bản cũ cụt còn trong bộ nhớ đệm
        assertNull("trình phát hỏi bài với mục danh mục: file cụt bị xoá, không đưa cho ExoPlayer", catalog.use(link, info))
        assertFalse(file.exists())
        assertEquals(good.size.toLong(), catalog.download(link, info)!!.length())
        file.writeBytes(ByteArray(0)) // file rỗng không phải bài đã tải
        assertNull(catalog.cached(link))
        assertEquals(good.size.toLong(), catalog.download(link, info)!!.length())
        assertNotNull("bài đủ cỡ dùng như thường", catalog.use(link, info))
    }

    // ---- A2 ----------------------------------------------------------------------------------------------------

    @Test
    fun onlyATrackThatMustBeCreditedAndLacksTheAuthorIsRefused() {
        val credited = JSONObject().put("license", "by").put("creator", "Tác giả").put("attribution", "\"Calm\" by Tác giả")
        assertFalse(MusicCatalog.lacksCredit(credited))
        assertTrue(MusicCatalog.lacksCredit(JSONObject(credited.toString()).put("creator", "")))
        assertTrue(MusicCatalog.lacksCredit(JSONObject(credited.toString()).put("creator", "  ")))
        assertTrue(MusicCatalog.lacksCredit(JSONObject(credited.toString()).put("attribution", JSONObject.NULL)))
        assertTrue("thiếu cả hai", MusicCatalog.lacksCredit(JSONObject().put("license", "by-sa")))
        assertFalse(MusicCatalog.lacksCredit(JSONObject().put("license", "cc0")))
        assertFalse(MusicCatalog.lacksCredit(JSONObject().put("license", "CC0").put("creator", "")))
        assertFalse("nhạc người dùng nhập không bị đòi", MusicCatalog.lacksCredit(JSONObject().put("source", "local").put("license", "by")))
        assertFalse("danh mục không ghi giấy phép: không có gì để đòi", MusicCatalog.lacksCredit(JSONObject()) || MusicCatalog.lacksCredit(null))
    }

    @Test
    fun aTrackWithoutAnAuthorFoundInTheCatalogueIsNotAvailableAnywhere() {
        val named = JSONObject().put("license", "by").put("creator", "Tác giả").put("attribution", "\"Calm\" by Tác giả").put("duration", 100)
        val nameless = JSONObject(named.toString()).put("creator", "").put("attribution", "\"Calm\" by  licensed")
        val cloud = File(root, "cloud").apply { mkdirs() }
        File(cloud, "tracks").mkdirs()
        val links = listOf(link, twin)
        for ((shard, group) in links.groupBy { MusicCatalog.shardOf(it) }) {
            val data = JSONObject()
            for (item in group) data.put(item, if (item == link) nameless else named)
            File(cloud, "tracks/$shard.json").writeText(data.toString())
        }
        CatalogSigning.writeManifest(cloud, JSONObject().put("format", "abook-music-catalog").put("version", 1).put("revision", "r1")
            .put("shards", JSONArray(links.map { MusicCatalog.shardOf(it) }.distinct())))
        val catalog = MusicCatalog(File(root, "cache"), cloud.path, publicKey = CatalogSigning.publicKey)
        assertTrue("chưa tra danh mục thì chưa biết", catalog.available(link))
        assertTrue("bộ chọn phải chọn lại", catalog.verifySizes(listOf(link, twin)))
        assertFalse(catalog.available(link))
        assertTrue("bài đủ ghi công vẫn dùng được", catalog.available(twin))
        assertFalse("tra rồi thì lần sau không báo nữa", catalog.verifySizes(listOf(link, twin)))
    }
}
