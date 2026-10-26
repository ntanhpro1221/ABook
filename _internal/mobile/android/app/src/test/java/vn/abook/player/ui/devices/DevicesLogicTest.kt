package vn.abook.player.ui.devices

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Phần thuần của ba màn Thiết bị: lời trạng thái, nhãn nút tải, điều kiện "Kết nối", lời hỏi trước khi bỏ ghép, và đọc JSON thật của lõi. */
class DevicesLogicTest {
    // ---- đường nối ----

    @Test
    fun `a route names the way in without showing the address`() {
        assertEquals("Chưa kết nối", DeviceText.route(""))
        assertEquals("Chưa kết nối", DeviceText.route(null))
        assertEquals("Đang nối qua Bluetooth", DeviceText.route("bluetooth"))
        assertEquals("Đang nối qua Bluetooth", DeviceText.route("bt:AA:BB"))
        assertEquals("Đang nối qua Wi-Fi nhà", DeviceText.route("192.168.1.20:47630"))
        assertEquals("Đang nối qua Wi-Fi nhà", DeviceText.route("10.0.0.5"))
        assertEquals("Đang nối qua Wi-Fi nhà", DeviceText.route("172.20.1.1:1"))
        assertEquals("Đang nối qua Tailscale", DeviceText.route("100.101.2.3:47630"))
        assertEquals("Đang nối qua mạng", DeviceText.route("example.com:47630"))
        assertEquals("Đang nối qua mạng", DeviceText.route("8.8.8.8"))
    }

    @Test
    fun `a device row says what is wrong in the words a listener knows`() {
        val ok = Paired("", "Máy bàn", DeviceKind.Computer, via = "192.168.1.20:47630", reach = Reach.Ok)
        assertEquals("Đang nối qua Wi-Fi nhà", ok.state)
        assertFalse(ok.failed)
        assertEquals("Đang kiểm tra", ok.copy(via = "", reach = Reach.Checking).state)
        assertEquals(DeviceText.OFFLINE, ok.copy(reach = Reach.Offline("x")).state)
        assertTrue(ok.copy(reach = Reach.Offline("x")).failed)
        assertEquals("Máy bàn đã thôi ghép với điện thoại này", ok.copy(reach = Reach.Unpaired).state)
        assertEquals("Chứng chỉ đã đổi", ok.copy(reach = Reach.Changed("Chứng chỉ đã đổi")).state)
        assertEquals("2 cuốn nghe được · Đang nối qua Wi-Fi nhà", ok.copy(key = "p1", books = 2).state)
    }

    // ---- sách ----

    @Test
    fun `the book button names what is new, chapters first`() {
        val fresh = RemoteBook("a", title = "A", chaptersAvailable = 3, chaptersTotal = 10)
        assertEquals("Tải", fresh.action)
        val have = fresh.copy(downloaded = true)
        assertTrue(have.upToDate)
        assertEquals("+2 chương", have.copy(newChapters = 2, newAudio = true).action)
        assertEquals("Cập nhật bản thu", have.copy(newAudio = true, newCover = true).action)
        assertEquals("Cập nhật bìa", have.copy(newCover = true, newMeta = true).action)
        assertEquals("Cập nhật tên", have.copy(newMeta = true, newWords = true).action)
        assertEquals("Cập nhật chữ", have.copy(newWords = true).action)
        assertFalse(have.copy(newWords = true).upToDate)
        assertFalse("chưa tải thì không có gì là 'đã tải'", fresh.upToDate)
    }

    @Test
    fun `a book line gives chapters, length and the size to download`() {
        val book = RemoteBook("a", title = "A", chaptersAvailable = 3, chaptersTotal = 10, duration = 5400.0, bytes = 40L * 1024 * 1024)
        assertEquals("3/10 chương · 1 giờ 30 phút · 40 MB", book.detail)
        assertEquals("3/10 chương · 1 giờ 30 phút", book.copy(downloaded = true).detail)
        assertEquals("3/10 chương · 1 giờ 30 phút · 40 MB · đang làm", book.copy(producing = true).detail)
    }

