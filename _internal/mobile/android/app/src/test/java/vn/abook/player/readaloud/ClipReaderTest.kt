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
    fun aVieneuVoiceThatFailsFallsBackToTheDeviceVoiceNeverToAnOnlineOne() {
        val vieneu = FakeVoice("vieneu:nano/Adam", VoiceException("Giọng VieNeu chưa tải", reason = "voice"))
        val edge = FakeVoice("edge:v")
        val device = FakeVoice("device:vi")
        val notices = ArrayList<String>()
        val reader = ClipReader(ClipCache(dir), { if (it.startsWith("vieneu:")) vieneu else edge }, { device }, { now },
            onlineFallback = { edge }, notice = { notices.add(it) })
        assertEquals("device:vi", reader.read("một", "vieneu:nano/Adam").voice)
        reader.read("hai", "vieneu:nano/Adam")
        assertEquals("chữ của sách không rời điện thoại", 0, edge.calls)
        assertEquals("không thử lại VieNeu ở mỗi đoạn", 1, vieneu.calls)
        assertEquals(listOf("Giọng VieNeu chưa đọc được lúc này - tạm đọc bằng giọng của máy."), notices)
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

    // ---- giọng dùng khoá của người dùng: khoá -> Edge -> giọng của máy -------------------------------------------------------

    private fun keyedReader(keyed: FakeVoice, edge: FakeVoice, device: FakeVoice?, notices: MutableList<String>) = ClipReader(
        ClipCache(dir), { if (it.startsWith("fpt:")) keyed else edge }, { device }, { now }, onlineFallback = { edge }, notice = { notices += it },
    )

    @Test
    fun anExhaustedKeyFallsToEdgeSaysSoOnceAndStopsCallingThatProvider() {
        val keyed = FakeVoice("fpt:banmai", VoiceException("Khóa FPT.AI đã hết hạn mức", reason = "quota"))
        val edge = FakeVoice("edge:vi-VN-HoaiMyNeural")
        val notices = mutableListOf<String>()
        val reader = keyedReader(keyed, edge, FakeVoice("device:vi"), notices)
        assertEquals("edge:vi-VN-HoaiMyNeural", reader.read("một", "fpt:banmai").voice)
        assertEquals("edge:vi-VN-HoaiMyNeural", reader.read("hai", "fpt:banmai").voice)
        assertEquals("không gọi lại khoá đã hết hạn mức ở mỗi đoạn", 1, keyed.calls)
        assertEquals(listOf("Khóa FPT.AI đã hết hạn mức - tạm đọc bằng giọng Edge."), notices)
        now += ClipReader.KEY_BREAK_MS + 1
        reader.read("ba", "fpt:banmai")
        assertEquals(2, keyed.calls)
    }

    @Test
    fun aRejectedKeyAndAnOfflineEdgeEndOnTheDeviceVoice() {
        val keyed = FakeVoice("fpt:banmai", VoiceException("FPT.AI từ chối khóa của bạn", reason = "auth"))
        val edge = FakeVoice("edge:vi-VN-HoaiMyNeural", VoiceException("Không có mạng", offline = true))
        val device = FakeVoice("device:vi")
        val notices = mutableListOf<String>()
        val clip = keyedReader(keyed, edge, device, notices).read("Xin", "fpt:banmai")
        assertEquals("device:vi", clip.voice)
        assertEquals(listOf(1, 1, 1), listOf(keyed.calls, edge.calls, device.calls))
        assertEquals(listOf(
            "Khóa FPT.AI không dùng được - tạm đọc bằng giọng Edge. Kiểm tra lại khóa trong Cài đặt.",
            "Không dùng được giọng trực tuyến - tạm đọc bằng giọng của máy.",
        ), notices)
    }

    @Test
    fun whenEveryVoiceFailsTheChosenVoicesProblemLeads() {
        val keyed = FakeVoice("fpt:banmai", VoiceException("Khóa FPT.AI đã hết hạn mức", reason = "quota"))
        val edge = FakeVoice("edge:vi-VN-HoaiMyNeural", VoiceException("Không có mạng", offline = true))
        try {
            keyedReader(keyed, edge, FakeVoice("device:vi", VoiceException("Máy chưa có giọng tiếng Việt")), mutableListOf()).read("Xin", "fpt:banmai")
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(error.message!!.startsWith("Khóa FPT.AI đã hết hạn mức"))
            assertTrue(error.message!!.contains("giọng tiếng Việt"))
            assertEquals("quota", error.reason)
        }
    }

    @Test
    fun aSampleUsesExactlyThatVoiceWithoutFallingBack() {
        val edge = FakeVoice("edge:v", VoiceException("Không có mạng", offline = true))
        try {
            reader(edge, FakeVoice("device:vi")).readExactly("Xin", "edge:v")
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertEquals("offline", error.reason)
        }
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
