package vn.abook.player

import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.audio.AudioSink
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.lang.reflect.Proxy
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Dịch pha trong dòng của [LoopSeam.LoopSink] ([LoopSeam.LoopSink.shift]): chèn khung lặng / bỏ khung, pts sink trong nhận liên tục với số khung đã ghi, vị trí báo ExoPlayer theo nội dung. */
@OptIn(UnstableApi::class)
class LoopSinkShiftTest {
    private val sr = 44100
    private fun us(frames: Long) = frames * 1_000_000L / sr

    /** Hai vị trí (µs) cách nhau không quá `tol` (mặc định 1 µs: làm tròn của phép đổi khung -> µs). */
    private fun near(expected: Long, actual: Long, tol: Long = 1) = assertTrue("$expected != $actual", Math.abs(expected - actual) <= tol)

    /** Một khung ở 44,1 kHz (µs, làm tròn lên): sai số của vị trí bù (làm tròn khung đã phát). */
    private val frameUs = 23L

    /** Một buffer sink trong đã nhận: pts, số khung, kênh 0 của khung đầu, toàn số 0 hay không. */
    private data class Got(val pts: Long, val frames: Int, val first: Int, val silent: Boolean)

    /** Cùng các buffer (cỡ, nội dung) và pts lệch nhau <= 1 µs. */
    private fun assertGot(expected: List<Got>, actual: List<Got>) {
        assertEquals(expected.map { it.copy(pts = 0) }, actual.map { it.copy(pts = 0) })
        for (i in expected.indices) near(expected[i].pts, actual[i].pts)
    }

    /**
     * Sink trong giả: mỗi handleBuffer nhận tối đa `budget` byte (mặc định hết) và trả true khi đã nhận hết buffer - như DefaultAudioSink giữ buffer dở và đòi đưa lại đúng nó.
     * Ghi một [Got] mỗi buffer MỚI (pts của lần đưa đầu). `position` = vị trí nó báo (µs).
     */
    private class Inner {
        val got = mutableListOf<Got>()
        var budget = Int.MAX_VALUE
        var position = 0L
        private var pending: ByteBuffer? = null
        val sink: AudioSink = Proxy.newProxyInstance(AudioSink::class.java.classLoader, arrayOf(AudioSink::class.java)) { _, method, params ->
            when {
                method.name == "handleBuffer" -> {
                    val buffer = params!![0] as ByteBuffer
                    if (pending != null) check(buffer === pending) { "sink trong đang giữ dở buffer khác" }
                    else {
                        val view = buffer.duplicate().order(ByteOrder.LITTLE_ENDIAN)
                        var silent = true
                        while (view.hasRemaining()) if (view.get() != 0.toByte()) silent = false
                        got += Got(params[1] as Long, buffer.remaining() / 4, buffer.duplicate().order(ByteOrder.LITTLE_ENDIAN).getShort(buffer.position()).toInt(), silent)
                    }
                    val n = minOf(budget, buffer.remaining())
                    buffer.position(buffer.position() + n)
                    pending = if (buffer.hasRemaining()) buffer else null
                    !buffer.hasRemaining()
                }
                method.name == "flush" -> {
                    pending = null
                    null
                }
                method.name == "getCurrentPositionUs" -> position
                method.returnType == Boolean::class.javaPrimitiveType -> false
                method.returnType == Int::class.javaPrimitiveType -> 0
                method.returnType == Long::class.javaPrimitiveType -> 0L
                method.returnType == Float::class.javaPrimitiveType -> 0f
                else -> null
            }
        } as AudioSink
    }

    private fun format() = Format.Builder().setSampleMimeType(MimeTypes.AUDIO_RAW).setPcmEncoding(C.ENCODING_PCM_16BIT).setChannelCount(2).setSampleRate(sr).build()

    /** Khối giả: khung n có kênh 0 = n (cắt 15 bit), kênh 1 = -n; n = 0 cũng là khung lặng nên các khối bắt đầu ở n >= 1. */
    private fun chunk(first: Int, frames: Int): ByteBuffer {
        val b = ByteBuffer.allocate(frames * 4).order(ByteOrder.LITTLE_ENDIAN)
        for (n in first until first + frames) b.putShort(n.toShort()).putShort((-n).toShort())
        b.flip()
        return b
    }

    private fun sink(inner: Inner) = LoopSeam.LoopSink(inner.sink).also {
        it.configure(AudioSink.AudioSinkConfig.Builder(format()).build())
        it.flush()
    }

    @Test
    fun withoutAShiftTheStreamAndPositionAreUntouched() {
        val inner = Inner()
        val s = sink(inner)
        s.handleBuffer(chunk(1, 4410), 0, 1)
        s.handleBuffer(chunk(4411, 4410), 100_000, 1)
        assertEquals(listOf(Got(0, 4410, 1, false), Got(100_000, 4410, 4411, false)), inner.got)
        assertTrue(s.appliedShifts.isEmpty())
        inner.position = 123_456
        assertEquals(123_456L, s.getCurrentPositionUs(false))
    }