    // ---- ghép ----

    @Test
    fun `an address is host and port with the default port filled in`() {
        assertEquals("192.168.1.20:47630", normalizeAddress("192.168.1.20"))
        assertEquals("192.168.1.20:5000", normalizeAddress(" 192.168.1.20:5000 "))
        assertEquals("bt:AA:BB", normalizeAddress("bt:AA:BB"))
        assertNull(normalizeAddress(""))
        assertNull(normalizeAddress("192.168.1.20:abc"))
        assertNull(normalizeAddress("192.168.1.20:70000"))
        assertNull(normalizeAddress(":47630"))
    }

    @Test
    fun `connect needs a target and exactly six digits`() {
        assertFalse(PairForm().ready)
        assertFalse(PairForm(picked = "1.2.3.4:1", code = "12345").ready)
        assertTrue(PairForm(picked = "1.2.3.4:1", code = "123 456").ready)
        assertFalse("địa chỉ gõ tay chỉ tính khi đang ở chế độ gõ", PairForm(address = "192.168.1.20", code = "123456").ready)
        assertTrue(PairForm(address = "192.168.1.20", code = "123456", manual = true).ready)
        assertFalse("chữ không phải địa chỉ", PairForm(address = "abc", code = "123456", manual = true).ready)
    }

    @Test
    fun `found machines already paired are not offered again`() {
        val paired = listOf(Paired("", "Máy bàn", DeviceKind.Computer, host = "192.168.1.20"))
        val found = listOf(Found("192.168.1.20:47630", "Máy bàn", DeviceKind.Computer), Found("192.168.1.21:47630", "Máy khác", DeviceKind.Computer))
        assertEquals(listOf("192.168.1.21:47630"), found.withoutPaired(paired).map { it.address })
        assertEquals("Qua Bluetooth", Found("bt:AA", "", DeviceKind.Computer, bluetooth = true).detail)
        assertEquals("192.168.1.21", found[1].detail)
        assertEquals("Máy khác", found[1].shown)
        assertEquals("192.168.1.21", found[1].copy(name = "").shown)
    }

    // ---- bỏ ghép ----

    private val edited = Unsent(listOf(UnsentBook("Sách A", 2), UnsentBook("Sách B", 1)), 3, sendable = true, cacheBooks = 2, cacheBytes = 80L * 1024 * 1024, places = 1)

    @Test
    fun `nothing to lose means no question`() {
        assertNull(DeviceText.forgetCopy("Máy phụ", Unsent(), reachable = true))
        assertNull(DeviceText.forgetCopy("Máy phụ", null, reachable = true))
    }

    @Test
    fun `unsent edits offer sending first when the other side can take them`() {
        val copy = DeviceText.forgetCopy("Máy phụ", edited, reachable = true)!!
        assertEquals("Bỏ ghép Máy phụ?", copy.title)
        assertEquals("Gửi trước rồi bỏ ghép", copy.send)
        assertEquals("Vẫn bỏ ghép, bỏ thay đổi", copy.discard)
        assertTrue(copy.edited)
        assertTrue(copy.lines.any { it.contains("2 cuốn có 3 thay đổi chưa gửi về Máy phụ sẽ mất: “Sách A”, “Sách B”.") })
        assertTrue(copy.lines.any { it.startsWith("2 cuốn của Máy phụ sẽ rời Thư viện, và 80 MB đã tải về điện thoại này sẽ bị xoá.") })
        assertTrue(copy.lines.any { it.startsWith("Chỗ nghe của 1 cuốn vẫn giữ") })
    }

