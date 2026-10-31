package vn.abook.player.net

import java.io.Closeable
import java.io.IOException
import java.io.InterruptedIOException
import java.net.HttpURLConnection
import java.net.Inet6Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Proxy
import java.net.ProxySelector
import java.net.Socket
import java.net.SocketTimeoutException
import java.net.URL
import java.net.UnknownHostException
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit

/**
 * MỘT cửa cho mọi kết nối TCP/HTTP đi ra khỏi app (31-10: mạng nhà sau cúp điện có địa chỉ IPv6 mà không có đường IPv6; DNS trả IPv6 trước, mà
 * HttpURLConnection của Android - như hầu hết thư viện - thử từng địa chỉ một, mỗi địa chỉ chờ trọn hạn nối trước khi sang IPv4: N địa chỉ = N lần hạn).
 *
 * [connect] đua các địa chỉ của một tên máy kiểu RFC 8305: xen kẽ họ IPv6/IPv4, bắt đầu địa chỉ kế sau [STAGGER_MS] hoặc ngay khi địa chỉ trước hỏng,
 * địa chỉ nối được đầu tiên thắng, phần còn lại đóng; hạn là hạn CHUNG của cả cuộc đua. Địa chỉ số (và tên chỉ ra một địa chỉ) đi y như trước:
 * một lần nối, không luồng phụ.
 *
 * [open] cho HttpURLConnection. Thư viện của Android không cho cắm đường nối. Mạng bình thường (địa chỉ ĐẦU của tên máy nối được - HttpURLConnection
 * thử nó trước) thì đi THẲNG, không proxy, không chép byte thêm; kết luận theo họ địa chỉ nhớ 5 phút nên chỉ lần đầu mới đua. Chỉ khi địa chỉ đầu chết
 * (vd IPv6 không có đường) kết nối mới đi qua [Tunnel] (proxy cục bộ do chính app dựng, nối ra bằng cuộc đua). Với HTTPS, TLS vẫn đầu-cuối với đúng tên máy gốc: SNI, kiểm chứng chỉ và vân tay ghim
 * ([vn.abook.player.Pin]) không đổi (đổi URL sang địa chỉ số thì mất SNI và kiểm tên, nên không làm thế). Địa chỉ số, tên chỉ ra một địa chỉ, hay máy có
 * proxy hệ thống: `URL.openConnection` như cũ. Kết nối của [open] KHÔNG tự theo chuyển hướng (proxy chỉ cho đúng máy đã đăng ký); nơi cần theo thì dùng [get].
 *
 * Quy tắc máy dò (FastConnectRulesTest): ngoài file này không ai được gọi `openConnection()` hay nối `Socket` trực tiếp.
 */
