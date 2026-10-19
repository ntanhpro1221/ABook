package vn.abook.player

import androidx.media3.common.C
import androidx.media3.common.DataReader
import androidx.media3.common.Format
import androidx.media3.common.util.ParsableByteArray
import androidx.media3.extractor.DefaultExtractorInput
import androidx.media3.extractor.Extractor
import androidx.media3.extractor.ExtractorInput
import androidx.media3.extractor.ExtractorOutput
import androidx.media3.extractor.PositionHolder
import androidx.media3.extractor.SeekMap
import androidx.media3.extractor.TrackOutput
import androidx.media3.extractor.mp3.Mp3Extractor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import kotlin.math.abs

/**
 * Bộ tách mp3 tua đúng khung của nhạc nền (loopfix): trên ba file mẫu nhỏ (test/resources/mp3seek, ffmpeg libmp3lame, 4 s mono) -
 * VBR có Xing + mục lục (MPEG-1 44,1 kHz), CBR có Info (MPEG-2 22,05 kHz), CBR không header. Làm như ProgressiveMediaPeriod với trình
 * phát mới có chỗ bắt đầu: đọc từ 0 tới khi có SeekMap, `getSeekPoints(t).first`, `seek(vị trí, t)`, đọc tiếp từ byte ấy; khung đầu được
 * giữ là khung đầu có nhãn >= t. Thời điểm thật của khung = k*spf/sr, k đếm khung từ đầu file (đọc liền từ 0).
 */
class ExactSeekMp3ExtractorTest {
    private class Sample(val timeUs: Long, val start: Long)

    private class Out : ExtractorOutput, TrackOutput {
        var seekMap: SeekMap? = null
        var format: Format? = null
        var input: ExtractorInput? = null
        val samples = ArrayList<Sample>()
        private val scratch = ByteArray(8192)
        override fun track(id: Int, type: Int): TrackOutput = this
        override fun endTracks() {}
        override fun seekMap(seekMap: SeekMap) { this.seekMap = seekMap }
        override fun format(format: Format) { this.format = format }
        override fun sampleData(input: DataReader, length: Int, allowEndOfInput: Boolean, sampleDataPart: Int): Int {
            val n = input.read(scratch, 0, minOf(length, scratch.size))
            return if (n == C.RESULT_END_OF_INPUT && !allowEndOfInput) throw java.io.EOFException() else n
        }
        override fun sampleData(data: ParsableByteArray, length: Int, sampleDataPart: Int) = data.skipBytes(length)
        override fun sampleMetadata(timeUs: Long, flags: Int, size: Int, offset: Int, cryptoData: TrackOutput.CryptoData?) {
            samples += Sample(timeUs, input!!.position - size - offset)
        }
    }

    private class Mp3(val bytes: ByteArray, val sampleRate: Int) {
        val samplesPerFrame = if (sampleRate >= 32000) 1152 else 576
    }

    private fun load(name: String, sampleRate: Int) =
        Mp3(javaClass.classLoader!!.getResourceAsStream("mp3seek/$name")!!.use { it.readBytes() }, sampleRate)

    private fun input(file: Mp3, position: Long): ExtractorInput {
        var at = position.toInt()
        val reader = DataReader { buffer, offset, length ->
            if (length == 0) return@DataReader 0
            if (at >= file.bytes.size) return@DataReader C.RESULT_END_OF_INPUT
            val n = minOf(length, file.bytes.size - at)
            System.arraycopy(file.bytes, at, buffer, offset, n)
            at += n
            n
        }
        return DefaultExtractorInput(reader, position, file.bytes.size.toLong())
    }

    /** Đọc tới khi `stop`, theo RESULT_SEEK sang input mới. */
    private fun pump(extractor: Extractor, out: Out, file: Mp3, start: ExtractorInput, stop: (Out) -> Boolean) {
        var current = start
        out.input = current
        val holder = PositionHolder()
        while (!stop(out)) {
            when (extractor.read(current, holder)) {
                Extractor.RESULT_SEEK -> current = input(file, holder.position).also { out.input = it }
                Extractor.RESULT_END_OF_INPUT -> return
            }
        }
    }

    private class Prepared(val extractor: Extractor, val out: Out)

    private fun prepare(file: Mp3, make: () -> Extractor, stop: (Out) -> Boolean = { it.seekMap != null && it.format != null }): Prepared {
        val extractor = make()
        val out = Out()
        extractor.init(out)
        val start = input(file, 0)
        assertTrue(extractor.sniff(start))
        start.resetPeekPosition()
        pump(extractor, out, file, start, stop)
        return Prepared(extractor, out)
    }

    /** Trình phát mới vào từ `timeUs`: khung đầu được giữ (nhãn >= timeUs). */
    private fun firstKept(file: Mp3, make: () -> Extractor, timeUs: Long): Sample {
        val prepared = prepare(file, make)
        val point = prepared.out.seekMap!!.getSeekPoints(timeUs).first
        prepared.extractor.seek(point.position, timeUs)
        prepared.out.samples.clear()
        pump(prepared.extractor, prepared.out, file, input(file, point.position)) { out -> out.samples.any { it.timeUs >= timeUs } }
        return prepared.out.samples.first { it.timeUs >= timeUs }
    }

    /** Byte đầu của từng khung âm thanh khi đọc liền từ 0 (chỉ số = k). */
    private fun frameStarts(file: Mp3): List<Long> = prepare(file, { Mp3Extractor() }) { false }.out.samples.map { it.start }

    private val newOne = { ExactSeekMp3Extractor() as Extractor }
    private val today = { Mp3Extractor() as Extractor } // = bộ của DefaultExtractorsFactory (cờ mp3 mặc định 0)

