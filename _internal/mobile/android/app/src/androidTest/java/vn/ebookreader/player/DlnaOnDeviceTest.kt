package vn.ebookreader.player

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Phát lên loa / TV trên máy Android THẬT (máy ảo), không phải JVM: bộ đọc XML của Android (DocumentBuilder của Harmony),
 * HttpURLConnection của Android, socket trong tiến trình app. Loa giả (FakeRenderer, dùng chung với DlnaTest) chạy ngay
 * trong tiến trình bài thử: tìm -> mô tả -> đưa chương -> loa tải file từ cổng của điện thoại -> tự sang chương sau.
 */
@RunWith(AndroidJUnit4::class)
class DlnaOnDeviceTest {
    private val cleanups = mutableListOf<() -> Unit>()

    @After
    fun tearDown() {
        cleanups.reversed().forEach { runCatching(it) }
    }

    private fun <T> until(seconds: Double = 10.0, check: () -> T?): T {
        val deadline = System.currentTimeMillis() + (seconds * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            check()?.takeIf { it != false }?.let { return it }
            Thread.sleep(50)
        }
        fail("hết giờ chờ")
        throw IllegalStateException()
    }

    @Test
    fun aChapterOnThePhonePlaysOnTheRendererAndMovesOn() {
        val device = FakeRenderer("TV phòng khách", speed = 5.0).start().also { cleanups += it::stop }
        val found = Dlna.describe(device.location, "127.0.0.1")!!
        assertEquals("tv", found.kind)
        val folder = File(InstrumentationRegistry.getInstrumentation().targetContext.cacheDir, "dlna-test").apply { mkdirs() }
        cleanups += { folder.deleteRecursively() }
        val chapters = (1..2).map { id ->
            val file = File(folder, "%05d.mp3".format(id)).apply { writeBytes(ByteArray(40_000 + id) { id.toByte() }) }
            DlnaPlayers.Chapter(id, "Chương $id", 10.0, file)
        }
        val saved = mutableListOf<List<Any>>()
        val players = DlnaPlayers(
            book = { id -> if (id == "sach") DlnaPlayers.Book("Sách thử", chapters) else null },
            save = { id, chapter, seconds, duration -> synchronized(saved) { saved += listOf(id, chapter, Math.round(seconds * 10) / 10.0, duration) } },
            media = Dlna.Media("127.0.0.1"),
            find = { Dlna.search(400, listOf(device.ssdp), multicast = false) },
        ).apply {
            playingPollMs = 150
            idlePollMs = 200
            graceMs = 1000
        }
        cleanups += players::close
        players.scan()
        val id = until { players.view().takeIf { it.length() > 0 }?.getJSONObject(0)?.getString("id") }
        players.send(id, JSONObject().put("action", "load").put("bookId", "sach").put("chapterId", 1).put("seconds", 0.0))
        assertEquals(chapters[0].file.length().toInt(), until { synchronized(device) { device.fetched.firstOrNull() } })
        until(12.0) { players.view().getJSONObject(0).optJSONObject("state")?.takeIf { it.getInt("chapterId") == 2 } }
        assertTrue(synchronized(saved) { saved.contains(listOf("sach", 1, 10.0, 10.0)) })
    }
}
