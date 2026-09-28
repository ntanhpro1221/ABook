package vn.ebookreader.player

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

/**
 * Đường hầm Bluetooth - ĐÚNG giao thức của ebook_reader/webui/bluetooth.py: MỘT kết nối RFCOMM mang nhiều luồng TCP của cổng
 * đồng bộ HTTP. Khung: loại (1 byte), luồng (4 byte), độ dài (4 byte), big-endian, rồi dữ liệu (tối đa 16 KB). Mỗi luồng có
 * cửa sổ tín dụng 256 KB như HTTP/2: gửi trong phần tín dụng, trả tín dụng sau khi đã ghi xuống socket cục bộ - trình phát
 * ngừng đọc thì chỉ luồng của nó đứng. CLOSE = hết dữ liệu theo chiều ấy; luồng xong khi cả hai chiều đã CLOSE.
 *
 * `dial`: bên phục vụ mở kết nối cục bộ cho mỗi luồng bên kia mở; `open(socket)`: bên kết nối đưa một socket cục bộ vào.
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

    internal fun send(kind: Int, number: Int, payload: ByteArray = ByteArray(0), length: Int = payload.size) {
        if (!alive) throw IOException("đường hầm đã đóng")
        val header = ByteBuffer.allocate(HEADER).put(kind.toByte()).putInt(number).putInt(length).array()
        try {
            synchronized(sendLock) {
                output.write(header)
                if (length > 0) output.write(payload, 0, length)
                output.flush()
            }
        } catch (error: IOException) {
            shutdown()
            throw error
        }
    }

    internal fun forget(number: Int) {
        synchronized(streams) { streams.remove(number) }
    }

    fun open(local: Socket): Int {
        val stream: Stream
        synchronized(streams) {
            if (streams.size >= MAX_STREAMS) {
                local.close()
                throw IOException("quá nhiều luồng")
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
                    stream == null -> Unit // luồng đã đóng: khung trễ, bỏ
                    kind == DATA -> if (!stream.receive(payload)) {
                        stream.close()
                        send(CLOSE, number)
                    }
                    kind == CLOSE -> stream.remoteEnded()
                    kind == WINDOW && length == 4 -> stream.grant(ByteBuffer.wrap(payload).getInt())
                }
            }
        } catch (_: EOFException) {
        } catch (_: IOException) {
        } finally {
            shutdown()
        }
    }

    private fun accept(number: Int) {
        val full = synchronized(streams) { streams.size >= MAX_STREAMS || streams.containsKey(number) }
        val dialer = dial
        if (dialer == null || full) {
            send(CLOSE, number)
            return
        }
        val local = try {
            dialer()
        } catch (_: IOException) {
            send(CLOSE, number)
            return
        }
        val stream = Stream(this, number, local)
        synchronized(streams) { streams[number] = stream }
        stream.start()
    }

    fun shutdown() {
        if (!live.compareAndSet(true, false)) return
        val all = synchronized(streams) { streams.values.toList() }
        all.forEach { it.close() }
        runCatching { closeLink() }
    }

    internal class Stream(private val mux: BtMux, val number: Int, private val local: Socket) {
        private val lock = Object()
        private var credit = WINDOW_SIZE
        private var queued = 0
        private var closed = false
        private val outgoing = LinkedBlockingQueue<ByteArray>()
        private val end = ByteArray(0)
        @Volatile private var sentEnd = false
        @Volatile private var gotEnd = false

        fun start() {
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
            val buffer = ByteArray(MAX_DATA)
            try {
                val stream = local.getInputStream()
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
            } catch (_: IOException) {
            } catch (_: InterruptedException) {
            }
            sentEnd = true
            runCatching { mux.send(CLOSE, number) }
            maybeDone()
        }

        /** đường hầm -> socket cục bộ; trả tín dụng sau khi đã ghi. */
        private fun drain() {
            try {
                val stream = local.getOutputStream()
                while (true) {
                    val data = outgoing.take()
                    if (data === end) {
                        runCatching { local.shutdownOutput() }
                        break
                    }
                    stream.write(data)
                    stream.flush()
                    synchronized(lock) { queued -= data.size }
                    mux.send(WINDOW, number, ByteBuffer.allocate(4).putInt(data.size).array())
                }
            } catch (_: IOException) {
                close()
            } catch (_: InterruptedException) {
            }
            gotEnd = true
            maybeDone()
        }

        private fun maybeDone() {
            if (sentEnd && gotEnd) close()
        }

        fun close() {
            synchronized(lock) {
                if (closed) return
                closed = true
                lock.notifyAll()
            }
            runCatching { local.close() }
            outgoing.put(end)
            mux.forget(number)
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
