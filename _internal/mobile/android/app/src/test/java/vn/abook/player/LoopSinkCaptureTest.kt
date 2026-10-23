package vn.abook.player

import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.audio.AudioSink
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.lang.reflect.Proxy
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Lưới an toàn của [LoopSeam.LoopSink] ([LoopSeam.LoopSink.Capture]): chép K khung đầu SAU khi cắt, một lần; không có lệnh chép thì không chép gì. */
@OptIn(UnstableApi::class)
class LoopSinkCaptureTest {
    /** Sink trong giả: ghi (pts, khung đầu của buffer theo mẫu kênh 0) mỗi handleBuffer; `refuse` > 0 thì lần ấy không nhận gì và trả false (sink đầy). */
    private class Inner {
        val got = mutableListOf<Pair<Long, Int>>()
        var refuse = 0
        val sink: AudioSink = Proxy.newProxyInstance(AudioSink::class.java.classLoader, arrayOf(AudioSink::class.java)) { _, method, params ->
            when {
                method.name == "handleBuffer" -> {
                    val buffer = params!![0] as ByteBuffer
                    if (refuse > 0) {
                        refuse--
                        false
                    } else {
                        got += (params[1] as Long) to buffer.duplicate().order(ByteOrder.LITTLE_ENDIAN).getShort(buffer.position()).toInt()
                        buffer.position(buffer.limit())
                        true
                    }
                }
                method.returnType == Boolean::class.javaPrimitiveType -> false
                method.returnType == Int::class.javaPrimitiveType -> 0
                method.returnType == Long::class.javaPrimitiveType -> 0L
                method.returnType == Float::class.javaPrimitiveType -> 0f
                else -> null
            }
        } as AudioSink
    }

    private fun format(encoding: Int) = Format.Builder().setSampleMimeType(MimeTypes.AUDIO_RAW).setPcmEncoding(encoding).setChannelCount(2).setSampleRate(44100).build()

    /** Khối WAV giả: khung n của Nối có kênh 0 = n (cắt 15 bit), kênh 1 = -n. */
    private fun chunk(first: Int, frames: Int): ByteBuffer {
        val b = ByteBuffer.allocate(frames * 4).order(ByteOrder.LITTLE_ENDIAN)
        for (n in first until first + frames) b.putShort(n.toShort()).putShort((-n).toShort())
        b.flip()
        return b
    }

    private fun expected(first: Int, frames: Int) = ShortArray(frames * 2) { if (it % 2 == 0) (first + it / 2).toShort() else (-(first + it / 2)).toShort() }

    private fun sink(inner: Inner, encoding: Int = C.ENCODING_PCM_16BIT) = LoopSeam.LoopSink(inner.sink).also { it.configure(AudioSink.AudioSinkConfig.Builder(format(encoding)).build()) }

    @Test
    fun withoutACaptureNothingIsCopiedOrHandedOn() {
        val inner = Inner()
        val s = sink(inner)
        s.armSeek(4063) // tua Clip / Nối không có lưới an toàn (đường thường)
        assertFalse(s.capturing)
        s.flush()
        assertFalse(s.capturing)
        s.handleBuffer(chunk(17640, 4410), 400_000, 1)
        s.handleBuffer(chunk(22050, 4410), 500_000, 1)
        assertFalse(s.capturing)
        assertEquals(listOf(400_000L + 4063L * 1_000_000 / 44100 to 21703, 500_000L to 22050), inner.got)
    }

    @Test
    fun capturesTheFirstFramesAfterTheTrimOnce() {
        val inner = Inner()
        val s = sink(inner)
        val calls = mutableListOf<ShortArray>()
        s.armSeek(4063, LoopSeam.LoopSink.Capture(256) { calls += it })
        assertFalse(s.capturing) // lệnh chép chỉ bắt đầu ở lần xả của lệnh tua
        s.flush()
        assertTrue(s.capturing)
        s.handleBuffer(chunk(17640, 4410), 400_000, 1) // còn 347 khung sau cắt: đủ 256
        assertEquals(1, calls.size)
        assertArrayEquals(expected(21703, 256), calls[0])
        assertFalse(s.capturing)
        s.handleBuffer(chunk(22050, 4410), 500_000, 1)
        assertEquals(1, calls.size)
        // đường tiếng y như không có lưới an toàn
        assertEquals(listOf(400_000L + 4063L * 1_000_000 / 44100 to 21703, 500_000L to 22050), inner.got)
    }

    @Test
    fun captureSpansBuffersAndSurvivesTheStepAsideFlush() {
        val inner = Inner()
        val s = sink(inner)
        val calls = mutableListOf<ShortArray>()
        s.armSeek(4300, LoopSeam.LoopSink.Capture(256) { calls += it })
        s.flush() // lệnh tua đệm
        s.flush() // lệnh tua thật: không nạp lại, số cắt + lệnh chép giữ nguyên (seekPending)
        assertTrue(s.capturing)
        s.handleBuffer(chunk(17640, 4410), 400_000, 1) // 110 khung sau cắt
        assertTrue(calls.isEmpty())
        s.handleBuffer(chunk(22050, 4410), 500_000, 1) // 146 khung còn thiếu
        assertEquals(1, calls.size)
        assertArrayEquals(expected(17640 + 4300, 256), calls[0])
    }

