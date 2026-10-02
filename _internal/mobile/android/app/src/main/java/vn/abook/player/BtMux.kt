package vn.abook.player

import java.io.DataInputStream
import java.io.EOFException
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.ByteBuffer
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.atomic.AtomicBoolean

/** Đường hầm đứt (tắt Bluetooth, ra ngoài tầm, máy kia đóng app) - khác lỗi của một socket cục bộ. */
class LinkClosed(message: String) : IOException(message)

/**
 * Đường hầm Bluetooth - ĐÚNG giao thức của abook/webui/bluetooth.py: MỘT kết nối RFCOMM mang nhiều luồng TCP của cổng
 * đồng bộ HTTP. Khung: loại (1 byte), luồng (4 byte), độ dài (4 byte), big-endian, rồi dữ liệu (tối đa 16 KB). Mỗi luồng có
 * cửa sổ tín dụng 256 KB như HTTP/2: gửi trong phần tín dụng, trả tín dụng sau khi đã ghi xuống socket cục bộ - trình phát
 * ngừng đọc thì chỉ luồng của nó đứng. CLOSE = hết dữ liệu theo chiều ấy; luồng xong khi cả hai chiều đã CLOSE.
 *
 * RESET = bỏ luồng ngay, cả hai chiều: ExoPlayer đóng kết nối mỗi lần tua ra ngoài bộ đệm, đổi chương, dừng - bên kia phải
 * thôi gửi, không thì nó chờ tín dụng mãi (giữ luồng, luồng đọc, socket; bên phục vụ là điện thoại thì còn giữ cả luồng của
 * LibraryServer). DATA tới luồng không còn -> đáp RESET; WINDOW/CLOSE/RESET tới luồng không còn là khung trễ, bỏ qua - không
 * bao giờ đáp RESET cho RESET.
 *
 * `dial`: bên phục vụ mở kết nối cục bộ cho mỗi luồng bên kia mở (ở luồng riêng: nối chậm không làm mọi luồng đứng theo luồng
 * đọc); `open(socket)`: bên kết nối đưa một socket cục bộ vào.
 */