    @Test
    fun `an unreachable device only gets a try-to-send`() {
        val copy = DeviceText.forgetCopy("Máy phụ", edited, reachable = false)!!
        assertEquals("Thử gửi trước rồi bỏ ghép", copy.send)
        assertTrue(copy.lines.any { it.contains("đang tắt hay khác mạng") })
    }

    @Test
    fun `a device that takes no edits cannot be sent to and says so`() {
        val copy = DeviceText.forgetCopy("Điện thoại bạn", edited.copy(sendable = false), reachable = true)!!
        assertNull(copy.send)
        assertTrue(copy.lines.any { it.contains("không nhận phần sửa") })
    }

    @Test
    fun `only cache to lose is a plain forget`() {
        val copy = DeviceText.forgetCopy("Máy phụ", Unsent(cacheBooks = 1, cacheBytes = 10), reachable = true)!!
        assertEquals("Bỏ ghép", copy.discard)
        assertFalse(copy.edited)
        assertNull(copy.send)
        assertTrue(copy.lines.single().contains("dưới 1 MB"))
    }

    @Test
    fun `many unsent books are summarised after three`() {
        val many = Unsent((1..5).map { UnsentBook("S$it", 1) }, 5, sendable = true)
        val line = DeviceText.forgetCopy("Máy phụ", many, reachable = true)!!.lines.first()
        assertTrue(line, line.endsWith("“S1”, “S2”, “S3” và 2 cuốn khác."))
    }

    // ---- chia sẻ, dung lượng ----

    @Test
    fun `the share address line shows every address with the port`() {
        assertEquals("Chưa vào mạng Wi-Fi nào", Share().addressLine)
        assertEquals("192.168.1.9:47631", Share(port = 47631, addresses = listOf("192.168.1.9")).addressLine)
        assertEquals("192.168.1.9:1, [fe80::1]:1", Share(port = 1, addresses = listOf("192.168.1.9", "fe80::1")).addressLine)
    }

    @Test
    fun `the bluetooth line speaks only when it carries news`() {
        assertNull(Share().bluetoothLine)
        assertNull(Share(bluetooth = "running").bluetoothLine)
        assertEquals("Bluetooth: 2 máy đang nối", Share(bluetooth = "running", bluetoothConnections = 2).bluetoothLine)
        assertEquals("Cần quyền Thiết bị ở gần", Share(bluetooth = "Cần quyền Thiết bị ở gần").bluetoothLine)
        assertTrue(Share(bluetooth = "Cần quyền Thiết bị ở gần").needsNearby)
    }

    @Test
    fun `the clock for a code is the phone's own time as hours and minutes`() {
        val text = DeviceText.clock(1_700_000_000.0)
        assertTrue(text, Regex("""\d\d:\d\d""").matches(text))
    }

    @Test
    fun `listen only machines are told before the tap`() {
        assertTrue(DeviceText.listenOnly("Máy bàn").startsWith("Máy tính Máy bàn chỉ cho nghe"))
    }

    // ---- JSON của lõi ----

    @Test
    fun `core json becomes the model`() {
        val link = DevicesJson.link(JSONObject("""{"paired":true,"name":"Máy bàn","host":"192.168.1.20","connectedVia":"192.168.1.20:47630","deviceName":"Điện thoại"}"""))
        assertTrue(link.paired)
        assertEquals("Máy bàn", link.shownName)
        assertEquals("Điện thoại", link.deviceName)
        assertEquals("Máy tính", Link().shownName)
        assertEquals("AA:BB", Link(host = "bt:AA:BB").shownName)

        val found = DevicesJson.found(JSONObject("""{"host":"192.168.1.20","port":5000,"name":"Máy bàn","kind":"computer"}"""))
        assertEquals("192.168.1.20:5000", found.address)
        assertEquals(DeviceKind.Computer, found.kind)
        val phone = DevicesJson.found(JSONObject("""{"host":"192.168.1.22","name":"Điện thoại","kind":"phone"}"""))
        assertEquals("192.168.1.22:47630", phone.address)
        assertEquals(DeviceKind.Phone, phone.kind)
        val bt = DevicesJson.bluetooth(JSONObject("""{"address":"AA:BB","name":"Máy bàn","kind":"computer","abook":true}"""))
        assertEquals("bt:AA:BB", bt.address)
        assertTrue(bt.bluetooth)
    }

