package vn.abook.player.net

import androidx.test.core.app.ApplicationProvider
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.NetErrors
import vn.abook.player.StudioError
import vn.abook.player.StudioErrors
import vn.abook.player.SyncLink
import java.io.File

/**
 * Lời gọi THẬT của điện thoại tới máy đã ghép ([SyncLink.request]) với máy giả trên vòng lặp: im thì gửi lại một lần rồi báo "timeout"; tải về chậm mà đều thì không bị cắt; lỗi của
 * chính máy kia đi nguyên; hạn riêng của phép dò nhanh không gửi lại.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class HostWaitSyncTest {
    private val context = ApplicationProvider.getApplicationContext<android.content.Context>()

    @After fun reset() { HostWait.idleOverrideMs = 0 }

    private fun fast() { HostWait.idleOverrideMs = 300 }

    private fun get(host: FakeHost, path: String = "/api/listen/library", readTimeoutMs: Int? = null): String =
        SyncLink.request(context, "GET", path, auth = false, root = host.base, token = "t", readTimeoutMs = readTimeoutMs, connectTimeoutMs = 1000)

    @Test fun aSilentComputerGetsOneResendThenTimesOutAsTimeout() {
        fast()
        FakeHost(FakeHost.silent).use { host ->
            val started = System.nanoTime()
            val error = runCatching { get(host) }.exceptionOrNull()
            val seconds = (System.nanoTime() - started) / 1e9
            assertTrue("$error", error is HostWait.Timeout)
            assertEquals("timeout", (error as HostWait.Timeout).reason)
            assertEquals(NetErrors.Kind.TIMEOUT, NetErrors.kind(error))
            assertEquals(2, host.connections)
            assertTrue("$seconds s", seconds < 5)
        }
    }

    @Test fun aPostIsResentToo_theSameRequestOnce() {
        fast()
        val heads = ArrayList<String>()
        FakeHost { attempt, socket, head ->
            synchronized(heads) { heads += head }
            if (attempt == 1) FakeHost.silent(attempt, socket, head) else FakeHost.reply(socket, 200, """{"ok":true}""")
        }.use { host ->
            val text = SyncLink.request(context, "POST", "/api/books/b1/voice/preview", JSONObject().put("voice", "v"),
                auth = false, root = host.base, token = "t", connectTimeoutMs = 1000)
            assertEquals("""{"ok":true}""", text)
            assertEquals(2, host.connections)
            assertEquals(heads[0].substringBefore("\r\n"), heads[1].substringBefore("\r\n"))
            assertTrue(heads[0].startsWith("POST /api/books/b1/voice/preview "))
        }
    }

    @Test fun aSteadyTrickleLongerThanTheLimitIsNeverCut() {
        fast()
        val body = """{"ok":true}"""
        FakeHost { _, socket, _ ->
            socket.getOutputStream().apply {
                write("HTTP/1.1 200 X\r\nContent-Type: application/json\r\nContent-Length: ${body.length}\r\nConnection: close\r\n\r\n".toByteArray())
                flush()
                for (ch in body) { Thread.sleep(120); write(ch.code); flush() }
            }
        }.use { host ->
            assertEquals(body, get(host))
            assertEquals(1, host.connections)
        }
    }

    @Test fun theComputersOwnErrorPassesThroughAndIsNotResent() {
        fast()
        FakeHost { _, socket, _ -> FakeHost.reply(socket, 504, """{"error":"Microsoft trả lời quá chậm.","reason":"timeout"}""") }.use { host ->
            val error = runCatching { get(host, "/api/readaloud/clip") }.exceptionOrNull()
            assertTrue("$error", error is NetErrors.Refused)
            assertEquals(504, (error as NetErrors.Refused).code)
            assertEquals("Microsoft trả lời quá chậm.", error.message)
            assertEquals(1, host.connections)
            assertFalse(error is HostWait.Timeout)
        }
    }

    @Test fun aQuickProbeWithItsOwnLimitIsNotResent() {
        FakeHost(FakeHost.silent).use { host ->
            val error = runCatching { get(host, readTimeoutMs = 300) }.exceptionOrNull()
            assertTrue("$error", error is HostWait.Timeout)
            assertEquals(1, host.connections)
        }
    }

    @Test fun anUploadIsNotResentButItsStalledWriteIsCut() {
        fast()
        FakeHost { _, socket, _ -> Thread.sleep(8000); socket.close() }.use { host ->
            val started = System.nanoTime()
            val error = runCatching {
                SyncLink.request(context, "POST", "/api/sources/upload", auth = false, root = host.base, token = "t", connectTimeoutMs = 1000,
                    stream = { out -> val chunk = ByteArray(64 * 1024); repeat(4096) { out.write(chunk) } })
            }.exceptionOrNull()
            assertTrue("$error", error is HostWait.Timeout)
            assertEquals(1, host.connections)
            assertTrue((System.nanoTime() - started) / 1e9 < 6)
        }
    }

    @Test fun aFileUploadStallsTheSameWay() {
        fast()
        val file = File.createTempFile("upload", ".zip").apply { writeBytes(ByteArray(64 * 1024 * 1024)); deleteOnExit() }
        FakeHost { _, socket, _ -> Thread.sleep(8000); socket.close() }.use { host ->
            val error = runCatching {
                SyncLink.request(context, "POST", "/sync/v1/books/b/edits", auth = false, root = host.base, token = "t", connectTimeoutMs = 1000, upload = file)
            }.exceptionOrNull()
            assertTrue("$error", error is HostWait.Timeout)
            assertEquals(1, host.connections)
        }
    }

    @Test fun studioShowsTheTimeoutAsTheComputersOwnTimeoutNotAsOffline() {
        val failure = StudioErrors.of(HostWait.Timeout())
        assertTrue("$failure", failure is StudioError.Server)
        failure as StudioError.Server
        assertEquals(504, failure.status)
        assertEquals(HostWait.TIMEOUT_MESSAGE, failure.message)
        assertEquals("timeout", StudioErrors.detail(failure, "reason"))
        // Lỗi nối thật (máy tắt) vẫn là "không tới được".
        assertTrue(StudioErrors.of(java.net.ConnectException("refused")) is StudioError.Offline)
    }

    @Test fun aConnectionTimeoutStaysOfflineNotATimeoutOfTheComputer() {
        // Máy tắt: kết nối không bao giờ xong - hạn NỐI, không phải hạn "im lặng" của một máy đang sống.
        fast()
        val error = runCatching {
            SyncLink.request(context, "GET", "/x", auth = false, root = "http://10.255.255.1:9", token = "t", connectTimeoutMs = 400)
        }.exceptionOrNull()
        assertTrue("$error", error != null)
        assertFalse("$error", error is HostWait.Timeout)
    }
}
