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

private fun frame(kind: Int, number: Int, payload: ByteArray): ByteArray =
    ByteBuffer.allocate(BtMux.HEADER + payload.size).put(kind.toByte()).putInt(number).putInt(payload.size).put(payload).array()

private fun int4(value: Int): ByteArray = ByteBuffer.allocate(4).putInt(value).array()

/**
 * Đường hầm Bluetooth - ĐÚNG giao thức của abook/webui/bluetooth.py: MỘT kết nối RFCOMM mang nhiều luồng TCP của cổng
 * đồng bộ HTTP. Khung: loại (1 byte), luồng (4 byte), độ dài (4 byte), big-endian, rồi dữ liệu (DATA tối đa 4 KB). Mỗi luồng
 * có cửa sổ tín dụng 64 KB mỗi chiều như HTTP/2: gửi trong phần tín dụng, trả tín dụng sau khi đã ghi xuống socket cục bộ
 * (mỗi 16 KB) - trình phát ngừng đọc thì chỉ luồng của nó đứng. Cả đường hầm còn một cửa sổ chung 256 KB (WINDOW luồng 0):
 * trần bộ nhớ nhận. CLOSE = hết dữ liệu theo chiều ấy; luồng xong khi cả hai chiều đã CLOSE.
 *
 * RESET = bỏ luồng ngay, cả hai chiều: ExoPlayer đóng kết nối mỗi lần tua ra ngoài bộ đệm, đổi chương, dừng - bên kia phải
 * thôi gửi, không thì nó chờ tín dụng mãi (giữ luồng, luồng đọc, socket; bên phục vụ là điện thoại thì còn giữ cả luồng của
 * LibraryServer). DATA tới luồng không còn -> đáp RESET; WINDOW/CLOSE/RESET tới luồng không còn là khung trễ, bỏ qua - không
 * bao giờ đáp RESET cho RESET.
 *
 * Công bằng (08-10: tải 3 MB ở 143 KB/s làm một yêu cầu nhỏ bên cạnh chờ ~3,5 giây): khung của mỗi luồng xếp hàng riêng, MỘT
 * luồng ghi chọn theo deficit round robin ([BtOutbox]); bên nhận báo số byte đã đọc (ACK, luồng 0, mỗi 4 KB) và bên gửi giữ
 * không quá IN_FLIGHT byte chưa được báo - bộ đệm socket RFCOMM không còn nuốt hàng trăm KB trước mặt yêu cầu nhỏ. Luồng đọc
 * không bao giờ chờ ai: khung trả lời chỉ được xếp hàng.
 *
 * `dial`: bên phục vụ mở kết nối cục bộ cho mỗi luồng bên kia mở (ở luồng riêng: nối chậm không làm mọi luồng đứng theo luồng
 * đọc); `open(socket)`: bên kết nối đưa một socket cục bộ vào. `limit`: IN_FLIGHT (thử).
 */
