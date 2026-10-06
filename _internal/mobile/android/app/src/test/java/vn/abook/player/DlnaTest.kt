package vn.abook.player

import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File
import java.net.HttpURLConnection
import java.net.Proxy
import java.net.URL
import java.nio.file.Files

/**
 * Điện thoại tự phát lên loa / TV (Dlna.kt, DlnaPlayers.kt) với loa giả - 01-10, chủ sách không có loa hay TV ("giả lập hay
 * gì đó đi"). Loa giả cư xử như scripts/fake_renderer.py của máy tính: trả lời SSDP, mô tả, SOAP AVTransport; chỉ tua khi
 * đã chạy (701), hết bài về STOPPED vị trí 0; TẢI audio từ cổng của điện thoại khi Play; vị trí chạy nhanh gấp `speed`.
 */
class DlnaTest {
    private val cleanups = mutableListOf<() -> Unit>()

    @After
    fun tearDown() {
        cleanups.reversed().forEach { runCatching(it) }
    }

    private fun renderer(name: String = "Loa phòng khách", speed: Double = 1.0, pause: Boolean = true): FakeRenderer =
        FakeRenderer(name, speed, pause).start().also { cleanups += it::stop }

    private fun book(seconds: Double = 10.0): Pair<DlnaPlayers.Book, MutableList<List<Any>>> {
        val folder = Files.createTempDirectory("dlna").toFile().also { cleanups += { it.deleteRecursively() } }
        val chapters = (1..3).map { id ->
            val file = File(folder, "%05d.mp3".format(id)).apply { writeBytes(ByteArray(50_000 + id) { id.toByte() }) }
            DlnaPlayers.Chapter(id, "Chương $id: Phần $id", seconds, file)
        }
        return DlnaPlayers.Book("Sách thử", chapters) to mutableListOf()
    }

    private fun players(device: FakeRenderer, chosen: DlnaPlayers.Book, saved: MutableList<List<Any>>): DlnaPlayers =
        DlnaPlayers(
            book = { id -> if (id == "sach") chosen else null },
            save = { id, chapter, seconds, duration -> synchronized(saved) { saved += listOf(id, chapter, Math.round(seconds * 10) / 10.0, duration) } },
            media = Dlna.Media("127.0.0.1"),
            find = { Dlna.search(400, listOf(device.ssdp), multicast = false) },
        ).apply {
            playingPollMs = 150
            idlePollMs = 200
            graceMs = 1000
            cleanups += ::close
        }

    private fun <T> until(seconds: Double = 8.0, check: () -> T?): T {
        val deadline = System.currentTimeMillis() + (seconds * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            check()?.takeIf { it != false }?.let { return it }
            Thread.sleep(50)
        }
        fail("hết giờ chờ")
        throw IllegalStateException()
    }

    private fun DlnaPlayers.only(): JSONObject = view().getJSONObject(0)
    private fun JSONObject.now(): JSONObject? = optJSONObject("state")

    private fun DlnaPlayers.found(): String {
        scan()
        return until { view().takeIf { it.length() > 0 }?.getJSONObject(0)?.getString("id") }
    }

    private fun command(action: String, vararg extra: Pair<String, Any>) =
        JSONObject().put("action", action).also { json -> extra.forEach { (key, value) -> json.put(key, value) } }

    @Test
    fun aRendererAnswersTheSearchAndDescribesItself() {
        val device = renderer()
        assertEquals(listOf(device.location to "127.0.0.1"), Dlna.search(400, listOf(device.ssdp), multicast = false))
        val found = Dlna.describe(device.location, "127.0.0.1")!!
        assertEquals("Loa phòng khách", found.name)
        assertEquals("speaker", found.kind)
        assertTrue(found.avUrl.endsWith("/AVTransport/control"))
        assertEquals(12, found.id.length)
        assertEquals("tv", Dlna.describe(renderer("[TV] Samsung Q60 Series (55)").location, "127.0.0.1")!!.kind)
    }

