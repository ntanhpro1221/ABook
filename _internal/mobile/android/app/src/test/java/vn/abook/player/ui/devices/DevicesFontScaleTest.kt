package vn.abook.player.ui.devices

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.assertNoTextOverflow
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Ba màn Thiết bị khi người dùng đặt cỡ chữ hệ thống 1.3: dòng phụ (14) to lên mà mọi chữ vẫn xuống dòng, không bị cắt. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi", fontScale = 1.3f)
class DevicesFontScaleTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val sheets = SheetHost()
    private val source = FakeDevicesSource()
    private val main = Link(paired = true, name = "Máy bàn", host = "192.168.1.20", via = "192.168.1.20:47630", deviceName = "Điện thoại của tôi")

    private fun book(id: String, title: String, downloaded: Boolean = false, newChapters: Int = 0) = RemoteBook(
        id = id, title = title, chaptersAvailable = 12 + newChapters, chaptersTotal = 40, duration = 12 * 3600.0, bytes = 380L * 1024 * 1024,
        downloaded = downloaded, newChapters = newChapters,
    )

    private fun show(page: DevicesPage): Int {
        val devices = DevicesState(source, CoroutineScope(Dispatchers.Unconfined), DeviceLinks(), pollMs = 3_600_000)
        rule.setContent {
            AbookTheme(false) {
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
        return rule.assertNoTextOverflow()
    }

    @Test
    fun pairedScreenKeepsEveryWord() {
        source.link = main
        source.remote = RemoteLibrary("Máy bàn", listOf(book("a", "Tắt đèn"), book("c", "Chiến tranh và hòa bình - bản dịch đầy đủ có chú giải", downloaded = true, newChapters = 3)))
        source.peers = listOf(PeerLibrary(Paired("p1", "Máy xách tay trong phòng ngủ", DeviceKind.Computer, via = "192.168.1.30:47630", reach = Reach.Ok, books = 1, host = "192.168.1.30"), emptyList()))
        assertTrue(show(DevicesPage.Pair) > 4)
    }

    @Test
    fun shareScreenKeepsEveryWord() {
        source.share = Share(
            running = true, name = "Điện thoại của tôi", port = 47631, addresses = listOf("192.168.1.9"), code = Code("482915", 1_700_000_600.0),
            devices = listOf(Sharer("d1", "Máy bàn của nhà", 1_700_000_000.0)), bluetooth = "running", bluetoothConnections = 1,
        )
        assertTrue(show(DevicesPage.Share) > 4)
    }

    @Test
    fun storageScreenKeepsEveryWord() {
        source.storage = Storage(
            bytes = 1_700L * 1024 * 1024, free = 22L * 1024 * 1024 * 1024,
            entries = listOf(
                Stored("a", "Chiến tranh và hòa bình - bản dịch đầy đủ có chú giải của nhà xuất bản", 900L * 1024 * 1024, false),
                Stored("c", "Nhà giả kim", 150L * 1024 * 1024, true, "Máy bàn"),
            ),
        )
        assertTrue(show(DevicesPage.Storage) > 4)
    }
}
