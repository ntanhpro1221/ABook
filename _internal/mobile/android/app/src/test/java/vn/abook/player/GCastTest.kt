package vn.abook.player

import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertArrayEquals
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
 * Điện thoại tự phát lên Chromecast / Google TV / loa Nest (GCast.kt, DlnaPlayers.kt) với thiết bị giả
 * sharedTest/FakeCastReceiver.kt - 02-10, như bài thử của máy tính (tests/test_gcast.py). Thiết bị giả nghe CASTV2 qua TLS
 * thật trên 127.0.0.1, trả lời mDNS ở một cổng UDP riêng, TẢI file chương qua HTTP (không bao giờ giải mã hay phát audio) và
 * cho vị trí chạy theo đồng hồ. Các dãy byte cố định bên dưới do chính bộ mã hoá Python của máy tính (abook/webui/gcast.py)
 * sinh ra: hai bên phải khớp từng byte.
 */
class GCastTest {
    private val cleanups = mutableListOf<() -> Unit>()

    @After
    fun tearDown() {
        cleanups.reversed().forEach { runCatching(it) }
    }

    private val fast = GCast.Timing(reply = 4000, launch = 4000, load = 4000, heartbeat = 300, status = 300, dead = 1200, reconnect = 300, tick = 50)

    private fun device(name: String = "Loa Nest thử", speed: Double = 1.0, duration: Double = 10.0, video: Boolean = false): FakeCastReceiver =
        FakeCastReceiver(name, speed, duration, video).start().also { cleanups += it::stop }

    private fun book(): Pair<DlnaPlayers.Book, MutableList<List<Any>>> {
        val folder = Files.createTempDirectory("gcast").toFile().also { cleanups += { it.deleteRecursively() } }
        val chapters = (1..3).map { id ->
            val file = File(folder, "%05d.mp3".format(id)).apply { writeBytes(ByteArray(50_000 + id) { id.toByte() }) }
            DlnaPlayers.Chapter(id, "Chương $id: Phần $id", 10.0, file)
        }
        return DlnaPlayers.Book("Sách thử", chapters) to mutableListOf()
    }

