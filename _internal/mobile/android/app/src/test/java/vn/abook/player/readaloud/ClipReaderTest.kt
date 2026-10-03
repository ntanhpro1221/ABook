package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** Đọc một đoạn: bộ nhớ đệm trước, giọng mạng hỏng thì rơi về giọng của máy mà không dừng, và không chờ lại giọng mạng hỏng ở mỗi đoạn. */
class ClipReaderTest {
    private val dir: File = Files.createTempDirectory("clip-reader").toFile()
    private var now = 0L

    @After
    fun cleanUp() {
        dir.deleteRecursively()
    }

    private class FakeVoice(override val id: String, val failWith: VoiceException? = null) : Voice {
        override val extension = "mp3"
        var calls = 0
        override fun synthesize(text: String, out: File): Clip {
            calls++
            failWith?.let { throw it }
            out.writeBytes(ByteArray(50) { 3 })
            return Clip(out, 700, listOf(Span(0, 700)), id)
        }
    }

    private fun reader(edge: FakeVoice, device: FakeVoice?) = ClipReader(
        ClipCache(dir), { if (it.startsWith("edge:")) edge else device ?: FakeVoice(it) }, { device }, { now },
    )

    @Test
    fun readsWithTheChosenVoiceAndCachesTheClip() {
        val edge = FakeVoice("edge:v")
        val reader = reader(edge, null)
        val first = reader.read("Xin", "edge:v")
        val second = reader.read("Xin", "edge:v")
        assertEquals("edge:v", first.voice)
        assertEquals(1, edge.calls)
        assertEquals(first.file, second.file)
    }

    @Test
    fun offlineEdgeFallsBackToTheDeviceVoiceForThatClip() {
        val edge = FakeVoice("edge:v", VoiceException("Không có mạng", offline = true))
        val device = FakeVoice("device:vi")
        val clip = reader(edge, device).read("Xin", "edge:v")
        assertEquals("device:vi", clip.voice)
        assertEquals(1, edge.calls)
        assertEquals(1, device.calls)
    }

    @Test
    fun aFailedEdgeIsNotRetriedOnEveryParagraphButIsRetriedLater() {
        val edge = FakeVoice("edge:v", VoiceException("Không có mạng", offline = true))
        val device = FakeVoice("device:vi")
        val reader = reader(edge, device)
        reader.read("một", "edge:v")
        reader.read("hai", "edge:v")
        reader.read("ba", "edge:v")
        assertEquals("chỉ thử Edge một lần rồi nghỉ", 1, edge.calls)
        now += ClipReader.EDGE_BREAK_MS + 1
        reader.read("bốn", "edge:v")
        assertEquals(2, edge.calls)
    }

    @Test
    fun aClipAlreadyInTheCacheNeedsNoNetworkEvenWhileEdgeIsDown() {
        val edge = FakeVoice("edge:v")
        val reader = reader(edge, FakeVoice("device:vi"))
        reader.read("Xin", "edge:v")
        val broken = FakeVoice("edge:v", VoiceException("hỏng", offline = true))
        val again = reader(broken, FakeVoice("device:vi")).read("Xin", "edge:v")
        assertEquals("edge:v", again.voice)
        assertEquals(0, broken.calls)
    }

    @Test
    fun bothVoicesFailingGivesOneClearMessage() {
        val edge = FakeVoice("edge:v", VoiceException("Không có mạng để dùng giọng Edge", offline = true))
        val device = FakeVoice("device:vi", VoiceException("Máy chưa có giọng tiếng Việt"))
        try {
            reader(edge, device).read("Xin", "edge:v")
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(error.message!!.contains("Không có mạng"))
            assertTrue(error.message!!.contains("giọng tiếng Việt"))
        }
    }

    @Test
    fun withNoDeviceVoiceTheNetworkErrorIsWhatTheListenerSees() {
        val edge = FakeVoice("edge:v", VoiceException("Không có mạng để dùng giọng Edge", offline = true))
        try {
            reader(edge, null).read("Xin", "edge:v")
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertEquals("Không có mạng để dùng giọng Edge", error.message)
        }
    }

    @Test
    fun aDeviceVoiceThatFailsIsNotRetriedWithItself() {
        val device = FakeVoice("device:vi", VoiceException("Giọng của máy báo lỗi"))
        try {
            reader(FakeVoice("edge:v"), device).read("Xin", "device:vi")
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertEquals(1, device.calls)
        }
    }

    @Test
    fun aVoiceThatCrashesWithAnOrdinaryExceptionBecomesAVoiceError() {
        val crashing = object : Voice {
            override val id = "edge:v"
            override val extension = "mp3"
            override fun synthesize(text: String, out: File): Clip = throw IllegalStateException("boom")
        }
        val reader = ClipReader(ClipCache(dir), { crashing }, { FakeVoice("device:vi") }, { now })
        assertEquals("device:vi", reader.read("Xin", "edge:v").voice)
    }

    @Test
    fun failedAttemptsLeaveNoTempFilesBehind() {
        val edge = FakeVoice("edge:v", VoiceException("hỏng", offline = true))
        try {
            reader(edge, null).read("Xin", "edge:v")
        } catch (expected: VoiceException) {
        }
        assertEquals(0, dir.listFiles()!!.count { it.name.endsWith(".part") })
    }
}
