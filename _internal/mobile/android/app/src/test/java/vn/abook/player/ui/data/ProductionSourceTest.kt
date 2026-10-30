package vn.abook.player.ui.data

import androidx.test.core.app.ApplicationProvider
import java.net.InetAddress
import java.net.ServerSocket
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.Peers
import vn.abook.player.StudioLink

/**
 * Thư viện native biết máy tính đang làm cuốn nào (GET /api/listen/library trả MẢNG): đi qua SyncLink.request thật tới một máy giả trên vòng lặp.
 * Trước khi SyncLink nhận mảng, lời gọi ném và bị nuốt - Thư viện không bao giờ thấy trạng thái "đang làm".
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ProductionSourceTest {
    private val context = ApplicationProvider.getApplicationContext<android.content.Context>()
    private lateinit var server: ServerSocket
    private var body = "[]"
    private var status = 200
    private val paths = ArrayList<String>()

    @Before fun start() {
        server = ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"))
        Thread {
            while (!server.isClosed) {
                val socket = runCatching { server.accept() }.getOrNull() ?: break
                socket.use {
                    val reader = it.getInputStream().bufferedReader()
                    paths += reader.readLine().split(" ")[1]
                    while (reader.readLine().orEmpty().isNotEmpty()) { /* tới dòng trống cuối đầu yêu cầu */ }
                    val bytes = body.toByteArray()
                    it.getOutputStream().write(("HTTP/1.1 $status X\r\nContent-Type: application/json\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n").toByteArray() + bytes)
                }
            }
        }.apply { isDaemon = true }.start()
    }

    @After fun stop() = server.close()

    private val link get() = Peers.Link("http://127.0.0.1:${server.localPort}", "t")
    private val pc = StudioLink.Computer(StudioLink.MAIN, "Máy bàn")
    private val laptop = StudioLink.Computer("b2", "Laptop")

    private fun source(vararg computers: StudioLink.Computer, linked: (String) -> Peers.Link? = { link }) =
        ProductionSource(context, computers = { computers.toList() }, link = linked)

    @Test fun theArrayAComputerSendsReachesTheLibrary() {
        body = """[{"id":"b1","producing":true,"paused":false,"eta":{"phase":"analysis","seconds":300.0}},
            {"id":"b2","producing":true,"paused":true,"pauseReason":"battery"},{"id":"b3","producing":false}]"""
        val read = source(pc).read()
        assertEquals(listOf("/api/listen/library"), paths)
        assertEquals(setOf(StudioLink.MAIN to "b1", StudioLink.MAIN to "b2", StudioLink.MAIN to "b3"), read.keys)
        val first = read.getValue(StudioLink.MAIN to "b1")
        assertTrue(first.producing)
        assertEquals("analysis", first.etaPhase)
        assertEquals(300.0, first.etaSeconds!!, 0.0)
        assertEquals("battery", read.getValue(StudioLink.MAIN to "b2").pauseReason)
        assertEquals(false, read.getValue(StudioLink.MAIN to "b3").producing)
    }

    @Test fun eachComputerKeepsItsOwnBooksAndADeadOneIsSkipped() {
        body = """[{"id":"b1","producing":true}]"""
        val read = source(pc, laptop) { key -> if (key == "b2") null else link }.read()
        assertEquals(setOf(StudioLink.MAIN to "b1"), read.keys)
    }

    @Test fun anErrorOrANonArrayAnswerLeavesTheLibraryUntouched() {
        status = 500
        body = """{"error":"hỏng"}"""
        assertTrue(source(pc).read().isEmpty())
        status = 200
        body = "17"
        assertTrue(source(pc).read().isEmpty())
        assertNotNull(paths.firstOrNull())
        assertNull(paths.firstOrNull { it != "/api/listen/library" })
    }
}
