package vn.abook.player

import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.audio.AudioSink
import org.junit.Assert.assertEquals
import org.junit.Test
import java.lang.reflect.Proxy
import java.nio.ByteBuffer

/** Móc đo [LoopSeam.LoopSink.Probe]: chỉ đọc trạng thái; có móc hay không thì sink trong nhận đúng cùng dữ liệu + nhãn thời gian. */
@OptIn(UnstableApi::class)
class LoopSinkProbeTest {
    /** Sink trong giả: ghi (pts, số khung) mỗi handleBuffer rồi coi như đã nhận hết. */
    private fun recordingSink(into: MutableList<Pair<Long, Int>>): AudioSink =
        Proxy.newProxyInstance(AudioSink::class.java.classLoader, arrayOf(AudioSink::class.java)) { _, method, params ->
            when {
                method.name == "handleBuffer" -> {
                    val buffer = params!![0] as ByteBuffer
                    into += (params[1] as Long) to buffer.remaining() / 4
                    buffer.position(buffer.limit())
                    true
                }
                method.returnType == Boolean::class.javaPrimitiveType -> false
                method.returnType == Int::class.javaPrimitiveType -> 0
                method.returnType == Long::class.javaPrimitiveType -> 0L
                method.returnType == Float::class.javaPrimitiveType -> 0f
                else -> null
            }
        } as AudioSink

    private val pcm = Format.Builder().setSampleMimeType(MimeTypes.AUDIO_RAW).setPcmEncoding(C.ENCODING_PCM_16BIT).setChannelCount(2).setSampleRate(44100).build()

    /** Như lần 3 của ls_06: tua tới mẫu 21703 = khối 400 ms + 4063; rồi một flush không nạp số cắt. */
    private fun drive(sink: LoopSeam.LoopSink) {
        sink.configure(AudioSink.AudioSinkConfig.Builder(pcm).build())
        sink.armSeek(4063)
        sink.flush()
        sink.handleBuffer(ByteBuffer.allocate(4410 * 4), 400_000, 1)
        sink.handleBuffer(ByteBuffer.allocate(4410 * 4), 500_000, 1)
        sink.flush()
        sink.handleBuffer(ByteBuffer.allocate(100 * 4), 900_000, 1)
    }

    @Test
    fun probeSeesFlushAndFirstBufferWithoutChangingOutput() {
        val plain = mutableListOf<Pair<Long, Int>>()
        drive(LoopSeam.LoopSink(recordingSink(plain)))

        val probed = mutableListOf<Pair<Long, Int>>()
        val events = mutableListOf<String>()
        val sink = LoopSeam.LoopSink(recordingSink(probed))
        sink.probe = object : LoopSeam.LoopSink.Probe {
            override fun onFlush(armed: Boolean, toDrop: Long, seekPending: Boolean, expectedUs: Long) {
                events += "flush $armed $toDrop $seekPending $expectedUs"
            }

            override fun onFirstBuffer(presentationTimeUs: Long, frames: Long, toDrop: Long, seekPending: Boolean, match: Int) {
                events += "first $presentationTimeUs $frames $toDrop $seekPending $match"
            }

            override fun onSkip(presentationTimeUs: Long, expectedUs: Long) {
                events += "skip $presentationTimeUs $expectedUs"
            }
        }
        drive(sink)

        // cắt 4063 khung đầu: còn 347 khung, nhãn dời 4063 / 44100 s
        assertEquals(listOf(400_000L + 4063L * 1_000_000 / 44100 to 347, 500_000L to 4410, 900_000L to 100), plain)
        assertEquals(plain, probed)
        assertEquals(
            // lệnh không có vị trí đích: không kiểm nhãn (đường đếm lần xả), khớp -1
            listOf("flush true 4063 true -1", "first 400000 4410 4063 true -1", "flush false 0 false -1", "first 900000 100 0 false -1"),
            events,
        )
    }

    @Test
    fun probeReportsTheExpectedPtsAndASkippedStaleBuffer() {
        val sink = LoopSeam.LoopSink(recordingSink(mutableListOf()))
        val events = mutableListOf<String>()
        sink.probe = object : LoopSeam.LoopSink.Probe {
            override fun onFlush(armed: Boolean, toDrop: Long, seekPending: Boolean, expectedUs: Long) {
                events += "flush $armed $toDrop $seekPending $expectedUs"
            }

            override fun onFirstBuffer(presentationTimeUs: Long, frames: Long, toDrop: Long, seekPending: Boolean, match: Int) {
                events += "first $presentationTimeUs $match"
            }

            override fun onSkip(presentationTimeUs: Long, expectedUs: Long) {
                events += "skip $presentationTimeUs $expectedUs"
            }
        }
        sink.configure(AudioSink.AudioSinkConfig.Builder(pcm).build())
        sink.setOutputStreamOffsetUs(1_000_000_000_000L)
        sink.armSeek(4063, positionUs = 400_000)
        sink.flush()
        sink.handleBuffer(ByteBuffer.allocate(4410 * 4), 1_000_000_200_000L, 1) // buffer cũ
        sink.flush()
        sink.handleBuffer(ByteBuffer.allocate(4410 * 4), 1_000_000_400_000L, 1)
        assertEquals(
            listOf(
                "flush true 4063 true 1000000400000", "first 1000000200000 0", "skip 1000000200000 1000000400000",
                "flush true 4063 true 1000000400000", "first 1000000400000 1",
            ),
            events,
        )
    }
}
