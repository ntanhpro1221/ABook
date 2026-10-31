package vn.abook.player.net

import java.io.Closeable
import java.io.InputStream
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.atomic.AtomicInteger

/**
 * Máy giả trên vòng lặp cho bài thử chính sách chờ: mỗi kết nối vào `answer(số lượt, socket, đầu yêu cầu)`. Đếm số kết nối ([connections]) để biết app đã gửi bao nhiêu lượt.
 * [silent] nhận kết nối, đọc đầu yêu cầu rồi KHÔNG nói gì (máy treo); [reply] trả một lời đáp đủ.
 */
internal class FakeHost(private val answer: (attempt: Int, socket: Socket, head: String) -> Unit) : Closeable {
    private val server = ServerSocket(0, 16, InetAddress.getByName("127.0.0.1"))
    private val count = AtomicInteger()
    val connections: Int get() = count.get()
    val base: String get() = "http://127.0.0.1:${server.localPort}"

    init {
        Thread {
            while (!server.isClosed) {
                val socket = runCatching { server.accept() }.getOrNull() ?: break
                val attempt = count.incrementAndGet()
                Thread {
                    try {
                        socket.tcpNoDelay = true
                        answer(attempt, socket, readHead(socket.getInputStream()))
                    } catch (_: Exception) {
                    } finally {
                        runCatching { socket.close() }
                    }
                }.apply { isDaemon = true }.start()
            }
        }.apply { isDaemon = true }.start()
    }

    override fun close() = server.close()

    companion object {
        fun readHead(input: InputStream): String {
            val text = StringBuilder()
            while (!text.endsWith("\r\n\r\n")) {
                val b = input.read()
                if (b < 0) break
                text.append(b.toChar())
            }
            return text.toString()
        }

        /** Máy treo: nghe tiếp tới khi app đóng kết nối. */
        val silent: (Int, Socket, String) -> Unit = { _, socket, _ ->
            while (socket.getInputStream().read() >= 0) { /* chờ app bỏ */ }
        }

        fun reply(socket: Socket, status: Int, body: String, type: String = "application/json") {
            val bytes = body.toByteArray()
            socket.getOutputStream().apply {
                write("HTTP/1.1 $status X\r\nContent-Type: $type\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n".toByteArray())
                write(bytes)
                flush()
            }
        }
    }
}
