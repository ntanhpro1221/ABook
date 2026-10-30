package vn.abook.player.ui.devices

import vn.abook.player.ui.studio.StudioRoute
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Việc của ba màn Thiết bị với nguồn giả: ghép (tìm, chọn, mã, thành công, lỗi, đang chạy), bỏ ghép, tải sách và huỷ, chia sẻ, dung lượng và xoá. Phạm vi chạy ngay
 * (Unconfined) nên sau mỗi lời gọi trạng thái đã xong; chỉ việc bị giữ bằng cổng mới còn dang dở.
 */
class DevicesStateTest {
    private val source = FakeDevicesSource()
    private var changed = 0
    private var studioOpened: Pair<String, StudioRoute>? = null
    private var asked = 0
    private var settingsOpened = 0
    private var notificationsAsked = 0

    private val computer = Found("192.168.1.20:47630", "Máy bàn", DeviceKind.Computer)
    private val main = Link(paired = true, name = "Máy bàn", host = "192.168.1.20", via = "192.168.1.20:47630", deviceName = "Điện thoại của tôi")

    private fun book(id: String, title: String = "Sách $id", downloaded: Boolean = false, newChapters: Int = 0) = RemoteBook(
        id = id, title = title, chaptersAvailable = 3 + newChapters, chaptersTotal = 10, duration = 7200.0, bytes = 40L * 1024 * 1024,
        downloaded = downloaded, newChapters = newChapters,
    )

    private fun peer(key: String, name: String = "Máy phụ", reach: Reach = Reach.Ok, books: List<RemoteBook> = emptyList()) =
        PeerLibrary(Paired(key, name, DeviceKind.Computer, via = "192.168.1.30:47630", reach = reach, books = books.size, host = "192.168.1.30"), books)

    private fun state(links: DeviceLinks = DeviceLinks(
        openStudio = { computer, route -> studioOpened = computer to route },
        openAppSettings = { settingsOpened++ },
        askNearby = { result -> asked++; result(source.nearby) },
        askNotifications = { then -> notificationsAsked++; then() },
    )) = DevicesState(source, CoroutineScope(Dispatchers.Unconfined), links, changed = { changed++ }, pollMs = 3_600_000)

    // ---- ghép ----

    @Test
    fun `an unpaired phone looks for computers and picks the only one it finds`() {
        source.found = listOf(computer)
        val devices = state()
        devices.openPair()
        val ui = devices.pair.value
        assertTrue(ui.loaded)
        assertTrue(ui.showForm)
        assertFalse(ui.scanning)
        assertEquals(PairMethod.Wifi, ui.method)
        assertEquals(computer.address, ui.form.picked)
        assertTrue(ui.devices.isEmpty())
    }

    @Test
    fun `several computers are listed and none is picked for you`() {
        source.found = listOf(computer, Found("192.168.1.21:47630", "Máy xách tay", DeviceKind.Computer))
        val devices = state()
        devices.openPair()
        assertEquals(2, devices.pair.value.wifiChoices.size)
        assertNull(devices.pair.value.form.picked)
        devices.pick(computer)
        assertEquals(computer.address, devices.pair.value.form.picked)
        devices.pick(computer)
        assertNull("chạm lần nữa bỏ chọn", devices.pair.value.form.picked)
    }

    @Test
    fun `the code is six digits and connect stays off until the target and code are there`() {
        source.found = listOf(computer, Found("192.168.1.21:47630", "Máy xách tay", DeviceKind.Computer))
        val devices = state()
        devices.openPair()
        assertFalse(devices.pair.value.form.ready)
        devices.pick(computer)
        devices.setCode("12ab34")
        assertEquals("1234", devices.pair.value.form.code)
        assertFalse(devices.pair.value.form.ready)
        devices.setCode("123 456 789")
        assertEquals("123456", devices.pair.value.form.code)
        assertTrue(devices.pair.value.form.ready)
    }

