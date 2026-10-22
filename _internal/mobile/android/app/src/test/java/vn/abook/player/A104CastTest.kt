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
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Soát a104 (phát ra loa / TV, điện thoại tự phát): chỗ nghe thuộc hồ sơ đã bấm "Phát trên…", hai lệnh sang chương chồng nhau đi
 * tiếp nhau, "Nghe ở đây" chỉ dọn phiên khi thiết bị đã dừng, khung media không nhảy loa khi Tạm dừng, bìa đi cùng chương.
 * Thiết bị giả nằm ngay trong bài thử (không mạng ngoài, không phát tiếng).
 */
class A104CastTest {
    private val cleanups = mutableListOf<() -> Unit>()

    @After
    fun tearDown() {
        cleanups.reversed().forEach { runCatching(it) }
    }

    private class FakeBackend : CastBackend {
        val loads = mutableListOf<CastTrack>()
        @Volatile var stopError: Dlna.Failure? = null
        @Volatile var holdChapter: String? = null
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        @Volatile private var current: CastTrack? = null
        @Volatile private var playing = true

        override fun load(track: CastTrack, seconds: Double): Double {
            if (track.title == holdChapter) {
                holdChapter = null
                entered.countDown()
                release.await(5, TimeUnit.SECONDS)
            }
            synchronized(loads) { loads += track }
            current = track
            playing = true
            return seconds
        }

        override fun play() {
            playing = true
        }

        override fun pause(): Boolean {
            playing = false
            return false
        }

        override fun stop(timeoutMs: Int) {
            stopError?.let { throw it }
        }

        override fun seek(seconds: Double) {}

        override fun status(): CastStatus = CastStatus(if (playing) "PLAYING" else "PAUSED_PLAYBACK", 30.0, 300.0, current?.url.orEmpty())
    }

    private fun command(action: String, vararg extra: Pair<String, Any>) =
        JSONObject().put("action", action).also { json -> extra.forEach { (key, value) -> json.put(key, value) } }

    private fun folder(): File = Files.createTempDirectory("a104").toFile().also { dir -> cleanups += { dir.deleteRecursively() } }

    private fun book(cover: File? = null): DlnaPlayers.Book {
        val dir = folder()
        val chapters = (1..3).map { id -> DlnaPlayers.Chapter(id, "Chương $id", 300.0, File(dir, "$id.mp3").apply { writeBytes(ByteArray(2000) { id.toByte() }) }) }
        return DlnaPlayers.Book("Sách thử", chapters, cover)
    }

    private class Harness(val players: DlnaPlayers, val backends: Map<String, FakeBackend>, val saved: MutableList<Pair<Int, String?>>) {
        var active: String? = "ho-so-a"
    }

    private fun harness(chosen: DlnaPlayers.Book, vararg devices: String): Harness {
        val backends = devices.associateWith { FakeBackend() }
        val saved = mutableListOf<Pair<Int, String?>>()
        lateinit var out: Harness
        val players = DlnaPlayers(
            book = { id -> if (id == "sach") chosen else null },
            save = { _, chapter, _, _, record -> synchronized(saved) { saved += chapter to record } },
            media = Dlna.Media("127.0.0.1"),
            find = { devices.map { it to "127.0.0.1" } },
            read = { location, host -> Dlna.Renderer(location, "TV $location", "tv", host, protocol = "gcast") },
            backend = { renderer -> backends.getValue(renderer.id) },
            record = { out.active },
        ).apply {
            playingPollMs = 100
            idlePollMs = 100
            cleanups += ::close
        }
        out = Harness(players, backends, saved)
        players.scan()
        val deadline = System.currentTimeMillis() + 8000
        while (players.view().length() < devices.size && System.currentTimeMillis() < deadline) Thread.sleep(30)
        assertEquals(devices.size, players.view().length())
        return out
    }

    private fun load(h: Harness, device: String, chapter: Int = 1, vararg extra: Pair<String, Any>) {
        h.players.send(device, command("load", "bookId" to "sach", "chapterId" to chapter, "seconds" to 20.0, *extra))
    }

