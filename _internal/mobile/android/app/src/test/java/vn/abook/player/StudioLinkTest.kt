package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Studio của máy tính đã ghép mở trên điện thoại (StudioActivity): chọn máy, đường trang không mang mã, chờ máy ấy trả lời lại. */
class StudioLinkTest {
    private val peers = JSONObject()
        .put("b2", JSONObject().put("name", "Máy phòng khách").put("kind", "computer").put("token", "ma-b2"))
        .put("a1", JSONObject().put("name", "Điện thoại của Lan").put("kind", "phone").put("token", "ma-a1"))
        .put("c3", JSONObject().put("name", "Laptop chưa trả lời").put("token", "ma-c3"))

    @Test
    fun onlyComputersHaveAStudioAndTheMainComputerComesFirst() {
        val computers = StudioLink.computers(true, "NGDtuanh-Lecoo", peers)
        assertEquals(listOf(StudioLink.Computer(StudioLink.MAIN, "NGDtuanh-Lecoo"), StudioLink.Computer("b2", "Máy phòng khách")), computers)
        assertEquals(listOf(StudioLink.Computer("b2", "Máy phòng khách")), StudioLink.computers(false, "", peers))
        assertEquals(emptyList<StudioLink.Computer>(), StudioLink.computers(false, "", JSONObject()))
        assertTrue(StudioLink.known("b2", false, peers))
        assertFalse("điện thoại khác không có Studio", StudioLink.known("a1", true, peers))
        assertFalse("máy tính chính đã bỏ ghép", StudioLink.known(StudioLink.MAIN, false, peers))
    }

    @Test
    fun theDeepLinkOpensTheBookAndNeverCarriesTheCode() {
        assertEquals("/#/studio/b-1_x", StudioLink.bookPath("b-1_x"))
        assertEquals("/#/studio", StudioLink.bookPath(null))
        assertEquals("mã lạ thì về danh sách dự án", "/#/studio", StudioLink.bookPath("../api/app?t=1"))
        assertEquals("/#/studio/b1?tab=work", StudioLink.safePath("/#/studio/b1?tab=work"))
        assertEquals("/#/studio", StudioLink.safePath("https://evil.example/"))
        assertEquals("/#/studio", StudioLink.safePath(null))
        for (path in listOf(StudioLink.bookPath("b1"), StudioLink.bookPath(null))) {
            for (token in listOf("ma-b2", "ma-a1", "abook_device", "token")) assertFalse(path, token in path)
        }
    }

    @Test
    fun comingBackReloadsThePageBeingViewedEvenOverAnotherRoute() {
        val wifi = "https://192.168.1.5:47630"
        val bluetooth = "https://127.0.0.1:41234"
        assertEquals("$wifi/#/studio/b1?tab=work", StudioLink.rebase("$wifi/#/studio/b1?tab=work", wifi, wifi, "/#/studio"))
        assertEquals("$bluetooth/#/studio/b1", StudioLink.rebase("$wifi/#/studio/b1", wifi, bluetooth, "/#/studio"))
        assertEquals("chưa nạp được gì: trang đã xin lúc mở", "$wifi/#/studio/b2", StudioLink.rebase(null, wifi, wifi, "/#/studio/b2"))
        assertEquals("$wifi/#/studio", StudioLink.rebase("https://192.168.1.50:47630/#/x", wifi, wifi, "/#/studio"))
    }

    @Test
    fun differentVersionsAreRefusedButASourceBuildIsNot() {
        assertTrue(StudioLink.mismatched("0.4.50", "0.4.51"))
        assertFalse(StudioLink.mismatched("0.4.51", "0.4.51"))
        assertFalse(StudioLink.mismatched("", "0.4.51"))
        assertFalse(StudioLink.mismatched("dev", "0.4.51"))
        assertEquals("Cập nhật ABook ở hai máy cùng phiên bản", StudioLink.MISMATCH)
    }

    @Test
    fun theWaitingLineNamesTheComputer() {
        assertEquals("Máy NGDtuanh-Lecoo không trả lời - đang chờ nối lại", StudioLink.silentLine("NGDtuanh-Lecoo"))
        assertEquals("Máy phòng khách không trả lời - đang chờ nối lại", StudioLink.silentLine("máy phòng khách"))
    }

    /** Lịch giả: việc hẹn chỉ chạy khi test gọi [run], đồng hồ tiến theo khoảng hẹn. */
    private class FakeClock {
        var now = 0L
        val queue = ArrayDeque<Pair<Long, () -> Unit>>()
        fun schedule(ms: Long, task: () -> Unit) {
            queue.addLast(ms to task)
        }
        fun run(): Boolean {
            val (ms, task) = queue.removeFirstOrNull() ?: return false
            now += ms
            task()
            return true
        }
        fun drain() {
            while (run()) continue
        }
    }

    @Test
    fun askAgainEveryFiveSecondsUntilTheComputerAnswersThenReloadOnce() {
        val clock = FakeClock()
        val answers = ArrayDeque(listOf(false, false, true))
        var asked = 0
        var back = 0
        StudioLink.Watch(reachable = { asked++; answers.removeFirst() }, onBack = { back++ }, schedule = clock::schedule, now = { clock.now }).start()
        clock.drain()
        assertEquals(3, asked)
        assertEquals(1, back)
        assertEquals("nhịp 5 giây như watchUntilBack", 15_000L, clock.now)
    }

    @Test
    fun anErrorWhileAskingCountsAsNotAnsweringAndTheWatchGivesUpAfterHalfAnHour() {
        val clock = FakeClock()
        var back = 0
        val watch = StudioLink.Watch(reachable = { throw java.io.IOException("tắt") }, onBack = { back++ }, schedule = clock::schedule, now = { clock.now }).start()
        clock.drain()
        assertEquals(0, back)
        assertTrue(watch.stopped)
        assertTrue(clock.now in 30 * 60_000L..31 * 60_000L)
    }

    @Test
    fun theComputerSaysWhenThisPhoneMayOnlyListen() {
        assertTrue(StudioLink.listenOnly("""{"version":"0.4.58","remote":true,"listenOnly":true,"machine":"NGD-PC"}"""))
        assertFalse(StudioLink.listenOnly("""{"version":"0.4.58","remote":true,"listenOnly":false}"""))
        assertFalse("máy cũ chưa có cờ này", StudioLink.listenOnly("""{"version":"0.4.50"}"""))
        assertFalse("không đọc được thì nút vẫn mở", StudioLink.listenOnly("không phải json"))
    }

    @Test
    fun aStoppedWatchNeverReloads() {
        val clock = FakeClock()
        var back = 0
        val watch = StudioLink.Watch(reachable = { true }, onBack = { back++ }, schedule = clock::schedule, now = { clock.now }).start()
        watch.stop()
        clock.drain()
        assertEquals(0, back)
    }
}
