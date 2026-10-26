package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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
    fun offlineWithNoVoiceThatWorksOfflineSaysSoInsteadOfPromisingTheDeviceVoice() {
        val edge = FakeVoice("edge:v", VoiceException("Không có mạng để dùng giọng Edge", offline = true))
        val reader = reader(edge, null)
        for (attempt in 0 until 2) { // lần sau (Edge đang "nghỉ") cũng cùng câu ấy
            try {
                reader.read("Xin $attempt", "edge:v")
                fail("không có giọng nào đọc được")
            } catch (error: VoiceException) {
                assertEquals(ClipReader.NO_OFFLINE_VOICE, error.message)
                // Giao diện nhận ra thông báo này nhờ mở đầu chung với bản máy tính (readAloudVoice.ts NO_OFFLINE_LEAD), thay "đang chọn" bằng tên giọng và đưa nút theo tình huống.
                assertEquals("Không có mạng - giọng đang chọn cần mạng.", error.message)
                assertTrue(error.message!!.startsWith(ClipReader.NO_OFFLINE_LEAD))
                assertTrue(error.message!!.endsWith("."))
                assertTrue(error.offline)
            }
        }
        // Có giọng máy mà giọng máy cũng hỏng: không phải chuyện "thiếu giọng ngoại tuyến", giữ lời của từng giọng.
        val broken = FakeVoice("device:vi", VoiceException("Giọng của máy hỏng"))
        try {
            reader(FakeVoice("edge:v", VoiceException("Không có mạng để dùng giọng Edge", offline = true)), broken).read("Xin", "edge:v")
            fail("cả hai giọng đều hỏng")
        } catch (error: VoiceException) {
            assertTrue(error.message!!.startsWith("Không có mạng để dùng giọng Edge;"))
        }
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
    fun withNoDeviceVoiceTheServiceErrorIsWhatTheListenerSees() {
        // Có mạng mà dịch vụ hỏng (Edge 403, 503...): cùng đường ra như mất mạng - câu NO_USABLE_VOICE, giao diện đưa "Đọc bằng …" / "Tải giọng VieNeu".
        val edge = FakeVoice("edge:v", VoiceException("Dịch vụ đọc to đang bận (HTTP 503)"))
        try {
            reader(edge, null).read("Xin", "edge:v")
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertEquals(ClipReader.NO_USABLE_VOICE, error.message)
            assertEquals("Giọng đang chọn đang không dùng được.", error.message)
            assertFalse(error.offline)
            assertEquals("service", error.reason)
        }
        val rejected = FakeVoice("edge:v", VoiceException("Dịch vụ giọng Edge từ chối (403) - có thể đã đổi cách dùng", reason = "rejected"))
        try {
            reader(rejected, null).read("Xin", "edge:v")
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertEquals(ClipReader.NO_USABLE_VOICE, error.message)
            assertEquals("rejected", error.reason)
        }
    }

    @Test
    fun whenTheCallerWillRetryATransientEdgeErrorGoesUpUntouchedWithoutBenchingEdgeOrFallingBack() {
        // Một lần Edge cắt lượt / chậm không được làm Edge "nghỉ" 30 giây (cả chương đọc bằng giọng máy, hay hiện "đang không dùng được") khi thử lại là xong.
        val edge = FakeVoice("edge:v", VoiceException("Giọng Edge đang không trả lời", reason = "service"))
        val device = FakeVoice("device:vi")
        val reader = reader(edge, device)
        for (reason in listOf("service", "timeout")) {
            val flaky = FakeVoice("edge:v", VoiceException("hỏng", reason = reason))
            try {
                reader(flaky, device).read("Xin $reason", "edge:v", willRetry = true)
                fail("đáng ra lỗi gốc")
            } catch (error: VoiceException) {
                assertEquals(reason, error.reason)
                assertFalse(error.final)
                assertTrue(error.transient)
            }
        }
        assertEquals("không rơi sang giọng máy", 0, device.calls)
        // Edge sống lại ở lần thử kế: đọc bằng chính Edge (không bị nghỉ).
        val sequence = ArrayDeque(listOf<VoiceException?>(VoiceException("cắt lượt", reason = "service"), null))
        val recovering = object : Voice {
            override val id = "edge:v"
            override val extension = "mp3"
            override fun synthesize(text: String, out: File): Clip {
                sequence.removeFirst()?.let { throw it }
                out.writeBytes(ByteArray(50) { 3 })
                return Clip(out, 700, listOf(Span(0, 700)), id)
            }
        }
        val retry = ClipReader(ClipCache(dir), { recovering }, { device }, { now })
        try { retry.read("Xin", "edge:v", willRetry = true); fail("lần đầu hỏng") } catch (error: VoiceException) { assertTrue(error.transient) }
        assertEquals("edge:v", retry.read("Xin", "edge:v", willRetry = true).voice)
        assertEquals(0, device.calls)
        // Lần thử cuối (willRetry tắt): xử lý như trước - rơi sang giọng máy, Edge nghỉ.
        assertEquals("device:vi", reader.read("Xin cuối", "edge:v").voice)
        reader.read("Xin nữa", "edge:v")
        assertEquals("Edge nghỉ sau lần cuối", 1, edge.calls)
    }

    @Test
    fun whenTheRetryBudgetIsSpentATransientErrorFallsBackAtOnceInsteadOfWaitingForARetryThatWillNotCome() {
        // Quỹ thời gian thử lại ([ClipBudget]) đã hết: người gọi sẽ không thử lại nữa, nên lần hỏng này phải rơi sang giọng kế ngay (không thì thành "Thử lại" sau cả phút chờ).
        var spent = 0L
        val scope = ClipBudget.Scope(0L, ClipBudget.BUDGET_MS) { spent }
        scope.nextDelayMs = 2_000L
        val edge = FakeVoice("edge:v", VoiceException("Giọng Edge trả lời quá chậm", reason = "timeout"))
        val device = FakeVoice("device:vi")
        val before = ClipBudget.enter(scope)
        try {
            spent = 15_000_000_000L // 15 s đã qua: còn 5 s, mà nghỉ 2 s + lần thử tối thiểu 4 s thì không đủ
            assertEquals("device:vi", reader(edge, device).read("Xin hết quỹ", "edge:v", willRetry = true).voice)
            assertEquals(1, device.calls)
            // Còn quỹ: ném lỗi gốc lên như cũ.
            spent = 1_000_000_000L
            val flaky = FakeVoice("edge:v", VoiceException("hỏng", reason = "timeout"))
            try {
                reader(flaky, FakeVoice("device:vi")).read("Xin còn quỹ", "edge:v", willRetry = true)
                fail("đáng ra lỗi gốc")
            } catch (error: VoiceException) {
                assertTrue(error.transient)
            }
        } finally {
            ClipBudget.leave(before)
        }
    }

    @Test
    fun willRetryDoesNotApplyToErrorsThatRetryingCannotFix() {
        for (error in listOf(
            VoiceException("Không có mạng", offline = true),
            VoiceException("Dịch vụ từ chối", reason = "rejected"),
            VoiceException("Khoá sai", reason = "auth"),
            VoiceException("Hết hạn mức", reason = "quota"),
        )) {
            val edge = FakeVoice("edge:v", error)
            val device = FakeVoice("device:vi")
            assertEquals(error.reason, "device:vi", reader(edge, device).read("Xin ${error.reason}", "edge:v", willRetry = true).voice)
            assertEquals(1, device.calls)
        }
        // Giọng chạy trên máy: willRetry không đổi gì.
        val vieneu = FakeVoice("vieneu:nano/Adam", VoiceException("chưa tải", reason = "service"))
        val device = FakeVoice("device:vi")
        val reader = ClipReader(ClipCache(dir), { vieneu }, { device }, { now })
        assertEquals("device:vi", reader.read("Xin", "vieneu:nano/Adam", willRetry = true).voice)
    }

    @Test
    fun theLastWordOfTheReaderIsFinalSoNobodyRetriesItAgain() {
        val edge = FakeVoice("edge:v", VoiceException("Edge bận", reason = "service"))
        val error = try { reader(edge, null).read("Xin", "edge:v"); null } catch (caught: VoiceException) { caught }
        assertEquals(ClipReader.NO_USABLE_VOICE, error!!.message)
        assertTrue(error.final)
        assertFalse(error.transient)
        // Lời cuối ghép từ hai giọng hỏng cũng là lời cuối.
        val both = try { reader(FakeVoice("edge:v", VoiceException("Edge bận", reason = "service")), FakeVoice("device:vi", VoiceException("Máy hỏng"))).read("Hai", "edge:v"); null } catch (caught: VoiceException) { caught }
        assertTrue(both!!.final)
        assertFalse(both.transient)
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
        val keyed = FakeVoice("fpt:banmai", VoiceException("Khoá FPT.AI đã hết hạn mức", reason = "quota"))
        val edge = FakeVoice("edge:vi-VN-HoaiMyNeural")
        val notices = mutableListOf<String>()
        val reader = keyedReader(keyed, edge, FakeVoice("device:vi"), notices)
        assertEquals("edge:vi-VN-HoaiMyNeural", reader.read("một", "fpt:banmai").voice)
        assertEquals("edge:vi-VN-HoaiMyNeural", reader.read("hai", "fpt:banmai").voice)
        assertEquals("không gọi lại khoá đã hết hạn mức ở mỗi đoạn", 1, keyed.calls)
        assertEquals(listOf("Khoá FPT.AI đã hết hạn mức - tạm đọc bằng giọng Edge."), notices)
        now += ClipReader.KEY_BREAK_MS + 1
        reader.read("ba", "fpt:banmai")
        assertEquals(2, keyed.calls)
    }

    @Test
    fun aRejectedKeyAndAnOfflineEdgeEndOnTheDeviceVoice() {
        val keyed = FakeVoice("fpt:banmai", VoiceException("FPT.AI từ chối khoá của bạn", reason = "auth"))
        val edge = FakeVoice("edge:vi-VN-HoaiMyNeural", VoiceException("Không có mạng", offline = true))
        val device = FakeVoice("device:vi")
        val notices = mutableListOf<String>()
        val clip = keyedReader(keyed, edge, device, notices).read("Xin", "fpt:banmai")
        assertEquals("device:vi", clip.voice)
        assertEquals(listOf(1, 1, 1), listOf(keyed.calls, edge.calls, device.calls))
        assertEquals(listOf(
            "Khoá FPT.AI không dùng được - tạm đọc bằng giọng Edge. Kiểm tra lại khoá trong Cài đặt.",
            "Không dùng được giọng trực tuyến - tạm đọc bằng giọng của máy.",
        ), notices)
    }

    @Test
    fun whenEveryVoiceFailsTheChosenVoicesProblemLeads() {
        val keyed = FakeVoice("fpt:banmai", VoiceException("Khoá FPT.AI đã hết hạn mức", reason = "quota"))
        val edge = FakeVoice("edge:vi-VN-HoaiMyNeural", VoiceException("Không có mạng", offline = true))
        try {
            keyedReader(keyed, edge, FakeVoice("device:vi", VoiceException("Máy chưa có giọng tiếng Việt")), mutableListOf()).read("Xin", "fpt:banmai")
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(error.message!!.startsWith("Khoá FPT.AI đã hết hạn mức"))
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

    @Test
    fun aFreshReadForgetsTheBreakAfterAServiceFailure() {
        // Edge trục trặc, giọng của máy cũng không đọc được: Edge bị cho nghỉ; Edge khoẻ lại mà lần đọc thường vẫn bị chặn (không một lượt gọi nào đi ra), lần hỏi MỚI thì gọi thật.
        var edgeFailure: VoiceException? = VoiceException("Dịch vụ đọc to đang bận (HTTP 503)")
        var edgeCalls = 0
        val edge = object : Voice {
            override val id = "edge:v"
            override val extension = "mp3"
            override fun synthesize(text: String, out: File): Clip {
                edgeCalls++
                edgeFailure?.let { throw it }
                out.writeBytes(ByteArray(50) { 3 })
                return Clip(out, 700, listOf(Span(0, 700)), id)
            }
        }
        val device = FakeVoice("device:vi", VoiceException("Máy chưa có giọng tiếng Việt"))
        val reader = ClipReader(ClipCache(dir), { if (it.startsWith("edge:")) edge else device }, { device }, { now })
        try {
            reader.read("Xin", "edge:v")
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertEquals("service", error.reason)
        }
        assertEquals(1, edgeCalls)
        edgeFailure = null // Edge khoẻ lại
        try {
            reader.read("Xin", "edge:v")
            fail("Edge còn đang nghỉ")
        } catch (error: VoiceException) {
            assertEquals(1, edgeCalls)
        }
        assertEquals("edge:v", reader.read("Xin", "edge:v", fresh = true).voice)
        assertEquals(2, edgeCalls)
        assertEquals("edge:v", reader.read("Hai", "edge:v").voice) // hết nghỉ luôn
    }

    @Test
    fun aRejectedKeyWithoutEdgeConsentFallsStraightToTheDeviceVoiceAndNeverCallsEdge() {
        // onlineFallback trả null khi người nghe chưa đồng ý "edge" (ReadAloud.edgeFallback): chữ không được rời máy tới Microsoft (soát a79 lỗi 1).
        val keyed = FakeVoice("azure:vi-VN-HoaiMyNeural", VoiceException("Azure từ chối khoá của bạn", reason = "auth"))
        val edge = FakeVoice("edge:vi-VN-HoaiMyNeural")
        val device = FakeVoice("device:vi")
        val reader = ClipReader(ClipCache(dir), { if (it.startsWith("azure:")) keyed else edge }, { device }, { now }, onlineFallback = { null })
        assertEquals("device:vi", reader.read("Xin", "azure:vi-VN-HoaiMyNeural").voice)
        assertEquals(0, edge.calls)
        assertEquals(listOf(1, 1), listOf(keyed.calls, device.calls))
    }
}
