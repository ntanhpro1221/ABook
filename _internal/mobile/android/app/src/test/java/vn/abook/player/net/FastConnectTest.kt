package vn.abook.player.net

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.BufferedReader
import java.io.File
import java.io.IOException
import java.io.InputStreamReader
import java.net.ConnectException
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.nio.file.Files
import java.security.KeyStore
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.TimeUnit
import javax.net.ssl.SNIMatcher
import javax.net.ssl.SNIServerName
import javax.net.ssl.StandardConstants
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.KeyManagerFactory
import javax.net.ssl.SNIHostName
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLException
import javax.net.ssl.SSLServerSocket
import javax.net.ssl.SSLSocket
import javax.net.ssl.TrustManagerFactory

/**
 * Cuộc đua địa chỉ (RFC 8305) với bộ tra tên giả và một "mạng" giả: địa chỉ IPv6 mù (nối treo tới hết hạn), IPv4 là máy chủ cục bộ thật.
 * Phần HTTP/HTTPS chạy kết nối thật của JDK tới máy chủ cục bộ, nên kênh CONNECT, header Host và TLS (SNI + kiểm tên) được thử đầu-cuối.
 */
class FastConnectTest {
    private val blackhole = InetAddress.getByName("2001:db8::1") // dải tài liệu: không bao giờ tới
    private val blackhole2 = InetAddress.getByName("2001:db8::2")
    private val live = InetAddress.getByName("127.0.0.1")
    private val closeables = mutableListOf<AutoCloseable>()

    @After fun cleanUp() { closeables.reversed().forEach { runCatching { it.close() } } }

    private fun <T : AutoCloseable> T.track(): T = also { closeables += it }

    private fun resolver(vararg addresses: InetAddress) = FastConnect.Resolver { addresses.toList() }

    /** Địa chỉ `dead` treo tới khi socket bị đóng (hay hết hạn), `refused` hỏng ngay, còn lại nối vào máy chủ cục bộ ở `port`. */
    private class Net(val port: Int, @Volatile var dead: Set<InetAddress> = emptySet(), @Volatile var refused: Set<InetAddress> = emptySet()) : FastConnect.Connector {
        val started = CopyOnWriteArrayList<InetAddress>()
        val sockets = CopyOnWriteArrayList<Socket>()
        val threads = CopyOnWriteArrayList<String>()
        val budgets = CopyOnWriteArrayList<Int>()

        override fun connect(socket: Socket, address: InetSocketAddress, timeoutMs: Int) {
            started += address.address
            sockets += socket
            threads += Thread.currentThread().name
            budgets += timeoutMs
            when (address.address) {
                in refused -> throw ConnectException("không tới được ${address.address.hostAddress}")
                in dead -> {
                    val end = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(if (timeoutMs > 0) timeoutMs.toLong() else 60_000)
                    while (!socket.isClosed) {
                        if (System.nanoTime() - end >= 0) throw SocketTimeoutException("treo ${address.address.hostAddress}")
                        Thread.sleep(5)
                    }
                    throw SocketException("đã đóng")
                }
                else -> socket.connect(InetSocketAddress(InetAddress.getByName("127.0.0.1"), port), timeoutMs)
            }
        }
    }

    private fun server() = ServerSocket(0, 50, live).track()

