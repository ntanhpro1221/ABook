package vn.abook.player

import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Đường hầm Bluetooth phía Android (BtMux.kt). Một cặp socket TCP đứng thay cho kết nối RFCOMM - giao thức khung, cửa sổ tín
 * dụng, đóng nửa chiều và đứt kết nối là của đường hầm. `BTMUX_PY_PORT`: cổng của một đầu Python (webui/bluetooth.py) đang
 * nghe - thử hai bản cài đặt nói cùng một giao thức.
 */
private const val CRLF = "\r\n"

class BtMuxTest {
    private val big = ByteArray(4 * 1024 * 1024) { (it % 251).toByte() }
    private lateinit var http: ServerSocket
    private val cleanups = mutableListOf<() -> Unit>()

    /** Máy chủ HTTP tí hon (classpath test của Android không có com.sun.net.httpserver): /big 4 MB, còn lại "nho". */
    @Before
    fun startFiles() {
        http = ServerSocket(0, 50, InetAddress.getByName("127.0.0.1"))
        val workers = Executors.newCachedThreadPool()
        Thread {
            while (!http.isClosed) {
                val client = try { http.accept() } catch (_: java.io.IOException) { break }
                workers.execute {
                    client.use { socket ->
                        val head = StringBuilder()
                        val input = socket.getInputStream()
                        while (!head.endsWith(CRLF + CRLF)) {
                            val next = input.read()
                            if (next < 0) return@use
                            head.append(next.toChar())
                        }
                        val path = head.split(" ").getOrElse(1) { "/" }
                        val body = if (path == "/big") big else "nho".toByteArray()
                        val out = socket.getOutputStream()
                        out.write("HTTP/1.1 200 OK${CRLF}Content-Length: ${body.size}${CRLF}Connection: close$CRLF$CRLF".toByteArray())
                        runCatching { out.write(body); out.flush() }
                    }
                }
            }
        }.apply { isDaemon = true }.start()
    }

    @After
    fun stop() {
        cleanups.forEach { runCatching(it) }
        http.close()
    }

