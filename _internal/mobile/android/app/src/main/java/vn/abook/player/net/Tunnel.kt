package vn.abook.player.net

import java.io.Closeable
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Proxy
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit

/**
 * Proxy cục bộ của [FastConnect]: HttpURLConnection của Android tự nối từng địa chỉ một nên không đua được; ta cho nó đi qua một "proxy"
 * trên 127.0.0.1 do chính app chạy. Proxy nhận `CONNECT tên:cổng` (HTTPS) hay `GET http://tên:cổng/...` (HTTP thường), nối ra bằng [FastConnect.connect]
 * (đua địa chỉ) rồi chuyển byte hai chiều - với HTTPS, TLS vẫn đầu-cuối giữa HttpURLConnection và máy chủ với đúng tên máy gốc (SNI, kiểm chứng chỉ,
 * ghim vân tay không đổi).
 *
 * An toàn: cổng loopback mở cho mọi app trên máy, nên kênh CHỈ nối tới `tên:cổng` mà [proxyFor] vừa đăng ký (vài phút) - app khác không dùng được nó
 * làm cửa ra mạng (nó không có quyền INTERNET cũng không mượn được). Vì thế kết nối của [FastConnect.open] không tự theo chuyển hướng.
 */
internal class Tunnel(private val fast: FastConnect, private val pool: ExecutorService) : Closeable {
    private class Allowed(val until: Long, val timeoutMs: Int)
    private class Ready(val socket: Socket, val at: Long)

    private val allowed = ConcurrentHashMap<String, Allowed>()
    private val ready = ConcurrentHashMap<String, ConcurrentLinkedQueue<Ready>>()
    private var server: ServerSocket? = null
    @Volatile private var closed = false
    /** Số kết nối khách đã nhận (bài thử: đường thẳng không được đụng tới proxy). */
    val accepted = java.util.concurrent.atomic.AtomicInteger()

