package vn.ebookreader.player

import android.content.ComponentName
import android.os.Looper
import androidx.media3.common.MediaItem
import androidx.media3.session.MediaBrowser
import androidx.media3.session.SessionToken
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Android Auto nhìn thấy gì (PlaybackService là MediaLibraryService): trình duyệt media kết nối như xe hơi, duyệt gốc ->
 * cuốn -> chương, chọn cuốn thì nghe tiếp đúng chương, đúng giây đang dở. Chạy trên máy ảo: `gradlew
 * connectedDebugAndroidTest` (máy ảo tắt tiếng - test có phát audio im lặng).
 */
@RunWith(AndroidJUnit4::class)
class AutoBrowseTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val id = "autotest0123456789abcdef"
    private lateinit var browser: MediaBrowser

    private fun <T> onMain(block: () -> T): T {
        var result: Result<T>? = null
        instrumentation.runOnMainSync { result = runCatching(block) }
        return result!!.getOrThrow()
    }

    /** WAV im lặng, 16 kHz mono 16 bit. */
    private fun silence(seconds: Double): ByteArray {
        val samples = (16_000 * seconds).toInt()
        val data = samples * 2
        val out = ByteArrayOutputStream()
        fun int(value: Int) = out.write(byteArrayOf(value.toByte(), (value shr 8).toByte(), (value shr 16).toByte(), (value shr 24).toByte()))
        fun short(value: Int) = out.write(byteArrayOf(value.toByte(), (value shr 8).toByte()))
        out.write("RIFF".toByteArray()); int(36 + data); out.write("WAVEfmt ".toByteArray())
        int(16); short(1); short(1); int(16_000); int(32_000); short(2); short(16)
        out.write("data".toByteArray()); int(data); out.write(ByteArray(data))
        return out.toByteArray()
    }

    @Before
    fun setUp() {
        Store.init(context)
        val dir = Store.bookDir(id)
        File(dir, "chapters").mkdirs()
        val chapters = JSONArray()
        for (chapter in 1..2) {
            File(dir, "chapters/$chapter.wav").writeBytes(silence(3.0))
            chapters.put(JSONObject().put("id", chapter).put("fullTitle", "Chương $chapter").put("available", true)
                .put("file", "chapters/$chapter.wav").put("duration", 3.0))
        }
        Store.writeAtomic(File(dir, "book.json"), JSONObject().put("id", id).put("title", "Sách thử Android Auto")
            .put("narrator", "Người kể").put("chapters", chapters).toString())
        Store.progress(id, 2, 1.5, 3.0) // người nghe đang dở chương 2, giây 1,5
        val token = SessionToken(context, ComponentName(context, PlaybackService::class.java))
        browser = MediaBrowser.Builder(context, token).setApplicationLooper(Looper.getMainLooper()).buildAsync()
            .get(30, TimeUnit.SECONDS)
    }

    @After
    fun tearDown() {
        onMain {
            browser.stop()
            browser.release()
        }
        Store.deleteBook(id)
    }

    @Test
    fun a_car_sees_the_books_and_their_chapters_and_resumes_where_the_listener_left_off() {
        val root = onMain { browser.getLibraryRoot(null) }.get(10, TimeUnit.SECONDS).value!!
        assertEquals(LibraryTree.ROOT, root.mediaId)
        assertTrue(root.mediaMetadata.isBrowsable == true)

        val books = onMain { browser.getChildren(root.mediaId, 0, 50, null) }.get(10, TimeUnit.SECONDS).value!!
        val book = books.first { it.mediaId == "book/$id" }
        assertEquals("Sách thử Android Auto", book.mediaMetadata.title.toString())
        assertEquals("Nghe tiếp: Chương 2", book.mediaMetadata.subtitle.toString())
        assertTrue(book.mediaMetadata.isPlayable == true && book.mediaMetadata.isBrowsable == true)
        assertEquals("bìa đi bằng địa chỉ, không nhúng ảnh", "content", book.mediaMetadata.artworkUri?.scheme)
        val cover = context.contentResolver.openInputStream(book.mediaMetadata.artworkUri!!)!!.use { it.readBytes() }
        assertTrue(cover.size > 1000)

        val chapters = onMain { browser.getChildren(book.mediaId, 0, 50, null) }.get(10, TimeUnit.SECONDS).value!!
        assertEquals(listOf("chapter/$id/1", "chapter/$id/2"), chapters.map { it.mediaId })
        assertEquals("Đang nghe dở", chapters[1].mediaMetadata.subtitle.toString())

        onMain {
            browser.setMediaItem(MediaItem.Builder().setMediaId(book.mediaId).build())
            browser.prepare()
        }
        val deadline = System.currentTimeMillis() + 10_000
        while (onMain { Playback.bookId } != id && System.currentTimeMillis() < deadline) Thread.sleep(100)
        assertEquals("trình phát nhận đúng cuốn xe vừa chọn", id, onMain { Playback.bookId })
        assertEquals("2", onMain { browser.currentMediaItem?.mediaId })
        val position = onMain { browser.currentPosition }
        assertTrue("nghe tiếp từ giây 1,5 (thấy $position ms)", position in 1_000L..2_500L)

        onMain { browser.setMediaItem(MediaItem.Builder().setMediaId("chapter/$id/1").build()) }
        val chosen = System.currentTimeMillis() + 10_000
        while (onMain { browser.currentMediaItem?.mediaId } != "1" && System.currentTimeMillis() < chosen) Thread.sleep(100)
        assertEquals("1", onMain { browser.currentMediaItem?.mediaId })
        assertTrue(onMain { browser.currentPosition } < 1_000L)
    }
}
