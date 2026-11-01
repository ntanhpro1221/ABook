package vn.abook.player

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.File
import java.io.IOException
import java.io.InputStream

/** Lượt tải sẵn chương kế đứng nhường giọng đọc ([MusicCatalog.download] `yields`): đứng rồi chạy tiếp ra bài đủ; đứt vì mạng sau lúc đứng không làm nguồn bị coi là hỏng. */
class MusicWarmYieldTest {
    private lateinit var root: File
    private val good = ByteArray(5000) { (it % 251).toByte() }
    private val link = "https://x/next.mp3"

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-music-warm-yield")
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    private fun catalog(open: (String) -> InputStream) = MusicCatalog(File(root, "cache"), "https://catalog/", open = open, publicKey = CatalogSigning.publicKey)

    @Test
    fun aStandingDownloadWaitsThenFinishesTheWholeTrack() {
        var asked = 0
        var readsWhileStanding = 0
        var standing = true
        val catalog = catalog({
            object : InputStream() {
                private val body = ByteArrayInputStream(good)
                override fun read(): Int = body.read()
                override fun read(b: ByteArray, off: Int, len: Int): Int {
                    if (standing) readsWhileStanding++
                    return body.read(b, off, len)
                }
            }
        })
        val file = catalog.download(link, null) {
            asked++
            standing = asked <= 3 // giọng thiếu đệm ba lần hỏi đầu
            standing
        }
        assertEquals(good.size.toLong(), file!!.length())
        assertEquals("không đọc gì từ mạng lúc đang nhường", 0, readsWhileStanding)
        assertTrue(asked > 3)
    }

    @Test
    fun aDropAfterStandingIsYieldedAndTheHostStaysUsable() {
        var asked = 0
        val catalog = catalog({
            object : InputStream() {
                private var served = false
                override fun read(): Int = throw IOException("reset")
                override fun read(b: ByteArray, off: Int, len: Int): Int {
                    if (served) throw IOException("Connection reset") // nguồn đóng kết nối nằm im lâu
                    served = true
                    return 1000.also { good.copyInto(b, off, 0, it) }
                }
            }
        })
        val error = runCatching { catalog.download(link, null) { ++asked == 1 } }.exceptionOrNull()
        assertTrue("đứt sau lúc đứng nhường: $error", error is MusicCatalog.Yielded)
        assertFalse("nguồn không bị coi là mất mạng", catalog.hostDown(link))
        assertTrue("không để lại .part", File(root, "cache/files").listFiles().orEmpty().isEmpty())
    }

    @Test
    fun aDropWithoutStandingIsStillOffline() {
        val catalog = catalog({ MusicCatalog.Sized(ByteArrayInputStream(good.copyOf(1000)), good.size.toLong()) })
        val error = runCatching { catalog.download(link, null) { false } }.exceptionOrNull()
        assertTrue("$error", error is MusicCatalog.Offline)
        assertTrue(catalog.hostDown(link))
    }
}
