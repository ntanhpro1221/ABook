package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** Bộ nhớ đệm đoạn đọc: khoá sha256, ghi/đọc lại, dọn LRU khi quá hạn mức. */
class ClipCacheTest {
    private val dir: File = Files.createTempDirectory("clip-cache").toFile()
    private var now = 1_000_000L

    @After
    fun cleanUp() {
        dir.deleteRecursively()
    }

    private fun cache(cap: Long) = ClipCache(dir, cap) { now }

    private fun put(cache: ClipCache, voice: String, text: String, size: Int): Clip {
        val tmp = cache.temp("mp3")
        tmp.writeBytes(ByteArray(size) { 1 })
        now += 1000
        return cache.put(voice, text, tmp, "mp3", 1234, listOf(Span(0, 600), Span(600, 1200)))
    }

    @Test
    fun keyIsSha256OfProviderVoiceAndText() {
        val expected = java.security.MessageDigest.getInstance("SHA-256").digest("edge|vi-VN-HoaiMyNeural|Xin chào".toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
        assertEquals(expected, ClipCache.key("edge", "vi-VN-HoaiMyNeural", "Xin chào"))
        assertNotEquals(ClipCache.key("edge", "a", "x"), ClipCache.key("device", "a", "x"))
        assertNotEquals(ClipCache.key("edge", "a", "x"), ClipCache.key("edge", "b", "x"))
        assertEquals("edge" to "vi-VN-X", ClipCache.split("edge:vi-VN-X"))
    }

    @Test
    fun aStoredClipComesBackWithItsDurationAndWords() {
        val cache = cache(1_000_000)
        put(cache, "edge:v", "Xin chào", 100)
        val clip = cache.get("edge:v", "Xin chào")!!
        assertEquals(1234, clip.durationMs)
        assertEquals(listOf(Span(0, 600), Span(600, 1200)), clip.words)
        assertEquals(100, clip.file.length())
        assertEquals("edge:v", clip.voice)
        assertNull("giọng khác thì đoạn khác", cache.get("edge:w", "Xin chào"))
        assertNull("chữ khác thì đoạn khác", cache.get("edge:v", "Xin chào!"))
    }

    @Test
    fun aMissingAudioFileOrBrokenJsonCountsAsNotCached() {
        val cache = cache(1_000_000)
        val clip = put(cache, "edge:v", "a", 10)
        clip.file.delete()
        assertNull(cache.get("edge:v", "a"))
        val other = put(cache, "edge:v", "b", 10)
        File(dir, other.file.name.substringBefore('.') + ".json").writeText("{ not json")
        assertNull(cache.get("edge:v", "b"))
    }

    @Test
    fun overTheCapTheLeastRecentlyUsedClipsGoFirst() {
        val cache = cache(2500)
        val a = put(cache, "edge:v", "a", 1000)
        put(cache, "edge:v", "b", 1000)
        // Nghe lại "a": nó thành đoạn mới dùng nhất.
        now += 1000
        assertNotNull(cache.get("edge:v", "a"))
        put(cache, "edge:v", "c", 1000)
        assertNull("b lâu không dùng nhất nên bị xoá", cache.get("edge:v", "b"))
        assertNotNull(cache.get("edge:v", "a"))
        assertNotNull(cache.get("edge:v", "c"))
        assertTrue(cache.sizeBytes() <= 2500 + 200)
        assertTrue(a.file.isFile)
    }

    @Test
    fun trimRemovesBothFilesOfAnEvictedClip() {
        val cache = cache(1500)
        val a = put(cache, "edge:v", "a", 1000)
        put(cache, "edge:v", "b", 1000)
        assertFalse(a.file.exists())
        assertFalse(File(dir, a.file.name.substringBefore('.') + ".json").exists())
    }

    @Test
    fun staleTempFilesAreSweptButFreshOnesAreKept() {
        now = 10_000_000_000L
        val cache = cache(1_000_000)
        val old = cache.temp("mp3").apply { writeBytes(ByteArray(5)); setLastModified(now - 3_600_000) }
        val fresh = cache.temp("mp3").apply { writeBytes(ByteArray(5)); setLastModified(now) }
        cache.trim()
        assertFalse(old.exists())
        assertTrue(fresh.exists())
    }

    @Test
    fun pinnedClipsOutliveNewerUnpinnedOnesUntilTheListenerReachesThem() {
        val pins = File(dir.parentFile, "${dir.name}-pins.txt")
        try {
            val cache = ClipCache(dir, 2500, pins) { now }
            cache.pin("edge:v", "a")
            put(cache, "edge:v", "a", 1000) // làm trước
            put(cache, "edge:v", "b", 1000) // nghe trực tiếp
            put(cache, "edge:v", "c", 1000)
            assertTrue("đoạn ghim cũ nhất vẫn còn", cache.contains("edge:v", "a"))
            assertFalse("đoạn thường cũ nhất đi trước", cache.contains("edge:v", "b"))
            assertEquals(1000L + File(dir, ClipCache.key("edge", "v", "a") + ".json").length(), cache.pinnedBytes())
            // Ghim nhớ qua lần mở app sau.
            val reopened = ClipCache(dir, 2500, pins) { now }
            assertTrue(reopened.isPinned("edge:v", "a"))
            reopened.unpin("edge:v", "a")
            assertFalse(ClipCache(dir, 2500, pins) { now }.isPinned("edge:v", "a"))
            put(reopened, "edge:v", "d", 1000)
            assertFalse("bỏ ghim rồi thì lại theo LRU", reopened.contains("edge:v", "a"))
            reopened.pin("edge:v", "x")
            reopened.clearPins()
            assertEquals(0L, reopened.pinnedBytes())
        } finally {
            pins.delete()
        }
    }

    @Test
    fun containsDoesNotCountAsAUse() {
        val cache = cache(2500)
        put(cache, "edge:v", "a", 1000)
        put(cache, "edge:v", "b", 1000)
        now += 1000
        assertTrue(cache.contains("edge:v", "a"))
        assertFalse(cache.contains("edge:w", "a"))
        put(cache, "edge:v", "c", 1000)
        assertFalse("hỏi có chưa không làm a thành mới dùng", cache.contains("edge:v", "a"))
    }

    @Test
    fun theDefaultCapIs300Megabytes() {
        assertEquals(300L * 1024 * 1024, ClipCache.CAP_BYTES)
    }
}