class BtMux(
    input: InputStream,
    private val output: OutputStream,
    private val closeLink: () -> Unit,
    private val dial: (() -> Socket)? = null,
    odd: Boolean = true,
) {
    companion object {
        const val OPEN = 1
        const val DATA = 2
        const val CLOSE = 3
        const val WINDOW = 4
        const val RESET = 5
        const val HEADER = 9
        const val MAX_DATA = 16 * 1024
        const val WINDOW_SIZE = 256 * 1024
        const val MAX_STREAMS = 64
    }

    private val input = DataInputStream(input)
    private val streams = HashMap<Int, Stream>()
    private val sendLock = Any()
    private var next = if (odd) 1 else 2
    private val live = AtomicBoolean(true)
    val alive: Boolean get() = live.get()

    /** Số luồng đang mở - cho test và màn trạng thái. */
    val openStreams: Int get() = synchronized(streams) { streams.size }

    internal fun send(kind: Int, number: Int, payload: ByteArray = ByteArray(0), length: Int = payload.size) {
        if (!alive) throw LinkClosed("đường hầm đã đóng")
        val header = ByteBuffer.allocate(HEADER).put(kind.toByte()).putInt(number).putInt(length).array()
        try {
            synchronized(sendLock) {
                output.write(header)
                if (length > 0) output.write(payload, 0, length)
                output.flush()
            }
        } catch (error: IOException) {
            shutdown()
            throw LinkClosed(error.message ?: "đường hầm đứt")
        }
    }

    internal fun forget(number: Int) {
        synchronized(streams) { streams.remove(number) }
    }

    fun open(local: Socket): Int {
        val stream: Stream
        synchronized(streams) {
            if (!alive || streams.size >= MAX_STREAMS) {
                runCatching { local.close() }
                throw LinkClosed(if (!alive) "đường hầm đã đóng" else "quá nhiều luồng")
            }
            val number = next
            next += 2
            stream = Stream(this, number, local)
            streams[number] = stream
        }
        send(OPEN, stream.number)
        stream.start()
        return stream.number
    }

    /** Đọc khung tới khi đường hầm đứt; đứt thì đóng mọi luồng. */
    fun run() {
        val header = ByteArray(HEADER)
        try {
            while (true) {
                input.readFully(header)
                val buffer = ByteBuffer.wrap(header)
                val kind = buffer.get().toInt()
                val number = buffer.getInt()
                val length = buffer.getInt()
                if (length < 0 || length > MAX_DATA) throw IOException("khung quá lớn")
                val payload = ByteArray(length)
                if (length > 0) input.readFully(payload)
                val stream = synchronized(streams) { streams[number] }
                when {
                    kind == OPEN -> accept(number)
                    stream == null -> if (kind == DATA) send(RESET, number) // bên kia tưởng luồng còn sống: bảo nó thôi
                    kind == RESET -> stream.close()
                    kind == DATA -> if (!stream.receive(payload)) stream.close(reset = true) // quá tín dụng: sai giao thức
                    kind == CLOSE -> stream.remoteEnded()
                    kind == WINDOW -> {
                        // Không dấu, trong (0, WINDOW_SIZE] - như phía Python; số âm từ getInt() là sai giao thức.
                        val amount = if (length == 4) ByteBuffer.wrap(payload).getInt() else 0
                        if (amount in 1..WINDOW_SIZE) stream.grant(amount) else stream.close(reset = true)
                    }
                }
            }
        } catch (_: EOFException) {
        } catch (_: IOException) {
        } finally {
            shutdown()
        }
    }

    private fun accept(number: Int) {
        val dialer = dial
        val stream = synchronized(streams) {
            if (!alive || dialer == null || streams.size >= MAX_STREAMS || streams.containsKey(number)) {
                null
            } else {
                Stream(this, number, null).also { streams[number] = it }
            }
        }
        if (stream == null || dialer == null) {
            send(RESET, number)
            return
        }
        Thread({
            val local = try {
                dialer()
            } catch (_: Exception) {
                stream.close(reset = true) // cổng đồng bộ tắt: bên gọi thấy luồng bị bỏ, không treo
                return@Thread
            }
            stream.start(local)
        }, "bt-dial-$number").apply { isDaemon = true }.start()
    }

    fun shutdown() {
        val all = synchronized(streams) {
            // open()/accept() kiểm `alive` dưới cùng khoá: không luồng nào đăng ký sau ảnh chụp này.
            if (!live.compareAndSet(true, false)) return
            streams.values.toList()
        }
        all.forEach { it.close() }
        runCatching { closeLink() }
    }

    internal class Stream(private val mux: BtMux, val number: Int, @Volatile private var local: Socket?) {
        private val lock = Object()
        private var credit = WINDOW_SIZE
        private var queued = 0
        private var closed = false
        private val outgoing = LinkedBlockingQueue<ByteArray>()
        private val end = ByteArray(0)
        @Volatile private var sentEnd = false
        @Volatile private var gotEnd = false

        /** Bắt đầu bơm hai chiều; `socket` cho luồng bên kia mở (nối xong mới có). Đã bị đóng trong lúc nối thì đóng nó luôn. */
        fun start(socket: Socket? = null) {
            if (socket != null) {
                val attached = synchronized(lock) {
                    if (!closed) local = socket
                    !closed
                }
                if (!attached) {
                    runCatching { socket.close() }
                    return
                }
            }
            Thread({ pump() }, "bt-pump-$number").apply { isDaemon = true }.start()
            Thread({ drain() }, "bt-drain-$number").apply { isDaemon = true }.start()
        }

        fun grant(amount: Int) = synchronized(lock) {
            credit += amount
            lock.notifyAll()
        }

        /** false: bên kia gửi quá tín dụng - sai giao thức. */
        fun receive(data: ByteArray): Boolean {
            synchronized(lock) {
                queued += data.size
                if (queued > WINDOW_SIZE) return false
            }
            outgoing.put(data)
            return true
        }

        fun remoteEnded() = outgoing.put(end)

        /** socket cục bộ -> đường hầm, chỉ trong phần tín dụng. */
        private fun pump() {
            val socket = local ?: return
            val buffer = ByteArray(MAX_DATA)
            try {
                val stream = socket.getInputStream()
                while (true) {
                    val budget = synchronized(lock) {
                        while (credit <= 0 && !closed) lock.wait()
                        if (closed) return
                        minOf(MAX_DATA, credit)
                    }
                    val count = stream.read(buffer, 0, budget)
                    if (count < 0) break
                    synchronized(lock) { credit -= count }
                    mux.send(DATA, number, buffer, count)
                }
            } catch (_: LinkClosed) {
                return // đường hầm đứt: shutdown() đã đóng mọi luồng
            } catch (_: IOException) {
                close(reset = true) // ứng dụng cục bộ cắt ngang, hay luồng vừa bị đóng
                return
            } catch (_: InterruptedException) {
                return
            }
            sentEnd = true
            try {
                mux.send(CLOSE, number)
            } catch (_: IOException) {
                return
            }
            maybeDone()
        }

        /** đường hầm -> socket cục bộ; trả tín dụng sau khi đã ghi. */
        private fun drain() {
            val socket = local ?: return
            try {
                val stream = socket.getOutputStream()
                while (true) {
                    val data = outgoing.take()
                    if (data === end) {
                        if (!synchronized(lock) { closed }) runCatching { socket.shutdownOutput() }
                        break
                    }
                    stream.write(data)
                    stream.flush()
                    synchronized(lock) { queued -= data.size }
                    mux.send(WINDOW, number, ByteBuffer.allocate(4).putInt(data.size).array())
                }
            } catch (_: LinkClosed) {
                return
            } catch (_: IOException) {
                close(reset = true) // ứng dụng cục bộ đã đóng kết nối (trình phát tua, đổi chương): bên kia thôi gửi
                return
            } catch (_: InterruptedException) {
                return
            }
            gotEnd = true
            maybeDone()
        }

        private fun maybeDone() {
            if (sentEnd && gotEnd) close()
        }

        /** Đóng luồng (một lần). `reset`: đóng ngang - báo bên kia bỏ luồng, để nó không chờ tín dụng mãi. */
        fun close(reset: Boolean = false) {
            synchronized(lock) {
                if (closed) return
                closed = true
                lock.notifyAll()
            }
            local?.let { runCatching { it.close() } }
            outgoing.put(end)
            mux.forget(number)
            if (reset) runCatching { mux.send(RESET, number) }
        }
    }
}

/**
 * Bên kết nối: cổng TCP cục bộ (127.0.0.1) mà mọi kết nối vào đều đi qua đường hầm - trình phát, SyncLink... chỉ việc dùng
 * http://127.0.0.1:<port> như một máy tính trong mạng. `port` 0 = để hệ thống chọn.
 */
class BtLocalPort(private val mux: BtMux, port: Int = 0) {
    private val server = ServerSocket(port, 50, InetAddress.getByName("127.0.0.1"))
    val port: Int = server.localPort

    init {
        Thread({ accept() }, "bt-local").apply { isDaemon = true }.start()
    }

    private fun accept() {
        while (mux.alive) {
            val client = try {
                server.accept()
            } catch (_: IOException) {
                return
            }
            try {
                mux.open(client)
            } catch (_: IOException) {
                runCatching { client.close() }
                return
            }
        }
        runCatching { server.close() }
    }

    fun close() = runCatching { server.close() }
}
