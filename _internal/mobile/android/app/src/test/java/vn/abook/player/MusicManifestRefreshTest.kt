package vn.abook.player

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Làm mới mục lục danh mục khi quá 24 giờ (soát a47, phần nhỏ): lượt gọi mạng chậm / hỏng không giữ khoá chung (hỏi bài vẫn chạy), và làm mới hỏng thì không bị thử lại ở mỗi lần hỏi.
 */
class MusicManifestRefreshTest {
    private lateinit var root: File
    private var now = System.currentTimeMillis()

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-manifest-refresh")
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    private fun nextDay() {
        now += 25L * 3600 * 1000
    }

    @Test
    fun aFailedRefreshIsNotRetriedOnEveryAskButOnlyOnceAMinute() {
        val cloud = CatalogSigning.cloud(root)
        var manifestFetches = 0
        var offline = false
        val catalog = MusicCatalog(File(root, "cache"), cloud.path, open = { url ->
            if (url.endsWith("manifest.json")) manifestFetches += 1
            if (offline) throw IOException("mất mạng")
            MusicCatalog.openUrl(url)
        }, clock = { now }, publicKey = CatalogSigning.publicKey, log = {})
        assertNotNull(catalog.manifest())
        assertEquals(1, manifestFetches)
        nextDay()
        offline = true
        repeat(5) { assertNotNull("mất mạng thì dùng bản đã cất", catalog.manifest()) }
        assertEquals("một lần thử rồi nghỉ, không phải năm lần", 2, manifestFetches)
        now += MusicCatalog.MANIFEST_RETRY_MS
        assertNotNull(catalog.manifest())
        assertEquals(3, manifestFetches)
        // Có mạng lại: làm mới được, rồi không hỏi nữa (đã tươi).
        offline = false
        now += MusicCatalog.MANIFEST_RETRY_MS
        assertNotNull(catalog.manifest())
        assertEquals(4, manifestFetches)
        File(root, "cache/manifest.json").setLastModified(now) // giờ file theo đồng hồ giả
        assertNotNull(catalog.manifest())
        assertEquals(4, manifestFetches)
    }

    @Test
    fun aSlowRefreshDoesNotBlockOtherCatalogCalls() {
        val cloud = CatalogSigning.cloud(root)
        val gate = CountDownLatch(1)
        val entered = CountDownLatch(1)
        var slow = false
        val catalog = MusicCatalog(File(root, "cache"), cloud.path, open = { url ->
            if (slow && url.endsWith("manifest.json")) {
                entered.countDown()
                gate.await(10, TimeUnit.SECONDS)
            }
            MusicCatalog.openUrl(url)
        }, clock = { now }, publicKey = CatalogSigning.publicKey, log = {})
        assertNotNull(catalog.manifest())
        nextDay()
        slow = true
        val refreshing = Thread { catalog.manifest() }.also { it.start() }
        assertTrue(entered.await(5, TimeUnit.SECONDS))
        // Lượt làm mới đang chờ mạng: hỏi cỡ / bài đã tải của bài không bị chặn chờ nó.
        val answered = CountDownLatch(1)
        Thread { catalog.usable("https://x/calm.mp3", null); catalog.available("https://x/calm.mp3"); answered.countDown() }.start()
        assertTrue("usable / available không chờ lượt làm mới", answered.await(2, TimeUnit.SECONDS))
        gate.countDown()
        refreshing.join(5_000)
    }
}