    @Test
    fun `a book from the core knows what changed since the last download`() {
        val book = DevicesJson.book(
            JSONObject(
                """{"id":"a","title":"Tắt đèn","chaptersAvailable":5,"chaptersTotal":9,"duration":3600,"bytes":1048576,"downloaded":true,
                   "localChapters":3,"audioVersion":"v2","localAudioVersion":"v1","metaVersion":"m","localMetaVersion":"m","cover":{"version":4},"localCoverVersion":4}""",
            ),
        )
        assertEquals(2, book.newChapters)
        assertTrue(book.newAudio)
        assertFalse(book.newMeta)
        assertFalse(book.newCover)
        assertEquals("+2 chương", book.action)
        val fresh = DevicesJson.book(JSONObject("""{"id":"b","title":"B","chaptersAvailable":5,"downloaded":false,"localChapters":3}"""))
        assertEquals(0, fresh.newChapters)
        assertEquals("Tải", fresh.action)
    }

    @Test
    fun `share json carries the code, the listeners and the bluetooth state`() {
        val share = DevicesJson.share(
            JSONObject(
                """{"running":true,"name":"Điện thoại","port":47631,"addresses":["192.168.1.9"],"pairing":{"code":"482915","expiresAt":1700000600},
                   "blocked":false,"devices":[{"id":"d1","name":"Máy khách","lastSeen":1700000000}],"error":"",
                   "bluetooth":{"status":"running","connections":1},"backgroundAllowed":false}""",
            ),
        )
        assertTrue(share.running)
        assertEquals("482915", share.code?.digits)
        assertEquals("d1", share.devices.single().id)
        assertEquals("Bluetooth: 1 máy đang nối", share.bluetoothLine)
        assertFalse(share.backgroundAllowed)
        assertNull(DevicesJson.share(JSONObject("""{"running":false,"pairing":null}""")).code)
    }

    @Test
    fun `storage json is biggest first and tells a finished book from a partial one`() {
        val storage = DevicesJson.storage(
            JSONObject("""{"bytes":100,"free":900,"books":[{"id":"small","bytes":10,"title":"Nhỏ"},{"id":"big","bytes":60,"title":"Lớn"},{"id":"half","bytes":30}]}"""),
            isBook = { it != "half" }, holder = { "Máy bàn" },
        )
        assertEquals(listOf("big", "half", "small"), storage.entries.map { it.id })
        val half = storage.entries[1]
        assertTrue(half.partial)
        assertEquals("Máy bàn", half.holder)
        assertEquals("Sách tải dở", half.title)
        assertFalse(storage.entries[0].partial)
        assertEquals("", storage.entries[0].holder)
    }

    @Test
    fun `peer json says why a device did not answer`() {
        fun peer(extra: String) = DevicesJson.peer(JSONObject("""{"key":"p1","name":"Máy phụ","kind":"computer","connectedVia":"192.168.1.30:47630"$extra}"""))
        assertEquals(Reach.Ok, peer("").device.reach)
        assertEquals(Reach.Unpaired, peer(""","unpaired":true""").device.reach)
        assertTrue(peer(""","pinChanged":true,"error":"Chứng chỉ đã đổi"""").device.reach is Reach.Changed)
        assertEquals(Reach.Offline("Không nối được", "timeout"), peer(""","error":"Không nối được","technical":"timeout"""").device.reach)
        val withBooks = peer(""","books":[{"id":"p1:1","title":"A"}]""")
        assertEquals(1, withBooks.books.size)
        assertEquals(1, withBooks.device.books)
    }
}
