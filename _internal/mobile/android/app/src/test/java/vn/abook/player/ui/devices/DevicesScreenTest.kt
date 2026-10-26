package vn.abook.player.ui.devices

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.hasAnyAncestor
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performTextReplacement
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.assertIconLedTextColumns
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.data.FakeSettingsCore
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.screens.SettingsGroupScreen
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.ThemeReveal

/**
 * Ba màn Thiết bị trên JVM với nguồn giả: ảnh chụp (Roborazzi) từng trạng thái sáng / tối - chưa nối, chọn máy, đang ghép, ghép lỗi, đã nối kèm sách đang tải,
 * chia sẻ đang bật, dung lượng - các bảng trượt, và kịch bản bấm thật; cộng luật căn hàng: biểu tượng đầu hàng và phần cuối hàng cùng thẳng dòng đầu của tên.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class DevicesScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val sheets = SheetHost()
    private val source = FakeDevicesSource()
    private lateinit var devices: DevicesState
    private var studio: Pair<String, String>? = null
    private var settingsOpened = 0
    private var opened: DevicesPage? = null

    private val main = Link(paired = true, name = "Máy bàn", host = "192.168.1.20", via = "192.168.1.20:47630", deviceName = "Điện thoại của tôi")
    private val bàn = Found("192.168.1.20:47630", "Máy bàn của nhà", DeviceKind.Computer)
    private val xáchTay = Found("192.168.1.21:47630", "Máy xách tay", DeviceKind.Computer)

    private fun book(id: String, title: String, downloaded: Boolean = false, newChapters: Int = 0) = RemoteBook(
        id = id, title = title, chaptersAvailable = 12 + newChapters, chaptersTotal = 40, duration = 12 * 3600.0, bytes = 380L * 1024 * 1024,
        downloaded = downloaded, newChapters = newChapters,
    )

    private fun peer(key: String, name: String, reach: Reach = Reach.Ok, books: List<RemoteBook> = emptyList()) =
        PeerLibrary(Paired(key, name, DeviceKind.Computer, via = "192.168.1.30:47630", reach = reach, books = books.size, host = "192.168.1.30"), books)

    private fun makeDevices() = DevicesState(
        source, CoroutineScope(Dispatchers.Unconfined),
        DeviceLinks(openStudio = { computer, path -> studio = computer to path }, openAppSettings = { settingsOpened++ }),
        pollMs = 3_600_000,
    )

    private fun show(page: DevicesPage, dark: Boolean = false) {
        devices = makeDevices()
        rule.setContent {
            AbookTheme(dark) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    when (page) {
                        DevicesPage.Pair -> PairScreen(devices, sheets) {}
                        DevicesPage.Share -> ShareScreen(devices, sheets) {}
                        DevicesPage.Storage -> StorageScreen(devices, sheets) {}
                    }
                    SheetLayer(sheets)
                }
            }
        }
        rule.waitForIdle()
    }

    private fun ui(block: () -> Unit) {
        rule.runOnUiThread(block)
        rule.waitForIdle()
    }

    private fun shot(name: String) {
        rule.assertIconLedTextColumns()
        rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")
    }

    private fun theme(dark: Boolean) = if (dark) "dark" else "light"

    private fun tap(tag: String) {
        rule.onNodeWithTag(tag).performClick()
        rule.waitForIdle()
    }

    // ---- Nối máy tính: ảnh chụp ----

    private fun pairEmpty(dark: Boolean) {
        source.link = Link(deviceName = "Điện thoại của tôi")
        show(DevicesPage.Pair, dark)
        rule.onNodeWithTag("pair_method").assertIsDisplayed()
        rule.onNodeWithTag("pair_none").assertIsDisplayed()
        rule.onNodeWithTag("pair_connect").assertIsDisplayed()
        shot("devices_pair_empty_${theme(dark)}")
    }

    @Test fun pairEmptyLight() = pairEmpty(false)
    @Test fun pairEmptyDark() = pairEmpty(true)

    private fun pairPick(dark: Boolean) {
        source.found = listOf(bàn, xáchTay)
        show(DevicesPage.Pair, dark)
        tap("found_${bàn.address}")
        rule.onNodeWithTag("pair_code").assertIsDisplayed()
        rule.onNodeWithTag("pair_code").performTextInput("482")
        rule.waitForIdle()
        rule.onNodeWithTag("found_${bàn.address}").assertIsSelected()
        shot("devices_pair_pick_${theme(dark)}")
    }

    @Test fun pairPickLight() = pairPick(false)
    @Test fun pairPickDark() = pairPick(true)

    private fun pairWorking(dark: Boolean) {
        source.found = listOf(bàn)
        source.pairGate = CompletableDeferred()
        show(DevicesPage.Pair, dark)
        ui { devices.setCode("482915") }
        rule.mainClock.autoAdvance = false
        tap("pair_connect")
        rule.mainClock.advanceTimeBy(3000)
        rule.onNodeWithTag("pair_working").assertIsDisplayed()
        rule.onNodeWithText("Đang nối Máy bàn của nhà").assertIsDisplayed()
        shot("devices_pair_working_${theme(dark)}")
        rule.mainClock.autoAdvance = true
        source.pairGate!!.complete(Unit)
        rule.waitForIdle()
    }

    @Test fun pairWorkingLight() = pairWorking(false)
    @Test fun pairWorkingDark() = pairWorking(true)

    private fun pairFailed(dark: Boolean) {
        source.found = listOf(bàn)
        source.pairError = DeviceFailure("Mã chưa đúng - bạn nhập lại, hoặc tạo mã mới trên máy tính.")
        show(DevicesPage.Pair, dark)
        ui { devices.setCode("000000") }
        tap("pair_connect")
        rule.onNodeWithTag("pair_problem").assertIsDisplayed()
        rule.onNodeWithTag("pair_problem-retry").assertIsDisplayed()
        shot("devices_pair_failed_${theme(dark)}")
    }

    @Test fun pairFailedLight() = pairFailed(false)
    @Test fun pairFailedDark() = pairFailed(true)

    private fun pairedScene() {
        source.link = main
        source.remote = RemoteLibrary(
            "Máy bàn",
            listOf(book("a", "Tắt đèn"), book("c", "Chiến tranh và hòa bình - bản dịch đầy đủ có chú giải", downloaded = true, newChapters = 3), book("d", "Nhà giả kim"), book("e", "Dế Mèn phiêu lưu ký")),
        )
        source.peers = listOf(peer("p1", "Máy xách tay trong phòng ngủ", books = listOf(book("p1:9", "Số đỏ"))), peer("p2", "Máy kho", Reach.Offline("x")))
        source.studio = listOf(StudioComputer(MAIN_KEY, "Máy bàn", listenOnly = false))
    }

    private fun pairPaired(dark: Boolean) {
        pairedScene()
        show(DevicesPage.Pair, dark)
        ui { devices.download(devices.pair.value.sections.first().books.first { it.id == "d" }) }
        source.events.tryEmit(DownloadEvent("d", 0.4f))
        source.events.tryEmit(DownloadEvent("e", 0.2f, error = "Mất mạng giữa chừng."))
        rule.waitForIdle()
        rule.onNodeWithTag("device_main").assertIsDisplayed()
        rule.onNodeWithTag("device_p2").assertIsDisplayed()
        rule.onNodeWithTag("cancel_d").assertIsDisplayed()
        shot("devices_pair_paired_${theme(dark)}")
    }

    @Test @Config(sdk = [35], qualifiers = "w360dp-h1100dp-xxhdpi") fun pairPairedLight() = pairPaired(false)
    @Test @Config(sdk = [35], qualifiers = "w360dp-h1100dp-xxhdpi") fun pairPairedDark() = pairPaired(true)

    // ---- Chia sẻ thư viện ----

    private fun shareOn(dark: Boolean) {
        source.share = Share(
            running = true, name = "Điện thoại của tôi", port = 47631, addresses = listOf("192.168.1.9"), code = Code("482915", 1_700_000_600.0),
            devices = listOf(Sharer("d1", "Máy bàn của nhà", 1_700_000_000.0), Sharer("d2", "Điện thoại của chị", 1_699_000_000.0)),
            bluetooth = "running", bluetoothConnections = 1,
        )
        show(DevicesPage.Share, dark)
        rule.onNodeWithTag("share_switch").assertIsDisplayed()
        rule.onNodeWithTag("share_code").assertIsDisplayed()
        rule.onNodeWithTag("sharer_d1").assertIsDisplayed()
        shot("devices_share_on_${theme(dark)}")
    }

    @Test fun shareOnLight() = shareOn(false)
    @Test fun shareOnDark() = shareOn(true)

    private fun shareOff(dark: Boolean) {
        source.share = Share(devices = listOf(Sharer("d1", "Máy bàn của nhà", 1_700_000_000.0)))
        show(DevicesPage.Share, dark)
        rule.onNodeWithTag("share_address").assertDoesNotExist()
        shot("devices_share_off_${theme(dark)}")
    }

    @Test fun shareOffLight() = shareOff(false)
    @Test fun shareOffDark() = shareOff(true)

    // ---- Dung lượng ----

    private val stored = Storage(
        bytes = 1_700L * 1024 * 1024, free = 22L * 1024 * 1024 * 1024,
        entries = listOf(
            Stored("a", "Chiến tranh và hòa bình - bản dịch đầy đủ có chú giải của nhà xuất bản", 900L * 1024 * 1024, false),
            Stored("b", "Tắt đèn", 600L * 1024 * 1024, false),
            Stored("c", "Nhà giả kim", 150L * 1024 * 1024, true, "Máy bàn"),
            Stored("d", "Sách tải dở", 50L * 1024 * 1024, true),
        ),
    )

    private fun storageList(dark: Boolean) {
        source.storage = stored
        show(DevicesPage.Storage, dark)
        rule.onNodeWithTag("storage_total").assertIsDisplayed()
        rule.onNodeWithTag("stored_a").assertIsDisplayed()
        shot("devices_storage_${theme(dark)}")
    }

    @Test fun storageLight() = storageList(false)
    @Test fun storageDark() = storageList(true)

    @Test
    fun storageEmpty() {
        source.storage = Storage(bytes = 0, free = 22L * 1024 * 1024 * 1024)
        show(DevicesPage.Storage)
        rule.onNodeWithTag("storage_empty").assertIsDisplayed()
        shot("devices_storage_empty_light")
    }

    // ---- bảng trượt ----

    @Test
    fun deviceSheetLists() {
        pairedScene()
        show(DevicesPage.Pair)
        tap("device_main")
        rule.onNodeWithTag("device_sheet").assertIsDisplayed()
        rule.onNodeWithTag("device_studio").assertIsDisplayed()
        shot("devices_sheet_device_light")
    }

    @Test
    fun forgetSheetSaysWhatIsLost() {
        pairedScene()
        source.unsent = Unsent(listOf(UnsentBook("Số đỏ", 2)), 2, sendable = true, cacheBooks = 1, cacheBytes = 40L * 1024 * 1024)
        show(DevicesPage.Pair, dark = true)
        tap("device_p1")
        tap("device_forget")
        rule.onNodeWithTag("forget_confirm").assertIsDisplayed()
        rule.onNodeWithTag("forget_send").assertIsDisplayed()
        shot("devices_sheet_forget_dark")
    }

    @Test
    fun renameAndRevokeAndDeleteSheets() {
        source.link = main
        source.share = Share(running = true, devices = listOf(Sharer("d1", "Máy bàn của nhà", 1_700_000_000.0)), addresses = listOf("192.168.1.9"), port = 47631)
        show(DevicesPage.Share)
        tap("sharer_d1")
        rule.onNodeWithTag("revoke_confirm").assertIsDisplayed()
        shot("devices_sheet_revoke_light")
    }

    // ---- kịch bản ----

    @Test
    fun pickingAComputerRevealsTheCodeAndConnectNeedsSixDigits() {
        source.found = listOf(bàn, xáchTay)
        show(DevicesPage.Pair)
        rule.onNodeWithTag("pair_code").assertDoesNotExist()
        tap("found_${bàn.address}")
        rule.onNodeWithTag("pair_code").performTextInput("1234")
        rule.waitForIdle()
        tap("pair_connect")
        assertTrue("chưa đủ 6 số thì không ghép", source.pairs.isEmpty())
        rule.onNodeWithTag("pair_code").performTextInput("56")
        rule.waitForIdle()
        tap("pair_connect")
        assertEquals(listOf(Triple(bàn.address, "123456", false)), source.pairs)
        rule.onNodeWithTag("device_main").assertIsDisplayed()
        rule.onNodeWithTag("pair_connect").assertDoesNotExist()
        rule.onNodeWithTag("pair_add").assertIsDisplayed()
    }

    @Test
    fun theMethodRowSwitchesBetweenWifiBluetoothAndAddress() {
        source.found = listOf(bàn, xáchTay)
        source.bluetooth = listOf(Found("bt:AA:BB", "Máy qua Bluetooth", DeviceKind.Computer, bluetooth = true))
        show(DevicesPage.Pair)
        rule.onNodeWithTag("pair_method_wifi").assertIsSelected()
        tap("pair_method_bluetooth")
        rule.onNodeWithTag("found_bt:AA:BB").assertIsDisplayed()
        rule.onNodeWithTag("found_${bàn.address}").assertDoesNotExist()
        tap("pair_method_address")
        rule.onNodeWithTag("pair_address").assertIsDisplayed()
        rule.onNodeWithTag("found_bt:AA:BB").assertDoesNotExist()
        rule.onNodeWithTag("pair_address").performTextInput("192.168.1.20")
        tap("pair_method_wifi")
        rule.onNodeWithTag("found_${xáchTay.address}").assertIsDisplayed()
    }

    @Test
    fun aRefusedBluetoothPermissionPointsToSettings() {
        source.nearby = false
        devices = DevicesState(source, CoroutineScope(Dispatchers.Unconfined), DeviceLinks(askNearby = { it(false) }, openAppSettings = { settingsOpened++ }), pollMs = 3_600_000)
        rule.setContent {
            AbookTheme(false) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { PairScreen(devices, sheets) {}; SheetLayer(sheets) } }
        }
        rule.waitForIdle()
        tap("pair_method_bluetooth")
        rule.onNodeWithTag("pair_denied").assertIsDisplayed()
        tap("pair_open_settings")
        assertEquals(1, settingsOpened)
        shot("devices_pair_bluetooth_denied_light")
    }

    @Test
    fun forgettingADeviceFromItsSheet() {
        pairedScene()
        show(DevicesPage.Pair)
        tap("device_p1")
        tap("device_forget")
        tap("forget_yes")
        assertEquals(listOf("p1" to ForgetChoice.Plain), source.forgets)
        rule.onNodeWithTag("device_p1").assertDoesNotExist()
        rule.onNodeWithTag("device_sheet").assertDoesNotExist()
        rule.onNodeWithTag("device_main").assertIsDisplayed()
    }

    @Test
    fun forgetCanSendUnsentEditsFirst() {
        pairedScene()
        source.unsent = Unsent(listOf(UnsentBook("Số đỏ", 2)), 2, sendable = true)
        show(DevicesPage.Pair)
        tap("device_p1")
        tap("device_forget")
        tap("forget_send")
        assertEquals(listOf("p1" to ForgetChoice.Send), source.forgets)
        rule.onNodeWithTag("device_p1").assertDoesNotExist()
    }

    @Test
    fun keepingADeviceLeavesItAlone() {
        pairedScene()
        show(DevicesPage.Pair)
        tap("device_p1")
        tap("device_forget")
        tap("forget_keep")
        rule.onNodeWithTag("device_forget").assertIsDisplayed()
        assertTrue(source.forgets.isEmpty())
    }

    @Test
    fun aRefusedForgetShowsTheWordsInTheSheet() {
        pairedScene()
        source.forgetError = DeviceFailure("Còn thay đổi chưa gửi.")
        show(DevicesPage.Pair)
        tap("device_p1")
        tap("device_forget")
        tap("forget_yes")
        rule.onNodeWithText("Còn thay đổi chưa gửi.").assertIsDisplayed()
        rule.onNodeWithTag("device_p1").assertIsDisplayed()
    }

    @Test
    fun unpairingTheMainComputerFromItsSheet() {
        pairedScene()
        show(DevicesPage.Pair)
        tap("device_main")
        tap("device_forget")
        tap("forget_yes")
        assertEquals(1, source.unpairs)
        rule.onNodeWithTag("device_main").assertDoesNotExist()
        rule.onNodeWithTag("pair_connect").assertIsDisplayed()
    }

    @Test
    fun studioOpensFromTheSheet() {
        pairedScene()
        source.target = "Máy bàn" to "/studio"
        show(DevicesPage.Pair)
        tap("device_main")
        tap("device_studio")
        assertEquals("Máy bàn" to "/studio", studio)
        rule.onNodeWithTag("device_sheet").assertDoesNotExist()
    }

    @Test
    fun aListenOnlyComputerExplainsItselfInsteadOfOpeningStudio() = listenOnly(false)

    @Test fun listenOnlyDeviceDark() = listenOnly(true)

    private fun listenOnly(dark: Boolean) {
        pairedScene()
        source.studio = listOf(StudioComputer(MAIN_KEY, "Máy bàn", listenOnly = true))
        show(DevicesPage.Pair, dark)
        tap("device_main")
        rule.onNodeWithText(DeviceText.listenOnly("Máy bàn"), useUnmergedTree = true).assertIsDisplayed()
        rule.assertIconLedTextColumns()
        tap("device_studio")
        assertEquals(null, studio)
        shot("gap1c_device_listen_only_${theme(dark)}")
    }

    @Test
    fun aBookDownloadsWithItsOwnProgressAndCancels() {
        pairedScene()
        show(DevicesPage.Pair)
        tap("download_a")
        assertEquals(listOf("a"), source.downloads)
        rule.onNodeWithTag("cancel_a").assertIsDisplayed()
        rule.onNodeWithTag("download_a").assertDoesNotExist()
        source.events.tryEmit(DownloadEvent("a", 0.5f))
        rule.waitForIdle()
        tap("cancel_a")
        assertEquals(listOf("a"), source.cancels)
        source.events.tryEmit(DownloadEvent("a", 0.5f, cancelled = true))
        rule.waitForIdle()
        rule.onNodeWithTag("download_a").assertIsDisplayed()
    }

    @Test
    fun aFailedDownloadOffersRetryOnTheFirstLine() {
        pairedScene()
        show(DevicesPage.Pair)
        source.events.tryEmit(DownloadEvent("e", 0.2f, error = "Mất mạng giữa chừng."))
        rule.waitForIdle()
        rule.onNodeWithTag("pair_list").performScrollToNode(hasTestTag("book_e"))
        rule.onNodeWithText("Mất mạng giữa chừng.").assertIsDisplayed()
        assertFirstLine("book_e", trailing = true)
        tap("download_e")
        assertEquals(listOf("e"), source.downloads)
    }

    // ---- chia sẻ: kịch bản ----

    @Test
    fun theSwitchTurnsSharingOnAndOff() {
        source.share = Share(port = 47631, addresses = listOf("192.168.1.9"))
        show(DevicesPage.Share)
        rule.onNodeWithTag("share_address").assertDoesNotExist()
        tap("share_switch")
        assertTrue(source.share.running)
        rule.onNodeWithTag("share_address").assertIsDisplayed()
        rule.onNodeWithTag("share_new_code").assertIsDisplayed()
        tap("share_switch")
        assertFalse(source.share.running)
        rule.onNodeWithTag("share_address").assertDoesNotExist()
    }

    @Test
    fun aFailedSwitchSaysWhyAndStaysOff() {
        source.share = Share()
        source.shareError = DeviceFailure("Chưa vào mạng Wi-Fi nào.")
        show(DevicesPage.Share)
        tap("share_switch")
        rule.onNodeWithTag("share_problem").assertIsDisplayed()
        rule.onNodeWithText("Chưa vào mạng Wi-Fi nào.").assertIsDisplayed()
        assertFalse(source.share.running)
        shot("devices_share_failed_light")
    }

    @Test
    fun aCodeIsMadeAndCancelled() {
        source.share = Share(running = true, port = 47631, addresses = listOf("192.168.1.9"))
        show(DevicesPage.Share)
        tap("share_new_code")
        rule.onNodeWithTag("share_code").assertIsDisplayed()
        rule.onNodeWithText("482 915").assertIsDisplayed()
        tap("share_cancel_code")
        rule.onNodeWithTag("share_code").assertDoesNotExist()
        rule.onNodeWithTag("share_new_code").assertIsDisplayed()
    }

    @Test
    fun aListenerIsRevokedAfterAConfirmation() {
        source.share = Share(running = true, port = 1, addresses = listOf("192.168.1.9"), devices = listOf(Sharer("d1", "Máy bàn", 1_700_000_000.0), Sharer("d2", "Máy khách", 1_700_000_000.0)))
        show(DevicesPage.Share)
        tap("sharer_d1")
        tap("revoke_keep")
        assertEquals(2, source.share.devices.size)
        tap("sharer_d1")
        tap("revoke_yes")
        assertEquals(listOf("d2"), source.share.devices.map { it.id })
        rule.onNodeWithTag("sharer_d1").assertDoesNotExist()
        rule.onNodeWithTag("sharer_d2").assertIsDisplayed()
    }

    @Test
    fun missingNearbyPermissionAndBackgroundShowTheirRowsOnlyWhenSharingIsOn() {
        source.share = Share(running = true, port = 1, addresses = listOf("192.168.1.9"), bluetooth = "Cần quyền Thiết bị ở gần", backgroundAllowed = false)
        show(DevicesPage.Share)
        rule.onNodeWithTag("share_nearby").assertIsDisplayed()
        rule.onNodeWithTag("share_background").assertIsDisplayed()
        tap("share_open_settings")
        assertEquals(1, settingsOpened)
        shot("devices_share_notes_light")
    }

    // ---- dung lượng: kịch bản ----

    @Test
    fun deleteAsksFirstThenUsesTheBookCore() {
        source.storage = stored
        show(DevicesPage.Storage)
        tap("stored_b")
        rule.onNodeWithTag("delete_confirm").assertIsDisplayed()
        rule.onNodeWithText("“Tắt đèn” sẽ bị xoá khỏi máy này. Muốn nghe lại, bạn cần thêm lại file sách.").assertIsDisplayed()
        shot("devices_sheet_delete_light")
        tap("delete_keep")
        assertTrue(source.deleted.isEmpty())
        tap("stored_b")
        tap("delete_yes")
        assertEquals(listOf("b"), source.deleted)
        rule.onNodeWithTag("stored_b").assertDoesNotExist()
        rule.onNodeWithTag("stored_a").assertIsDisplayed()
    }

    @Test
    fun aPartialThingSaysWhereTheBookStillIs() {
        source.storage = stored
        show(DevicesPage.Storage)
        tap("stored_c")
        rule.onNodeWithText("Phần đã tải của “Nhà giả kim” sẽ bị xoá khỏi máy này. Sách vẫn còn trên Máy bàn.").assertIsDisplayed()
    }

    @Test
    fun aFailedDeleteKeepsTheRowAndSaysWhy() {
        source.storage = stored
        source.deleteError = "Chưa xoá được."
        show(DevicesPage.Storage)
        tap("stored_b")
        tap("delete_yes")
        rule.onNodeWithTag("delete_confirm_problem").assertIsDisplayed()
        rule.onNodeWithTag("stored_b").assertIsDisplayed()
    }

    @Test
    fun aThingBeingDownloadedCannotBeDeleted() {
        source.storage = stored
        show(DevicesPage.Storage)
        ui { devices.download(RemoteBook("a", title = "Tắt đèn")) }
        rule.onNodeWithText("Đang tải").assertIsDisplayed()
        tap("stored_a")
        rule.onNodeWithTag("delete_confirm").assertDoesNotExist()
    }

    // ---- trang nhóm Thiết bị ----

    private fun group(dark: Boolean = false, withDevices: Boolean = true) {
        source.link = main
        source.remote = RemoteLibrary("Máy bàn", emptyList())
        source.share = Share(running = true, devices = listOf(Sharer("d1", "Máy khách", 0.0)))
        source.storage = Storage(300L * 1024 * 1024, 10L * 1024 * 1024 * 1024)
        devices = makeDevices()
        val core = FakeSettingsCore()
        val repo = SettingsRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined)
        runBlocking { repo.load() }
        rule.setContent {
            val scope = rememberCoroutineScope()
            val env = remember { SettingsEnv(repo, ThemeReveal(scope), devices = if (withDevices) devices else null) }
            AbookTheme(dark) {
                Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    SettingsGroupScreen(SettingsGroup.Devices, env, sheets, onBack = {}, openDevices = { opened = it })
                    SheetLayer(sheets)
                }
            }
        }
        rule.waitForIdle()
    }

    @Test
    fun groupPageShowsOneValueLineForEachScreenLight() {
        group()
        rule.onNodeWithText("Đã nối Máy bàn").assertIsDisplayed()
        rule.onNodeWithText("Đang bật · 1 máy").assertIsDisplayed()
        rule.onNodeWithText("Sách 300 MB · còn trống 10 GB").assertIsDisplayed()
        rule.onNodeWithText("Điện thoại của tôi").assertIsDisplayed()
        shot("settings_devices_filled_light")
    }

    @Test
    fun groupPageShowsOneValueLineForEachScreenDark() {
        group(dark = true)
        rule.onNodeWithText("Đã nối Máy bàn").assertIsDisplayed()
        shot("settings_devices_filled_dark")
    }

    @Test
    fun groupPageRowsOpenTheirScreens() {
        group()
        tap("devices_pair")
        assertEquals(DevicesPage.Pair, opened)
        tap("devices_share")
        assertEquals(DevicesPage.Share, opened)
        tap("devices_storage")
        assertEquals(DevicesPage.Storage, opened)
    }

    @Test
    fun renamingThePhoneGoesToTheCoreAndShowsOnTheRow() {
        group()
        tap("devices_name")
        rule.onNodeWithTag("rename_sheet").assertIsDisplayed()
        shot("devices_sheet_rename_light")
        rule.onNodeWithTag("rename_field").performTextReplacement("Máy ngủ")
        rule.waitForIdle()
        tap("rename_save")
        assertEquals("Máy ngủ", source.deviceName)
        rule.onNodeWithTag("rename_sheet").assertDoesNotExist()
        rule.onNodeWithText("Máy ngủ").assertIsDisplayed()
    }

    @Test
    fun groupPageWithoutACoreStillDrawsItsRows() {
        group(withDevices = false)
        for (tag in listOf("devices_pair", "devices_share", "devices_storage", "devices_name")) rule.onNodeWithTag(tag).assertIsDisplayed()
        rule.onNodeWithText("Nối máy tính").assertIsDisplayed()
    }

    // ---- căn hàng: biểu tượng đầu hàng và phần cuối hàng cùng thẳng dòng đầu của tên ----

    /** Tâm của `row_leading` / `row_trailing` trong hàng `tag` trùng tâm dòng chữ đầu của tên (đỉnh tên + 12), kể cả khi tên xuống dòng. */
    private fun assertFirstLine(tag: String, leading: Boolean = false, trailing: Boolean = false) {
        val title = rule.onNode(hasTestTag("row_title") and hasAnyAncestor(hasTestTag(tag)), useUnmergedTree = true).getUnclippedBoundsInRoot()
        val sides = listOfNotNull("row_leading".takeIf { leading }, "row_trailing".takeIf { trailing })
        assertTrue("$tag: không có bên nào để kiểm", sides.isNotEmpty())
        for (side in sides) {
            val edge = rule.onNode(hasTestTag(side) and hasAnyAncestor(hasTestTag(tag)), useUnmergedTree = true).getUnclippedBoundsInRoot()
            val center = (edge.top + edge.bottom) / 2
            assertTrue("$tag/$side: tâm dòng đầu ${title.top + 12.dp}, tâm $center", ((title.top + 12.dp) - center).value in -0.6f..0.6f)
        }
    }

    /** Thanh tiến độ của hàng chạy từ cột chữ tới mép phải của hàng (bằng đường kẻ), qua cả cột hành động; "Huỷ tải" vẫn ở dòng đầu. */
    @Test
    fun aProgressBarRunsToTheRightEdgeOfItsRow() {
        pairedScene()
        show(DevicesPage.Pair)
        tap("download_a")
        source.events.tryEmit(DownloadEvent("a", 0.5f))
        rule.waitForIdle()
        val row = rule.onNodeWithTag("book_a", useUnmergedTree = true).getUnclippedBoundsInRoot()
        val bar = rule.onNode(hasTestTag("row_below") and hasAnyAncestor(hasTestTag("book_a")), useUnmergedTree = true).getUnclippedBoundsInRoot()
        val title = rule.onNode(hasTestTag("row_title") and hasAnyAncestor(hasTestTag("book_a")), useUnmergedTree = true).getUnclippedBoundsInRoot()
        assertTrue("thanh ${bar.right} phải tới mép phải hàng ${row.right}", (row.right - bar.right).value in -0.6f..0.6f)
        assertTrue("thanh bắt đầu cùng cột chữ", (bar.left - title.left).value in -0.6f..0.6f)
        assertFirstLine("book_a", trailing = true)
    }

    @Test
    fun foundRowsShareTheFirstLine() {
        source.found = listOf(Found("192.168.1.20:47630", "Máy tính ở phòng khách của nhà bà ngoại trong khu tập thể cũ", DeviceKind.Computer), xáchTay)
        show(DevicesPage.Pair)
        tap("found_192.168.1.20:47630")
        assertFirstLine("found_192.168.1.20:47630", leading = true, trailing = true)
        assertFirstLine("found_${xáchTay.address}", leading = true)
    }

    @Test
    fun bluetoothFoundRowsShareTheFirstLine() {
        source.bluetooth = listOf(Found("bt:AA:BB", "Máy qua Bluetooth", DeviceKind.Computer, bluetooth = true))
        show(DevicesPage.Pair)
        tap("pair_method_bluetooth")
        assertFirstLine("found_bt:AA:BB", leading = true)
    }

    @Test
    fun deviceRowsShareTheFirstLineWithChevronAndRetry() {
        source.link = main.copy(name = "Máy tính ở phòng khách của nhà bà ngoại trong khu tập thể cũ")
        source.remote = RemoteLibrary("x", emptyList())
        source.peers = listOf(peer("p2", "Máy kho", Reach.Offline("x")))
        show(DevicesPage.Pair)
        assertFirstLine("device_main", leading = true, trailing = true)
        assertFirstLine("device_p2", leading = true, trailing = true)
        rule.onNodeWithTag("retry_p2").assertIsDisplayed()
    }

    @Test
    fun bookRowsShareTheFirstLineForEveryButton() {
        pairedScene()
        show(DevicesPage.Pair)
        ui { devices.download(devices.pair.value.sections.first().books.first { it.id == "d" }) }
        for (id in listOf("a", "c", "d")) assertFirstLine("book_$id", trailing = true)
    }

    @Test
    fun sharerAndCodeRowsShareTheFirstLine() {
        source.share = Share(
            running = true, port = 1, addresses = listOf("192.168.1.9"), code = Code("482915", 1_700_000_600.0),
            devices = listOf(Sharer("d1", "Máy tính ở phòng khách của nhà bà ngoại trong khu tập thể cũ", 1_700_000_000.0)),
        )
        show(DevicesPage.Share)
        assertFirstLine("sharer_d1", leading = true, trailing = true)
        assertFirstLine("share_code", trailing = true)
    }

    @Test
    fun storedRowsShareTheFirstLineWithTheirSize() {
        source.storage = stored
        show(DevicesPage.Storage)
        for (id in listOf("a", "b", "c")) assertFirstLine("stored_$id", trailing = true)
    }
}