    @Test
    fun `pairing success shows the computer and its books`() {
        source.found = listOf(computer)
        source.remote = RemoteLibrary("Máy bàn", listOf(book("a"), book("b", downloaded = true)))
        val devices = state()
        devices.openPair()
        devices.setCode("123456")
        devices.connect()
        assertEquals(listOf(Triple(computer.address, "123456", false)), source.pairs)
        val ui = devices.pair.value
        assertTrue(ui.paired)
        assertEquals(Attempt.Idle, ui.attempt)
        assertEquals(listOf(MAIN_KEY), ui.devices.map { it.key })
        assertEquals(Reach.Ok, ui.devices.single().reach)
        assertEquals(1, ui.sections.size)
        assertEquals(2, ui.sections.single().books.size)
        assertFalse("đã nối thì khung ghép đóng lại", ui.showForm)
        assertEquals("form về trống", PairForm(), ui.form)
    }

    @Test
    fun `a wrong code fails in place and can be retried`() {
        source.found = listOf(computer)
        source.pairError = DeviceFailure("Mã chưa đúng - bạn nhập lại.")
        val devices = state()
        devices.openPair()
        devices.setCode("000000")
        devices.connect()
        val failed = devices.pair.value.attempt
        assertTrue(failed is Attempt.Failed)
        assertEquals("Chưa ghép được. Mã chưa đúng - bạn nhập lại.", (failed as Attempt.Failed).message)
        assertFalse(devices.pair.value.paired)
        assertEquals("mã vẫn còn để sửa", "000000", devices.pair.value.form.code)
        source.pairError = null
        devices.setCode("482915")
        assertEquals("sửa mã là xoá lỗi", Attempt.Idle, devices.pair.value.attempt)
        devices.connect()
        assertEquals(2, source.pairs.size)
        assertTrue(devices.pair.value.paired)
    }

    @Test
    fun `pairing in progress shows the name and ignores a second tap`() {
        source.found = listOf(computer)
        source.pairGate = CompletableDeferred()
        val devices = state()
        devices.openPair()
        devices.setCode("123456")
        devices.connect()
        assertEquals(Attempt.Working("Máy bàn"), devices.pair.value.attempt)
        devices.connect()
        assertEquals(1, source.pairs.size)
        source.pairGate!!.complete(Unit)
        assertTrue(devices.pair.value.paired)
    }

    @Test
    fun `a typed address gets the default port and a bad one never reaches the core`() {
        val devices = state()
        devices.openPair()
        devices.setMethod(PairMethod.Address)
        devices.setAddress("192.168.1.20")
        devices.setCode("123456")
        devices.connect()
        assertEquals("192.168.1.20:47630", source.pairs.single().first)
        source.link = Link()
        val other = state()
        other.openPair()
        other.setMethod(PairMethod.Address)
        other.setAddress("192.168.1.20:abc")
        other.setCode("123456")
        other.connect()
        assertEquals(1, source.pairs.size)
        assertTrue(other.pair.value.attempt is Attempt.Failed)
    }

    @Test
    fun `adding a second device pairs as an extra and keeps the main computer`() {
        source.link = main
        source.remote = RemoteLibrary("Máy bàn", emptyList())
        source.found = listOf(Found("192.168.1.30:47630", "Máy phụ", DeviceKind.Computer))
        val devices = state()
        devices.openPair()
        assertFalse(devices.pair.value.showForm)
        devices.setAdding(true)
        assertTrue(devices.pair.value.showForm)
        assertEquals("một máy duy nhất được chọn sẵn", "192.168.1.30:47630", devices.pair.value.form.picked)
        devices.setCode("123456")
        devices.connect()
        assertTrue(source.pairs.single().third)
        assertFalse(devices.pair.value.adding)
        assertEquals("Máy bàn", devices.pair.value.devices.first().name)
    }

    @Test
    fun `bluetooth asks for nearby devices first and says so when refused for good`() {
        source.nearby = false
        source.bluetooth = listOf(Found("bt:AA:BB", "Máy bàn", DeviceKind.Computer, bluetooth = true))
        val denied = state(DeviceLinks(askNearby = { result -> asked++; result(false) }))
        denied.openPair()
        denied.setMethod(PairMethod.Bluetooth)
        assertEquals(0, asked)
        assertEquals(Bluetooth.Explain, denied.pair.value.bluetooth)
        denied.requestBluetooth()
        assertEquals(1, asked)
        assertEquals(Bluetooth.Denied, denied.pair.value.bluetooth)
        assertEquals(PairMethod.Bluetooth, denied.pair.value.method)
        val granted = state(DeviceLinks(askNearby = { result -> source.nearby = true; result(true) }))
        granted.openPair()
        granted.setMethod(PairMethod.Bluetooth)
        granted.requestBluetooth()
        assertEquals(listOf("bt:AA:BB"), granted.pair.value.bluetoothChoices.map { it.address })
        assertEquals("một máy duy nhất được chọn sẵn", "bt:AA:BB", granted.pair.value.form.picked)
        granted.setMethod(PairMethod.Wifi)
        assertEquals(Bluetooth.Off, granted.pair.value.bluetooth)
    }