class FastConnect internal constructor(
    private val resolver: Resolver = Resolver.Dns,
    private val connector: Connector = Connector.Plain,
    private val staggerMs: Long = STAGGER_MS,
) : Closeable {

    /** Tra tên máy ra các địa chỉ, theo thứ tự hệ thống ưu tiên (đã sắp theo RFC 6724). */
    fun interface Resolver {
        fun resolve(host: String): List<InetAddress>

        companion object { val Dns = Resolver { InetAddress.getAllByName(it).toList() } }
    }

    /** Một lần nối TCP (đổi được trong bài thử để giả mạng "mù"). */
    fun interface Connector {
        fun connect(socket: Socket, address: InetSocketAddress, timeoutMs: Int)

        companion object { val Plain = Connector { socket, address, timeoutMs -> socket.connect(address, timeoutMs) } }
    }

    private val pool: ExecutorService = Executors.newCachedThreadPool { task -> Thread(task, "fast-connect").apply { isDaemon = true } }
    private val winners = ConcurrentHashMap<String, Winner>()
    /** Kết luận theo HỌ địa chỉ (true = IPv6) trên mạng hiện tại: sống / chết, 5 phút ([forgetNetwork] xoá khi đổi mạng). */
    private val verdicts = ConcurrentHashMap<Boolean, Verdict>()

    private class Verdict(val alive: Boolean, val at: Long)
    private var tunnelInstance: Tunnel? = null

    /** Số kết nối đã vào proxy cục bộ (bài thử: đường thẳng thì 0). */
    internal val tunnelAccepted: Int get() = synchronized(this) { tunnelInstance?.accepted?.get() ?: 0 }

    @Synchronized private fun tunnel(): Tunnel = tunnelInstance ?: Tunnel(this, pool).also { tunnelInstance = it }

    private class Winner(val address: InetAddress, val at: Long)

    private class Attempt(val address: InetSocketAddress) {
        val socket = Socket()
        @Volatile var error: IOException? = null
    }

    /**
     * Socket đã nối tới `host:port`. `timeoutMs` là hạn của cả việc (tra tên + đua); <= 0 là không hạn. Lỗi: [UnknownHostException] khi tên không ra
     * địa chỉ nào, [SocketTimeoutException] khi hết hạn, còn lại là lỗi của địa chỉ thử CUỐI CÙNG.
     */
    fun connect(host: String, port: Int, timeoutMs: Int): Socket {
        val deadline = deadlineIn(timeoutMs)
        return connectTo(host, addressesOf(host), port, deadline)
    }

    /** Như [connect] nhưng ưu tiên địa chỉ vừa thắng gần đây (không đua lại khi không cần); hỏng thì đua lại từ đầu. */
    internal fun connectWarm(host: String, port: Int, timeoutMs: Int): Socket {
        val cached = warm(host)
        if (cached != null) {
            val socket = Socket()
            try {
                connector.connect(socket, InetSocketAddress(cached, port), if (timeoutMs > 0) minOf(timeoutMs, WARM_TRY_MS) else WARM_TRY_MS)
                return socket
            } catch (error: IOException) {
                closeQuietly(socket)
                winners.remove(key(host))
            }
        }
        val deadline = deadlineIn(timeoutMs)
        return connectTo(host, healthyFirst(addressesOf(host)), port, deadline)
    }

    internal fun warm(host: String): InetAddress? =
        winners[key(host)]?.takeIf { System.nanoTime() - it.at < TimeUnit.MILLISECONDS.toNanos(WARM_MS) }?.address

    /**
     * Cuộc đua dạy về mạng: địa chỉ ĐẦU (cái HttpURLConnection thử trước) thắng thì họ của nó sống; họ khác thắng thì họ đầu coi như chết (không có đường,
     * hay chậm hơn cả [staggerMs]) và họ kia sống. Cùng họ nhưng không phải địa chỉ đầu thì chưa kết luận gì.
     */
    private fun learn(first: InetAddress, winner: InetAddress) {
        val now = System.nanoTime()
        val firstV6 = first is Inet6Address
        if (winner == first) verdicts[firstV6] = Verdict(true, now)
        else if ((winner is Inet6Address) != firstV6) {
            verdicts[firstV6] = Verdict(false, now)
            verdicts[!firstV6] = Verdict(true, now)
        }
    }

    /** true / false = họ của `first` đang sống / chết (còn hạn); null = chưa biết. */
    private fun familyAlive(first: InetAddress): Boolean? =
        verdicts[first is Inet6Address]?.takeIf { System.nanoTime() - it.at < TimeUnit.MILLISECONDS.toNanos(VERDICT_MS) }?.alive

    /** Đổi mạng (Wi-Fi <-> 4G, có/mất IPv6): mọi kết luận cũ hết giá trị. */
    fun forgetNetwork() { verdicts.clear(); winners.clear() }

    /** Họ đang chết đi sau cùng, để cuộc đua mở đầu bằng họ còn sống. */
    private fun healthyFirst(addresses: List<InetAddress>): List<InetAddress> =
        addresses.sortedBy { familyAlive(it) == false }

    private fun key(host: String) = host.trim().trim('[', ']').lowercase()

    private fun addressesOf(host: String): List<InetAddress> {
        val bare = host.trim().trim('[', ']')
        if (bare.isEmpty()) throw UnknownHostException("thiếu tên máy")
        if (isLiteral(bare)) return listOf(InetAddress.getByName(bare))
        val found = interleave(resolver.resolve(bare))
        if (found.isEmpty()) throw UnknownHostException(bare)
        return found
    }

    private fun connectTo(host: String, addresses: List<InetAddress>, port: Int, deadline: Long): Socket {
        if (addresses.size == 1) {
            val socket = Socket()
            try {
                connector.connect(socket, InetSocketAddress(addresses[0], port), remainingMs(deadline))
                return socket
            } catch (error: Throwable) {
                closeQuietly(socket)
                throw error
            }
        }
        return race(host, addresses, port, deadline).socket
    }

    private fun race(host: String, addresses: List<InetAddress>, port: Int, deadline: Long): Attempt {
        val outcomes = LinkedBlockingQueue<Attempt>()
        val started = ArrayList<Attempt>(addresses.size)
        var winner: Attempt? = null
        var lastError: IOException? = null
        var failures = 0
        var nextAt = System.nanoTime()
        try {
            while (true) {
                val now = System.nanoTime()
                if (deadline != NO_DEADLINE && now - deadline >= 0) {
                    throw SocketTimeoutException("hết giờ nối tới $host:$port").apply { lastError?.let { initCause(it) } }
                }
                if (started.size < addresses.size && now - nextAt >= 0) {
                    val attempt = Attempt(InetSocketAddress(addresses[started.size], port))
                    started += attempt
                    val budget = remainingMs(deadline)
                    pool.execute {
                        try {
                            connector.connect(attempt.socket, attempt.address, budget)
                        } catch (error: IOException) {
                            attempt.error = error
                        } catch (error: Throwable) {
                            attempt.error = IOException(error)
                        }
                        outcomes.add(attempt)
                    }
                    nextAt = now + TimeUnit.MILLISECONDS.toNanos(staggerMs)
                    continue
                }
                var wake = if (started.size < addresses.size) nextAt - now else Long.MAX_VALUE
                if (deadline != NO_DEADLINE) wake = minOf(wake, deadline - now)
                val done = try {
                    outcomes.poll(wake, TimeUnit.NANOSECONDS)
                } catch (error: InterruptedException) {
                    Thread.currentThread().interrupt()
                    throw InterruptedIOException("bị ngắt khi đang nối")
                } ?: continue
                val error = done.error
                if (error == null) {
                    winner = done
                    done.address.address.let { winners[key(host)] = Winner(it, System.nanoTime()) }
                    learn(addresses[0], done.address.address)
                    return done
                }
                lastError = error
                failures++
                if (failures == addresses.size) throw error // hỏng hết: lỗi của địa chỉ hỏng sau cùng
                if (started.size < addresses.size) nextAt = System.nanoTime() // địa chỉ trước hỏng: địa chỉ kế đi ngay
            }
        } finally {
            for (attempt in started) if (attempt !== winner) closeQuietly(attempt.socket)
        }
    }

    // ---- HttpURLConnection ---------------------------------------------------------------------------------------------

    /**
     * Kết nối HTTP(S) tới `url`, `connectTimeout` đã đặt, KHÔNG tự theo chuyển hướng. `proxy` như `URL.openConnection(proxy)`
     * (null = proxy hệ thống như cũ). Tra tên + đua địa chỉ xảy ra NGAY ở đây (lỗi mạng ra đúng loại: [UnknownHostException], [SocketTimeoutException]...),
     * không đợi tới lúc đọc trả lời.
     */
    fun open(url: String, connectTimeoutMs: Int, proxy: Proxy? = null): HttpURLConnection {
        val connection = prepare(URL(url), connectTimeoutMs, proxy)
        connection.connectTimeout = connectTimeoutMs
        connection.instanceFollowRedirects = false
        return connection
    }

    /** GET-kiểu: [open] rồi `configure` (header, hạn đọc), theo tối đa [maxRedirects] chuyển hướng (không bao giờ https -> http); trả kết nối đã có mã trả lời cuối. */
    fun get(url: String, connectTimeoutMs: Int, maxRedirects: Int = 5, configure: (HttpURLConnection) -> Unit = {}): HttpURLConnection {
        var current = url
        repeat(maxRedirects + 1) {
            val connection = open(current, connectTimeoutMs)
            try {
                configure(connection)
                val code = connection.responseCode
                if (code !in REDIRECTS) return connection
                val next = URL(URL(current), connection.getHeaderField("Location") ?: throw IOException("HTTP $code không có nơi chuyển tới"))
                if (current.startsWith("https://", ignoreCase = true) && !next.protocol.equals("https", ignoreCase = true)) {
                    throw IOException("bị chuyển sang địa chỉ không an toàn")
                }
                current = next.toString()
            } catch (error: Throwable) {
                connection.disconnect()
                throw error
            }
            connection.disconnect()
        }
        throw IOException("chuyển hướng quá nhiều lần")
    }

    /**
     * Cho nơi chỉ nhận được địa chỉ (không nhận được HttpURLConnection - Media3 DefaultHttpDataSource): `url` với tên máy đổi thành địa chỉ thắng cuộc.
     * CHỈ dùng khi việc kiểm chứng chứng chỉ không dựa vào tên máy (thiết bị đã ghép, ghim vân tay); không đổi khi là địa chỉ số hay chỉ có một địa chỉ.
     */
    fun literalUrl(url: String, connectTimeoutMs: Int = LITERAL_MS): String {
        val target = URL(url)
        val host = target.host.trim('[', ']')
        if (host.isEmpty() || isLiteral(host)) return url
        val deadline = deadlineIn(connectTimeoutMs)
        val addresses = addressesOf(host)
        if (addresses.size <= 1) return url
        val socket = connectTo(host, addresses, portOf(target), deadline)
        val chosen = socket.inetAddress
        closeQuietly(socket)
        return URL(target.protocol, literalHost(chosen), target.port, target.file).toString()
    }

    private fun prepare(target: URL, connectTimeoutMs: Int, proxy: Proxy?): HttpURLConnection {
        fun direct() = (if (proxy != null) target.openConnection(proxy) else target.openConnection()) as HttpURLConnection
        val host = target.host.trim('[', ']')
        if (!target.protocol.equals("https", ignoreCase = true) && !target.protocol.equals("http", ignoreCase = true)) return direct()
        if (host.isEmpty() || isLiteral(host)) return direct()
        if (proxy != null && proxy.type() != Proxy.Type.DIRECT) return direct()
        if (proxy == null && viaSystemProxy(target)) return direct()
        val deadline = deadlineIn(connectTimeoutMs)
        val addresses = addressesOf(host)
        if (addresses.size <= 1) return direct()
        val port = portOf(target)
        // Đường bình thường đi THẲNG (không chép byte qua proxy): HttpURLConnection thử địa chỉ ĐẦU trước, nên họ của nó sống là đủ.
        // Chỉ khi địa chỉ đầu chết (vd IPv6 không có đường) mới qua proxy, nơi cuộc đua chọn địa chỉ khác.
        val first = addresses[0]
        when (familyAlive(first)) {
            true -> return direct()
            false -> Unit
            null -> {
                // Chưa biết mạng này: đua một lần (cái socket thắng dùng luôn nếu phải qua proxy); kết luận nhớ 5 phút nên host khác khỏi đua.
                val attempt = race(host, addresses, port, deadline)
                if (attempt.address.address == first) {
                    closeQuietly(attempt.socket)
                    return direct()
                }
                return target.openConnection(tunnel().proxyFor(host, port, connectTimeoutMs, attempt.socket)) as HttpURLConnection
            }
        }
        // Họ đầu đang chết: nối ngay bằng họ còn sống (đua lại chỉ khi chưa có địa chỉ thắng gần đây cho host này).
        val ahead = if (warm(host) == null) connectTo(host, healthyFirst(addresses), port, deadline) else null
        return target.openConnection(tunnel().proxyFor(host, port, connectTimeoutMs, ahead)) as HttpURLConnection
    }

    private fun viaSystemProxy(target: URL): Boolean = try {
        ProxySelector.getDefault()?.select(target.toURI())?.any { it.type() != Proxy.Type.DIRECT } == true
    } catch (_: Exception) {
        false
    }

    private fun portOf(target: URL) = if (target.port > 0) target.port else target.defaultPort

    override fun close() {
        synchronized(this) { tunnelInstance?.close() }
        pool.shutdownNow()
    }

    companion object {
        /** Chờ bao lâu thì thử địa chỉ kế khi địa chỉ trước chưa trả lời (RFC 8305 §5: 250 ms). */
        const val STAGGER_MS = 250L
        private const val WARM_MS = 30_000L
        private const val VERDICT_MS = 300_000L
        private const val WARM_TRY_MS = 3_000
        private const val LITERAL_MS = 5_000
        private const val NO_DEADLINE = Long.MAX_VALUE
        private val REDIRECTS = setOf(301, 302, 303, 307, 308)
        private val IPV4 = Regex("""(?:[0-9]{1,3}\.){3}[0-9]{1,3}""")

        private val shared by lazy { FastConnect() }

        fun connect(host: String, port: Int, timeoutMs: Int): Socket = shared.connect(host, port, timeoutMs)
        fun open(url: String, connectTimeoutMs: Int, proxy: Proxy? = null): HttpURLConnection = shared.open(url, connectTimeoutMs, proxy)
        fun forgetNetwork() = shared.forgetNetwork()
        fun get(url: String, connectTimeoutMs: Int, maxRedirects: Int = 5, configure: (HttpURLConnection) -> Unit = {}): HttpURLConnection =
            shared.get(url, connectTimeoutMs, maxRedirects, configure)
        fun literalUrl(url: String, connectTimeoutMs: Int = LITERAL_MS): String = shared.literalUrl(url, connectTimeoutMs)

        /** Địa chỉ viết thẳng (IPv4 hay IPv6): không cần tra tên, không đua. */
        internal fun isLiteral(host: String): Boolean = ':' in host || IPV4.matches(host)

        /** Xen kẽ hai họ địa chỉ, họ của địa chỉ đầu (hệ thống đã ưu tiên) đi trước; bỏ trùng, giữ thứ tự trong từng họ. */
        internal fun interleave(addresses: List<InetAddress>): List<InetAddress> {
            val unique = addresses.distinct()
            if (unique.size < 2) return unique
            val firstIsV6 = unique[0] is Inet6Address
            val same = unique.filter { (it is Inet6Address) == firstIsV6 }
            val other = unique.filter { (it is Inet6Address) != firstIsV6 }
            return buildList { for (i in 0 until maxOf(same.size, other.size)) { same.getOrNull(i)?.let(::add); other.getOrNull(i)?.let(::add) } }
        }

        private fun literalHost(address: InetAddress): String =
            if (address is Inet6Address) "[${address.hostAddress.substringBefore('%')}]" else address.hostAddress.orEmpty()

        private fun deadlineIn(timeoutMs: Int): Long =
            if (timeoutMs <= 0) NO_DEADLINE else System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(timeoutMs.toLong())

        /** Mili giây còn lại tới hạn (>= 1: 0 nghĩa là "không hạn" với Socket.connect); hết hạn thì [SocketTimeoutException]. */
        private fun remainingMs(deadline: Long): Int {
            if (deadline == NO_DEADLINE) return 0
            val left = TimeUnit.NANOSECONDS.toMillis(deadline - System.nanoTime())
            if (left <= 0) throw SocketTimeoutException("hết giờ trước khi nối")
            return minOf(left, Int.MAX_VALUE.toLong()).toInt()
        }

        internal fun closeQuietly(socket: Socket) {
            try { socket.close() } catch (_: IOException) { }
        }
    }
}
