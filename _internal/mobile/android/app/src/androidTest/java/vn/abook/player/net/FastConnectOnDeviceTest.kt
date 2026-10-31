package vn.abook.player.net

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException
import java.util.concurrent.CopyOnWriteArrayList

/**
 * Trên máy Android THẬT (máy ảo): HttpURLConnection của Android (libcore) đi qua proxy cục bộ của FastConnect như đã tính - HTTP thường ra đúng thân + header Host
 * gốc, HTTPS gửi CONNECT rồi ClientHello mang SNI là tên máy gốc (không phải địa chỉ số). Địa chỉ IPv6 trong bài này mù (nối treo); IPv4 là máy chủ cục bộ.
 */
@RunWith(AndroidJUnit4::class)
class FastConnectOnDeviceTest {
    private val blackhole = InetAddress.getByName("2001:db8::1")
    private val closers = mutableListOf<() -> Unit>()

    @After fun tearDown() { closers.reversed().forEach { runCatching(it) } }

    private class Hung(val port: Int) : FastConnect.Connector {
        override fun connect(socket: Socket, address: InetSocketAddress, timeoutMs: Int) {
            if (address.address == InetAddress.getByName("2001:db8::1")) {
                val end = System.nanoTime() + 20_000_000_000L
                while (!socket.isClosed && System.nanoTime() < end) Thread.sleep(5)
                throw SocketException("mù")
            }
            socket.connect(InetSocketAddress(InetAddress.getByName("127.0.0.1"), port), timeoutMs)
        }
    }

    private fun fast(port: Int) = FastConnect({ listOf(blackhole, InetAddress.getByName("127.0.0.1")) }, Hung(port), staggerMs = 100)
        .also { closers += it::close }

    private fun listen(onClient: (Socket) -> Unit): ServerSocket {
        val server = ServerSocket(0, 50, InetAddress.getByName("127.0.0.1")).also { closers += it::close }
        Thread({
            while (!server.isClosed) {
                val client = try { server.accept() } catch (_: IOException) { break }
                Thread({ client.use { runCatching { onClient(it) } } }, "ondevice-server").apply { isDaemon = true }.start()
            }
        }, "ondevice-accept").apply { isDaemon = true }.start()
        return server
    }

    @Test fun libcoreHttpGoesThroughTheRaceWithTheOriginalHostHeader() {
        val heads = CopyOnWriteArrayList<String>()
        val server = listen { client ->
            val input = client.getInputStream()
            val head = StringBuilder()
            while (!head.endsWith("\r\n\r\n")) { val b = input.read(); if (b < 0) return@listen; head.append(b.toChar()) }
            heads += head.toString()
            client.getOutputStream().write("HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok".toByteArray())
        }
        val start = System.nanoTime()
        val connection = fast(server.localPort).open("http://abook.test:${server.localPort}/x?y=1", 5000)
        connection.readTimeout = 5000
        assertEquals("ok", connection.inputStream.use { String(it.readBytes()) })
        val ms = (System.nanoTime() - start) / 1_000_000
        assertTrue("mất $ms ms (IPv6 mù phải bị bỏ qua sau ~100 ms)", ms < 1500)
        val head = heads.first { it.startsWith("GET ") }
        assertTrue(head, head.startsWith("GET /x?y=1 HTTP/1.1"))
        assertTrue(head, head.contains("Host: abook.test:${server.localPort}"))
    }

    @Test fun libcoreHttpsSendsConnectAndASniOfTheOriginalName() {
        val hello = ByteArrayOutputStream()
        val got = java.util.concurrent.CountDownLatch(1)
        val server = listen { client ->
            val buffer = ByteArray(2048)
            val count = client.getInputStream().read(buffer)
            if (count > 0) hello.write(buffer, 0, count)
            got.countDown()
        }
        val connection = fast(server.localPort).open("https://abook.test:${server.localPort}/", 5000)
        connection.readTimeout = 3000
        try { connection.inputStream.close() } catch (_: IOException) { } // máy chủ thử không nói TLS: bắt tay hỏng là đúng
        assertTrue(got.await(3, java.util.concurrent.TimeUnit.SECONDS))
        val bytes = hello.toByteArray()
        assertEquals("ClientHello (0x16)", 0x16, bytes[0].toInt())
        assertTrue("SNI phải là tên gốc", String(bytes, Charsets.ISO_8859_1).contains("abook.test"))
    }

    @Test fun anAddressThatNeverAnswersDoesNotCostItsFullTimeout() {
        val server = listen { }
        val start = System.nanoTime()
        fast(server.localPort).connect("abook.test", server.localPort, 10_000).close()
        assertTrue((System.nanoTime() - start) / 1_000_000 < 1000)
    }

    // ---- đo: đường thẳng so với qua proxy loopback ------------------------------------------------------------------------

    private fun threads(): Int = java.io.File("/proc/self/status").readLines().first { it.startsWith("Threads:") }.substringAfter(':').trim().toInt()

    private class Run(val ms: Long, val cpuMs: Long, val peakThreads: Int, val pssKb: Long, val proxyThreads: Int)