    @Test
    fun `a bluetooth failure is shown with its own words`() {
        source.bluetoothError = DeviceFailure("Chưa dùng được Bluetooth - bạn bật nó lên.")
        val devices = state()
        devices.openPair()
        devices.findBluetooth()
        assertEquals(Bluetooth.Failed("Chưa dùng được Bluetooth - bạn bật nó lên."), devices.pair.value.bluetooth)
    }

    // ---- thiết bị đã ghép ----

    @Test
    fun `an unreachable computer says why and keeps the row`() {
        source.link = main
        source.remoteError = DeviceFailure("Không nối được Máy bàn.")
        val devices = state()
        devices.openPair()
        val row = devices.pair.value.devices.single()
        assertTrue(row.reach is Reach.Offline)
        assertTrue(row.failed)
        assertEquals(DeviceText.OFFLINE, row.state)
    }

    @Test
    fun `a computer that forgot this phone is told apart from one that is only off`() {
        source.link = main
        source.remoteError = DeviceFailure("đã bỏ ghép", unpaired = true)
        val devices = state()
        devices.openPair()
        assertEquals(Reach.Unpaired, devices.pair.value.devices.single().reach)
        assertEquals("Máy bàn đã bỏ ghép với điện thoại này", devices.pair.value.devices.single().state)
    }

    @Test
    fun `forgetting a device asks the core and drops its row and books`() {
        source.link = main
        source.remote = RemoteLibrary("Máy bàn", emptyList())
        source.peers = listOf(peer("p1", books = listOf(book("p1:1"))))
        val devices = state()
        devices.openPair()
        assertEquals(listOf(MAIN_KEY, "p1"), devices.pair.value.devices.map { it.key })
        assertEquals(1, devices.pair.value.sections.size)
        val error = runBlocking { devices.forget("p1", ForgetChoice.Discard) }
        assertNull(error)
        assertEquals(listOf("p1" to ForgetChoice.Discard), source.forgets)
        assertEquals(listOf(MAIN_KEY), devices.pair.value.devices.map { it.key })
        assertTrue(devices.pair.value.sections.isEmpty())
        assertTrue("sách nghe thẳng của nó rời Thư viện", source.streamables > 0)
    }

    @Test
    fun `a refused forget keeps the device and returns the words`() {
        source.peers = listOf(peer("p1"))
        source.forgetError = DeviceFailure("Còn thay đổi chưa gửi.")
        val devices = state()
        devices.openPair()
        val error = runBlocking { devices.forget("p1", ForgetChoice.Plain) }
        assertEquals("Còn thay đổi chưa gửi.", error)
        assertEquals(listOf("p1"), devices.pair.value.devices.map { it.key })
    }

    @Test
    fun `unpairing the main computer removes it and offers the form again`() {
        source.link = main
        source.remote = RemoteLibrary("Máy bàn", listOf(book("a")))
        val devices = state()
        devices.openPair()
        assertNull(runBlocking { devices.unpairMain() })
        assertEquals(1, source.unpairs)
        assertFalse(devices.pair.value.paired)
        assertTrue(devices.pair.value.devices.none { it.main })
        assertTrue(devices.pair.value.sections.isEmpty())
        assertTrue(devices.pair.value.showForm)
    }

    @Test
    fun `pairing again after the computer forgot us starts from its last address`() {
        source.link = main.copy(lastAddress = "192.168.1.20:47630")
        source.remoteError = DeviceFailure("đã bỏ ghép", unpaired = true)
        val devices = state()
        devices.openPair()
        devices.repair(devices.pair.value.devices.single())
        assertFalse(devices.pair.value.paired)
        assertEquals("192.168.1.20", devices.pair.value.form.address)
        assertEquals(PairMethod.Address, devices.pair.value.method)
    }