    @Test
    fun savesGoToTheProfileThatStartedTheCast() {
        val h = harness(book(), "dev")
        load(h, "dev")
        h.active = "ho-so-b" // ai đó đổi hồ sơ trên điện thoại trong lúc TV vẫn phát phiên của A
        h.players.send("dev", command("pause"))
        h.players.send("dev", command("next"))
        synchronized(h.saved) { assertTrue(h.saved.isNotEmpty() && h.saved.all { it.second == "ho-so-a" }) }
        assertEquals(2, synchronized(h.saved) { h.saved.last().first })
    }

    @Test
    fun theProfileNamedByTheHandOffBeatsTheActiveOne() {
        val h = harness(book(), "dev")
        load(h, "dev", 1, "record" to "ho-so-c")
        h.players.send("dev", command("pause"))
        synchronized(h.saved) { assertTrue(h.saved.all { it.second == "ho-so-c" }) }
    }

    @Test
    fun overlappingNextCommandsReachChapterThree() {
        val h = harness(book(), "dev")
        load(h, "dev")
        val backend = h.backends.getValue("dev")
        backend.holdChapter = "Chương 2"
        val first = Thread { h.players.send("dev", command("next")) }.apply { start() }
        assertTrue(backend.entered.await(5, TimeUnit.SECONDS))
        val second = Thread { h.players.send("dev", command("next")) }.apply { start() }
        val deadline = System.currentTimeMillis() + 5000
        while (second.state != Thread.State.WAITING && second.state != Thread.State.TIMED_WAITING && System.currentTimeMillis() < deadline) Thread.sleep(10)
        backend.release.countDown()
        first.join(5000)
        second.join(5000)
        assertEquals(listOf("Chương 1", "Chương 2", "Chương 3"), synchronized(backend.loads) { backend.loads.map { it.title } })
        assertEquals(3, h.players.now()?.chapterId)
    }

    @Test
    fun aDeviceThatWillNotStopKeepsItsSession() {
        val h = harness(book(), "dev")
        load(h, "dev")
        val backend = h.backends.getValue("dev")
        backend.stopError = Dlna.Failure("không trả lời")
        try {
            h.players.send("dev", command("stop"))
            fail("lệnh dừng hỏng phải báo lỗi")
        } catch (error: Dlna.Failure) {
            assertTrue(error.message.orEmpty().contains("không trả lời"))
        }
        assertNotNull("phiên còn đó để thử lại", h.players.now())
        backend.stopError = null
        h.players.send("dev", command("stop"))
        assertNull(h.players.now())
    }

    @Test
    fun pausingTheChosenSpeakerDoesNotMoveTheMediaSessionToAnother() {
        val h = harness(book(), "a", "b")
        load(h, "a")
        load(h, "b") // người nghe vừa chọn B
        assertEquals("TV b", h.players.now()?.device)
        h.players.send("b", command("pause"))
        assertFalse(h.players.now()!!.playing)
        assertEquals("A vẫn đang phát nhưng khung media vẫn điều khiển B", "TV b", h.players.now()?.device)
        load(h, "a") // chọn lại A
        assertEquals("TV a", h.players.now()?.device)
    }

    @Test
    fun theCoverTravelsWithTheChapter() {
        val cover = File(folder(), "cover.jpg").apply { writeBytes(ByteArray(500) { 7 }) }
        val h = harness(book(cover), "dev")
        load(h, "dev")
        h.players.send("dev", command("next"))
        val loads = synchronized(h.backends.getValue("dev").loads) { h.backends.getValue("dev").loads.toList() }
        assertEquals(2, loads.size)
        assertTrue("bìa là địa chỉ ảnh của điện thoại: ${loads[0].art}", loads.all { it.art.startsWith("http://127.0.0.1:") && it.art.endsWith(".jpg") })
        val bare = harness(book(), "dev")
        load(bare, "dev")
        assertEquals("", synchronized(bare.backends.getValue("dev").loads) { bare.backends.getValue("dev").loads[0].art })
    }
}