    @Test
    fun insertWritesKSilentFramesThenTheRealDataWithContinuousPts() {
        val inner = Inner()
        val s = sink(inner)
        val applied = mutableListOf<LoopSeam.Shift>()
        s.handleBuffer(chunk(1, 4410), 0, 1)
        s.shift(6439) { applied += it } // P3 đi trước 146 ms
        assertTrue(applied.isEmpty()) // áp ở buffer kế
        s.handleBuffer(chunk(4411, 4410), 100_000, 1)
        s.handleBuffer(chunk(8821, 4410), 200_000, 1)
        assertGot(
            listOf(
                Got(0, 4410, 1, false),
                Got(100_000, 6439, 0, true), // lặng ở đúng chỗ đã ghi tới
                Got(100_000 + us(6439), 4410, 4411, false), // dữ liệu thật nguyên vẹn, pts liên tục với khung đã ghi
                Got(200_000 + us(6439), 4410, 8821, false),
            ),
            inner.got,
        )
        assertEquals(1, applied.size)
        assertEquals(4410L, applied[0].writtenAt)
        assertEquals(6439L, applied[0].frames)
        // pts liên tục: mỗi buffer bắt đầu đúng ở pts buffer trước + số khung của nó
        for (i in 1 until inner.got.size) near(inner.got[i - 1].pts + us(inner.got[i - 1].frames.toLong()), inner.got[i].pts)
    }

    @Test
    fun dropCutsLikeTheSeekTrimAcrossBuffersWithContinuousPts() {
        val inner = Inner()
        val s = sink(inner)
        val applied = mutableListOf<LoopSeam.Shift>()
        s.handleBuffer(chunk(1, 4410), 0, 1)
        s.shift(-5000) { applied += it } // P3 đi sau 113 ms
        assertTrue(s.handleBuffer(chunk(4411, 4410), 100_000, 1)) // bỏ cả buffer, không đưa gì xuống
        assertTrue(applied.isEmpty())
        s.handleBuffer(chunk(8821, 4410), 200_000, 1) // bỏ nốt 590 khung
        s.handleBuffer(chunk(13231, 4410), 300_000, 1)
        assertGot(
            listOf(
                Got(0, 4410, 1, false),
                Got(100_000, 3820, 4411 + 5000, false), // nội dung nhảy 5000 khung, pts vẫn nối tiếp phần đã ghi
                Got(100_000 + us(3820), 4410, 13231, false),
            ),
            inner.got,
        )
        assertEquals(1, applied.size)
        assertEquals(4410L, applied[0].writtenAt)
        assertEquals(-5000L, applied[0].frames)
    }

    @Test
    fun aRefusedBufferIsRetriedWithoutWritingSilenceTwice() {
        val inner = Inner()
        val s = sink(inner)
        val applied = mutableListOf<LoopSeam.Shift>()
        s.handleBuffer(chunk(1, 4410), 0, 1)
        s.shift(6439) { applied += it }
        val real = chunk(4411, 4410)
        inner.budget = 4000 * 4 // sink trong đầy giữa chừng phần lặng
        assertFalse(s.handleBuffer(real, 100_000, 1))
        assertTrue(applied.isEmpty())
        assertFalse(s.handleBuffer(real, 100_000, 1)) // xong lặng (2439 khung còn lại), rồi sink trong nhận 4000 khung thật và giữ dở
        assertEquals(1, applied.size)
        inner.budget = Int.MAX_VALUE
        assertTrue(s.handleBuffer(real, 100_000, 1)) // ExoPlayer đưa lại đúng buffer thật: không chèn thêm
        s.handleBuffer(chunk(8821, 4410), 200_000, 1)
        assertGot(
            listOf(Got(0, 4410, 1, false), Got(100_000, 6439, 0, true), Got(100_000 + us(6439), 4410, 4411, false), Got(200_000 + us(6439), 4410, 8821, false)),
            inner.got,
        )
        assertEquals(4410L, applied[0].writtenAt)
    }

    @Test
    fun aShiftWaitsWhileTheInnerSinkHoldsAPartBufferAndCountsWhatItTook() {
        val inner = Inner()
        val s = sink(inner)
        val applied = mutableListOf<LoopSeam.Shift>()
        val first = chunk(1, 4410)
        inner.budget = 1000 * 4
        assertFalse(s.handleBuffer(first, 0, 1)) // sink trong giữ dở buffer đầu (nhận 1000 khung)
        s.shift(-100) { applied += it }
        inner.budget = Int.MAX_VALUE
        assertTrue(s.handleBuffer(first, 0, 1)) // đưa lại buffer dở: chưa bỏ gì ở đây
        assertTrue(applied.isEmpty())
        s.handleBuffer(chunk(4411, 4410), 100_000, 1)
        assertEquals(4410L, applied.single().writtenAt) // số khung sink trong ĐÃ NHẬN, kể cả qua hai lần
        assertGot(listOf(Got(0, 4410, 1, false), Got(100_000, 4310, 4511, false)), inner.got)
    }