    private inline fun <T> timed(block: () -> T): Pair<T, Long> {
        val start = System.nanoTime()
        val result = block()
        return result to TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start)
    }

    // ---- cuộc đua ---------------------------------------------------------------------------------------------------------

    @Test fun blackholedIpv6FallsBackToIpv4InUnderASecond() {
        val server = server()
        val net = Net(server.localPort, dead = setOf(blackhole))
        val fast = FastConnect(resolver(blackhole, live), net).track()
        val (socket, ms) = timed { fast.connect("abook.test", 443, 5000) }
        assertTrue("mất $ms ms", ms < 1000)
        assertTrue(socket.isConnected && !socket.isClosed)
        assertEquals(listOf(blackhole, live), net.started)
        server.accept().close()
        // Cuộc thử mù bị đóng, không để rò socket.
        assertTrue(net.sockets[0].isClosed)
        socket.close()
    }

    @Test fun aFailedAttemptStartsTheNextAtOnceWithoutWaitingForTheStagger() {
        val server = server()
        val net = Net(server.localPort, refused = setOf(blackhole))
        val fast = FastConnect(resolver(blackhole, live), net, staggerMs = 60_000).track()
        val (socket, ms) = timed { fast.connect("abook.test", 443, 5000) }
        assertTrue("mất $ms ms", ms < 1000)
        socket.close()
    }

    @Test fun familiesAreInterleavedFirstChoiceFirst() {
        val a4 = InetAddress.getByName("10.0.0.1"); val b4 = InetAddress.getByName("10.0.0.2")
        val c6 = InetAddress.getByName("2001:db8::c"); val d6 = InetAddress.getByName("2001:db8::d")
        assertEquals(listOf(a4, c6, b4, d6), FastConnect.interleave(listOf(a4, b4, c6, d6)))
        assertEquals(listOf(c6, a4, d6), FastConnect.interleave(listOf(c6, d6, a4)))
        assertEquals(listOf(a4, b4), FastConnect.interleave(listOf(a4, b4, a4)))
        val net = Net(1, refused = setOf(a4, b4, c6, d6))
        val fast = FastConnect(resolver(a4, b4, c6, d6), net).track()
        try { fast.connect("abook.test", 443, 5000); fail() } catch (_: ConnectException) { }
        assertEquals(listOf(a4, c6, b4, d6), net.started)
    }

    @Test fun whenEveryAddressFailsTheLastErrorIsRaised() {
        val net = Net(1, refused = setOf(blackhole, blackhole2, live))
        val fast = FastConnect(resolver(blackhole, blackhole2, live), net).track()
        try {
            fast.connect("abook.test", 443, 5000)
            fail("phải hỏng")
        } catch (error: ConnectException) {
            // Thứ tự thử: v6, v4, v6 -> cái cuối là blackhole2.
            assertEquals(listOf(blackhole, live, blackhole2), net.started)
            assertTrue(error.message, error.message!!.contains(blackhole2.hostAddress!!))
        }
    }

    @Test fun theTimeoutCoversTheWholeRaceAndEveryAttemptIsClosed() {
        val net = Net(1, dead = setOf(blackhole, blackhole2))
        val fast = FastConnect(resolver(blackhole, blackhole2), net, staggerMs = 100).track()
        val (error, ms) = timed { try { fast.connect("abook.test", 443, 600); null } catch (e: SocketTimeoutException) { e } }
        assertNotNull("phải hết hạn", error)
        assertTrue("hạn chung 600 ms, mất $ms", ms in 550..1500)
        assertEquals(2, net.sockets.size)
        assertTrue(net.sockets.all { it.isClosed })
    }

    @Test fun anIpv4LiteralConnectsOnTheCallingThread() {
        val server = server()
        val net = Net(server.localPort)
        val fast = FastConnect(FastConnect.Resolver { throw AssertionError("không được tra tên cho địa chỉ số") }, net).track()
        fast.connect("127.0.0.1", server.localPort, 2000).close()
        assertEquals(listOf(Thread.currentThread().name), net.threads)
        assertTrue(net.budgets.single() in 1..2000)
    }

    @Test fun aNameWithOneAddressBehavesAsBefore() {
        val server = server()
        val net = Net(server.localPort)
        val fast = FastConnect(resolver(live), net).track()
        fast.connect("abook.test", 443, 3000).close()
        assertEquals(listOf(Thread.currentThread().name), net.threads) // không luồng phụ
        assertEquals(1, net.started.size)
    }

    @Test fun noAddressMeansUnknownHost() {
        val fast = FastConnect(resolver(), Net(1)).track()
        try { fast.connect("abook.test", 443, 1000); fail() } catch (_: UnknownHostException) { }
    }

    @Test fun theWinnerIsRememberedAndAFailingWarmAddressFallsBackToTheRace() {
        val server = server()
        val net = Net(server.localPort, dead = setOf(blackhole))
        val fast = FastConnect(resolver(blackhole, live), net, staggerMs = 50).track()
        assertNull(fast.warm("abook.test"))
        fast.connect("abook.test", 443, 5000).close()
        assertEquals(live, fast.warm("ABook.test"))
        // Địa chỉ nhớ vẫn nối được: không đua lại (chỉ thêm một lần thử).
        val before = net.started.size
        fast.connectWarm("abook.test", 443, 5000).close()
        assertEquals(before + 1, net.started.size)
        // Địa chỉ nhớ hỏng: quên nó rồi đua lại từ đầu (lần này cả hai đều hỏng nên báo lỗi).
        net.dead = emptySet()
        net.refused = setOf(blackhole, live)
        try { fast.connectWarm("abook.test", 443, 1000); fail() } catch (_: ConnectException) { }
        assertNull(fast.warm("abook.test"))
    }

    // ---- HTTP -------------------------------------------------------------------------------------------------------------

    /** Máy chủ HTTP/1.1 tối giản: ghi lại đầu yêu cầu (dòng đầu + header), trả `respond(path)`. */
    private class Http(val tls: SSLContext? = null, val respond: (String) -> Pair<Int, String> = { 200 to "ok" }) : AutoCloseable {
        private val listener: ServerSocket = if (tls == null) ServerSocket(0, 50, InetAddress.getByName("127.0.0.1"))
            else (tls.serverSocketFactory.createServerSocket(0, 50, InetAddress.getByName("127.0.0.1")) as SSLServerSocket).apply {
                // Ghi lại tên máy khách xin trong SNI (không có SNI thì không bao giờ được gọi).
                sslParameters = sslParameters.apply {
                    sniMatchers = listOf<SNIMatcher>(object : SNIMatcher(StandardConstants.SNI_HOST_NAME) {
                        override fun matches(serverName: SNIServerName): Boolean { this@Http.serverNames += (serverName as SNIHostName).asciiName; return true }
                    })
                }
            }
        val port get() = listener.localPort
        val requests = CopyOnWriteArrayList<Map<String, String>>()
        val serverNames = CopyOnWriteArrayList<String>()
        val failures = CopyOnWriteArrayList<Throwable>()

        init {
            Thread({
                while (!listener.isClosed) {
                    val client = try { listener.accept() } catch (_: IOException) { break }
                    Thread({ serve(client) }, "test-http").apply { isDaemon = true }.start()
                }
            }, "test-http-accept").apply { isDaemon = true }.start()
        }

        private fun serve(client: Socket) {
            try {
                client.use {
                    if (client is SSLSocket) client.startHandshake()
                    val reader = BufferedReader(InputStreamReader(client.getInputStream(), Charsets.ISO_8859_1))
                    // Kết nối thăm dò của cuộc đua đóng ngay không gửi gì: không phải yêu cầu.
                    val head = linkedMapOf("request-line" to (reader.readLine() ?: return))
                    while (true) {
                        val line = reader.readLine() ?: break
                        if (line.isEmpty()) break
                        head[line.substringBefore(':').lowercase()] = line.substringAfter(':').trim()
                    }
                    requests += head
                    val (status, body) = respond(head["request-line"]!!.split(' ')[1])
                    val extra = if (status in 300..399) "Location: $body\r\n" else ""
                    val bytes = if (status in 300..399) ByteArray(0) else body.toByteArray()
                    client.getOutputStream().write(("HTTP/1.1 $status X\r\n${extra}Content-Length: ${bytes.size}\r\nConnection: close\r\n\r\n").toByteArray() + bytes)
                    client.getOutputStream().flush()
                }
            } catch (error: Throwable) {
                failures += error
            }
        }

        override fun close() { listener.close() }
    }

    @Test fun plainHttpGoesThroughTheRaceKeepingTheOriginalHostHeader() {
        val http = Http().track()
        val net = Net(http.port, dead = setOf(blackhole))
        val fast = FastConnect(resolver(blackhole, live), net, staggerMs = 100).track()
        val (body, ms) = timed {
            val connection = fast.open("http://abook.test:${http.port}/path?q=1", 5000)
            connection.readTimeout = 5000
            connection.inputStream.use { String(it.readBytes()) }
        }
        assertEquals("ok", body)
        assertTrue("mất $ms ms", ms < 1500)
        assertEquals("abook.test:${http.port}", http.requests.single()["host"])
        assertEquals("GET /path?q=1 HTTP/1.1", http.requests.single()["request-line"]) // proxy đổi dạng tuyệt đối về dạng thường
    }

    @Test fun aLiveFirstAddressGoesStraightToTheServerWithoutTheProxyAndTeachesTheNetwork() {
        val http = Http().track()
        val net = Net(http.port, dead = setOf(blackhole))
        // "localhost" tra được bằng DNS thật: đường thẳng để HttpURLConnection tự nối.
        val fast = FastConnect(resolver(live, blackhole), net, staggerMs = 100).track()
        fun fetch(): String {
            val connection = fast.open("http://localhost:${http.port}/direct", 5000)
            connection.readTimeout = 5000
            return connection.inputStream.use { String(it.readBytes()) }
        }
        assertEquals("ok", fetch())
        assertEquals(0, fast.tunnelAccepted)
        assertEquals(listOf(live), net.started.toList()) // địa chỉ đầu thắng ngay, địa chỉ mù chưa kịp thử
        assertEquals("localhost:${http.port}", http.requests.single()["host"])
        // Họ đầu đã biết là sống: lần sau không đua (không thêm một cái bắt tay thừa).
        assertEquals("ok", fetch())
        assertEquals(1, net.started.size)
        assertEquals(0, fast.tunnelAccepted)
        // Đổi mạng: kết luận hết giá trị, đua lại.
        fast.forgetNetwork()
        assertEquals("ok", fetch())
        assertEquals(2, net.started.size)
    }

    @Test fun aDeadFirstAddressGoesThroughTheProxyAndOtherHostsSkipTheDeadFamilyAtOnce() {
        val http = Http().track()
        val net = Net(http.port, dead = setOf(blackhole))
        val fast = FastConnect(resolver(blackhole, live), net, staggerMs = 100).track()
        fun fetch(host: String): Long = timed {
            val connection = fast.open("http://$host:${http.port}/p", 5000)
            connection.readTimeout = 5000
            assertEquals("ok", connection.inputStream.use { String(it.readBytes()) })
        }.second
        val first = fetch("abook.test")
        assertTrue("mất $first ms", first < 1000)
        assertEquals(1, fast.tunnelAccepted)
        // Host khác: họ IPv6 đã biết là chết -> nối họ sống TRƯỚC, không chờ 100 ms của địa chỉ mù.
        net.started.clear()
        val second = fetch("other.test")
        assertTrue("mất $second ms", second < 1000)
        assertEquals(live, net.started.first())
        assertEquals(2, fast.tunnelAccepted)
    }

    @Test fun anIpLiteralUrlIsOpenedExactlyAsBefore() {
        val http = Http().track()
        val fast = FastConnect(FastConnect.Resolver { throw AssertionError("không tra tên") }, Net(http.port)).track()
        val connection = fast.open("http://127.0.0.1:${http.port}/x", 2000)
        assertEquals(2000, connection.connectTimeout)
        assertFalse(connection.instanceFollowRedirects)
        assertEquals("ok", connection.inputStream.use { String(it.readBytes()) })
        assertEquals("127.0.0.1:${http.port}", http.requests.single()["host"])
    }

    @Test fun openDoesNotFollowRedirectsButGetDoes() {
        val http = Http(respond = { path -> if (path == "/old") 302 to "/new" else 200 to "arrived" }).track()
        val fast = FastConnect(resolver(blackhole, live), Net(http.port, dead = setOf(blackhole)), staggerMs = 50).track()
        val plain = fast.open("http://abook.test:${http.port}/old", 5000)
        assertEquals(302, plain.responseCode)
        plain.disconnect()
        val followed = fast.get("http://abook.test:${http.port}/old", 5000) { it.readTimeout = 5000 }
        assertEquals(200, followed.responseCode)
        assertEquals("arrived", followed.inputStream.use { String(it.readBytes()) })
        assertEquals("abook.test:${http.port}", http.requests.last()["host"])
    }

    @Test fun getGivesUpAfterTooManyRedirects() {
        val http = Http(respond = { 302 to "/again" }).track()
        val fast = FastConnect(resolver(live), Net(http.port)).track()
        try { fast.get("http://127.0.0.1:${http.port}/", 2000, maxRedirects = 2); fail() } catch (error: IOException) {
            assertTrue(error.message, error.message!!.contains("quá nhiều"))
        }
        assertEquals(3, http.requests.size)
    }

    @Test fun literalUrlSwapsTheNameForTheWinnerAndLeavesLiteralsAlone() {
        val server = server()
        val fast = FastConnect(resolver(blackhole, live), Net(server.localPort, dead = setOf(blackhole)), staggerMs = 50).track()
        assertEquals("https://127.0.0.1:47630/sync/v1/x?a=1", fast.literalUrl("https://abook.test:47630/sync/v1/x?a=1"))
        assertEquals("https://192.168.1.5:47630/x", fast.literalUrl("https://192.168.1.5:47630/x"))
        assertEquals("https://[::1]:47630/x", fast.literalUrl("https://[::1]:47630/x"))
        val single = FastConnect(resolver(live), Net(server.localPort)).track()
        assertEquals("https://abook.test:47630/x", single.literalUrl("https://abook.test:47630/x"))
    }

    // ---- HTTPS qua kênh CONNECT ---------------------------------------------------------------------------------------------

    private class Pki(val server: SSLContext, val client: SSLContext)

    /** Chứng chỉ tự ký cho `san` (keytool của JDK đang chạy test); null = JDK không có keytool, bài thử bỏ qua. */
    private fun pki(san: String): Pki? {
        val keytool = File(System.getProperty("java.home"), "bin/" + if (System.getProperty("os.name").lowercase().contains("win")) "keytool.exe" else "keytool")
        if (!keytool.isFile) return null
        val dir = Files.createTempDirectory("fastconnect-pki").toFile().also { it.deleteOnExit() }
        val file = File(dir, "k.p12").also { it.deleteOnExit() }
        val process = ProcessBuilder(keytool.path, "-genkeypair", "-alias", "a", "-keyalg", "EC", "-groupname", "secp256r1", "-dname", "CN=$san",
            "-ext", "san=dns:$san", "-validity", "2", "-storetype", "PKCS12", "-keystore", file.path, "-storepass", "changeit", "-keypass", "changeit")
            .redirectErrorStream(true).start()
        process.inputStream.readBytes()
        if (process.waitFor() != 0) return null
        val store = KeyStore.getInstance("PKCS12").apply { file.inputStream().use { load(it, "changeit".toCharArray()) } }
        val keys = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm()).apply { init(store, "changeit".toCharArray()) }
        val trusted = KeyStore.getInstance(KeyStore.getDefaultType()).apply { load(null); setCertificateEntry("a", store.getCertificate("a")) }
        val trust = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm()).apply { init(trusted) }
        return Pki(
            SSLContext.getInstance("TLS").apply { init(keys.keyManagers, null, null) },
            SSLContext.getInstance("TLS").apply { init(null, trust.trustManagers, null) },
        )
    }

    @Test fun httpsThroughTheTunnelKeepsSniAndTheNameCheckOnTheOriginalHost() {
        val pki = pki("abook.test")
        assumeTrue("JDK không có keytool", pki != null)
        val http = Http(pki!!.server).track()
        val net = Net(http.port, dead = setOf(blackhole))
        val fast = FastConnect(resolver(blackhole, live), net, staggerMs = 100).track()
        val (body, ms) = timed {
            val connection = fast.open("https://abook.test:${http.port}/hello", 5000) as HttpsURLConnection
            connection.sslSocketFactory = pki.client.socketFactory
            connection.readTimeout = 5000
            connection.inputStream.use { String(it.readBytes()) }
        }
        assertEquals("ok", body)
        assertTrue("mất $ms ms", ms < 2500)
        assertEquals(listOf("abook.test"), http.serverNames.toList()) // SNI là tên gốc, không phải 127.0.0.1
        assertEquals("abook.test:${http.port}", http.requests.single()["host"])
        // Không còn socket mồ côi trong kênh sau khi dùng: socket thắng đã được trao cho kênh (chỉ hai cuộc thử: mù + thắng).
        assertEquals(2, net.started.size)
    }

    @Test fun httpsStillRejectsACertificateForAnotherName() {
        val pki = pki("other.test")
        assumeTrue("JDK không có keytool", pki != null)
        val http = Http(pki!!.server).track()
        val fast = FastConnect(resolver(blackhole, live), Net(http.port, dead = setOf(blackhole)), staggerMs = 50).track()
        val connection = fast.open("https://abook.test:${http.port}/", 5000) as HttpsURLConnection
        connection.sslSocketFactory = pki.client.socketFactory
        connection.readTimeout = 5000
        try {
            connection.inputStream.close()
            fail("chứng chỉ của tên khác phải bị từ chối")
        } catch (error: SSLException) {
            // đúng: kiểm tên vẫn chạy với tên gốc abook.test, không bị đổi thành địa chỉ số
        }
    }

    @Test fun bothAddressesBlindGiveATypedTimeoutAtOpenNotAtFirstRead() {
        val server = server()
        val fast = FastConnect(resolver(blackhole, live), Net(server.localPort, dead = setOf(blackhole, live)), staggerMs = 50).track()
        // Cả hai địa chỉ mù: cuộc đua ở open() báo hết hạn đúng loại, không chờ tới lúc đọc.
        val (error, ms) = timed { try { fast.open("https://abook.test/", 500); null } catch (e: SocketTimeoutException) { e } }
        assertNotNull(error)
        assertTrue("mất $ms ms", ms < 1500)
    }

    @Test fun theTunnelServesOnlyTargetsThatWereRegistered() {
        val fast = FastConnect(resolver(live), Net(1)).track()
        val tunnel = Tunnel(fast, java.util.concurrent.Executors.newCachedThreadPool { Thread(it).apply { isDaemon = true } }).track()
        val proxy = tunnel.proxyFor("abook.test", 443, 1000, null)
        val address = proxy.address() as InetSocketAddress
        assertEquals("127.0.0.1", address.address.hostAddress)
        fun ask(request: String): String = Socket(address.address, address.port).use { socket ->
            socket.soTimeout = 3000
            socket.getOutputStream().write(request.toByteArray())
            BufferedReader(InputStreamReader(socket.getInputStream())).readLine().orEmpty()
        }
        assertTrue(ask("CONNECT evil.test:443 HTTP/1.1\r\nHost: evil.test:443\r\n\r\n").contains("403"))
        assertTrue(ask("GET http://evil.test/ HTTP/1.1\r\n\r\n").contains("403"))
        assertTrue(ask("GET /origin-form HTTP/1.1\r\n\r\n").contains("405")) // không phải dạng proxy
        assertTrue(ask("CONNECT abook.test:443 HTTP/1.1\r\n\r\n").contains("502")) // đã đăng ký nhưng nối ra không được
        assertTrue(ask("CONNECT abook.test:8443 HTTP/1.1\r\n\r\n").contains("403")) // cổng khác cũng không
    }

    @Test fun aProxyConfiguredBySystemOrCallerIsLeftAlone() {
        val http = Http().track()
        val fast = FastConnect(FastConnect.Resolver { throw AssertionError("không tra tên khi có proxy") }, Net(http.port)).track()
        val proxy = java.net.Proxy(java.net.Proxy.Type.HTTP, InetSocketAddress(live, http.port))
        val connection = fast.open("http://abook.test/x", 1000, proxy)
        connection.readTimeout = 2000
        assertEquals("ok", connection.inputStream.use { String(it.readBytes()) }) // đi qua "proxy" là chính máy chủ thử, tên giữ nguyên
        assertEquals("GET http://abook.test/x HTTP/1.1", http.requests.single()["request-line"])
    }

}
