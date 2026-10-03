package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files

/** WAV của giọng máy và việc chia/nối đoạn dài (TextChunks, Wav.concat), cùng độ to cố định từng giọng (VoiceGain). */
class WavTest {
    private val dir: File = Files.createTempDirectory("wav").toFile()

    @After
    fun cleanUp() {
        dir.deleteRecursively()
    }

    /** WAV PCM 16 bit mono: đầu 44 byte + `samples` mẫu. `junk` chèn một mục LIST trước `data` như vài bộ đọc làm. */
    private fun wav(rate: Int, samples: Int, junk: Boolean = false, fill: Int = 1): ByteArray {
        val out = ByteArrayOutputStream()
        fun le32(v: Int) { for (i in 0 until 4) out.write((v shr (8 * i)) and 0xFF) }
        fun le16(v: Int) { out.write(v and 0xFF); out.write((v shr 8) and 0xFF) }
        val extra = if (junk) 12 else 0
        out.write("RIFF".toByteArray()); le32(36 + extra + samples * 2); out.write("WAVEfmt ".toByteArray()); le32(16)
        le16(1); le16(1); le32(rate); le32(rate * 2); le16(2); le16(16)
        if (junk) { out.write("LIST".toByteArray()); le32(4); out.write("INFO".toByteArray()) }
        out.write("data".toByteArray()); le32(samples * 2)
        repeat(samples * 2) { out.write(fill) }
        return out.toByteArray()
    }

    @Test
    fun readsTheFormatAndTheDurationFromTheFileSize() {
        val bytes = wav(22_050, 22_050)
        val format = Wav.parse(bytes.copyOf(100))!!
        assertEquals(22_050, format.sampleRate)
        assertEquals(1, format.channels)
        assertEquals(44, format.dataOffset)
        assertEquals(1000, format.durationMs(bytes.size.toLong()))
    }

    @Test
    fun skipsOtherChunksBeforeTheData() {
        val bytes = wav(16_000, 8_000, junk = true)
        val format = Wav.parse(bytes)!!
        assertEquals(56, format.dataOffset)
        assertEquals(500, format.durationMs(bytes.size.toLong()))
    }

    @Test
    fun aFileThatIsNotWavIsRejected() {
        assertNull(Wav.parse("RIFFxxxxAVI ".toByteArray()))
        assertNull(Wav.parse(ByteArray(3)))
    }

    @Test
    fun concatJoinsPartsIntoOneWavWithTheSummedLength() {
        val a = File(dir, "a.wav").apply { writeBytes(wav(16_000, 8_000, fill = 1)) }
        val b = File(dir, "b.wav").apply { writeBytes(wav(16_000, 16_000, junk = true, fill = 2)) }
        val out = File(dir, "out.wav")
        Wav.concat(listOf(a, b), out)
        val format = Wav.format(out)!!
        assertEquals(44, format.dataOffset)
        assertEquals(1500, format.durationMs(out.length()))
        val bytes = out.readBytes()
        assertEquals(1, bytes[44].toInt())
        assertEquals(2, bytes[44 + 16_000].toInt())
        assertNotNull(Wav.parse(bytes.copyOf(60)))
    }

    @Test
    fun concatRefusesMismatchedFormats() {
        val a = File(dir, "a.wav").apply { writeBytes(wav(16_000, 100)) }
        val b = File(dir, "b.wav").apply { writeBytes(wav(22_050, 100)) }
        try {
            Wav.concat(listOf(a, b), File(dir, "out.wav"))
            org.junit.Assert.fail("đáng ra lỗi")
        } catch (expected: java.io.IOException) {
        }
    }

    @Test
    fun longTextIsCutAtSpacesWithinTheLimitAndKeepsEveryCharacter() {
        val text = "một hai ba bốn năm sáu bảy tám chín mười"
        val parts = TextChunks.split(text, 15)
        assertEquals(text, parts.joinToString("") { it.second })
        assertEquals(parts.map { it.first }, parts.runningFold(0) { at, p -> at + p.second.length }.dropLast(1))
        assertEquals(true, parts.all { it.second.length <= 15 })
        assertEquals(true, parts.dropLast(1).all { it.second.endsWith(" ") })
    }

    @Test
    fun aWordLongerThanTheLimitIsCutHard() {
        val parts = TextChunks.split("a".repeat(25), 10)
        assertEquals(listOf(10, 10, 5), parts.map { it.second.length })
    }

    @Test
    fun shortTextIsOnePart() {
        assertEquals(listOf(0 to "Xin chào"), TextChunks.split("Xin chào", 100))
    }

    @Test
    fun chunkSizeCanBeCountedInBytes() {
        val parts = TextChunks.split("ạ ạ ạ ạ", 5) { EdgeProtocol.escapedBytes(it) }
        assertEquals(true, parts.all { part -> part.second.sumOf { EdgeProtocol.escapedBytes(it) } <= 5 })
        assertEquals("ạ ạ ạ ạ", parts.joinToString("") { it.second })
    }

    @Test
    fun voiceGainIsTheMeasuredLufsOffsetPerVoice() {
        assertEquals(-1.7, VoiceGain.db("edge:vi-VN-HoaiMyNeural"), 0.0)
        assertEquals(-0.3, VoiceGain.db("edge:vi-VN-NamMinhNeural"), 0.0)
        assertEquals(0.0, VoiceGain.db("device:vi-vn-x-gft-local"), 0.0)
        assertEquals(0.8222f, VoiceGain.factor(-1.7), 0.0005f)
        assertEquals(1f, VoiceGain.factor(0.0), 0f)
    }
}
