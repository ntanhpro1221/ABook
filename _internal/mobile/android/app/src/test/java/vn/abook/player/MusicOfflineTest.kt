package vn.abook.player

import java.io.File
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.security.MessageDigest
import javax.net.ssl.SSLHandshakeException
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

/**
 * Mất mạng KHÔNG làm hỏng bài nhạc (MusicCatalog.download + MusicFailures.dropOffline) - cùng luật với `music_track_file` /
 * `_music_network_failure` / `_music_note` của webui/server.py: lỗi tầng mạng không đánh dấu bài, nguồn (host) hỏng nghỉ 5 phút và chỉ
 * khoá bài của chính nó; lỗi HTTP / bản sao sai thì bài mới hỏng thật.
 */
class MusicOfflineTest {
    private lateinit var root: File
    private var now = 1_000_000L
    private val bytes = "ID3 bài thật".toByteArray()
    private val sha = MessageDigest.getInstance("SHA-1").digest(bytes).joinToString("") { "%02x".format(it) }
    private val asked = mutableListOf<String>()

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-music-offline")
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    private fun catalog(open: (String) -> java.io.InputStream) = MusicCatalog(File(root, "cache"), "https://catalog/", open = { url ->
        asked += url
        open(url)
    }, clock = { now })

    @Test
    fun only_errors_without_an_http_answer_count_as_the_network() {
        for (error in listOf(UnknownHostException("a"), ConnectException("b"), SocketTimeoutException("c"), SSLHandshakeException("d"),
            java.io.InterruptedIOException("e"), java.io.EOFException("f"), IOException("unexpected end of stream"))) {
            assertTrue(error.toString(), MusicCatalog.isNetworkFailure(error))
        }
        for (error in listOf(MusicCatalog.HttpFailure(404), MusicCatalog.LocalFailure("bản sao khác"), MusicCatalog.TrackTooBig(1),
            java.io.FileNotFoundException("x"), IllegalStateException("không phải IO"))) {
            assertFalse(error.toString(), MusicCatalog.isNetworkFailure(error))
        }
    }

    @Test
    fun a_network_failure_keeps_the_track_good_and_rests_only_that_host() {
        val catalog = catalog { url -> if (url.startsWith("https://dead.example/")) throw UnknownHostException("dead") else bytes.inputStream() }
        val dead = "https://dead.example/a.mp3"
        assertTrue(runCatching { catalog.download(dead, null) }.exceptionOrNull() is MusicCatalog.Offline)
        assertNull(catalog.cached(dead))
        assertTrue(catalog.hostDown(dead))
        assertTrue(catalog.degraded())
        assertEquals(MusicCatalog.OFFLINE_MESSAGE, catalog.offlineNotice())
        // Nguồn khác không bị khoá, và bài của nguồn chết không chờ hết giờ thêm lần nữa trong lúc nghỉ.
        assertNotNull(catalog.download("https://alive.example/b.mp3", null))
        asked.clear()
        assertTrue(runCatching { catalog.download("https://dead.example/c.mp3", null) }.exceptionOrNull() is MusicCatalog.Offline)
        assertEquals("nguồn đang nghỉ: không gọi mạng", emptyList<String>(), asked)
        // Hết 5 phút: thử lại; nguồn sống lại thì xoá cờ.
        now += MusicCatalog.HOST_REST_MS
        assertFalse(catalog.hostDown(dead))
        assertFalse(catalog.degraded())
        assertEquals("", catalog.offlineNotice())
    }

    @Test
    fun an_http_error_or_a_wrong_mirror_is_a_broken_track_not_a_network_failure() {
        val catalog = catalog { url -> if (url == "https://mirror/bad.mp3") "khác".toByteArray().inputStream() else throw MusicCatalog.HttpFailure(404) }
        assertNull(catalog.download("https://x/gone.mp3", null))
        assertFalse("nguồn trả lời 404 = vẫn nối được", catalog.hostDown("https://x/gone.mp3"))
        val info = JSONObject().put("sha1", sha).put("bytes", bytes.size).put("mirrors", JSONArray(listOf("https://mirror/bad.mp3")))
        assertNull("bản sao sai: bài hỏng thật", catalog.download("https://x/gone2.mp3", info))
        assertFalse(catalog.degraded())
    }

    @Test
    fun a_dead_original_with_a_working_mirror_still_downloads_and_one_network_plus_one_http_failure_is_a_broken_track() {
        val info = JSONObject().put("sha1", sha).put("bytes", bytes.size).put("mirrors", JSONArray(listOf("https://mirror/good.mp3")))
        val catalog = catalog { url -> if (url == "https://mirror/good.mp3") bytes.inputStream() else throw UnknownHostException(url) }
        assertNotNull(catalog.download("https://x/a.mp3", info))
        val mixed = catalog { url -> if (url == "https://mirror/good.mp3") throw MusicCatalog.HttpFailure(404) else throw UnknownHostException(url) }
        assertNull("không phải mọi nguồn hỏng vì mạng", mixed.download("https://x/b.mp3", info))
    }

    @Test
    fun a_network_drop_never_uses_up_the_retry_budget() {
        val failures = MusicFailures { now }
        val link = "https://x/a.mp3"
        repeat(10) {
            failures.dropOffline(link)
            assertTrue(failures.isFailed(link))
            now += MusicFailures.RETRY_MS
            assertFalse("sau ${MusicFailures.RETRY_MS} ms lại thử được, lần thứ ${it + 1}", failures.isFailed(link))
        }
        // Còn bài hỏng thật thì vẫn có hạn như cũ.
        repeat(MusicFailures.DOWNLOAD_RETRIES + 1) { failures.dropDownload(link) }
        now += 24L * 3600 * 1000
        assertTrue(failures.isFailed(link))
    }

    @Test
    fun the_queue_keeps_playing_the_current_track_when_a_late_shard_adds_tracks() {
        val failures = MusicFailures { now }
        val queue = PlaylistQueue(failures)
        val a = Playlists.Track("https://x/a.mp3", 100.0, -8.0)
        val b = Playlists.Track("https://x/b.mp3", 100.0, -8.0)
        queue.load(listOf(a))
        queue.currentSpan = 0
        queue.replace(listOf(a, b), a.link, 10.0)
        assertEquals(2, queue.spans.size)
        assertEquals("bài đang kêu vẫn là bài ở giây ấy: không khởi động lại", 0, queue.currentSpan)
        queue.replace(listOf(b, a), a.link, 10.0)
        assertEquals("đồng hồ nay rơi vào bài khác: để MusicBed chuyển bài", -1, queue.currentSpan)
    }
}
