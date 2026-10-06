package vn.abook.player

import android.media.MediaMetadataRetriever
import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.WorkInfo
import androidx.work.WorkManager
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.Collections
import java.util.UUID

/**
 * "Xuất MP3" trên máy Android (máy ảo): việc nền thật (WorkManager, Mp3ExportWorker) xuất một cuốn hai chương đã xong + một chương chưa
 * làm, rồi kiểm tên file, danh sách phát, bìa, và tag - chương 1 trùng từng byte với file ffmpeg của máy tính cho cùng đầu vào (bộ ví dụ
 * tests/fixtures/mp3_export, ca "vietnamese_drawn_cover", trừ khung TSSE) và Android đọc ra đúng tên, sách, giọng kể, số thứ tự, ảnh bìa.
 *
 * Nơi lưu là một thư mục `file:` của app: bộ chọn thư mục của hệ thống (SAF) cần người bấm, bài thử không tự cấp quyền được.
 */
@RunWith(AndroidJUnit4::class)
class Mp3ExportOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val id = "mp3-export-on-device"
    private lateinit var out: File

    private fun asset(name: String): ByteArray = instrumentation.context.assets.open(name).use { it.readBytes() }

    @Before
    fun setUp() {
        Store.init(context)
        val dir = Store.bookDir(id).apply { deleteRecursively(); mkdirs() }
        File(dir, "chapters").mkdirs()
        val chapters = JSONArray()
        listOf("Chương 1: Mở đầu", "Chương 2 · Về nhà", "Chương 3").forEachIndexed { index, title ->
            val done = index < 2
            val chapter = JSONObject().put("id", index + 1).put("index", index + 1).put("fullTitle", title)
                .put("duration", if (done) 0.3 else 0.0).put("available", done)
            if (done) {
                File(dir, "chapters/${index + 1}.mp3").writeBytes(asset("source.mp3"))
                chapter.put("file", "chapters/${index + 1}.mp3")
            }
            chapters.put(chapter)
        }
        File(dir, "book.json").writeText(JSONObject().put("format", "abook-book/1").put("title", "Sách thử").put("narrator", "Đức Trí")
            .put("chaptersTotal", 3).put("chapters", chapters).toString())
        out = File(context.getExternalFilesDir(null) ?: context.filesDir, "mp3-export-test").apply { deleteRecursively(); mkdirs() }
    }

    @After
    fun tearDown() {
        Mp3Exports.events = null
        Store.bookDir(id).deleteRecursively()
        out.deleteRecursively()
    }

    @Test
    fun exports_two_finished_chapters_in_the_background_with_the_desktop_tags() {
        val events = Collections.synchronizedList(ArrayList<JSONObject>())
        Mp3Exports.events = { events += it }
        // Sách không có bìa: bìa giao diện tự vẽ (PNG) đi kèm như từ menu.
        val drawn = File(context.cacheDir, "mp3-export-test-cover.png").apply { writeBytes(asset("cover.png")) }
        val run = Mp3Exports.start(context, id, Uri.fromFile(out), drawn)

        val work = WorkManager.getInstance(context)
        val deadline = System.currentTimeMillis() + 60_000
        var info: WorkInfo? = work.getWorkInfoById(UUID.fromString(run)).get()
        while (info?.state?.isFinished != true && System.currentTimeMillis() < deadline) {
            Thread.sleep(200)
            info = work.getWorkInfoById(UUID.fromString(run)).get()
        }
        assertEquals(WorkInfo.State.SUCCEEDED, info?.state)

        val folder = File(out, "Sách thử")
        assertEquals(listOf("01 - Chương 1 Mở đầu.mp3", "02 - Chương 2 · Về nhà.mp3", "Sách thử.m3u8", "cover.png"), folder.list()!!.sorted())
        assertTrue("bìa tự vẽ dọn sau khi xong", !drawn.exists())
        assertArrayEquals(asset("cover.png"), File(folder, "cover.png").readBytes())
        assertEquals("#EXTM3U\n#PLAYLIST:Sách thử\n#EXTINF:0,Chương 1: Mở đầu\n01 - Chương 1 Mở đầu.mp3\n" +
            "#EXTINF:0,Chương 2 · Về nhà\n02 - Chương 2 · Về nhà.mp3\n", File(folder, "Sách thử.m3u8").readText())

        // Chương 1 = ca "vietnamese_drawn_cover" của bộ ví dụ: ID3v2 và ID3v1 như ffmpeg của máy tính ghi.
        val first = File(folder, "01 - Chương 1 Mở đầu.mp3").readBytes()
        val desktop = asset("expected/vietnamese_drawn_cover.mp3")
        val tag = Id3Bytes.v2Without(desktop, "TSSE")
        assertArrayEquals(tag, first.copyOfRange(0, tag.size))
        assertArrayEquals(Id3Bytes.v1(desktop), Id3Bytes.v1(first))

        // Android đọc được tag và bìa (như mọi trình phát khác trên máy).
        MediaMetadataRetriever().apply {
            try {
                setDataSource(File(folder, "02 - Chương 2 · Về nhà.mp3").absolutePath)
                assertEquals("Chương 2 · Về nhà", extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE))
                assertEquals("Sách thử", extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM))
                assertEquals("Đức Trí", extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST))
                assertEquals("2/2", extractMetadata(MediaMetadataRetriever.METADATA_KEY_CD_TRACK_NUMBER))
                assertNotNull("ảnh bìa", embeddedPicture)
                assertArrayEquals(asset("cover.png"), embeddedPicture)
            } finally {
                release()
            }
        }

        // Giao diện nhận tiến độ rồi kết quả: 2 chương xuất, sách có 3 chương (chương chưa xong được nói là không có).
        val last = events.last()
        assertEquals(run, last.getString("run"))
        assertTrue(last.optBoolean("finished"))
        assertEquals(2, last.getInt("files"))
        assertEquals(3, last.getInt("chaptersTotal"))
        assertEquals("mp3-export-test/Sách thử", last.getString("folder"))
        assertTrue(events.any { it.optInt("done") == 1 && it.optInt("total") == 2 })
    }
}