    @Test
    fun aRetriedBufferIsNotCopiedTwice() {
        val inner = Inner()
        val s = sink(inner)
        val calls = mutableListOf<ShortArray>()
        s.armSeek(4300, LoopSeam.LoopSink.Capture(256) { calls += it })
        s.flush()
        val first = chunk(17640, 4410)
        inner.refuse = 1
        assertFalse(s.handleBuffer(first, 400_000, 1)) // sink trong đầy: ExoPlayer gọi lại cùng buffer
        assertTrue(s.handleBuffer(first, 400_000, 1))
        s.handleBuffer(chunk(22050, 4410), 500_000, 1)
        assertEquals(1, calls.size)
        assertArrayEquals(expected(17640 + 4300, 256), calls[0])
    }

    @Test
    fun anUnarmedFlushDropsAPendingCapture() {
        val inner = Inner()
        val s = sink(inner)
        val calls = mutableListOf<ShortArray>()
        s.armSeek(4300, LoopSeam.LoopSink.Capture(256) { calls += it })
        s.flush()
        s.handleBuffer(chunk(17640, 4410), 400_000, 1) // 110 khung
        s.flush() // xả khác (không phải lệnh tua này): bỏ lệnh chép dở
        assertFalse(s.capturing)
        s.handleBuffer(chunk(0, 4410), 0, 1)
        assertTrue(calls.isEmpty())
    }

    @Test
    fun theStepAsideBufferBetweenTwoFlushesNeitherUsesUpTheTrimNorFeedsTheLanding() {
        // Máy thật OPPO (rs46p, PLAN_loop §47.1): lệnh tua đệm (100 ms) xả, buffer của nó tới sink TRƯỚC lần xả của lệnh tua thật (200 ms). Trước đây: buffer đệm tiêu số cắt
        // + lượt chụp, buffer đúng ra loa không cắt (đáp -4063) và land báo khung của buffer đã bị xả.
        val inner = Inner()
        val s = sink(inner)
        val calls = mutableListOf<ShortArray>()
        s.armSeek(4063, LoopSeam.LoopSink.Capture(256) { calls += it }, flushes = 2)
        s.flush() // lần xả của lệnh tua đệm
        assertFalse(s.capturing) // chưa phải lần xả cuối: chưa chụp
        s.handleBuffer(chunk(4410, 4410), 100_000, 1) // buffer của lệnh tua đệm: vẫn bị cắt như thường
        assertTrue(calls.isEmpty())
        s.flush() // lần xả của lệnh tua thật: đặt lại số cắt + bắt đầu chụp
        assertTrue(s.capturing)
        s.handleBuffer(chunk(8820, 4410), 200_000, 1)
        assertEquals(1, calls.size)
        assertArrayEquals(expected(8820 + 4063, 256), calls[0]) // chỉ khung của buffer sau lần xả cuối
        val trimUs = 4063L * 1_000_000 / 44100
        assertEquals(listOf(100_000L + trimUs to 4410 + 4063, 200_000L + trimUs to 8820 + 4063), inner.got)
        // dùng hết: lần xả không kèm lệnh tua thì không cắt như cũ
        s.handleBuffer(chunk(13230, 4410), 300_000, 1)
        s.flush()
        s.handleBuffer(chunk(0, 4410), 0, 1)
        assertEquals(0L to 0, inner.got.last())
    }

    @Test
    fun oneFlushArmBehavesAsBefore() {
        val inner = Inner()
        val s = sink(inner)
        val calls = mutableListOf<ShortArray>()
        s.armSeek(4063, LoopSeam.LoopSink.Capture(256) { calls += it }, flushes = 1)
        s.flush()
        assertTrue(s.capturing)
        s.handleBuffer(chunk(17640, 4410), 400_000, 1)
        s.flush() // xả thêm không nạp: không cắt
        s.handleBuffer(chunk(0, 4410), 0, 1)
        assertArrayEquals(expected(21703, 256), calls.single())
        assertEquals(listOf(400_000L + 4063L * 1_000_000 / 44100 to 21703, 0L to 0), inner.got)
    }

    @Test
    fun anArmOlderThanTwoSecondsIsDropped() {
        val inner = Inner()
        val s = sink(inner)
        var now = 5_000_000_000L
        s.clock = { now }
        val calls = mutableListOf<ShortArray>()
        s.armSeek(4063, LoopSeam.LoopSink.Capture(256) { calls += it }, flushes = 2)
        now += 2_100_000_000L // lệnh tua không sinh đủ lần xả trong hạn
        s.flush() // lần xả lạ: không áp
        assertFalse(s.capturing)
        s.handleBuffer(chunk(4410, 4410), 100_000, 1)
        s.flush()
        s.handleBuffer(chunk(8820, 4410), 200_000, 1)
        assertEquals(listOf(100_000L to 4410, 200_000L to 8820), inner.got)
        assertTrue(calls.isEmpty())
    }

    @Test
    fun nonPcm16OutputIsNeverCaptured() {
        val inner = Inner()
        val s = sink(inner, C.ENCODING_PCM_FLOAT)
        val calls = mutableListOf<ShortArray>()
        s.armSeek(0, LoopSeam.LoopSink.Capture(256) { calls += it })
        s.flush()
        s.handleBuffer(ByteBuffer.allocate(4410 * 8), 0, 1)
        assertFalse(s.capturing)
        assertTrue(calls.isEmpty())
    }
}
