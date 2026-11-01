package vn.abook.player

import android.os.SystemClock
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Tải sẵn bài đầu chương kế ([NextChapterWarm]) trên máy thật / máy ảo, với danh mục nhạc thật qua mạng: (1) hỏi mốc chương 1 như lúc bắt đầu nghe, chương 2 dựng
 * xong ở hàng dựng trước trong bao lâu (phải trước hai phút cuối của chương 1); (2) [DeviceScenes.peek] không xếp việc dựng: chương ngoài tầm dựng trước vẫn
 * `pending` mãi; (3) bài mốc đầu chương 2 tải mất bao lâu - đó là quãng im ở đầu chương 2 khi KHÔNG tải sẵn, tải sẵn rồi thì bài đã có trên máy. Số in ra logcat
 * thẻ "NextWarmBench". Chạy: `gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=vn.abook.player.NextChapterWarmOnDeviceTest`.
 */
@RunWith(AndroidJUnit4::class)
class NextChapterWarmOnDeviceTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val id = "nextwarm-bench"

    // Chữ tự viết, mỗi chương một không khí, để cảnh của các chương khác nhau.
    private val moods = listOf(
        listOf("Buổi sáng ở làng ven sông yên ả, khói bếp bay lên chậm rãi.", "Bà cụ ngồi vá lưới, thỉnh thoảng ngẩng lên nhìn đàn cò trắng.", "Tiếng trẻ con cười vọng lại từ bến nước."),
        listOf("Tiếng còi báo động xé toang màn đêm.", "Họ chạy thục mạng qua con hẻm tối, tim đập dồn dập.", "Phía sau, ánh đèn pin quét loang loáng trên tường ẩm."),
        listOf("Trong căn phòng nhỏ, cô lặng lẽ đọc lại bức thư cũ.", "Nước mắt rơi xuống, nhoè đi những dòng chữ đã phai màu.", "Ngoài cửa sổ, mưa vẫn rơi không dứt."),
        listOf("Lễ hội mùa xuân rộn ràng khắp phố.", "Người ta nhảy múa, ca hát, tiếng trống vang lên không ngớt.", "Cậu bé cầm chiếc đèn lồng đỏ, cười rạng rỡ."),
        listOf("Con thuyền chòng chành giữa cơn bão lớn.", "Sóng dữ đập vào mạn, nước tràn qua boong.", "Người thuyền trưởng nghiến răng giữ chặt bánh lái."),
        listOf("Chiều muộn, hai người bạn già ngồi uống trà dưới gốc đa.", "Họ kể cho nhau nghe chuyện ngày xưa, giọng chậm và ấm.", "Gió nhẹ thổi qua, lá rơi lác đác."),
    )

    @Before
    fun setUp() {
        Store.init(context)
        MusicCues.mix = MusicMix.load(context) // như MusicBed.init: bộ chọn đọc hằng số trộn
        Store.deleteBook(id)
        val dir = Store.bookDir(id)
        File(dir, "texts").mkdirs()
        val chapters = JSONArray()
        for ((index, lines) in moods.withIndex()) {
            val chapter = index + 1
            // ~40 đoạn mỗi chương (vài phút đọc), các câu của cùng không khí xoay vòng.
            val text = (0 until 40).joinToString("\n\n") { p -> (0 until 3).joinToString(" ") { s -> lines[(p + s) % lines.size] } }
            File(dir, "texts/$chapter.txt").writeText(text)
            chapters.put(JSONObject().put("id", chapter).put("fullTitle", "Chương $chapter").put("state", "text").put("text", "texts/$chapter.txt"))
        }
        Store.writeAtomic(File(dir, "book.json"), JSONObject().put("id", id).put("title", "Sách thử tải sẵn nhạc").put("version", "1")
            .put("stage", "text").put("chapters", chapters).toString())
    }

    @After
    fun tearDown() {
        Store.deleteBook(id)
    }

    private fun peek(chapterId: Int): JSONObject? {
        val done = CountDownLatch(1)
        var answer: JSONObject? = null
        DeviceScenes.peek(context, id, chapterId) { result, _ ->
            answer = result
            done.countDown()
        }
        done.await(30, TimeUnit.SECONDS)
        return answer
    }

    private fun log(line: String) = Log.i("NextWarmBench", line)

    @Test
    fun theNextChapterIsReadyEarlyAndItsFirstTrackIsWarmable() {
        val t0 = SystemClock.elapsedRealtime()
        var first = DeviceScenes.cues(context, id, 1)
        var asks = 1
        while (first.optBoolean("pending")) {
            SystemClock.sleep(200)
            first = DeviceScenes.cues(context, id, 1)
            asks += 1
        }
        val scene1 = SystemClock.elapsedRealtime() - t0
        assertTrue("chương 1 có nhạc: $first", SceneAnchor.cuesOf(first).isNotEmpty())
        log("chương 1 dựng xong sau $scene1 ms ($asks lần hỏi)")

        var next = peek(2)
        while (next?.optBoolean("pending") == true && SystemClock.elapsedRealtime() - t0 < 120_000) {
            SystemClock.sleep(500)
            next = peek(2)
        }
        val ready2 = SystemClock.elapsedRealtime() - t0
        assertNotNull(next)
        assertTrue("chương 2 dựng xong trước hai phút cuối: $next", next!!.optBoolean("pending").not())
        val link = SceneAnchor.cuesOf(next).firstOrNull()?.link
        assertNotNull("chương 2 có nhạc", link)
        log("chương 2 dựng xong (hàng dựng trước) sau $ready2 ms kể từ lúc hỏi chương 1")

        // Chương 6 ngoài tầm dựng trước (1 + 3 chương kế): peek không xếp việc, nên vẫn chưa có sau 20 giây.
        val outside = (0 until 40).map { SystemClock.sleep(500); peek(6) }
        assertTrue("peek không dựng chương ngoài tầm", outside.all { it?.optBoolean("pending") == true })
        log("chương 6 (ngoài tầm dựng trước) vẫn pending sau 20 s peek")

        val catalog = DeviceMusic.catalog(context)
        val had = catalog.use(link!!) != null
        val t1 = SystemClock.elapsedRealtime()
        val file = catalog.use(link) ?: catalog.download(link, null)
        val fetched = SystemClock.elapsedRealtime() - t1
        assertNotNull("tải được bài mốc đầu chương 2", file)
        log("bài mốc đầu chương 2: ${if (had) "đã có trên máy" else "tải ${file!!.length() / 1024} KB mất $fetched ms"} ($link)")
        val t2 = SystemClock.elapsedRealtime()
        assertNotNull(catalog.use(link))
        log("sau khi tải sẵn: lấy bài mất ${SystemClock.elapsedRealtime() - t2} ms")
    }
}