    @Test
    fun `studio opens through the system link and reports a refusal`() {
        source.link = main
        source.studio = listOf(StudioComputer(MAIN_KEY, "Máy bàn", listenOnly = false))
        source.target = "Máy bàn" to StudioRoute("b1")
        val devices = state()
        devices.openPair()
        devices.loadStudio()
        assertNotNull(devices.pair.value.studio[MAIN_KEY])
        assertNull(runBlocking { devices.openStudio(MAIN_KEY) })
        assertEquals("Máy bàn" to StudioRoute("b1"), studioOpened)
        source.targetError = DeviceFailure("Máy này chỉ cho nghe.")
        assertEquals("Máy này chỉ cho nghe.", runBlocking { devices.openStudio(MAIN_KEY) })
    }

    // ---- tải sách ----

    @Test
    fun `a download shows progress in its own book and finishing refreshes the library`() {
        source.link = main
        source.remote = RemoteLibrary("Máy bàn", listOf(book("a"), book("b")))
        val devices = state()
        devices.openPair()
        val a = devices.pair.value.sections.single().books.first()
        devices.download(a)
        assertEquals(listOf("a"), source.downloads)
        assertEquals(setOf("a"), devices.pair.value.downloading)
        source.events.tryEmit(DownloadEvent("a", 0.4f))
        assertEquals(0.4f, devices.progress("a").value, 0f)
        assertEquals("sách khác không nhúc nhích", 0f, devices.progress("b").value, 0f)
        val before = devices.pair.value
        source.events.tryEmit(DownloadEvent("a", 0.7f))
        assertTrue("tiến độ không làm đổi trạng thái màn", before === devices.pair.value)
        source.events.tryEmit(DownloadEvent("a", 1f, finished = true))
        assertTrue(devices.pair.value.downloading.isEmpty())
        assertTrue(changed > 0)
    }

    @Test
    fun `cancel reaches the core and the row returns to its button`() {
        source.link = main
        source.remote = RemoteLibrary("Máy bàn", listOf(book("a")))
        val devices = state()
        devices.openPair()
        devices.download(devices.pair.value.sections.single().books.single())
        devices.cancelDownload("a")
        assertEquals(listOf("a"), source.cancels)
        source.events.tryEmit(DownloadEvent("a", 0.2f, cancelled = true))
        assertTrue(devices.pair.value.downloading.isEmpty())
        assertTrue(devices.pair.value.failed.isEmpty())
    }

    @Test
    fun `a failed download keeps its words on the row until retried`() {
        source.link = main
        source.remote = RemoteLibrary("Máy bàn", listOf(book("a")))
        source.downloadError = DeviceFailure("Máy không đủ chỗ.")
        val devices = state()
        devices.openPair()
        val a = devices.pair.value.sections.single().books.single()
        devices.download(a)
        assertEquals("Máy không đủ chỗ.", devices.pair.value.failed["a"])
        assertTrue(devices.pair.value.downloading.isEmpty())
        source.downloadError = null
        devices.download(a)
        assertTrue(devices.pair.value.failed.isEmpty())
        source.events.tryEmit(DownloadEvent("a", 0.3f, error = "Mất mạng giữa chừng."))
        assertEquals("Tải bị gián đoạn. Mất mạng giữa chừng.", devices.pair.value.failed["a"])
        assertTrue(devices.pair.value.downloading.isEmpty())
    }

    // ---- chia sẻ ----

    @Test
    fun `the switch asks for notifications then turns sharing on and off`() {
        val devices = state()
        devices.openShare()
        assertTrue(devices.share.value.loaded)
        assertFalse(devices.share.value.share.running)
        devices.setSharing(true)
        assertEquals(1, notificationsAsked)
        assertTrue(devices.share.value.share.running)
        assertFalse(devices.share.value.busy)
        devices.setSharing(false)
        assertFalse(devices.share.value.share.running)
        assertEquals("tắt không cần quyền", 1, notificationsAsked)
    }