class BtMux(
    input: InputStream,
    private val output: OutputStream,
    private val closeLink: () -> Unit,
    private val dial: (() -> Socket)? = null,
    odd: Boolean = true,
    limit: Int = IN_FLIGHT,
) {
    companion object {
        const val OPEN = 1
        const val DATA = 2
        const val CLOSE = 3
        const val WINDOW = 4
        const val RESET = 5
        const val ACK = 6
        const val HEADER = 9
        const val MAX_DATA = 4 * 1024 // khung DATA lớn nhất, cũng là phần mỗi lượt của một luồng
        const val STREAM_WINDOW = 64 * 1024
        const val LINK_WINDOW = 256 * 1024
        const val UPDATE_AFTER = 16 * 1024
        const val ACK_AFTER = 4 * 1024
        const val IN_FLIGHT = 16 * 1024 // ~0,1 giây ở 150 KB/s
        const val CONTROL_BURST = 4
        const val MAX_STREAMS = 64
    }

    private val input = DataInputStream(input)
    private val streams = HashMap<Int, Stream>()
    internal val out = BtOutbox(limit)
    private var next = if (odd) 1 else 2
    private val live = AtomicBoolean(true)
    private val creditLock = Any()
    private var held = 0 // byte DATA đã nhận mà chưa tiêu (trần LINK_WINDOW)
    private var unreturned = 0 // đã tiêu mà chưa trả tín dụng chung
    val alive: Boolean get() = live.get()

    /** Số luồng đang mở - cho test và màn trạng thái. */
    val openStreams: Int get() = synchronized(streams) { streams.size }

    init {
        Thread({ write() }, "bt-write").apply { isDaemon = true }.start()
    }

    /** Luồng ghi duy nhất của kết nối. */
    private fun write() {
        while (true) {
            val frame = out.next() ?: return
            try {
                output.write(frame)
                output.flush()
            } catch (_: IOException) {
                shutdown()
                return
            }
        }
    }

    /** `amount` byte DATA đã ghi xuống (hay bỏ): trả tín dụng chung, gộp mỗi UPDATE_AFTER. */
    internal fun consumed(amount: Int) {
        val grant = synchronized(creditLock) {
            held -= amount
            unreturned += amount
            if (unreturned >= UPDATE_AFTER) unreturned.also { unreturned = 0 } else 0
        }
        if (grant > 0) runCatching { out.send(WINDOW, 0, int4(grant)) }
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
        out.push(stream.number, OPEN)
        stream.start()
        return stream.number
    }

    /** Đọc khung tới khi đường hầm đứt; đứt thì đóng mọi luồng. Không bao giờ chờ luồng nào: chỉ xếp hàng. */
    fun run() {
        val header = ByteArray(HEADER)
        var read = 0
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
                read += HEADER + length
                if (read >= ACK_AFTER) {
                    out.send(ACK, 0, int4(read))
                    read = 0
                }
                // Không dấu - như phía Python; số âm từ getInt() là sai giao thức.
                val amount = if ((kind == WINDOW || kind == ACK) && length == 4) ByteBuffer.wrap(payload).getInt() else 0
                if (number == 0) {
                    if (kind == ACK && amount > 0) {
                        out.acked(amount)
                    } else if (kind == WINDOW) {
                        if (amount !in 1..LINK_WINDOW) throw IOException("tín dụng chung sai")
                        out.credit(amount)
                    }
                    continue
                }
                if (kind == DATA) synchronized(creditLock) {
                    held += length
                    if (held + unreturned > LINK_WINDOW) throw IOException("gửi quá tín dụng chung")
                }
                val stream = synchronized(streams) { streams[number] }
                when {
                    kind == OPEN -> accept(number)
                    stream == null -> if (kind == DATA) { // bên kia tưởng luồng còn sống: bảo nó thôi
                        consumed(length)
                        out.send(RESET, number)
                    }
                    kind == RESET -> stream.close(abandoned = true)
                    kind == DATA -> stream.receive(payload)
                    kind == CLOSE -> stream.remoteEnded()
                    kind == WINDOW -> if (amount in 1..STREAM_WINDOW) stream.grant(amount) else stream.close(reset = true)
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
            out.send(RESET, number)
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
        out.close()
        all.forEach { it.close() }
        runCatching { closeLink() }
    }

    internal class Stream(private val mux: BtMux, val number: Int, @Volatile private var local: Socket?) {
        private val lock = Object()
        private var credit = STREAM_WINDOW
        private var queued = 0 // đã nhận, chưa ghi xuống
        private var unreturned = 0 // đã ghi xuống, chưa trả tín dụng
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

        /** Dữ liệu bên kia gửi (luồng đọc gọi - không bao giờ chờ). Quá tín dụng là sai giao thức: RESET. */
        fun receive(data: ByteArray) {
            val overflow = synchronized(lock) {
                if (!closed && queued + unreturned + data.size <= STREAM_WINDOW) {
                    queued += data.size
                    outgoing.put(data)
                    return
                }
                !closed
            }
            mux.consumed(data.size) // không giữ thì trả tín dụng chung ngay
            if (overflow) close(reset = true)
        }

        fun remoteEnded() = outgoing.put(end)

        /** socket cục bộ -> hàng của luồng này, chỉ trong phần tín dụng. */
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
                    if (count == 0) continue
                    // Xếp dưới khoá: đã đóng (RESET) thì không còn khung nào lọt vào sau `drop`.
                    synchronized(lock) {
                        if (closed) return
                        credit -= count
                        mux.out.push(number, DATA, buffer.copyOf(count))
                    }
                }
                synchronized(lock) {
                    if (closed) return
                    sentEnd = true
                    mux.out.push(number, CLOSE)
                }
            } catch (_: LinkClosed) {
                return // đường hầm đứt: shutdown() đã đóng mọi luồng
            } catch (_: IOException) {
                close(reset = true) // ứng dụng cục bộ cắt ngang, hay luồng vừa bị đóng
                return
            } catch (_: InterruptedException) {
                return
            }
            maybeDone()
        }

        /** đường hầm -> socket cục bộ; trả tín dụng (luồng và chung) sau khi đã ghi. */
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
                    val grant = synchronized(lock) {
                        if (closed) return // close() đã trả tín dụng chung cho mọi byte còn giữ, kể cả chỗ này
                        queued -= data.size
                        unreturned += data.size
                        if (unreturned >= UPDATE_AFTER) unreturned.also { unreturned = 0 } else 0
                    }
                    if (grant > 0) mux.out.send(WINDOW, number, int4(grant))
                    mux.consumed(data.size)
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

        /**
         * Đóng luồng (một lần). `reset`: đóng ngang - báo bên kia bỏ luồng, để nó không chờ tín dụng mãi. `abandoned`: bên
         * kia đã bỏ luồng (nó gửi RESET). Hai trường hợp ấy bỏ luôn khung chưa gửi; đóng thường thì khung còn xếp vẫn đi hết.
         */
        fun close(reset: Boolean = false, abandoned: Boolean = false) {
            val leftover = synchronized(lock) {
                if (closed) return
                closed = true
                lock.notifyAll()
                queued.also { queued = 0 }
            }
            local?.let { runCatching { it.close() } }
            outgoing.put(end)
            mux.forget(number)
            if (leftover > 0) mux.consumed(leftover)
            if (reset || abandoned) mux.out.drop(number)
            if (reset) runCatching { mux.out.send(RESET, number) }
        }
    }
}