    private fun players(device: FakeCastReceiver, chosen: DlnaPlayers.Book, saved: MutableList<List<Any>>, lostAfter: Long = 1500): DlnaPlayers =
        DlnaPlayers(
            book = { id -> if (id == "sach") chosen else null },
            save = { id, chapter, seconds, duration -> synchronized(saved) { saved += listOf(id, chapter, Math.round(seconds * 10) / 10.0, duration) } },
            media = Dlna.Media("127.0.0.1"),
            find = { emptyList() },
            findGoogle = { GCast.discover(400, listOf(device.mdns), multicast = false) },
            backend = { GoogleCast(it, fast) },
        ).apply {
            playingPollMs = 150
            idlePollMs = 200
            graceMs = 1000
            lostAfterMs = lostAfter
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
    private fun DlnaPlayers.playingNow() = until { only().now()?.takeIf { it.getBoolean("playing") && !it.getBoolean("buffering") } }

    private fun DlnaPlayers.found(): String {
        scan()
        return until { view().takeIf { it.length() > 0 }?.getJSONObject(0)?.getString("id") }
    }

    private fun command(action: String, vararg extra: Pair<String, Any>) =
        JSONObject().put("action", action).also { json -> extra.forEach { (key, value) -> json.put(key, value) } }

    private fun load(chapter: Int, seconds: Double = 0.0) = command("load", "bookId" to "sach", "chapterId" to chapter, "seconds" to seconds)

    private fun hex(text: String): ByteArray = ByteArray(text.length / 2) { text.substring(it * 2, it * 2 + 2).toInt(16).toByte() }

    // ---- khung tin: so từng byte với bộ mã hoá Python --------------------------------------------------------------------

    private val connect = "0000005b0800120b73656e6465722d303030311a0a72656365697665722d30222875726e3a782d636173743a636f6d2e676f6f676c652e" +
        "636173742e74702e636f6e6e656374696f6e280032127b2274797065223a22434f4e4e454354227d"
    private val longMessage = "0000014d0800120f73656e6465722d61623132636433341a057765622d31222075726e3a782d636173743a636f6d2e676f6f676c652e" +
        "636173742e6d656469612800328c027b2274797065223a224c4f4144222c226d65646961223a7b22636f6e74656e744964223a22687474703a2f2f3132372e" +
        "302e302e313a312f632f782e6d7033222c226d65746164617461223a7b227469746c65223a224368c6b0c6a16e6720313a204de1bb9f20c491e1baa77522" +
        "2c22616c62756d4e616d65223a2253c3a16368207468e1bbad227d7d2c22706164223a22" + "78".repeat(120) + "227d"
    private val longPayload = "{\"type\":\"LOAD\",\"media\":{\"contentId\":\"http://127.0.0.1:1/c/x.mp3\",\"metadata\":{\"title\":\"Chương 1: Mở đầu\"," +
        "\"albumName\":\"Sách thử\"}},\"pad\":\"" + "x".repeat(120) + "\"}"

    @Test
    fun theMessagesAreTheSameBytesTheComputerWrites() {
        val short = GCast.frame(GCast.encode("sender-0001", "receiver-0", GCast.NS_CONNECTION, "{\"type\":\"CONNECT\"}"))
        assertArrayEquals(hex(connect), short)
        assertArrayEquals(hex(connect), FakeCastReceiver.pack("sender-0001", "receiver-0", GCast.NS_CONNECTION, "{\"type\":\"CONNECT\"}"))
        // Chuỗi dài hơn 127 byte (độ dài hai byte varint) và có chữ có dấu (UTF-8 nhiều byte).
        val long = GCast.frame(GCast.encode("sender-ab12cd34", "web-1", GCast.NS_MEDIA, longPayload))
        assertArrayEquals(hex(longMessage), long)
        assertArrayEquals(hex(longMessage), FakeCastReceiver.pack("sender-ab12cd34", "web-1", GCast.NS_MEDIA, longPayload))
        val decoded = GCast.decode(long.copyOfRange(4, long.size))
        assertEquals(GCast.Message("sender-ab12cd34", "web-1", GCast.NS_MEDIA, longPayload), decoded)
        assertEquals(listOf("sender-0001", "receiver-0", GCast.NS_CONNECTION, "{\"type\":\"CONNECT\"}"), FakeCastReceiver.unpack(short.copyOfRange(4, short.size)))
    }

    @Test
    fun theFramerAssemblesTheStreamAndRefusesOversizedMessages() {
        val stream = hex(connect) + hex(connect)
        val framer = GCast.Framer()
        val frames = stream.flatMap { framer.feed(byteArrayOf(it)) } // từng byte một
        assertEquals(2, frames.size)
        assertArrayEquals(hex(connect).copyOfRange(4, hex(connect).size), frames[0])
        assertEquals(2, GCast.Framer().feed(stream).size) // hai tin trong một lần đọc
        assertTrue(GCast.Framer().feed(hex(connect).copyOfRange(0, 30)).isEmpty()) // nửa tin: chưa có gì
        assertTrue("đúng trần 64 KiB vẫn nhận (chờ nốt phần thân)", GCast.Framer().feed(byteArrayOf(0, 1, 0, 0)).isEmpty())
        try {
            GCast.Framer().feed(byteArrayOf(0, 1, 0, 1))
            fail("quá 64 KiB là thiết bị lạ")
        } catch (_: Dlna.Failure) {
        }
        try {
            GCast.Framer().feed(byteArrayOf(0x7F, 0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte()))
            fail("độ dài khổng lồ")
        } catch (_: Dlna.Failure) {
        }
        // CastMessage lạ: payload nhị phân (payload_type 1) thành rỗng, trường lạ (fixed32) bị bỏ qua, thân cụt bị từ chối.
        val binary = byteArrayOf(0x08, 0x00, 0x12, 0x01, 'a'.code.toByte(), 0x28, 0x01, 0x32, 0x02, 'x'.code.toByte(), 'y'.code.toByte())
        assertEquals(GCast.Message("a", "", "", ""), GCast.decode(binary))
        val unknown = byteArrayOf(0x45, 1, 2, 3, 4, 0x12, 0x01, 'b'.code.toByte())
        assertEquals("b", GCast.decode(unknown).source)
        try {
            GCast.decode(byteArrayOf(0x12, 0x09, 'a'.code.toByte()))
            fail("chuỗi dài hơn thân")
        } catch (_: Dlna.Failure) {
        }
    }

    // ---- mDNS: truy vấn và đọc trả lời có nén tên (do thiết bị giả của máy tính sinh ra) ----------------------------------

    private val query = "0000000000010000000000000b5f676f6f676c6563617374045f746370056c6f63616c00000c8001"
    private val speakerAnswer = "0000840000010001000000030b5f676f6f676c6563617374045f746370056c6f63616c00000c0001c00c000c00010000000a0024214c6f61" +
        "2d4e6573742d70682d6e672d6b682d63682d303132333435363738396162c00cc034002100010000000a001500000000e7850c303132333435363738396162" +
        "c01dc034001000010000119400b62369643d30313233343536373839616263646566303132333435363738396162636465662363643d3031323334353637383" +
        "94142434445463031323334353637383941424344454603726d3d0576653d3035136d643d476f6f676c65204e657374204d696e691269633d2f7365747570" +
        "2f69636f6e2e706e6719666e3d4c6f61204e657374207068c3b26e67206b68c3a163680463613d340473743d300f62733d464138464341303030303030046e" +
        "663d310372733dc06a000100010000000a00047f000001"
    private val televisionElsewhere = speakerAnswer.replace("63613d34", "63613d35").replace("7f000001", "0a090909")
    private val speakerPort = 59269

    @Test
    fun theQueryAsksForCastDevicesAndWantsTheAnswerSentBack() {
        assertArrayEquals(hex(query), GCast.query())
    }

    @Test
    fun anAnswerWithCompressedNamesBecomesADevice() {
        val found = GCast.parse(hex(speakerAnswer), "127.0.0.1").single()
        assertEquals("127.0.0.1", found.host)
        assertEquals(speakerPort, found.port)
        assertEquals("Loa-Nest-ph-ng-kh-ch-0123456789ab._googlecast._tcp.local", found.instance)
        assertEquals("Loa Nest phòng khách", found.field("fn"))
        assertEquals("Google Nest Mini", found.field("md"))
        assertEquals("4", found.field("ca"))
        val renderer = GCast.describe(found)!!
        assertEquals(Dlna.Renderer("b1775a785f09", "Loa Nest phòng khách", "speaker", "127.0.0.1", protocol = "gcast", port = speakerPort), renderer)
        assertEquals("tv", GCast.describe(GCast.parse(hex(televisionElsewhere), "10.9.9.9").single())!!.kind)
        // Thiết bị giả của bài thử dựng cùng từng byte với bộ dựng của máy tính.
        val fake = FakeCastReceiver("Loa Nest phòng khách", model = "Google Nest Mini").apply { deviceId = "0123456789abcdef0123456789abcdef" }
        assertArrayEquals(hex(speakerAnswer), fake.mdnsResponse(servicePort = speakerPort))
        val television = FakeCastReceiver("Loa Nest phòng khách", video = true, model = "Google Nest Mini")
            .apply { deviceId = "0123456789abcdef0123456789abcdef"; advertisedHost = "10.9.9.9" }
        assertArrayEquals(hex(televisionElsewhere), television.mdnsResponse(servicePort = speakerPort))
    }

    @Test
    fun anAnswerThatPointsAtAnotherMachineOrIsBrokenIsIgnored() {
        assertTrue("A trỏ sang 10.9.9.9 mà gói tới từ 127.0.0.1", GCast.parse(hex(televisionElsewhere), "127.0.0.1").isEmpty())
        assertTrue("câu hỏi, không phải trả lời", GCast.parse(hex(query), "127.0.0.1").isEmpty())
        assertTrue(GCast.parse(hex(speakerAnswer).copyOfRange(0, 100), "127.0.0.1").isEmpty())
        assertTrue(GCast.parse(ByteArray(5), "127.0.0.1").isEmpty())
        assertTrue(GCast.parse(ByteArray(200) { (it * 37).toByte() }, "127.0.0.1").isEmpty())
        val forward = hex(speakerAnswer)
        forward[40] = 0xC0.toByte() // tên của bản ghi đầu: con trỏ nén chỉ tới phía sau - không được vòng
        forward[41] = 0xFF.toByte()
        assertTrue(GCast.parse(forward, "127.0.0.1").isEmpty())
        assertNull("địa chỉ ngoài nhà", GCast.describe(GCast.Found("8.8.8.8", 8009, "x._googlecast._tcp.local", emptyList())))
    }

    @Test
    fun discoveryAsksTheTargetAndFindsTheDevice() {
        val speaker = device("Loa phòng khách")
        val found = GCast.discover(400, listOf(speaker.mdns), multicast = false).single()
        assertEquals("Loa phòng khách", found.name)
        assertEquals("speaker", found.kind)
        assertEquals("gcast", found.protocol)
        assertEquals(speaker.port, found.port)
        assertEquals(12, found.id.length)
        assertEquals("tv", GCast.discover(400, listOf(device("TV phòng ngủ", video = true).mdns), multicast = false).single().kind)
        speaker.advertisedHost = "10.9.9.9"
        assertTrue("A trỏ chỗ khác", GCast.discover(400, listOf(speaker.mdns), multicast = false).isEmpty())
        speaker.advertisedHost = "127.0.0.1"
        speaker.sleep()
        assertTrue("thiết bị tắt nguồn im lặng", GCast.discover(400, listOf(speaker.mdns), multicast = false).isEmpty())
    }

    @Test
    fun theMediaPortAllowsTheWebReceiverToFetch() {
        val media = Dlna.Media("127.0.0.1").also { cleanups += it::close }
        val file = Files.createTempFile("chuong", ".mp3").toFile().apply { writeBytes(ByteArray(1024) { it.toByte() }) }
        cleanups += { file.delete() }
        val url = media.share(file, "127.0.0.1")
        for (range in listOf(null, "bytes=0-")) {
            val connection = URL(url).openConnection(Proxy.NO_PROXY) as HttpURLConnection
            range?.let { connection.setRequestProperty("Range", it) }
            connection.setRequestProperty("Origin", "https://www.gstatic.com")
            assertEquals(if (range == null) 200 else 206, connection.responseCode)
            assertEquals("*", connection.getHeaderField("Access-Control-Allow-Origin"))
            assertEquals(1024, connection.inputStream.use { it.readBytes() }.size)
        }
    }

    // ---- phát: mở ứng dụng, LOAD, sang chương, tạm dừng, tua, bị chiếm, tắt nguồn, dừng -----------------------------------------

    @Test
    fun castingOpensThePlayerLoadsTheChapterFromThePhoneAndMovesOnByItself() {
        val speaker = device(speed = 5.0)
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved)
        val id = players.found()
        assertEquals("gcast", players.only().getString("protocol"))
        assertNull(players.only().now())
        players.send(id, load(1))
        val names = speaker.names()
        assertEquals(listOf("connection.CONNECT", "receiver.GET_STATUS", "receiver.LAUNCH"), names.take(3))
        assertEquals("connection.CONNECT", names[names.indexOf("receiver.LAUNCH") + 1])
        assertEquals("media.LOAD", names[names.indexOf("receiver.LAUNCH") + 2])
        val first = speaker.calls("media.LOAD").single()
        val media = first.getJSONObject("media")
        assertTrue(media.getString("contentId").startsWith("http://127.0.0.1:"))
        assertEquals("audio/mpeg", media.getString("contentType"))
        assertEquals("BUFFERED", media.getString("streamType"))
        assertEquals(3, media.getJSONObject("metadata").getInt("metadataType"))
        assertEquals("Chương 1: Phần 1", media.getJSONObject("metadata").getString("title"))
        assertEquals("Sách thử", media.getJSONObject("metadata").getString("albumName"))
        assertTrue(first.getBoolean("autoplay"))
        assertEquals(0.0, first.getDouble("currentTime"), 1e-9)
        val fetch = until { synchronized(speaker) { speaker.fetches.firstOrNull() } }
        assertTrue(fetch.error, fetch.error.isEmpty())
        assertEquals("thiết bị tải đúng file chương từ điện thoại", chosen.chapters[0].file.length().toInt(), fetch.bytes)
        assertTrue(fetch.status == 200 || fetch.status == 206)
        assertEquals("audio/mpeg", fetch.type)
        assertEquals("*", fetch.cors)
        players.playingNow()
        // Hết chương 1 (10 giây, thiết bị chạy nhanh gấp 5): thiết bị báo IDLE / FINISHED, điện thoại tự sang chương 2.
        until(10.0) { players.only().now()?.takeIf { it.getInt("chapterId") == 2 } }
        assertTrue(synchronized(saved) { saved.contains(listOf("sach", 1, 10.0, 10.0)) })
        assertEquals(2, speaker.calls("media.LOAD").size)
        assertNotEquals(first.getJSONObject("media").getString("contentId"), speaker.content())
        players.send(id, command("jump", "chapterId" to 3, "seconds" to 0.0))
        // Hết chương cuối: phiên đóng, chương cuối ghi là đã nghe hết.
        until(10.0) { players.only().now() == null }
        assertTrue(synchronized(saved) { saved.contains(listOf("sach", 3, 10.0, 10.0)) })
        assertTrue("chỉ mở ứng dụng một lần", speaker.calls("receiver.LAUNCH").size == 1)
        assertTrue("PING đều đặn", speaker.pings > 0)
    }

