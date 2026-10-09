package vn.abook.player

import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMetadataRetriever
import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.WorkInfo
import androidx.work.WorkManager
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.Collections
import java.util.UUID

/**
 * "Xuất M4B" trên máy Android (máy ảo): việc nền thật (WorkManager, M4bExportWorker) làm file .m4b của một cuốn ba chương đã xong + một
 * chương chưa làm bằng bộ mã hoá AAC thật của Android, rồi kiểm cỡ, thời lượng, mục lục chương. File ra nằm trong thư mục ngoài của app
 * (`.../files/m4b-export-test/Sách thử.m4b`) để `adb pull` rồi đối chiếu bằng ffprobe trên máy tính.
 *
 * Nơi lưu là một file `file:` của app: hộp thoại "tạo file" của hệ thống (SAF) cần người bấm, bài thử không tự cấp quyền được.
 */
@RunWith(AndroidJUnit4::class)
class M4bExportOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val id = "m4b-export-on-device"
    private lateinit var out: File
    private var seconds = 0.0 // tổng thời lượng các chương nghe được, theo nguồn đã chọn trong setUp
    // Thời lượng Android giải mã được từ một lần lặp source.mp3 (file ghi 0,39 giây gồm cả độ trễ bộ mã hoá MP3 mà Android cắt).
    private val COPY_SECONDS = 0.3735
    private val repeats = listOf(8, 14, 5) // số lần lặp source.mp3 (0,39 giây) cho mỗi chương: ~3,1 s, ~5,5 s, ~2,0 s

    private fun asset(name: String): ByteArray = instrumentation.context.assets.open(name).use { it.readBytes() }

    /** `copies` lần lặp của MP3 mẫu thành một MP3 dài hơn (khung MP3 độc lập; chỉ giữ thẻ ID3v2 của bản đầu). */
    private fun longMp3(copies: Int): ByteArray {
        val source = asset("source.mp3")
        val tag = if (source.size > 10 && String(source, 0, 3) == "ID3") {
            ((source[6].toInt() and 0x7F) shl 21) or ((source[7].toInt() and 0x7F) shl 14) or ((source[8].toInt() and 0x7F) shl 7) or (source[9].toInt() and 0x7F)
        } else {
            -1
        }
        val body = if (tag >= 0) source.copyOfRange(10 + tag, source.size) else source
        val bytes = ByteArrayOutputStream()
        bytes.write(source)
        repeat(copies - 1) { bytes.write(body) }
        return bytes.toByteArray()
    }

    @Before
    fun setUp() {
        Store.init(context)
        val dir = Store.bookDir(id).apply { deleteRecursively(); mkdirs() }
        File(dir, "chapters").mkdirs()
        val chapters = JSONArray()
        val titles = listOf("Chương 1: Mở đầu", "Chương 2 · Về nhà", "Chương 3", "Chương 4 chưa làm")
        titles.forEachIndexed { index, title ->
            val done = index < repeats.size
            val chapter = JSONObject().put("id", index + 1).put("index", index + 1).put("fullTitle", title)
                .put("duration", if (done) repeats[index] * 0.39 else 0.0).put("available", done)
            if (done) {
                // Bộ MP3 mẫu của máy tính là im lặng; muốn đối chiếu tiếng thật (mốc chương, độ trễ bộ mã hoá) thì đẩy ch1.mp3.. ch3.mp3 có
                // tiếng vào .../files/m4b-fixtures/ bằng `adb push` - bài thử dùng chúng thay cho MP3 mẫu.
                val real = File(context.getExternalFilesDir(null) ?: context.filesDir, "m4b-fixtures/ch${index + 1}.mp3").takeIf { it.isFile }
                File(dir, "chapters/${index + 1}.mp3").writeBytes(real?.readBytes() ?: longMp3(repeats[index]))
                seconds += if (real != null) listOf(3.0, 3.0, 2.0)[index] else repeats[index] * COPY_SECONDS
                chapter.put("file", "chapters/${index + 1}.mp3")
            }
            chapters.put(chapter)
        }
        File(dir, "book.json").writeText(JSONObject().put("format", "abook-book/1").put("title", "Sách thử").put("narrator", "Đức Trí")
            .put("chaptersTotal", titles.size).put("chapters", chapters).toString())
        out = File(context.getExternalFilesDir(null) ?: context.filesDir, "m4b-export-test").apply { mkdirs() }
    }

    @After
    fun tearDown() {
        M4bExports.events = null
        Store.bookDir(id).deleteRecursively()
        // File ra (m4b-export-test/) để lại cho `adb pull`; lần chạy sau ghi đè.
    }

    @Test
    fun makesOneFileWithTheChaptersInTheBackground() {
        val events = Collections.synchronizedList(ArrayList<JSONObject>())
        M4bExports.events = { events += it }
        val drawn = File(context.cacheDir, "m4b-export-test-cover.png").apply { writeBytes(asset("cover.png")) }
        val target = File(out, "Sách thử.m4b")
        target.writeBytes(ByteArray(0)) // như file rỗng hộp thoại "tạo file" đã tạo sẵn
        val run = M4bExports.start(context, id, Uri.fromFile(target), drawn)

        val work = WorkManager.getInstance(context)
        val deadline = System.currentTimeMillis() + 120_000
        var info: WorkInfo? = work.getWorkInfoById(UUID.fromString(run)).get()
        while (info?.state?.isFinished != true && System.currentTimeMillis() < deadline) {
            Thread.sleep(200)
            info = work.getWorkInfoById(UUID.fromString(run)).get()
        }
        assertEquals(WorkInfo.State.SUCCEEDED, info?.state)
        assertTrue("bìa tự vẽ dọn sau khi xong", !drawn.exists())
        assertFalse("file trung gian dọn sau khi xong", File(context.cacheDir, "m4b-export").listFiles().orEmpty().isNotEmpty())

        assertTrue(target.length() > 4_000)
        val expected = seconds
        MediaMetadataRetriever().apply {
            try {
                setDataSource(target.absolutePath)
                val seconds = extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)!!.toLong() / 1000.0
                assertEquals("thời lượng = tổng các chương", expected, seconds, 0.2)
                assertEquals("Sách thử", extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE))
                assertEquals("Đức Trí", extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST))
                assertEquals("audio/mp4", extractMetadata(MediaMetadataRetriever.METADATA_KEY_MIMETYPE))
            } finally {
                release()
            }
        }
        // Trình phát của Android đọc được luồng AAC của file cuối.
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(target.absolutePath)
            val audio = (0 until extractor.trackCount).map(extractor::getTrackFormat).filter { it.getString(MediaFormat.KEY_MIME) == "audio/mp4a-latm" }
            assertEquals(1, audio.size)
            assertEquals(1, audio[0].getInteger(MediaFormat.KEY_CHANNEL_COUNT))
        } finally {
            extractor.release()
        }

        // Giao diện nhận tiến độ rồi kết quả: 3 chương xuất, sách có 4 chương (chương chưa xong được nói là không có).
        val last = events.last()
        assertEquals(run, last.getString("run"))
        assertTrue(last.optBoolean("finished"))
        assertEquals(3, last.getInt("chapters"))
        assertEquals(4, last.getInt("chaptersTotal"))
        assertEquals("Sách thử.m4b", last.getString("name"))
        assertEquals(target.length(), last.getLong("size"))
        assertTrue(events.any { it.optInt("done") == 1 && it.optInt("total") == 3 })
        assertTrue(events.any { it.optInt("percent") in 1..99 })
    }

    @Test
    fun stoppingMidwayLeavesNeitherThePartialNorTheScratchFile() {
        val plan = Mp3Export.plan(id)
        val work = File(context.cacheDir, "m4b-export-stop.m4a")
        var finished = 0
        try {
            M4bExport.run(plan, work, ByteArrayOutputStream(), M4bAudio, progress = { done, _, _ -> finished = done }, stopped = { finished >= 1 })
            fail("phải dừng")
        } catch (_: Mp3Export.Stopped) {
            assertFalse(work.exists())
        }
    }

    @Test
    fun aChapterThatCannotBeDecodedIsReportedAndNothingIsLeftBehind() {
        File(Store.bookDir(id), "chapters/2.mp3").writeBytes(ByteArray(2000) { (it * 31).toByte() })
        val work = File(context.cacheDir, "m4b-export-bad.m4a")
        try {
            M4bExport.run(Mp3Export.plan(id), work, ByteArrayOutputStream(), M4bAudio)
            fail("phải báo lỗi")
        } catch (error: Mp3Export.Refused) {
            assertTrue(error.message!!, error.message!!.contains("2.mp3"))
            assertFalse(work.exists())
        }
    }
}