    @Test
    fun aDescriptionCountsOnlyAtTheAddressThatAnswered() {
        val device = renderer()
        assertNull(Dlna.describe(device.location, "127.0.0.2"))
        val original = device.description
        device.description = { original().replace("<device>", "<URLBase>http://10.9.9.9/</URLBase><device>") }
        assertNull("địa chỉ điều khiển trỏ sang máy khác", Dlna.describe(device.location, "127.0.0.1"))
        device.description = { "<?xml version=\"1.0\"?><!DOCTYPE r [<!ENTITY a \"aaaa\">]><root>&a;</root>" }
        try {
            Dlna.describe(device.location, "127.0.0.1")
            fail("DOCTYPE phải bị từ chối")
        } catch (_: Dlna.Failure) {
        }
    }

    @Test
    fun onlyAnswersFromRenderersCount() {
        val answer = "HTTP/1.1 200 OK\r\nST: urn:schemas-upnp-org:device:MediaRenderer:1\r\nLOCATION: http://192.168.0.9:49152/d.xml\r\n\r\n"
        assertEquals("http://192.168.0.9:49152/d.xml", Dlna.location(answer.toByteArray()))
        assertEquals("", Dlna.location(answer.replace("MediaRenderer", "InternetGatewayDevice").toByteArray()))
        assertEquals("", Dlna.location("NOTIFY * HTTP/1.1\r\n\r\n".toByteArray()))
        assertEquals("1:02:05", Dlna.clock(3725.4))
        assertEquals(7.5, Dlna.secondsOf("0:00:07.500"), 1e-9)
        assertEquals(7.25, Dlna.secondsOf("0:00:07.1/4"), 1e-9)
        assertEquals(0.0, Dlna.secondsOf("NOT_IMPLEMENTED"), 1e-9)
    }

    @Test
    fun theMediaPortServesOnlyWhatWasShared() {
        val media = Dlna.Media("127.0.0.1").also { cleanups += it::close }
        val file = Files.createTempFile("chuong", ".mp3").toFile().apply { writeBytes(ByteArray(1024) { (it % 256).toByte() }) }
        cleanups += { file.delete() }
        val url = media.share(file, "127.0.0.1")
        assertTrue(url.startsWith("http://127.0.0.1:") && url.endsWith(".mp3"))
        val ranged = URL(url).openConnection(Proxy.NO_PROXY) as HttpURLConnection
        ranged.setRequestProperty("Range", "bytes=10-19")
        assertEquals(206, ranged.responseCode)
        assertEquals((10 until 20).map { it.toByte() }, ranged.inputStream.use { it.readBytes() }.toList())
        assertEquals("bytes 10-19/1024", ranged.getHeaderField("Content-Range"))
        assertTrue(ranged.getHeaderField("contentFeatures.dlna.org").contains("DLNA.ORG_OP=01"))
        val whole = URL(url).openConnection(Proxy.NO_PROXY) as HttpURLConnection
        assertEquals(file.readBytes().toList(), whole.inputStream.use { it.readBytes() }.toList())
        val wrong = URL(url.substringBeforeLast('/') + "/" + "0".repeat(32) + ".mp3").openConnection(Proxy.NO_PROXY) as HttpURLConnection
        assertEquals(404, wrong.responseCode)
        assertFalse("mỗi lần đưa một mã mới", media.share(file, "127.0.0.1") == url)
    }