    private fun assertNotEquals(left: Any, right: Any) = assertFalse("$left == $right", left == right)

    @Test
    fun resumingStartsAtTheRightPlaceAndClosingGivesTheDeviceBack() {
        val speaker = device(duration = 30.0)
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved)
        val id = players.found()
        players.send(id, load(2, 6.0))
        assertEquals(6.0, speaker.calls("media.LOAD").single().getDouble("currentTime"), 1e-9)
        assertTrue("không tua sau khi phát", speaker.calls("media.SEEK").isEmpty())
        assertTrue(speaker.position() >= 6)
        players.close()
        assertEquals("IDLE", speaker.state())
        assertTrue("ứng dụng do điện thoại mở thì đóng nó", !speaker.appRunning())
        assertTrue(speaker.calls("receiver.STOP").isNotEmpty())
        val last = synchronized(saved) { saved.last() }
        assertEquals(listOf("sach", 2), last.take(2))
        assertTrue((last[2] as Double) >= 6)
    }

    @Test
    fun pausePlaySeekSkipAndChapters() {
        val speaker = device(duration = 30.0)
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved)
        val id = players.found()
        players.send(id, load(1))
        players.playingNow()
        players.send(id, command("pause"))
        assertEquals("PAUSED", speaker.state())
        assertFalse(players.only().now()!!.getBoolean("playing"))
        players.send(id, command("toggle"))
        assertEquals("PLAYING", speaker.state())
        players.send(id, command("seek", "seconds" to 15.0))
        assertEquals(15.0, speaker.calls("media.SEEK").single().getDouble("currentTime"), 1e-9)
        assertTrue(speaker.position() in 14.0..17.0)
        val before = speaker.position()
        players.send(id, command("skip", "seconds" to 5.0))
        assertTrue(speaker.position() - before in 4.0..8.0)
        players.send(id, command("skip", "seconds" to 60.0))
        assertEquals(2, speaker.calls("media.LOAD").size)
        assertEquals(2, players.only().now()!!.getInt("chapterId"))
        players.send(id, command("previous"))
        assertEquals(1, players.only().now()!!.getInt("chapterId"))
        players.playingNow()
        assertEquals("LOAD đè lên bài đang phát không làm mất phiên", 1, players.playing().size)
        players.send(id, command("rate", "rate" to 1.0))
        try {
            players.send(id, command("rate", "rate" to 1.5))
            fail("tốc độ khác 1x")
        } catch (error: Dlna.Failure) {
            assertEquals("Loa Nest thử: loa, TV chỉ phát ở tốc độ 1x", error.message)
        }
    }

    private fun theSessionEndsWhen(trouble: (FakeCastReceiver) -> Unit): Pair<FakeCastReceiver, DlnaPlayers> {
        val speaker = device(duration = 30.0)
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved)
        val id = players.found()
        players.send(id, load(1))
        players.playingNow()
        trouble(speaker)
        until { players.only().now() == null }
        assertEquals("chỗ nghe lưu đúng chương", listOf("sach", 1), synchronized(saved) { saved.last() }.take(2))
        try {
            players.send(id, command("pause"))
            fail("phiên đã hết")
        } catch (_: Dlna.Failure) {
        }
        assertTrue(players.active().isEmpty())
        return speaker to players
    }

    @Test
    fun anotherSenderTakingTheDeviceEndsTheSessionWithoutTouchingWhatTheyPlay() {
        val (speaker, _) = theSessionEndsWhen { it.takeover("http://192.168.0.5:8200/MediaItems/22.mp3") }
        assertTrue("không dừng thứ người khác đang phát", speaker.calls("media.STOP").isEmpty() && speaker.calls("receiver.STOP").isEmpty())
        assertEquals("PLAYING", speaker.state())
    }

    @Test
    fun closingThePlayerOnTheTvOrCuttingTheSessionEndsIt() {
        theSessionEndsWhen { it.stopApp() }
        theSessionEndsWhen { it.interrupt() }
    }

    @Test
    fun aDeviceThatCannotFetchTheChapterEndsTheSession() {
        val speaker = device().also { it.failFetch = true }
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved)
        val id = players.found()
        try {
            players.send(id, load(1)) // lỗi tải tới trước hay sau câu trả lời LOAD tuỳ nhịp: cả hai đều là "không phát được"
        } catch (error: Dlna.Failure) {
            assertEquals("Loa Nest thử: ${Dlna.error(716)}", error.message)
        }
        until { players.only().now() == null }
        assertTrue(until { synchronized(speaker) { speaker.fetches.firstOrNull() } }.error.isNotEmpty())
    }

    @Test
    fun aRefusedLoadSaysWhyAndLeavesNothingBehind() {
        val speaker = device().also { it.refuseLoad = true }
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved)
        val id = players.found()
        try {
            players.send(id, load(1))
            fail("thiết bị từ chối")
        } catch (error: Dlna.Failure) {
            assertEquals("Loa Nest thử: ${Dlna.error(716)}", error.message)
        }
        assertNull(players.only().now())
        assertTrue("ứng dụng đã mở cho phiên không có thì đóng lại", !speaker.appRunning())
        assertTrue(synchronized(saved) { saved.isEmpty() })
    }

    @Test
    fun theStopActionGivesTheDeviceBackAndSavesThePlace() {
        val speaker = device(duration = 30.0)
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved)
        val id = players.found()
        players.send(id, load(1, 4.0))
        until { players.only().now()?.takeIf { it.getBoolean("playing") && it.getDouble("position") >= 5.0 } }
        players.send(id, command("stop"))
        assertEquals(listOf("media.STOP", "receiver.STOP"), speaker.names().filter { it.endsWith("STOP") })
        assertFalse(speaker.appRunning())
        assertNull(players.only().now())
        assertTrue(players.active().isEmpty())
        val last = synchronized(saved) { saved.last() }
        assertEquals(listOf("sach", 1), last.take(2))
        assertTrue((last[2] as Double) >= 5.0)
        players.send(id, command("stop")) // không còn gì để dừng: không lỗi
    }

    @Test
    fun stoppingLeavesAnApplicationSomeoneElseOpenedRunning() {
        val speaker = device(duration = 30.0)
        speaker.launch() // một người khác đã mở Default Media Receiver trước
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved)
        val id = players.found()
        players.send(id, load(1))
        players.playingNow()
        players.send(id, command("stop"))
        assertEquals(listOf("media.STOP"), speaker.names().filter { it.endsWith("STOP") })
        assertTrue(speaker.appRunning())
        assertEquals("không mở lần nữa", 0, speaker.calls("receiver.LAUNCH").size)
    }

    @Test
    fun aSleepingDeviceEndsTheSessionAndRefusesCommandsUntilItWakes() {
        val speaker = device(duration = 30.0)
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved)
        val id = players.found()
        players.send(id, load(1))
        players.playingNow()
        speaker.sleep()
        until(12.0) { players.only().now() == null }
        assertEquals(listOf("sach", 1), synchronized(saved) { saved.last() }.take(2))
        try {
            players.send(id, load(2))
            fail("thiết bị tắt nguồn")
        } catch (error: Dlna.Failure) {
            assertEquals("Loa Nest thử: không nối được - thiết bị đã tắt hay rời mạng?", error.message)
        }
        speaker.wake()
        players.send(id, load(2))
        players.playingNow()
        assertEquals(2, players.only().now()!!.getInt("chapterId"))
    }

    @Test
    fun aDeviceThatBlinksOffAndComesBackKeepsTheSession() {
        val speaker = device(duration = 60.0)
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved, lostAfter = 30_000)
        val id = players.found()
        players.send(id, load(1))
        players.playingNow()
        val connections = speaker.connections
        speaker.sleep()
        Thread.sleep(1800) // quá `dead` (1,2 giây): điện thoại coi đã đứt và thử nối lại
        speaker.wake()
        until(10.0) { speaker.connections > connections }
        val now = until { players.only().now()?.takeIf { it.getBoolean("playing") && !it.getBoolean("buffering") } }
        assertEquals(1, now.getInt("chapterId"))
        assertTrue("ứng dụng vẫn đó, không mở lại", speaker.appRunning() && speaker.calls("receiver.LAUNCH").size == 1)
        val at = now.getDouble("position")
        until { players.only().now()!!.getDouble("position") > at }
        assertNotNull(players.playing().singleOrNull())
    }

    @Test
    fun theVolumeKeysMoveTheCastDeviceVolume() {
        val speaker = device(duration = 30.0).apply { volume = 0.3 }
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved).apply { volumeEveryMs = 100 }
        val id = players.found()
        players.send(id, load(1))
        players.playingNow()
        assertEquals("âm lượng thiết bị báo khi mở ứng dụng", 30, players.now()!!.volume)
        players.send(id, command("volume", "level" to 64))
        assertEquals(0.64, speaker.calls("receiver.SET_VOLUME").single().getJSONObject("volume").getDouble("level"), 1e-9)
        assertEquals(0.64, speaker.volume, 1e-9)
        assertEquals(64, players.now()!!.volume)
        assertTrue(runCatching { players.send(id, command("volume", "level" to 101)) }.exceptionOrNull() is Dlna.Failure)
        assertEquals(1, speaker.calls("receiver.SET_VOLUME").size)
    }

    @Test
    fun aCastDeviceWithFixedVolumeLeavesThePhoneVolume() {
        val speaker = device(duration = 30.0).apply { fixedVolume = true }
        val (chosen, saved) = book()
        val players = players(speaker, chosen, saved).apply { volumeEveryMs = 100 }
        val id = players.found()
        players.send(id, load(1))
        players.playingNow()
        Thread.sleep(300)
        assertNull("loa giữ âm lượng riêng: phím âm lượng vẫn chỉnh điện thoại", players.now()!!.volume)
        assertTrue(runCatching { players.send(id, command("volume", "level" to 40)) }.exceptionOrNull() is Dlna.Failure)
        assertTrue(speaker.calls("receiver.SET_VOLUME").isEmpty())
    }
}
