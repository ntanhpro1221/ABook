package vn.abook.player

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Phần thuần tuý của [LoopSeam]: công thức trộn của Nối và tiêu đề WAV (phần giải mã / phát do MusicLoopSeamTest kiểm trên máy Android). */
class LoopSeamTest {
    @Test
    fun mixIsLinearPerSampleAndPerChannel() {
        // N = 4 mẫu, 2 kênh: g_mới = n/4
        val old = shortArrayOf(1000, -1000, 1000, -1000, 1000, -1000, 1000, -1000)
        val new = shortArrayOf(0, 4000, 0, 4000, 0, 4000, 0, 4000)
        // n=0: trọn bản cũ; n=1: .75 cũ + .25 mới; n=2: nửa nửa; n=3: .25 cũ + .75 mới
        val expect = shortArrayOf(1000, -1000, 750, 250, 500, 1500, 250, 2750)
        assertArrayEquals(expect, LoopSeam.mix(old, new, 2))
    }

    @Test
    fun mixClampsToPcm16() {
        val out = LoopSeam.mix(shortArrayOf(32767, -32768), shortArrayOf(32767, -32768), 1)
        assertArrayEquals(shortArrayOf(32767, -32768), out)
    }

    @Test
    fun wavHeaderDescribesPcm16() {
        val h = ByteBuffer.wrap(LoopSeam.wavHeader(48000, 2, 1000)).order(ByteOrder.LITTLE_ENDIAN)
        assertEquals(44, h.capacity())
        assertEquals(1036, h.getInt(4)) // RIFF cỡ = 36 + dữ liệu
        assertEquals(1, h.getShort(20).toInt()) // PCM
        assertEquals(2, h.getShort(22).toInt())
        assertEquals(48000, h.getInt(24))
        assertEquals(192000, h.getInt(28))
        assertEquals(4, h.getShort(32).toInt())
        assertEquals(16, h.getShort(34).toInt())
        assertEquals(1000, h.getInt(40))
    }

    private fun seam(rate: Int, preroll: Int): LoopSeam.Seam {
        val spf = 1152L
        // audibleStart' = khung 10, loopStart' = khung 100, loopEnd' = khung 1000, X' = 40 khung
        return LoopSeam.Seam(java.io.File("a.mp3"), java.io.File("a.wav"), 10 * spf, 100 * spf, 1000 * spf, (40 * spf).toInt(), rate, 2, spf.toInt(), 0, preroll)
    }

    @Test
    fun clipBoundsWithoutFixAreTheFrameBoundaries() {
        val s = seam(48000, 0) // 48 kHz: mọi khung là bội 24 ms đúng
        assertEquals(10 * 24L, s.clip0StartMs)
        assertEquals((1000 - 40) * 24L, s.clip0EndMs)
        assertEquals((100 + 40) * 24L, s.loopClipStartMs)
        assertEquals((1000 - 40) * 24L, s.loopClipEndMs)
        assertEquals(40 * 24L, s.seamMs)
    }

    @Test
    fun prerollOpensEarlyAndClosesOneFrameLate() {
        val s = seam(48000, 3)
        assertEquals((100 + 40 - 3) * 24L, s.loopClipStartMs)
        assertEquals((1000 - 40 + 1) * 24L, s.loopClipEndMs)
        assertEquals((1000 - 40 + 1) * 24L, s.clip0EndMs)
        assertEquals(3 * 1152, s.prerollSamples)
        assertEquals(1152, s.tailSamples)
        assertEquals(10 * 24L, s.clip0StartMs) // Clip đầu không mở sớm
    }

    @Test
    fun msRoundsDownLikeMusicBed() {
        val s = seam(44100, 0)
        assertEquals(1152L * 140 * 1000 / 44100, s.loopClipStartMs)
        assertEquals(3657L, s.loopClipStartMs) // 3657,14...
    }

    @Test
    fun seekIntoClipLandsThreeFramesBeforeTheFrameBelowTheTarget() {
        val s = seam(44100, 3)
        val spf = 1152L
        val start = 140 * spf // loopStart' + X' = mẫu 0 của trục danh nghĩa Clip lặp
        // đích = 100 mẫu sau ranh khung 150
        val plan = LoopSeam.seekPlan(s, 2, (150 - 140) * spf + 100)
        val b0 = (150 - 3) * spf
        assertEquals(s.ms(b0) - s.loopClipStartMs - 1, plan.positionMs)
        assertEquals(start + (150 - 140) * spf + 100 - b0, plan.trimFrames) // 3 khung + 100 mẫu
        assertEquals(3 * spf + 100, plan.trimFrames)
    }

    @Test
    fun seekNearTheClipStartNeverLandsBeforeTheOpenFrame() {
        val s = seam(44100, 3)
        val plan = LoopSeam.seekPlan(s, 2, 5) // 5 mẫu sau mẫu đầu danh nghĩa: cửa sổ mở sớm 3 khung
        assertEquals(0L, plan.positionMs)
        assertEquals(3 * 1152L + 5, plan.trimFrames)
        val first = LoopSeam.seekPlan(s, 0, 7) // Clip đầu không mở sớm
        assertEquals(0L, first.positionMs)
        assertEquals(7L, first.trimFrames)
    }

    @Test
    fun seekIntoSeamLandsOnTheHundredMillisecondChunk() {
        val s = seam(44100, 3)
        val plan = LoopSeam.seekPlan(s, 3, 44321) // 1005 ms + 1 mẫu; khối = 4410 khung
        assertEquals(1000L, plan.positionMs)
        assertEquals(44321L - 44100, plan.trimFrames)
        val exact = LoopSeam.seekPlan(s, 1, 4410)
        assertEquals(100L, exact.positionMs)
        assertEquals(0L, exact.trimFrames)
    }

    /** Khung mp3 MPEG-1 tầng 3, 128 kb/s, 44,1 kHz, stereo (FF FB 90 00) = 417 byte. */
    private fun frame(info: Boolean = false): ByteArray {
        val f = ByteArray(417)
        f[0] = 0xFF.toByte(); f[1] = 0xFB.toByte(); f[2] = 0x90.toByte(); f[3] = 0
        if (info) "Info".forEachIndexed { k, c -> f[36 + k] = c.code.toByte() }
        return f
    }

    @Test
    fun scanSkipsId3AndInfoFrameAndCountsAudioFrames() {
        val id3 = ByteArray(10 + 20).also { "ID3".forEachIndexed { k, c -> it[k] = c.code.toByte() }; it[3] = 4; it[9] = 20 }
        val data = id3 + frame(info = true) + (0 until 12).fold(ByteArray(0)) { a, _ -> a + frame() }
        val frames = checkNotNull(LoopSeam.scanMp3(data, 100))
        assertEquals(12, frames.count)
        assertEquals(1152, frames.samplesPerFrame)
        assertEquals(44100, frames.sampleRate)
        assertEquals(2, frames.channels)
        assertEquals(30 + 417, frames.offsets[0]) // sau thẻ ID3 và khung Info
        assertEquals(30 + 417 * 13 - 417, frames.offsets[11])
        assertEquals(5, checkNotNull(LoopSeam.scanMp3(data, 5)).count)
    }
}