    @Test
    fun castingPlaysTheChapterFromThePhoneAndMovesOnByItself() {
        val device = renderer(speed = 5.0)
        val (chosen, saved) = book()
        val players = players(device, chosen, saved)
        val id = players.found()
        assertNull(players.only().now())
        players.send(id, command("load", "bookId" to "sach", "chapterId" to 1, "seconds" to 0.0))
        assertEquals(listOf("SetAVTransportURI", "Play"), device.calls("SetAVTransportURI").let { _ -> synchronized(device) { device.actions.map { it.first }.take(2) } })
        val first = device.calls("SetAVTransportURI").first()
        assertTrue(first.getValue("CurrentURI").startsWith("http://127.0.0.1:"))
        assertTrue(first.getValue("CurrentURIMetaData").contains("Chương 1: Phần 1"))
        assertTrue(first.getValue("CurrentURIMetaData").contains("Sách thử"))
        assertEquals("thiết bị tải đúng file chương từ điện thoại", chosen.chapters[0].file.length().toInt(),
            until { synchronized(device) { device.fetched.firstOrNull() } })
        until { players.only().now()?.takeIf { it.getBoolean("playing") && !it.getBoolean("buffering") } }
        // Hết chương 1 (10 giây, loa chạy nhanh gấp 5): tự sang chương 2, chương 1 ghi là đã nghe hết.
        until(10.0) { players.only().now()?.takeIf { it.getInt("chapterId") == 2 } }
        assertTrue(synchronized(saved) { saved.contains(listOf("sach", 1, 10.0, 10.0)) })
        assertFalse(device.uri() == first.getValue("CurrentURI"))
        players.send(id, command("jump", "chapterId" to 3, "seconds" to 0.0))
        until(10.0) { players.only().now() == null }
        assertTrue(synchronized(saved) { saved.contains(listOf("sach", 3, 10.0, 10.0)) })
    }

    @Test
    fun resumingSeeksOnceTheRendererPlaysAndClosingStopsIt() {
        val device = renderer()
        val (chosen, saved) = book(30.0)
        val players = players(device, chosen, saved)
        val id = players.found()
        players.send(id, command("load", "bookId" to "sach", "chapterId" to 2, "seconds" to 6.0))
        val names = synchronized(device) { device.actions.map { it.first } }
        assertTrue(names.indexOf("Seek") > names.indexOf("Play"))
        assertEquals("0:00:06", device.calls("Seek").first()["Target"])
        assertTrue(device.position() >= 6)
        players.close()
        assertEquals("STOPPED", device.state())
        val last = synchronized(saved) { saved.last() }
        assertEquals(listOf("sach", 2), last.take(2))
        assertTrue((last[2] as Double) >= 6)
    }

    @Test
    fun pausePlaySkipRateAndChapters() {
        val device = renderer()
        val (chosen, saved) = book(30.0)
        val players = players(device, chosen, saved)
        val id = players.found()
        players.send(id, command("load", "bookId" to "sach", "chapterId" to 1, "seconds" to 0.0))
        until { players.only().now()?.takeIf { it.getBoolean("playing") && !it.getBoolean("buffering") } }
        players.send(id, command("pause"))
        assertEquals("PAUSED_PLAYBACK", device.state())
        players.send(id, command("toggle"))
        assertEquals("PLAYING", device.state())
        val before = device.position()
        players.send(id, command("skip", "seconds" to 15.0))
        assertTrue(device.position() - before in 14.0..17.0)
        players.send(id, command("skip", "seconds" to 60.0))
        assertEquals(2, device.calls("SetAVTransportURI").size)
        assertEquals(2, players.only().now()!!.getInt("chapterId"))
        players.send(id, command("previous"))
        assertEquals(1, players.only().now()!!.getInt("chapterId"))
        players.send(id, command("rate", "rate" to 1.0))
        try {
            players.send(id, command("rate", "rate" to 1.5))
            fail("tốc độ khác 1x")
        } catch (error: Dlna.Failure) {
            assertEquals("Loa phòng khách: loa, TV chỉ phát ở tốc độ 1x", error.message)
        }
    }

    @Test
    fun aRendererWithoutPauseStopsAndComesBackToTheSamePlace() {
        val device = renderer("TV phòng ngủ", pause = false)
        val (chosen, saved) = book(30.0)
        val players = players(device, chosen, saved)
        val id = players.found()
        assertEquals("tv", players.only().getString("kind"))
        players.send(id, command("load", "bookId" to "sach", "chapterId" to 1, "seconds" to 0.0))
        until { players.only().now()?.takeIf { it.getDouble("position") >= 1.5 } }
        players.send(id, command("pause"))
        assertTrue(device.calls("Stop").isNotEmpty())
        assertEquals("STOPPED", device.state())
        Thread.sleep(600) // vài lượt hỏi thấy STOPPED: là người dùng dừng, không phải hết chương
        val now = players.only().now()!!
        assertEquals(1, now.getInt("chapterId"))
        assertFalse(now.getBoolean("playing"))
        players.send(id, command("play"))
        assertEquals(2, device.calls("SetAVTransportURI").size)
        assertTrue(Dlna.secondsOf(device.calls("Seek").last()["Target"]) >= 1)
    }