    @Before
    fun setUp() {
        pretendMedia3IsUnderTest()
    }

    private fun checkExactSeeks(file: Mp3) {
        val starts = frameStarts(file)
        for (seconds in listOf(0.35, 1.3, 2.0, 2.71, 3.6)) {
            val timeUs = (seconds * 1e6).toLong()
            val kept = firstKept(file, newOne, timeUs)
            val k = starts.indexOf(kept.start)
            assertTrue("khung ở byte ${kept.start} không phải ranh khung", k >= 0)
            val trueUs = k * file.samplesPerFrame * 1_000_000.0 / file.sampleRate
            assertTrue("t=$seconds: nhãn ${kept.timeUs} µs, thật $trueUs µs", abs(kept.timeUs - trueUs) <= 1000.0)
            assertTrue(trueUs >= timeUs - 1000.0 && trueUs - timeUs < file.samplesPerFrame * 1e6 / file.sampleRate + 1000.0)
        }
    }

    private fun checkSameDurationAndGapless(file: Mp3) {
        val mine = prepare(file, newOne).out
        val theirs = prepare(file, today).out
        assertEquals(theirs.seekMap!!.durationUs, mine.seekMap!!.durationUs)
        assertEquals(theirs.format!!.encoderDelay, mine.format!!.encoderDelay)
        assertEquals(theirs.format!!.encoderPadding, mine.format!!.encoderPadding)
        assertEquals(theirs.format!!.sampleRate, mine.format!!.sampleRate)
        assertTrue(mine.format!!.encoderDelay > 0) // gapless LAME vẫn đọc được từ khung đã viết lại
    }

    @Test
    fun aVbrFileWithAXingTableSeeksByCountingFrames() {
        val file = load("vbr_xing.mp3", 44100)
        assertEquals("XingSeeker", prepare(file, today).out.seekMap!!.javaClass.simpleName)
        assertEquals("IndexSeeker", prepare(file, newOne).out.seekMap!!.javaClass.simpleName)
        checkSameDurationAndGapless(file)
        checkExactSeeks(file)
    }

    @Test
    fun aCbrFileWithAnInfoFrameSeeksByCountingFrames() {
        val file = load("cbr_info.mp3", 22050)
        assertEquals("ConstantBitrateSeeker", prepare(file, today).out.seekMap!!.javaClass.simpleName)
        assertEquals("IndexSeeker", prepare(file, newOne).out.seekMap!!.javaClass.simpleName)
        checkSameDurationAndGapless(file)
        checkExactSeeks(file)
    }

    @Test
    fun aFileWithoutAHeaderFrameIsLeftAsItIs() {
        val file = load("cbr_plain.mp3", 22050)
        val mine = prepare(file, newOne).out
        val theirs = prepare(file, today).out
        assertEquals(theirs.seekMap!!.javaClass.simpleName, mine.seekMap!!.javaClass.simpleName)
        assertEquals(theirs.seekMap!!.durationUs, mine.seekMap!!.durationUs)
        for (seconds in listOf(0.35, 1.3, 2.71, 3.6)) {
            val timeUs = (seconds * 1e6).toLong()
            val a = firstKept(file, newOne, timeUs)
            val b = firstKept(file, today, timeUs)
            assertEquals(b.start, a.start)
            assertEquals(b.timeUs, a.timeUs)
        }
    }

    @Test
    fun theMusicBedFactorySwapsOnlyTheMp3Extractor() {
        val other = object : Extractor {
            override fun sniff(input: ExtractorInput) = false
            override fun init(output: ExtractorOutput) {}
            override fun read(input: ExtractorInput, seekPosition: PositionHolder) = Extractor.RESULT_END_OF_INPUT
            override fun seek(position: Long, timeUs: Long) {}
            override fun release() {}
        }
        val swapped = Streaming.withExactMp3Seek(arrayOf(other, Mp3Extractor(), other))
        assertEquals(3, swapped.size)
        assertTrue(swapped[0] === other && swapped[2] === other)
        assertTrue(swapped[1] is ExactSeekMp3Extractor)
    }

    @Test
    fun theLoopStartsAtTheNearestFrameBoundary() {
        val frame44 = 1152.0 / 44100
        val start = ExactSeekMp3Extractor.frameBoundarySeconds(25.642, 44100)
        assertEquals(982.0 * frame44, start, 1e-9) // 25.642 s = khung 981,6 -> 982
        assertEquals(10.0 * frame44, ExactSeekMp3Extractor.frameBoundarySeconds(10.4 * frame44, 44100), 1e-9)
        assertEquals(11.0 * frame44, ExactSeekMp3Extractor.frameBoundarySeconds(10.6 * frame44, 44100), 1e-9)
        assertEquals(7.0 * 1152 / 48000, ExactSeekMp3Extractor.frameBoundarySeconds(7.0 * 1152 / 48000, 48000), 1e-12) // đã ở ranh: giữ
        assertEquals(40.0 * 576 / 22050, ExactSeekMp3Extractor.frameBoundarySeconds(40.3 * 576 / 22050, 22050), 1e-9) // MPEG-2: 576
        assertEquals(12.345, ExactSeekMp3Extractor.frameBoundarySeconds(12.345, 0), 0.0) // chưa biết tần số: giữ nguyên
        // MusicBed.open lấy mili giây làm tròn xuống: không bao giờ sau ranh khung (khung ấy được giữ)
        for (k in 0 until 5000) {
            val seconds = ExactSeekMp3Extractor.frameBoundarySeconds(k * frame44, 44100)
            assertTrue((seconds * 1000).toLong() * 1000 <= Math.round(k * 1152 * 1e6 / 44100))
        }
    }
}