    /** Máy chủ cục bộ (cổng đa năng: "localhost" ra cả ::1 lẫn 127.0.0.1) trả `bytes` byte số 0. */
    private fun bulkServer(bytes: Long): ServerSocket {
        val server = ServerSocket(0, 50).also { closers += it::close }
        Thread({
            while (!server.isClosed) {
                val client = try { server.accept() } catch (_: IOException) { break }
                Thread({
                    client.use {
                        runCatching {
                            val input = it.getInputStream()
                            // đọc tới dòng trống (hết đầu yêu cầu)
                            val seen = StringBuilder()
                            while (!seen.endsWith("\r\n\r\n")) { val b = input.read(); if (b < 0) return@runCatching; seen.append(b.toChar()) }
                            val out = it.getOutputStream()
                            out.write("HTTP/1.1 200 OK\r\nContent-Length: $bytes\r\nConnection: close\r\n\r\n".toByteArray())
                            val chunk = ByteArray(64 * 1024)
                            var left = bytes
                            while (left > 0) { val n = minOf(left, chunk.size.toLong()).toInt(); out.write(chunk, 0, n); left -= n }
                            out.flush()
                        }
                    }
                }, "bulk").apply { isDaemon = true }.start()
            }
        }, "bulk-accept").apply { isDaemon = true }.start()
        return server
    }

    private fun download(fast: FastConnect, url: String, bytes: Long): Run {
        System.gc()
        val baseThreads = threads()
        val pss0 = android.os.Debug.getPss()
        var peak = baseThreads
        var fastThreads = 0
        val sampler = Thread({ while (!Thread.currentThread().isInterrupted) { peak = maxOf(peak, threads()); fastThreads = maxOf(fastThreads, Thread.getAllStackTraces().keys.count { it.name.startsWith("fast-") }); try { Thread.sleep(10) } catch (_: InterruptedException) { break } } }, "sampler").apply { isDaemon = true }
        sampler.start()
        val cpu0 = android.os.Process.getElapsedCpuTime()
        val t0 = System.nanoTime()
        val connection = fast.open(url, 5000)
        connection.readTimeout = 20_000
        var got = 0L
        connection.inputStream.use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) { val n = input.read(buffer); if (n < 0) break; got += n }
        }
        val ms = (System.nanoTime() - t0) / 1_000_000
        val cpu = android.os.Process.getElapsedCpuTime() - cpu0
        val pss1 = android.os.Debug.getPss()
        sampler.interrupt(); sampler.join()
        assertEquals(bytes, got)
        return Run(ms, cpu, peak - baseThreads, pss1 - pss0, fastThreads)
    }

    @Test fun throughputDirectVersusTunnel() {
        val bytes = 50L * 1024 * 1024
        val server = bulkServer(bytes)
        val lo = InetAddress.getByName("127.0.0.1")
        val direct = FastConnect({ listOf(lo, blackhole) }, Hung(server.localPort), staggerMs = 100).also { closers += it::close }
        val tunnel = FastConnect({ listOf(blackhole, lo) }, Hung(server.localPort), staggerMs = 100).also { closers += it::close }
        // Khởi động nguội (JIT, kết luận về họ địa chỉ) rồi đo 3 lượt xen kẽ.
        download(direct, "http://localhost:${server.localPort}/w", bytes); download(tunnel, "http://abook.test:${server.localPort}/w", bytes)
        val d = mutableListOf<Run>(); val t = mutableListOf<Run>()
        repeat(3) {
            d += download(direct, "http://localhost:${server.localPort}/x", bytes)
            t += download(tunnel, "http://abook.test:${server.localPort}/x", bytes)
        }
        fun line(name: String, runs: List<Run>) = "$name: " + runs.joinToString(" | ") { "${it.ms} ms (${50_000 / maxOf(1, it.ms)} MB/s) cpu ${it.cpuMs} ms +thr ${it.peakThreads} (fast-* ${it.proxyThreads}) pss ${it.pssKb} KB" }
        android.util.Log.i("NETBENCH", line("direct", d))
        android.util.Log.i("NETBENCH", line("tunnel", t))
        assertEquals(0, direct.tunnelAccepted)
        assertTrue(tunnel.tunnelAccepted >= 4)
        // Giá của cuộc đua khi đi thẳng: lần nguội (đua + thả cái socket) so với lần ấm (không đua), chỉ vòng lặp cục bộ.
        val cold = (0 until 20).map { _ ->
            val f = FastConnect({ listOf(lo, blackhole) }, Hung(server.localPort), staggerMs = 100)
            val s = System.nanoTime(); f.open("http://localhost:${server.localPort}/", 5000).disconnect(); val ms = (System.nanoTime() - s) / 1000; f.close(); ms
        }
        val warmFast = FastConnect({ listOf(lo, blackhole) }, Hung(server.localPort), staggerMs = 100).also { closers += it::close }
        warmFast.open("http://localhost:${server.localPort}/", 5000).disconnect()
        val warm = (0 until 20).map { _ -> val s = System.nanoTime(); warmFast.open("http://localhost:${server.localPort}/", 5000).disconnect(); (System.nanoTime() - s) / 1000 }
        android.util.Log.i("NETBENCH", "open() us cold(race) median ${cold.sorted()[10]} | warm(no race) median ${warm.sorted()[10]}")
    }
}