    @Test
    fun theStopButtonOfTheNotificationEndsTheSessionAtTheRightPlace() {
        val device = renderer()
        val (chosen, saved) = book(30.0)
        val players = players(device, chosen, saved)
        val id = players.found()
        players.send(id, command("load", "bookId" to "sach", "chapterId" to 1, "seconds" to 0.0))
        until { players.only().now()?.takeIf { it.getBoolean("playing") && it.getDouble("position") >= 1.0 } }
        assertEquals(listOf(id to true), players.playing())
        players.end(id)
        assertEquals("STOPPED", device.state())
        assertNull(players.only().now())
        assertTrue(players.playing().isEmpty() && players.active().isEmpty())
        val last = synchronized(saved) { saved.last() }
        assertEquals(listOf("sach", 1), last.take(2))
        assertTrue((last[2] as Double) >= 1.0)
    }

    @Test
    fun anotherAppTakingTheRendererEndsTheSession() {
        val device = renderer()
        val (chosen, saved) = book(30.0)
        val players = players(device, chosen, saved)
        val id = players.found()
        players.send(id, command("load", "bookId" to "sach", "chapterId" to 1, "seconds" to 0.0))
        until { players.only().now()?.takeIf { it.getBoolean("playing") } }
        device.takeover("http://192.168.0.5:8200/MediaItems/22.mp3")
        until { players.only().now() == null }
        try {
            players.send(id, command("pause"))
            fail("phiên đã hết")
        } catch (_: Dlna.Failure) {
        }
        assertNotNull(players.view())
    }

    // ---- hẹn giờ tắt (như cast.py của máy tính: điện thoại giữ phiên phát nên điện thoại đếm) ----------------------------

    private fun sleepPausesAndKeepsThePlace(pause: Boolean) {
        val device = renderer(pause = pause)
        val (chosen, saved) = book(30.0)
        val players = players(device, chosen, saved)
        val id = players.found()
        players.send(id, command("load", "bookId" to "sach", "chapterId" to 1, "seconds" to 0.0))
        until { players.only().now()?.takeIf { it.getBoolean("playing") && !it.getBoolean("buffering") } }
        players.send(id, command("sleep", "minutes" to 0.04)) // 2,4 giây
        val sleep = players.only().getJSONObject("sleep")
        assertEquals("minutes", sleep.getString("kind"))
        assertTrue(sleep.getBoolean("counting") && sleep.getDouble("left") in 2.0..2.4)
        // Dừng thì đồng hồ dừng theo, phát lại thì chạy tiếp.
        players.send(id, command("pause"))
        val frozen = players.only().getJSONObject("sleep")
        assertFalse(frozen.getBoolean("counting"))
        Thread.sleep(500)
        assertEquals(frozen.getDouble("left"), players.only().getJSONObject("sleep").getDouble("left"), 0.0)
        players.send(id, command("play"))
        assertTrue(players.only().getJSONObject("sleep").getBoolean("counting"))

        until(6.0) { players.only().takeIf { it.isNull("sleep") && !it.now()!!.getBoolean("playing") } }
        assertEquals(if (pause) "PAUSED_PLAYBACK" else "STOPPED", device.state())
        val stopped = players.only().now()!!
        assertEquals(1, stopped.getInt("chapterId"))
        assertTrue(stopped.getDouble("position") >= 1.5)
        val last = synchronized(saved) { saved.last() }
        assertEquals(listOf("sach", 1), last.take(2))
        assertTrue((last[2] as Double) >= 1.5)
        Thread.sleep(500) // vài lượt hỏi sau: vẫn dừng ở đó, không phải hết chương
        assertFalse(players.only().now()!!.getBoolean("playing"))
        players.send(id, command("play"))
        until { players.only().now()?.takeIf { it.getBoolean("playing") } }
        assertTrue("nghe tiếp đúng chỗ hẹn giờ đã dừng", device.position() >= 1.5)
    }