    /** Đăng ký `host:port` rồi trả proxy cho `URL.openConnection(proxy)`. `ahead`: socket đã nối sẵn tới đó (cuộc đua đã thắng) để kênh dùng luôn. */
    fun proxyFor(host: String, port: Int, timeoutMs: Int, ahead: Socket?): Proxy {
        val now = System.nanoTime()
        sweep(now)
        val key = key(host, port)
        allowed[key] = Allowed(now + ALLOW_NS, timeoutMs)
        if (ahead != null) ready.computeIfAbsent(key) { ConcurrentLinkedQueue() }.add(Ready(ahead, now))
        val loopback = InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1))
        return Proxy(Proxy.Type.HTTP, InetSocketAddress(loopback, listener().localPort))
    }

    @Synchronized
    private fun listener(): ServerSocket {
        server?.let { return it }
        check(!closed) { "kênh đã đóng" }
        val socket = ServerSocket(0, 50, InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1)))
        server = socket
        Thread({
            while (!closed) {
                val client = try { socket.accept() } catch (_: IOException) { return@Thread }
                accepted.incrementAndGet()
                try { pool.execute { serve(client) } } catch (_: Exception) { FastConnect.closeQuietly(client) }
            }
        }, "fast-tunnel").apply { isDaemon = true }.start()
        return socket
    }

    private fun serve(client: Socket) {
        var upstream: Socket? = null
        try {
            client.soTimeout = HEAD_MS
            client.tcpNoDelay = true
            val head = readHead(client.getInputStream())
            val lines = head.split("\r\n")
            val parts = lines[0].split(' ')
            if (parts.size < 3) return reply(client, "400 Bad Request")
            // CONNECT tên:cổng (HTTPS) hay GET http://tên:cổng/đường (HTTP thường, dạng tuyệt đối của proxy).
            val tunnelled = parts[0] == "CONNECT"
            val target = if (tunnelled) null else runCatching { java.net.URI(parts[1]) }.getOrNull()
            if (!tunnelled && (target == null || !"http".equals(target.scheme, ignoreCase = true) || target.host == null)) return reply(client, "405 Method Not Allowed")
            val host = (if (tunnelled) parts[1].substringBeforeLast(':', "") else target!!.host).trim('[', ']').lowercase()
            val port = if (tunnelled) parts[1].substringAfterLast(':', "").toIntOrNull() else if (target!!.port > 0) target.port else 80
            if (host.isEmpty() || port == null) return reply(client, "400 Bad Request")
            val key = key(host, port)
            val entry = allowed[key]
            if (entry == null || System.nanoTime() - entry.until >= 0) return reply(client, "403 Forbidden")
            upstream = try {
                claim(key) ?: fast.connectWarm(host, port, entry.timeoutMs)
            } catch (error: SocketTimeoutException) {
                return reply(client, "504 Gateway Timeout")
            } catch (error: IOException) {
                return reply(client, "502 Bad Gateway")
            }
            upstream.tcpNoDelay = true
            if (tunnelled) {
                client.getOutputStream().apply { write("HTTP/1.1 200 Connection established\r\n\r\n".toByteArray(Charsets.US_ASCII)); flush() }
            } else {
                // Máy chủ đích nhận dòng đầu dạng thường, không có header riêng của proxy; yêu cầu sau trên cùng kết nối đi nguyên (dạng tuyệt đối, RFC 7230 §5.3.2).
                val path = (target!!.rawPath.takeUnless { it.isNullOrEmpty() } ?: "/") + (target.rawQuery?.let { "?$it" } ?: "")
                val forwarded = listOf("${parts[0]} $path ${parts[2]}") + lines.drop(1).filterNot { it.startsWith("Proxy-", ignoreCase = true) }
                upstream.getOutputStream().apply { write(forwarded.joinToString("\r\n").toByteArray(Charsets.ISO_8859_1)); flush() }
            }
            client.soTimeout = 0
            val other = upstream
            pool.execute { copy(other.getInputStream(), client.getOutputStream()); FastConnect.closeQuietly(client); FastConnect.closeQuietly(other) }
            copy(client.getInputStream(), other.getOutputStream())
        } catch (_: IOException) {
        } finally {
            FastConnect.closeQuietly(client)
            upstream?.let(FastConnect::closeQuietly)
        }
    }

    /** Đầu yêu cầu tới dòng trống, từng byte (không đọc lố sang TLS của khách, nó còn chờ ta trả lời). */
    private fun readHead(input: InputStream): String {
        val text = StringBuilder()
        while (!text.endsWith("\r\n\r\n")) {
            val b = input.read()
            if (b < 0) throw IOException("khách đóng giữa đầu yêu cầu")
            text.append(b.toChar())
            if (text.length > MAX_HEAD) throw IOException("đầu yêu cầu quá dài")
        }
        return text.toString()
    }

    private fun reply(client: Socket, status: String) {
        try {
            client.getOutputStream().apply { write("HTTP/1.1 $status\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".toByteArray(Charsets.US_ASCII)); flush() }
        } catch (_: IOException) { }
    }

    private fun copy(from: InputStream, to: OutputStream) {
        val buffer = ByteArray(16 * 1024)
        try {
            while (true) {
                val count = from.read(buffer)
                if (count < 0) return
                to.write(buffer, 0, count)
                to.flush()
            }
        } catch (_: IOException) { }
    }

    /** Socket nối sẵn còn tươi cho `key` (hơn thế thì máy chủ có thể đã đóng vì rảnh), bỏ cái cũ. */
    private fun claim(key: String): Socket? {
        val queue = ready[key] ?: return null
        while (true) {
            val item = queue.poll() ?: return null
            if (System.nanoTime() - item.at < READY_NS && !item.socket.isClosed) return item.socket
            FastConnect.closeQuietly(item.socket)
        }
    }

    private fun sweep(now: Long) {
        allowed.entries.removeIf { now - it.value.until >= 0 }
        for ((key, queue) in ready) {
            while (true) {
                val head = queue.peek() ?: break
                if (now - head.at < READY_NS) break
                queue.poll()?.let { FastConnect.closeQuietly(it.socket) }
            }
            if (queue.isEmpty()) ready.remove(key, queue)
        }
    }

    private fun key(host: String, port: Int) = "${host.trim('[', ']').lowercase()}:$port"

    @Synchronized
    override fun close() {
        closed = true
        server?.let { try { it.close() } catch (_: IOException) { } }
        for (queue in ready.values) while (true) FastConnect.closeQuietly((queue.poll() ?: break).socket)
        ready.clear()
        allowed.clear()
    }

    private companion object {
        val ALLOW_NS = TimeUnit.MINUTES.toNanos(5)
        val READY_NS = TimeUnit.SECONDS.toNanos(5)
        const val HEAD_MS = 10_000
        const val MAX_HEAD = 8 * 1024
    }
}
