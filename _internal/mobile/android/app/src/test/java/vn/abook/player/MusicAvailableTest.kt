package vn.abook.player

import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.net.UnknownHostException

/**
 * Bộ chọn nhạc theo cảnh trên điện thoại hỏi `MusicCatalog.available` - cùng luật với `music_track_available(sizes=False)` của máy tính (soát a47 mục 10): bài đã tải thì
 * luôn được; chưa tải thì không nếu nguồn của nó vừa hỏng vì mạng, cả máy đang mất mạng (từ hai nguồn cùng hỏng), hay bài vừa tải hỏng thật (24 giờ); quá 40 MB thì không.
 */
class MusicAvailableTest {
    private lateinit var root: File
    private var now = 1_000_000L
    private val bytes = "ID3 bài".toByteArray()

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-music-available")
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    private fun catalog(dead: Set<String> = emptySet()) = MusicCatalog(File(root, "cache"), "https://catalog/", open = { url ->
        if (dead.any { url.startsWith("https://$it/") }) throw UnknownHostException(url) else bytes.inputStream()
    }, clock = { now })

    private fun fail(catalog: MusicCatalog, link: String) {
        assertTrue(runCatching { catalog.download(link, null) }.exceptionOrNull() is MusicCatalog.Offline)
    }

    @Test
    fun aDeadSourceOnlyLocksItsOwnTracksAndRecoversAfterTheRest() {
        val catalog = catalog(dead = setOf("dead.example"))
        assertTrue(catalog.available("https://dead.example/a.mp3"))
        fail(catalog, "https://dead.example/a.mp3")
        assertFalse(catalog.available("https://dead.example/b.mp3"))
        assertTrue("một nguồn hỏng chưa là cả máy mất mạng", catalog.available("https://alive.example/c.mp3"))
        now += MusicCatalog.HOST_REST_MS
        assertTrue(catalog.available("https://dead.example/b.mp3"))
    }

    @Test
    fun twoSourcesDownAtOnceMeansTheMachineIsOfflineExceptForTracksAlreadyDownloaded() {
        val catalog = catalog(dead = setOf("one.example", "two.example"))
        assertNotNull(catalog(dead = emptySet()).download("https://three.example/kept.mp3", null)) // đã tải khi còn mạng
        fail(catalog, "https://one.example/a.mp3")
        fail(catalog, "https://two.example/b.mp3")
        assertTrue(catalog.offline())
        assertFalse("máy mất mạng: bài chưa tải thì bộ chọn không chọn", catalog.available("https://three.example/c.mp3"))
        assertTrue("bài đã tải thì vẫn được", catalog.available("https://three.example/kept.mp3"))
        now += MusicCatalog.HOST_REST_MS
        assertTrue(catalog.available("https://three.example/c.mp3"))
    }

    @Test
    fun aTrackThatFailedForRealIsAvoidedForADayAndAnOversizeOneForever() {
        val catalog = catalog()
        val link = "https://alive.example/gone.mp3"
        catalog.markUnavailable(link)
        assertFalse(catalog.available(link))
        now += MusicCatalog.UNAVAILABLE_MS - 1
        assertFalse(catalog.available(link))
        now += 1
        assertTrue(catalog.available(link))
        val huge = org.json.JSONObject().put("bytes", MusicCatalog.TRACK_MAX_BYTES + 1)
        assertTrue(runCatching { catalog.download("https://alive.example/huge.mp3", huge) }.exceptionOrNull() is MusicCatalog.TrackTooBig)
        assertFalse(catalog.available("https://alive.example/huge.mp3"))
        assertFalse("nhạc của người dùng nhập không tải từ đâu được", catalog.available(MusicStore.LOCAL_PREFIX + "abc"))
    }
}