/**
 * Mọi khung ra của một đầu đường hầm, cho MỘT luồng ghi - bản Kotlin của `_Outbox` (webui/bluetooth.py). Khung điều khiển
 * (`send`) đi trước, tối đa CONTROL_BURST khung liền khi DATA đang chờ; khung của từng luồng (`push`: OPEN, DATA, CLOSE -
 * giữ thứ tự trong luồng) xếp hàng riêng, chọn theo deficit round robin, mỗi lượt MAX_DATA byte. DATA còn cần tín dụng chung
 * (`credit`); mọi khung luồng dừng khi đã có `limit` byte đi mà bên kia chưa báo đọc (`acked`) - khung điều khiển thì không
 * bao giờ dừng (ACK hai chiều không được chờ nhau).
 */
internal class BtOutbox(private val limit: Int = BtMux.IN_FLIGHT, credit: Int = BtMux.LINK_WINDOW) {
    private val lock = Object()
    private val control = ArrayDeque<ByteArray>()
    private val queues = HashMap<Int, ArrayDeque<Pair<Int, ByteArray>>>()
    private val active = ArrayDeque<Int>() // luồng có khung chờ, theo lượt
    private val deficit = HashMap<Int, Int>()
    private var turn: Int? = null // luồng đang trong lượt (đã cộng phần lượt này)
    private var burst = 0
    private var linkCredit = credit
    private var inFlight = 0
    private var closed = false