    @Test
    fun flushCancelsPendingAndHalfDoneShifts() {
        val inner = Inner()
        val s = sink(inner)
        val applied = mutableListOf<LoopSeam.Shift>()
        s.handleBuffer(chunk(1, 4410), 0, 1)
        s.shift(6439) { applied += it }
        s.flush() // chưa áp: bỏ
        s.handleBuffer(chunk(1, 4410), 0, 1)
        s.handleBuffer(chunk(4411, 4410), 100_000, 1)
        assertTrue(inner.got.none { it.silent })
        // bỏ dở qua lần xả: phần còn lại không bỏ nữa, pts về như không có dịch
        s.shift(-6000) { applied += it }
        assertTrue(s.handleBuffer(chunk(8821, 4410), 200_000, 1))
        s.flush()
        assertTrue(s.appliedShifts.isEmpty())
        inner.got.clear()
        s.handleBuffer(chunk(1, 4410), 0, 1)
        s.handleBuffer(chunk(4411, 4410), 100_000, 1)
        assertEquals(listOf(Got(0, 4410, 1, false), Got(100_000, 4410, 4411, false)), inner.got)
        assertTrue(applied.isEmpty())
    }

    @Test
    fun reportedPositionFollowsTheContentNotTheWrittenFrames() {
        // Vị trí sink trong = pts đầu sau lần xả + khung đã phát (trục ĐÃ GHI). Sau dịch, ExoPlayer (currentPosition -> SeamClock.trackSeconds, `pos`) phải thấy nội dung đang ra loa.
        val inner = Inner()
        val s = sink(inner)
        val start = 400_000L // lần tua vào Nối: khung đầu ở 400 ms
        s.handleBuffer(chunk(1, 4410), start, 1)
        s.shift(6439)
        s.handleBuffer(chunk(4411, 4410), start + 100_000, 1)
        fun at(writtenFrames: Long): Long {
            inner.position = start + us(writtenFrames)
            return s.getCurrentPositionUs(false)
        }
        assertEquals(start + us(3000), at(3000)) // trước chỗ dịch: như cũ
        near(start + us(4410), at(4410 + 3000), frameUs) // đang phát lặng: nội dung đứng yên
        near(start + us(4410 + 100), at(4410 + 6439 + 100), frameUs) // qua lặng: trục nội dung = đã ghi - K
        // P3 trên trục bài: không lệch 146 ms so với nội dung thật (kiểm trôi / chỗ của vòng kế đọc vị trí này)
        val seam = LoopSeam.Seam(java.io.File("a.mp3"), java.io.File("a.wav"), 1152, 100 * 1152L, 1000 * 1152L, 77 * 1152, sr, 2, 1152, 0, 3)
        val reported = SeamClock.trackSeconds(seam, 1, at(4410 + 6439 + 100) / 1000)
        assertEquals(SeamClock.trackSeconds(seam, 1, (start + us(4510)) / 1000), reported, 1e-9)

        val inner2 = Inner()
        val d = sink(inner2)
        d.handleBuffer(chunk(1, 4410), start, 1)
        d.shift(-1014)
        d.handleBuffer(chunk(4411, 4410), start + 100_000, 1)
        inner2.position = start + us(4409)
        near(start + us(4409), d.getCurrentPositionUs(false), frameUs)
        inner2.position = start + us(4410 + 200)
        near(start + us(4410 + 1014 + 200), d.getCurrentPositionUs(false), frameUs) // đã qua chỗ bỏ: nội dung đi trước khung đã ghi
        inner2.position = AudioSink.CURRENT_POSITION_NOT_SET
        assertEquals(AudioSink.CURRENT_POSITION_NOT_SET, d.getCurrentPositionUs(false))
    }

    @Test
    fun contentFramesNeverGoesBackward() {
        val shifts = listOf(LoopSeam.Shift(1000, 500), LoopSeam.Shift(3000, -200))
        var last = Long.MIN_VALUE
        for (played in 0L..5000L) {
            val c = LoopSeam.contentFrames(played, shifts)
            assertTrue(c >= last)
            last = c
        }
        assertEquals(999L, LoopSeam.contentFrames(999, shifts))
        assertEquals(1000L, LoopSeam.contentFrames(1400, shifts)) // trong phần lặng
        assertEquals(2500L + 200, LoopSeam.contentFrames(3000, shifts)) // qua lặng (-500), tới chỗ bỏ (+200)
    }
}
