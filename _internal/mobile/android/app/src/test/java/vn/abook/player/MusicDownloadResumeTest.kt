package vn.abook.player

import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.net.UnknownHostException
import java.security.MessageDigest

/**
 * Bài nhạc tải đứt giữa chừng (nguồn chậm 11-30 KB/s, Wi-Fi chập chờn) không mất phần đã tải ([MusicCatalog.download]): `.part` của bài
 * nằm lại, lần sau tải tiếp bằng Range ([MusicCatalog.openUrl] `from`); nguồn không trả đúng phần còn lại thì tải lại từ 0. Đã nhận thêm
 * byte thì là nguồn chậm, không phải mất mạng: nguồn không nghỉ, tải sẵn xin lại ([MusicCatalog.Progressed]). Cùng luật với
 * `_music_download` của webui/server.py (tests/test_music_download_resumes.py).
 */
class MusicDownloadResumeTest {
    private lateinit var root: File
    private val full = ByteArray(1000) { (it * 7 % 251).toByte() }
    private val sha = MessageDigest.getInstance("SHA-1").digest(full).joinToString("") { "%02x".format(it) }
    private val link = "https://x/calm.mp3"
    private val info = JSONObject().put("bytes", full.size).put("sha1", sha)
    private val ranges = mutableListOf<Long>()

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-music-resume")
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    /** Nguồn gửi `body` rồi đứt (lỗi mạng) nếu `cut`, báo trước `length` byte. */
    private fun source(body: ByteArray, length: Long, from: Long = 0, cut: Boolean = false): InputStream =
        MusicCatalog.Sized(object : InputStream() {
            private val inner = ByteArrayInputStream(body)
            override fun read(): Int = throw UnsupportedOperationException()
            override fun read(b: ByteArray, off: Int, len: Int): Int {
                val n = inner.read(b, off, len)
                if (n < 0 && cut) throw IOException("unexpected end of stream")
                return n
            }
        }, length, from)

    private fun catalog(open: (String) -> InputStream, openFrom: (String, Long) -> InputStream) =
        MusicCatalog(File(root, "cache"), "https://catalog/", open = open, publicKey = CatalogSigning.publicKey, openFrom = { url, from ->
            ranges += from
            openFrom(url, from)
        })

    private fun parts() = File(root, "cache/files").listFiles { file -> file.name.endsWith(".part") }.orEmpty().map { it.length() }

    @Test
    fun aCutDownloadKeepsWhatItGotAndTheNextOneGoesOnFromThere() {
        val first = catalog({ source(full.copyOf(300), 1000, cut = true) }, { _, _ -> throw AssertionError("chưa có gì để tải tiếp") })
        val error = runCatching { first.download(link, info) }.exceptionOrNull()
        assertTrue("đứt sau khi đã có byte: $error", error is MusicCatalog.Progressed)
        assertTrue("Progressed vẫn là Offline (bài tốt, không tính vào số lần bỏ bài)", error is MusicCatalog.Offline)
        assertEquals("phần đã tải bị bỏ", listOf(300L), parts())
        assertNull("phần dở thành bài trong bộ đệm", first.cached(link))
        assertFalse("nguồn chậm bị cho nghỉ như mất mạng", first.hostDown(link))
        val next = catalog({ throw AssertionError("lần sau phải tải tiếp, không tải lại từ 0") }, { _, from -> source(full.copyOfRange(from.toInt(), 1000), 1000 - from, from) })
        val file = next.download(link, info)
        assertArrayEquals("nối phần tải tiếp sai chỗ", full, file!!.readBytes())
        assertEquals(listOf(300L), ranges)
        assertEquals(emptyList<Long>(), parts())
    }

    @Test
    fun aSourceThatIgnoresTheRangeIsDownloadedAgainFromZero() {
        runCatching { catalog({ source(full.copyOf(300), 1000, cut = true) }, { _, _ -> throw AssertionError() }).download(link, info) }
        val file = catalog({ throw AssertionError() }, { _, _ -> source(full, 1000) }).download(link, info) // 200 cả bài dù xin từ byte 300
        assertArrayEquals("nối cả bài vào sau phần cũ", full, file!!.readBytes())
        assertEquals(listOf(300L), ranges)
    }

