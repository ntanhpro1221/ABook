package vn.abook.player

import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMetadataRetriever
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import vn.abook.player.readaloud.Paragraphs
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import kotlin.math.PI
import kotlin.math.sin

/**
 * "Xuất sách nói" của sách Nghe ngay, đường mã hoá THẬT (bộ giải mã / mã hoá AAC và MediaMuxer của Android): hai chương, mỗi chương một đoạn giọng đọc giả - chương 1 là clip
 * WAV (giọng trên máy), chương 2 là clip MP3 (giọng trực tuyến, ở tần số khác) - qua đúng [ListenExport.Run] + [ListenAudio] + [M4bExport.run] của việc nền, rồi đọc lại file .m4b:
 * hai mốc chương (tên đúng, mốc đầu = 0 và nằm ngay sau chương 1), thời lượng, một track AAC mono, tag tên sách / tác giả. Không dùng giọng thật hay mạng. Thư mục làm việc và file ra nằm
 * trong thư mục ngoài của app (`.../files/listen-export-test/Sách thử.m4b`) để `adb pull` rồi đối chiếu bằng ffprobe trên máy tính.
 */
@RunWith(AndroidJUnit4::class)
class ListenExportOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private lateinit var folder: File

    @Before
    fun setUp() {
        folder = File(context.getExternalFilesDir(null) ?: context.filesDir, "listen-export-test").apply { deleteRecursively(); mkdirs() }
    }

    @After
    fun tearDown() {
        File(folder, "work").deleteRecursively()
    }

    private fun sineWav(seconds: Double, rate: Int): File {
        val frames = (seconds * rate).toInt()
        val data = ByteBuffer.allocate(frames * 2).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        for (i in 0 until frames) data.putShort((sin(2 * PI * 330 * i / rate) * 8000).toInt().toShort())
        val out = ByteArrayOutputStream()
        fun le32(v: Int) { for (i in 0 until 4) out.write((v shr (8 * i)) and 0xFF) }
        fun le16(v: Int) { out.write(v and 0xFF); out.write((v shr 8) and 0xFF) }
        out.write("RIFF".toByteArray()); le32(36 + data.capacity()); out.write("WAVEfmt ".toByteArray()); le32(16)
        le16(1); le16(1); le32(rate); le32(rate * 2); le16(2); le16(16)
        out.write("data".toByteArray()); le32(data.capacity())
        out.write(data.array())
        return File(folder, "clip-wav.wav").also { it.writeBytes(out.toByteArray()) }
    }

    /** Đọc mốc chương Nero (`chpl`) của file: (mốc đầu ms, tên). */
    private fun chapterMarks(file: File): List<Pair<Long, String>> {
        val bytes = file.readBytes()
        val at = (0..bytes.size - 4).first { String(bytes, it, 4, Charsets.ISO_8859_1) == "chpl" }
        val buffer = ByteBuffer.wrap(bytes, at + 4 + 4 + 4, bytes.size - at - 12) // sau tên hộp: phiên bản + cờ (4), dành riêng (4)
        val count = buffer.get().toInt() and 0xFF
        return (0 until count).map {
            val start = buffer.long / 10_000
            val title = ByteArray(buffer.get().toInt() and 0xFF).also(buffer::get)
            start to String(title, Charsets.UTF_8)
        }
    }

    @Test
    fun twoChaptersBecomeOneM4bWithTwoChapterMarksReadableBack() {
        val wav = sineWav(3.0, 24000)
        val mp3 = File(folder, "clip-mp3.mp3").also { it.writeBytes(instrumentation.context.assets.open("source.mp3").use { stream -> stream.readBytes() }) }
        val chapters = listOf(
            ListenExport.Chapter(1, "Chương 1 · Mở đầu", Paragraphs.split("Đoạn của chương một.")),
            ListenExport.Chapter(2, "Chương 2", Paragraphs.split("Đoạn của chương hai.")),
        )
        val reading = ListenExport.Reading("edge:vi-VN-HoaiMyNeural", null, emptyMap())
        val work = File(folder, "work").apply { mkdirs() }
        val progress = ArrayList<ListenExport.Progress>()
        val runner = ListenExport.Run(
            chapters, reading, work,
            synth = { text -> if (text.contains("một")) wav else mp3 },
            decoder = Clips, outputs = ListenAudio.outputs, progress = { progress += it }, stopped = { false },
        )
        val stamps = runner.build()
        assertEquals(24000, stamps[0].rate)
        assertEquals("chương 2 đổi về tần số chung của cuốn", 24000, stamps[1].rate)
        assertEquals(3.0, stamps[0].seconds, 0.01)
        assertTrue(stamps[1].seconds > 0.2)
        assertEquals(100, progress.last().percent)
        for (chapter in chapters) assertTrue(ListenExport.audioFile(work, chapter).length() > 1000)

        // Làm tiếp: lượt thứ hai không đọc lại gì.
        var reads = 0
        ListenExport.Run(chapters, reading, work, { reads += 1; null }, Clips, ListenAudio.outputs, {}, { false }).build()
        assertEquals(0, reads)

        val book = JSONObject().put("title", "Sách thử").put("author", "Đức Trí").put("chaptersTotal", 2)
        val plan = ListenExport.exportPlan(book, "sach-thu", chapters, stamps, work, null, "cover.png")
        val target = File(folder, "Sách thử.m4b")
        val result = target.outputStream().buffered().use { M4bExport.run(plan, File(work, "all.m4a"), it, ListenAudio) }
        assertEquals("Sách thử.m4b", result.name)
        assertEquals(2, result.chapters)
        assertEquals(target.length(), result.size)
        assertFalse("file nối trung gian dọn sau khi xong", File(work, "all.m4a").exists())

        // Hai mốc chương: chương 1 từ 0, chương 2 ngay sau chương 1 (3 giây tiếng + chừng 0,1 giây lặng của bộ mã hoá giữa hai chương).
        val marks = chapterMarks(target)
        assertEquals(listOf("Chương 1 · Mở đầu", "Chương 2"), marks.map { it.second })
        assertEquals(0L, marks[0].first)
        assertTrue("chương 2 bắt đầu sau 3 giây: ${marks[1].first}", marks[1].first in 3000..3400)

        MediaMetadataRetriever().apply {
            try {
                setDataSource(target.absolutePath)
                val seconds = extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)!!.toLong() / 1000.0
                val expected = stamps.sumOf { it.seconds }
                assertEquals("thời lượng = hai chương + lặng giữa chúng", expected, seconds, 0.4)
                assertEquals("Sách thử", extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE))
                assertEquals("Đức Trí", extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST))
            } finally {
                release()
            }
        }
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(target.absolutePath)
            val audio = (0 until extractor.trackCount).map(extractor::getTrackFormat).filter { it.getString(MediaFormat.KEY_MIME) == MediaFormat.MIMETYPE_AUDIO_AAC }
            assertEquals(1, audio.size)
            assertEquals(1, audio[0].getInteger(MediaFormat.KEY_CHANNEL_COUNT))
            assertEquals(24000, audio[0].getInteger(MediaFormat.KEY_SAMPLE_RATE))
        } finally {
            extractor.release()
        }
    }
}