    /** Hai đầu đường hầm trên hai socket nối nhau; đầu phục vụ nối vào máy chủ HTTP như máy tính nối vào cổng đồng bộ. */
    private fun tunnel(): Triple<BtMux, BtMux, BtLocalPort> {
        val listener = ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))
        val near = Socket("127.0.0.1", listener.localPort)
        val far = listener.accept()
        listener.close()
        val server = BtMux(far.getInputStream(), far.getOutputStream(), { far.close() },
            dial = { Socket("127.0.0.1", http.localPort) }, odd = false)
        val client = BtMux(near.getInputStream(), near.getOutputStream(), { near.close() })
        Thread { server.run() }.start()
        Thread { client.run() }.start()
        val local = BtLocalPort(client)
        cleanups += { client.shutdown(); server.shutdown(); local.close() }
        return Triple(client, server, local)
    }

    private fun get(port: Int, path: String): Pair<Int, ByteArray> {
        val connection = URL("http://127.0.0.1:$port$path").openConnection() as HttpURLConnection
        connection.connectTimeout = 5000
        connection.readTimeout = 20_000
        val code = connection.responseCode
        val body = connection.inputStream.use { it.readBytes() }
        connection.disconnect()
        return code to body
    }

    @Test
    fun manyStreamsShareOneLinkAndAStalledOneBlocksNobody() {
        val (_, _, local) = tunnel()
        val stalled = Socket("127.0.0.1", local.port)
        stalled.getOutputStream().write("GET /big HTTP/1.1\r\nHost: x\r\n\r\n".toByteArray())
        Thread.sleep(500) // luồng lớn dồn tới trần tín dụng
        val pool = Executors.newFixedThreadPool(8)
        val started = System.currentTimeMillis()
        val results = (1..8).map { pool.submit<Pair<Int, ByteArray>> { get(local.port, "/nho") } }.map { it.get(10, TimeUnit.SECONDS) }
        assertTrue("luồng nghẽn làm các luồng khác đứng", System.currentTimeMillis() - started < 5000)
        results.forEach { (code, body) -> assertEquals(200, code); assertArrayEquals("nho".toByteArray(), body) }

        // Luồng lớn đọc tiếp thì nhận đủ, đúng từng byte.
        stalled.soTimeout = 20_000
        val input = stalled.getInputStream()
        val all = ByteArrayOutputStream()
        val buffer = ByteArray(1 shl 16)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            all.write(buffer, 0, count)
            val bytes = all.toByteArray()
            val split = String(bytes, Charsets.ISO_8859_1).indexOf("\r\n\r\n")
            if (split >= 0 && bytes.size - split - 4 >= big.size) break
        }
        val bytes = all.toByteArray()
        val split = String(bytes, Charsets.ISO_8859_1).indexOf("\r\n\r\n")
        assertArrayEquals(big, bytes.copyOfRange(split + 4, split + 4 + big.size))
        stalled.close()
    }

    @Test
    fun halfCloseKeepsTheAnswerComing() {
        val (_, _, local) = tunnel()
        val caller = Socket("127.0.0.1", local.port)
        caller.soTimeout = 10_000
        caller.getOutputStream().write("GET /nho HTTP/1.0\r\nHost: x\r\n\r\n".toByteArray())
        caller.shutdownOutput()
        val answer = String(caller.getInputStream().readBytes())
        assertTrue(answer, answer.startsWith("HTTP/1.1 200") && answer.endsWith("nho"))
        caller.close()
    }

    @Test
    fun aBrokenLinkClosesEveryStream() {
        val (client, server, local) = tunnel()
        val caller = Socket("127.0.0.1", local.port)
        caller.soTimeout = 10_000
        caller.getOutputStream().write("GET /big HTTP/1.1\r\nHost: x\r\n\r\n".toByteArray())
        assertTrue(caller.getInputStream().read() >= 0)
        server.shutdown() // ra ngoài tầm Bluetooth
        val buffer = ByteArray(1 shl 16)
        val deadline = System.currentTimeMillis() + 10_000
        try {
            while (caller.getInputStream().read(buffer) >= 0) assertTrue(System.currentTimeMillis() < deadline)
        } catch (_: java.io.IOException) {
        }
        val until = System.currentTimeMillis() + 5000
        while (client.alive && System.currentTimeMillis() < until) Thread.sleep(50)
        assertTrue("đầu bên này không biết đường hầm đã đứt", !client.alive)
    }

    /**
     * ExoPlayer đóng kết nối mỗi lần tua ra ngoài bộ đệm, đổi chương, dừng. Bên phục vụ phải bỏ luồng ấy (RESET) - trước đây
     * nó chờ tín dụng mãi: 64 lần là đường hầm từ chối mọi luồng, điện thoại phục vụ thì kẹt cả luồng của LibraryServer.
     */
    private fun abandonDownloads(abrupt: Boolean) {
        val (client, server, local) = tunnel()
        repeat(3) {
            val player = Socket("127.0.0.1", local.port)
            player.soTimeout = 10_000
            player.getOutputStream().write("GET /big HTTP/1.1${CRLF}Host: x$CRLF$CRLF".toByteArray())
            assertTrue(player.getInputStream().read(ByteArray(65536)) > 0)
            if (abrupt) player.setSoLinger(true, 0) // RST như app bị giết
            player.close()
        }
        val until = System.currentTimeMillis() + 10_000
        while ((client.openStreams > 0 || server.openStreams > 0) && System.currentTimeMillis() < until) Thread.sleep(50)
        assertEquals("luồng bị bỏ vẫn giữ chỗ", 0 to 0, client.openStreams to server.openStreams)
        val (code, body) = get(local.port, "/nho")
        assertEquals(200, code)
        assertArrayEquals("nho".toByteArray(), body)
    }

    @Test
    fun anAbandonedDownloadFreesBothEnds() = abandonDownloads(abrupt = false)

    @Test
    fun anAbruptlyAbandonedDownloadFreesBothEnds() = abandonDownloads(abrupt = true)

    private fun rawPeer(): Pair<Socket, BtMux> {
        val listener = ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))
        val near = Socket("127.0.0.1", listener.localPort)
        val far = listener.accept()
        listener.close()
        val mux = BtMux(far.getInputStream(), far.getOutputStream(), { far.close() },
            dial = { Socket("127.0.0.1", http.localPort) }, odd = false)
        Thread { mux.run() }.start()
        cleanups += { mux.shutdown(); near.close() }
        near.soTimeout = 5000
        return near to mux
    }

    private fun frame(kind: Int, number: Int, payload: ByteArray = ByteArray(0)): ByteArray =
        java.nio.ByteBuffer.allocate(9 + payload.size).put(kind.toByte()).putInt(number).putInt(payload.size).put(payload).array()

    private fun readFrame(socket: Socket): Triple<Int, Int, Int> {
        val header = ByteArray(9)
        java.io.DataInputStream(socket.getInputStream()).readFully(header)
        val buffer = java.nio.ByteBuffer.wrap(header)
        return Triple(buffer.get().toInt(), buffer.getInt(), buffer.getInt())
    }

    @Test
    fun dataForAStreamThatIsGoneIsAnsweredWithResetButResetNever() {
        val (near, _) = rawPeer()
        near.getOutputStream().write(frame(BtMux.RESET, 7) + frame(BtMux.DATA, 99, "abc".toByteArray()))
        assertEquals(Triple(BtMux.RESET, 99, 0), readFrame(near))
        near.soTimeout = 300
        try {
            near.getInputStream().read()
            throw AssertionError("không được đáp RESET cho RESET")
        } catch (_: java.net.SocketTimeoutException) {
        }
    }

    @Test
    fun aNegativeWindowResetsTheStream() {
        val (near, mux) = rawPeer()
        near.getOutputStream().write(frame(BtMux.OPEN, 3))
        val until = System.currentTimeMillis() + 5000
        while (mux.openStreams == 0 && System.currentTimeMillis() < until) Thread.sleep(20)
        near.getOutputStream().write(frame(BtMux.WINDOW, 3, java.nio.ByteBuffer.allocate(4).putInt(-1).array()))
        assertEquals(Triple(BtMux.RESET, 3, 0), readFrame(near))
    }

    /** Nói chuyện với đầu Python thật (webui/bluetooth.py) - chạy tay: BTMUX_PY_PORT=<cổng> gradlew testDebugUnitTest. */
    @Test
    fun speaksTheSameProtocolAsThePythonSide() {
        val port = System.getenv("BTMUX_PY_PORT")?.toIntOrNull()
        assumeTrue("đặt BTMUX_PY_PORT để thử với đầu Python", port != null)
        val link = Socket("127.0.0.1", port!!)
        val client = BtMux(link.getInputStream(), link.getOutputStream(), { link.close() })
        Thread { client.run() }.start()
        val local = BtLocalPort(client)
        cleanups += { client.shutdown(); local.close() }
        val (code, body) = get(local.port, System.getenv("BTMUX_PY_PATH") ?: "/")
        assertEquals(200, code)
        assertTrue(body.isNotEmpty())
        val expected = System.getenv("BTMUX_PY_SIZE")?.toIntOrNull()
        if (expected != null) assertEquals(expected, body.size)
    }
}