    @Test
    fun `a failed switch says why and leaves the switch where it was`() {
        source.shareError = DeviceFailure("Chưa vào mạng Wi-Fi nào.")
        val devices = state()
        devices.openShare()
        devices.setSharing(true)
        assertEquals("Chưa vào mạng Wi-Fi nào.", devices.share.value.problem)
        assertFalse(devices.share.value.share.running)
        assertFalse(devices.share.value.busy)
    }

    @Test
    fun `a pairing code shows then cancels and a listener can be revoked`() {
        source.share = Share(running = true, name = "Điện thoại", port = 47631, addresses = listOf("192.168.1.9"), devices = listOf(Sharer("d1", "Máy khách", 1_700_000_000.0)))
        val devices = state()
        devices.openShare()
        devices.newCode()
        assertEquals("482915", devices.share.value.share.code?.digits)
        devices.cancelCode()
        assertNull(devices.share.value.share.code)
        devices.revoke("d1")
        assertTrue(devices.share.value.share.devices.isEmpty())
        assertEquals("192.168.1.9:47631", devices.share.value.share.addressLine)
    }

    @Test
    fun `the notification button turning sharing off reaches the screen`() {
        source.share = Share(running = true)
        val devices = state()
        devices.openShare()
        assertTrue(devices.share.value.share.running)
        source.share = Share(running = false)
        source.shareEvents.tryEmit(Unit)
        assertFalse(devices.share.value.share.running)
    }

    // ---- dung lượng ----

    @Test
    fun `storage lists what the core reports and delete removes through the same core call`() {
        source.storage = Storage(
            bytes = 90L * 1024 * 1024, free = 5L * 1024 * 1024 * 1024,
            entries = listOf(Stored("a", "Sách A", 60L * 1024 * 1024, false), Stored("b", "Sách B", 30L * 1024 * 1024, true, "Máy bàn")),
        )
        val devices = state()
        devices.openStorage()
        assertEquals(listOf("a", "b"), devices.storage.value.storage.entries.map { it.id })
        assertNull(runBlocking { devices.delete("a") })
        assertEquals(listOf("a"), source.deleted)
        assertEquals(listOf("b"), devices.storage.value.storage.entries.map { it.id })
    }

    @Test
    fun `a failed delete keeps the row and returns the words`() {
        source.storage = Storage(1, 1, listOf(Stored("a", "Sách A", 1, false)))
        source.deleteError = "Chưa xoá được."
        val devices = state()
        devices.openStorage()
        assertEquals("Chưa xoá được.", runBlocking { devices.delete("a") })
        assertEquals(1, devices.storage.value.storage.entries.size)
    }

    // ---- trang nhóm ----

    @Test
    fun `the group page reads three summary lines and the phone name`() {
        source.link = main
        source.share = Share(running = true, devices = listOf(Sharer("d1", "Máy khách", 0.0), Sharer("d2", "Máy nữa", 0.0)))
        source.storage = Storage(300L * 1024 * 1024, 10L * 1024 * 1024 * 1024)
        source.remote = RemoteLibrary("Máy bàn", emptyList())
        val devices = state()
        assertNull(devices.summary.value.pair)
        devices.loadSummary()
        val summary = devices.summary.value
        assertEquals("Đã nối Máy bàn", summary.pair)
        assertEquals("Đang bật · 2 máy", summary.sharing)
        assertEquals("Sách 300 MB · còn trống 10 GB", summary.storageLine)
        assertEquals("Điện thoại của tôi", summary.deviceName)
    }

    @Test
    fun `an unpaired phone says so on the group page`() {
        val devices = state()
        devices.loadSummary()
        assertEquals("Chưa nối", devices.summary.value.pair)
        assertEquals("Đang tắt", devices.summary.value.sharing)
    }

    @Test
    fun `renaming the phone goes to the core and shows at once`() {
        source.link = main
        val devices = state()
        devices.loadSummary()
        assertNull(runBlocking { devices.rename("Máy ngủ") })
        assertEquals("Máy ngủ", source.deviceName)
        assertEquals("Máy ngủ", devices.summary.value.deviceName)
    }

    @Test
    fun `restoring at launch is passed to the core`() {
        state().restore()
        assertEquals(1, source.restores)
    }
}