    fun send(kind: Int, number: Int, payload: ByteArray = ByteArray(0)) = synchronized(lock) {
        if (closed) throw LinkClosed("đường hầm đã đóng")
        control.addLast(frame(kind, number, payload))
        lock.notifyAll()
    }

    fun push(number: Int, kind: Int, payload: ByteArray = ByteArray(0)) = synchronized(lock) {
        if (closed) throw LinkClosed("đường hầm đã đóng")
        val waiting = queues.getOrPut(number) {
            deficit[number] = 0
            active.addLast(number)
            ArrayDeque()
        }
        waiting.addLast(kind to payload)
        lock.notifyAll()
    }

    /** Bỏ mọi khung chưa gửi của một luồng (RESET): bên kia đã hay sẽ quên luồng ấy. */
    fun drop(number: Int) = synchronized(lock) {
        if (queues.remove(number) != null) {
            active.remove(number)
            deficit.remove(number)
            if (turn == number) turn = null
        }
    }

    fun credit(amount: Int) = synchronized(lock) {
        linkCredit += amount
        lock.notifyAll()
    }

    fun acked(amount: Int) = synchronized(lock) {
        inFlight = maxOf(0, inFlight - amount)
        lock.notifyAll()
    }

    fun close() = synchronized(lock) {
        closed = true
        lock.notifyAll()
    }

    /** Khung kế tiếp cho luồng ghi, chờ tới khi có khung gửi được. null: đã đóng (hay hết `timeoutMillis` nếu > 0). */
    fun next(timeoutMillis: Long = 0): ByteArray? = synchronized(lock) {
        val deadline = System.currentTimeMillis() + timeoutMillis
        while (!closed) {
            val frame = pick()
            if (frame != null) {
                inFlight += frame.size
                return frame
            }
            if (timeoutMillis > 0) {
                val left = deadline - System.currentTimeMillis()
                if (left <= 0) return null
                lock.wait(left)
            } else {
                lock.wait()
            }
        }
        null
    }

    private fun pick(): ByteArray? {
        if (control.isNotEmpty() && burst < BtMux.CONTROL_BURST) {
            burst++
            return control.removeFirst()
        }
        val frame = nextInTurn()
        if (frame != null) {
            burst = 0
            return frame
        }
        return control.removeFirstOrNull()
    }

    private fun nextInTurn(): ByteArray? {
        if (inFlight >= limit) return null
        repeat(active.size + 1) {
            val number = active.firstOrNull() ?: return null
            val waiting = queues.getValue(number)
            val (kind, payload) = waiting.first()
            val cost = payload.size
            if (kind == BtMux.DATA && cost > linkCredit) { // chờ tín dụng chung; luồng sau vẫn có thể gửi OPEN/CLOSE
                active.addLast(active.removeFirst())
                turn = null
                return@repeat
            }
            if (turn != number) {
                turn = number
                deficit[number] = deficit.getValue(number) + BtMux.MAX_DATA
            }
            if (cost > deficit.getValue(number)) { // hết lượt
                active.addLast(active.removeFirst())
                turn = null
                return@repeat
            }
            waiting.removeFirst()
            deficit[number] = deficit.getValue(number) - cost
            if (waiting.isEmpty()) {
                queues.remove(number)
                deficit.remove(number)
                active.removeFirst()
                turn = null
            }
            if (kind == BtMux.DATA) linkCredit -= cost
            return frame(kind, number, payload)
        }
        return null
    }
}

/**
 * Bên kết nối: cổng TCP cục bộ (127.0.0.1) mà mọi kết nối vào đều đi qua đường hầm - trình phát, SyncLink... chỉ việc dùng
 * https://127.0.0.1:<port> như một máy tính trong mạng. `port` 0 = để hệ thống chọn.
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