    @Test
    fun aRangeTheSourceCannotServeStartsOver() {
        runCatching { catalog({ source(full.copyOf(300), 1000, cut = true) }, { _, _ -> throw AssertionError() }).download(link, info) }
        val file = catalog({ source(full, 1000) }, { _, _ -> throw MusicCatalog.HttpFailure(416) }).download(link, info)
        assertArrayEquals(full, file!!.readBytes())
        assertEquals(listOf(300L), ranges)
    }

    @Test
    fun aCutBeforeAnyByteIsStillTheNetwork() {
        val catalog = catalog({ throw UnknownHostException("x") }, { _, _ -> throw AssertionError() })
        val error = runCatching { catalog.download(link, info) }.exceptionOrNull()
        assertTrue("$error", error is MusicCatalog.Offline && error !is MusicCatalog.Progressed)
        assertEquals("giữ file dở rỗng", emptyList<Long>(), parts())
        assertTrue("chưa nhận byte nào là mất mạng: nguồn phải nghỉ", catalog.hostDown(link))
    }

    @Test
    fun aResumeThatAddsNothingIsTheNetworkAgain() {
        runCatching { catalog({ source(full.copyOf(300), 1000, cut = true) }, { _, _ -> throw AssertionError() }).download(link, info) }
        val catalog = catalog({ throw AssertionError() }, { _, _ -> throw UnknownHostException("x") })
        val error = runCatching { catalog.download(link, info) }.exceptionOrNull()
        assertTrue("$error", error is MusicCatalog.Offline && error !is MusicCatalog.Progressed)
        assertEquals("phần đã tải vẫn giữ để lần sau", listOf(300L), parts())
        assertTrue(catalog.hostDown(link))
    }

    @Test
    fun aWrongTrackAfterResumingIsNotKept() {
        runCatching { catalog({ source(full.copyOf(300), 1000, cut = true) }, { _, _ -> throw AssertionError() }).download(link, info) }
        val wrong = full.copyOf().also { it[999] = (it[999] + 1).toByte() }
        assertNull(catalog({ throw AssertionError() }, { _, from -> source(wrong.copyOfRange(from.toInt(), 1000), 1000 - from, from) }).download(link, info))
        assertEquals("bài sai sha1 không để lại phần dở", emptyList<Long>(), parts())
    }

    @Test
    fun pruneKeepsAPartThatCanStillBeResumed() {
        val now = 100L * 24 * 3600 * 1000
        val catalog = MusicCatalog(File(root, "cache"), "https://catalog/", clock = { now })
        val files = File(root, "cache/files").apply { mkdirs() }
        fun partOf(link: String, ageMs: Long) = File(files, MessageDigest.getInstance("SHA-1").digest(link.toByteArray()).joinToString("") { "%02x".format(it) } + ".mp3.part")
            .apply { writeBytes(full.copyOf(300)); setLastModified(now - ageMs) }
        val hour = partOf("https://x/hour.mp3", 3_600_000L)
        val oldKept = partOf("https://x/kept.mp3", 8L * 24 * 3600 * 1000)
        val oldGone = partOf("https://x/gone.mp3", 8L * 24 * 3600 * 1000)
        catalog.prune(keep = listOf("https://x/kept.mp3"))
        assertTrue("phần dở một giờ (từng bị xoá sau 10 phút) phải còn để tải tiếp", hour.isFile)
        assertTrue("phần dở của bài đang cần không bị xoá", oldKept.isFile)
        assertFalse("phần dở bỏ đã lâu vẫn được dọn", oldGone.isFile)
    }

    @Test
    fun theRealOpenerAsksForTheRestOfAFile() {
        val file = File(root, "src.mp3").apply { writeBytes(full) }
        val rest = MusicCatalog.openUrl(file.path, 300) as MusicCatalog.Sized
        assertEquals(300L, rest.from)
        assertEquals(700L, rest.length)
        assertArrayEquals(full.copyOfRange(300, 1000), rest.use { it.readBytes() })
    }
}
