package vn.abook.player

import org.json.JSONArray
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.File

/**
 * Thẻ ID3 điện thoại ghi (Id3Tag) so với file máy tính ghi bằng ffmpeg cho cùng đầu vào (bộ ví dụ chung tests/fixtures/mp3_export,
 * sinh bằng tests/mp3_export_fixtures.py): ID3v2 trùng từng byte trừ khung TSSE (tên phiên bản ffmpeg), ID3v1 trùng từng byte, âm
 * thanh là đúng các khung MP3 của file nguồn.
 */
class Id3TagTest {
    companion object {
        val dir: File by lazy {
            val found = File("../../../tests/fixtures/mp3_export")
            if (!File(found, "tags.json").isFile) {
                fail("Không thấy bộ ví dụ dùng chung: ${found.absoluteFile} (chạy test từ mobile/android/app; sinh lại bằng " +
                    "runtime/.venv/Scripts/python.exe -m tests.mp3_export_fixtures)")
            }
            found.canonicalFile
        }
    }

    private fun fields(case: org.json.JSONObject): Id3Tag.Fields = Id3Tag.Fields(
        title = case.getString("title"),
        album = case.getString("album"),
        artist = case.getString("narrator"),
        number = case.getInt("number"),
        total = case.getInt("total"),
        cover = if (case.isNull("cover")) null else Id3Tag.Cover.of(File(dir, case.getString("cover")).readBytes()),
    )

    private val cases: List<org.json.JSONObject> by lazy {
        val array = JSONArray(File(dir, "tags.json").readText(Charsets.UTF_8))
        (0 until array.length()).map { array.getJSONObject(it) }
    }

    @Test
    fun theTagsAreTheBytesTheDesktopWritesWithoutTheFfmpegVersion() {
        assertEquals(3, cases.size)
        for (case in cases) {
            val expected = File(dir, case.getString("expected")).readBytes()
            val ours = Id3Tag.v2(fields(case))
            assertArrayEquals(case.getString("name"), Id3Bytes.v2Without(expected, "TSSE"), ours)
            assertArrayEquals(case.getString("name"), Id3Bytes.v1(expected), Id3Tag.v1(fields(case)))
        }
    }

    @Test
    fun theAudioIsTheSourceFramesUntouched() {
        val source = File(dir, "source.mp3")
        val bytes = source.readBytes()
        val range = Id3Tag.audioRange(source)
        // Nguồn có cả ID3v2 ("645", "lo16") lẫn ID3v1: phần âm thanh bắt đầu ở khung MP3 đầu tiên, dừng trước "TAG".
        assertEquals(0xFF, bytes[range.first.toInt()].toInt() and 0xFF)
        assertEquals("TAG", String(bytes, range.last.toInt() + 1, 3, Charsets.ISO_8859_1))
        assertEquals(bytes.size.toLong(), range.last + 1 + 128)
        val audio = bytes.copyOfRange(range.first.toInt(), range.last.toInt() + 1)
        for (case in cases) {
            val out = ByteArrayOutputStream()
            Id3Tag.write(source, out, fields(case))
            val written = out.toByteArray()
            val v2 = Id3Tag.v2(fields(case))
            assertArrayEquals(v2, written.copyOfRange(0, v2.size))
            assertArrayEquals(audio, written.copyOfRange(v2.size, written.size - 128))
            // ffmpeg (`-c:a copy`) cũng giữ nguyên các khung âm thanh; chỉ khung đầu (khung Info/Xing không mang tiếng) được viết lại.
            val expected = File(dir, case.getString("expected")).readBytes()
            val start = 10 + Id3Bytes.syncsafe(expected, 6)
            val theirs = expected.copyOfRange(start + Id3Bytes.frameLength(expected, start), expected.size - 128)
            val sourceFrames = audio.copyOfRange(Id3Bytes.frameLength(audio, 0), audio.size)
            assertArrayEquals(case.getString("name"), sourceFrames, theirs)
        }
    }

    @Test
    fun aFileWithoutTagsIsAllAudio() {
        val file = File.createTempFile("plain", ".mp3")
        try {
            val audio = File(dir, "source.mp3").readBytes().let { it.copyOfRange(Id3Tag.audioRange(File(dir, "source.mp3")).first.toInt(), it.size - 128) }
            file.writeBytes(audio)
            assertEquals(0L until audio.size.toLong(), Id3Tag.audioRange(file))
        } finally {
            file.delete()
        }
    }

    @Test
    fun onlyJpegAndPngAreCovers() {
        assertEquals("image/jpeg", Id3Tag.Cover.of(File(dir, "cover.jpg").readBytes())?.mime)
        assertEquals("image/png", Id3Tag.Cover.of(File(dir, "cover.png").readBytes())?.mime)
        assertEquals(null, Id3Tag.Cover.of("RIFF....WEBP".toByteArray()))
        // Giọng kể trống: không có khung TPE1/TPE2 (ffmpeg bỏ `-metadata artist=` rỗng).
        val tag = String(Id3Tag.v2(Id3Tag.Fields("a", "b", "", 1, 1, null)), Charsets.ISO_8859_1)
        assertTrue(tag.contains("TIT2") && !tag.contains("TPE1") && !tag.contains("TPE2"))
    }
}