    @Test
    fun aSleepTimerPausesTheRendererAndKeepsThePlace() = sleepPausesAndKeepsThePlace(pause = true)

    @Test
    fun aSleepTimerStopsARendererWithoutPauseAndComesBackToTheSamePlace() = sleepPausesAndKeepsThePlace(pause = false)

    @Test
    fun aSleepTimerAtTheEndOfTheChapterWaitsAtTheNextOne() {
        val device = renderer(speed = 5.0)
        val (chosen, saved) = book()
        val players = players(device, chosen, saved)
        val id = players.found()
        players.send(id, command("load", "bookId" to "sach", "chapterId" to 1, "seconds" to 0.0))
        players.send(id, command("sleep", "endOfChapter" to true))
        assertEquals("chapter", players.only().getJSONObject("sleep").getString("kind"))
        val parked = until(10.0) { players.only().takeIf { it.now()?.getInt("chapterId") == 2 } }
        assertTrue(parked.isNull("sleep"))
        assertFalse(parked.now()!!.getBoolean("playing"))
        assertEquals(0.0, parked.now()!!.getDouble("position"), 0.0)
        assertEquals("Chương 2: Phần 2", parked.now()!!.getString("chapterTitle"))
        assertTrue(synchronized(saved) { saved.contains(listOf("sach", 1, 10.0, 10.0)) && saved.last() == listOf("sach", 2, 0.0, 10.0) })
        Thread.sleep(600) // thiết bị nằm yên ở STOPPED: không tự đưa chương 2
        assertEquals(1, device.calls("SetAVTransportURI").size)
        players.send(id, command("play"))
        assertEquals(2, device.calls("SetAVTransportURI").size)
        until { players.only().now()?.takeIf { it.getBoolean("playing") && it.getInt("chapterId") == 2 } }
    }

    @Test
    fun aSleepTimerIsCancelledAndNotCarriedToTheNextCast() {
        val device = renderer()
        val (chosen, saved) = book(30.0)
        val players = players(device, chosen, saved)
        val id = players.found()
        try {
            players.send(id, command("sleep", "minutes" to 15))
            fail("chưa phát gì")
        } catch (_: Dlna.Failure) {
        }
        players.send(id, command("sleep", "minutes" to 0)) // tắt khi chưa có gì: không lỗi
        players.send(id, command("load", "bookId" to "sach", "chapterId" to 1, "seconds" to 0.0))
        players.send(id, command("sleep", "minutes" to 15))
        assertEquals(15.0, players.only().getJSONObject("sleep").getDouble("minutes"), 0.0)
        players.send(id, command("next")) // sang chương: vẫn đếm
        assertEquals(15.0, players.only().getJSONObject("sleep").getDouble("minutes"), 0.0)
        players.send(id, command("sleep", "minutes" to 0))
        assertTrue(players.only().isNull("sleep"))
        players.send(id, command("sleep", "minutes" to 15))
        players.send(id, command("load", "bookId" to "sach", "chapterId" to 1, "seconds" to 0.0))
        assertTrue("một lần “Phát trên…” mới bắt đầu không hẹn giờ", players.only().isNull("sleep"))
    }

    @Test
    fun theLockScreenSeesTheSessionThatIsPlaying() {
        val device = renderer()
        val (chosen, saved) = book(30.0)
        val players = players(device, chosen, saved)
        val id = players.found()
        assertNull(players.now())
        players.send(id, command("load", "bookId" to "sach", "chapterId" to 2, "seconds" to 0.0))
        val now = until { players.now()?.takeIf { it.playing && !it.buffering } }
        assertEquals(id, now.id)
        assertEquals("Loa phòng khách", now.device)
        assertEquals("Sách thử", now.bookTitle)
        assertEquals(2, now.chapterId)
        assertEquals(listOf(1, 2, 3), now.chapters.map { it.id })
        players.send(id, command("pause"))
        assertFalse(players.now()!!.playing)
        players.end(id)
        assertNull(players.now())
    }
}
