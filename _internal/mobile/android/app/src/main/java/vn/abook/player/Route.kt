package vn.abook.player

import vn.abook.player.net.FastConnect
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

/**
 * Tự chọn đường tới máy tính chính (feat/auto-route, chủ sách 27-09: "tự nhận biết LAN hay..."): ghép một lần, lời đáp
 * ghép cho biết mọi đường (địa chỉ LAN + cổng, địa chỉ Bluetooth - sync.py `routes`), rồi mỗi yêu cầu đi Wi-Fi khi địa chỉ
 * LAN đang thông, Bluetooth khi không.
 *
 * KHÔNG BAO GIỜ CHẶN người gọi (có chỗ gọi từ luồng giao diện): chọn theo kết quả thử đã biết; kết quả cũ hơn FRESH_MS
 * hay chưa có thì thử lại ở luồng nền (nối TCP 1,5 giây) - lần gọi sau thấy kết quả mới. Yêu cầu qua LAN hỏng lúc nối
 * thì `markDown` ngay. Network workers use [resolve] to verify IP candidates before HTTP; Bluetooth remains the fallback.
 */
object Route {
    const val FRESH_MS = 60_000L
    private const val PROBE_MS = 1500

    private data class Seen(val up: Boolean, val at: Long)

    private val seen = ConcurrentHashMap<String, Seen>()
    private val probing = ConcurrentHashMap.newKeySet<String>()
    private val admission = Any()
    private val pool = Executors.newFixedThreadPool(2) { task -> Thread(task, "route-probe").apply { isDaemon = true } }
    private val resolver = TlsRouteResolver()
    private val verified = ConcurrentHashMap<String, Long>()

    /** TLS only. TCP success prioritizes a candidate; it never bypasses the pin check. */
    internal fun resolve(lan: List<String>, identity: String = "", probe: (String) -> Boolean): String? {
        val targets = PeerAddresses.candidates(lan)
            .sortedByDescending { seen[it]?.up == true }
        targets.firstOrNull { System.currentTimeMillis() - (verified["$identity|$it"] ?: 0L) < 5000 }?.let { return it }
        return resolver.resolve(identity, targets) { target ->
            if (!probe(target)) { markDown(target); false }
            else {
                markUp(target)
                verified["$identity|$target"] = System.currentTimeMillis()
                true
            }
        }
    }

    internal fun invalidate(identity: String) = resolver.invalidate(identity)
    private var network = ""
    @Synchronized internal fun noteNetwork(value: String) {
        if (network != value) {
            network = value
            seen.clear()
            verified.clear()
            resolver.invalidateAll()
        }
    }

    /** Kết quả chọn: `lan` = "host:port" đi Wi-Fi, hay `bluetooth` = địa chỉ Bluetooth. */
    data class Choice(val lan: String?, val bluetooth: String?)

    /**
     * Chọn đường, thuần (test được): LAN đã biết là thông -> LAN đầu tiên như thế; không có mà có Bluetooth -> Bluetooth
     * nếu mọi LAN đã biết là hỏng hay không có LAN nào; còn lại (chưa biết) -> LAN đầu tiên (lạc quan: cùng Wi-Fi là thường
     * gặp nhất) - nếu không có LAN thì Bluetooth.
     */
    fun choose(lan: List<String>, bluetooth: String?, known: (String) -> Boolean?): Choice {
        lan.firstOrNull { known(it) == true }?.let { return Choice(it, null) }
        val bt = bluetooth?.takeIf { it.isNotBlank() }
        if (bt != null && (lan.isEmpty() || lan.all { known(it) == false })) return Choice(null, bt)
        val untried = lan.firstOrNull { known(it) == null }
        return when {
            untried != null -> Choice(untried, null)
            bt != null -> Choice(null, bt)
            lan.isNotEmpty() -> Choice(lan.first(), null)
            else -> Choice(null, null)
        }
    }

    /** Chọn đường cho các địa chỉ ấy, và thử lại nền những địa chỉ chưa biết hay đã cũ. */
    fun pick(lan: List<String>, bluetooth: String?, now: Long = System.currentTimeMillis(),
             probe: ((String) -> Boolean)? = null): Choice {
        val targets = PeerAddresses.candidates(lan)
        for (target in targets) {
            if (probe == null && !numeric(target)) continue
            val accepted = synchronized(admission) {
                val last = seen[target]
                (last == null || now - last.at > FRESH_MS) && probing.size < 2 && probing.add(target)
            }
            if (accepted) {
                pool.execute {
                    try {
                        seen[target] = Seen((probe ?: ::probe)(target), System.currentTimeMillis())
                    } finally {
                        probing.remove(target)
                    }
                }
            }
        }
        return choose(targets, bluetooth) { target -> seen[target]?.takeIf { now - it.at <= FRESH_MS }?.up }
    }

    fun markDown(target: String) {
        verified.keys.filter { it.endsWith("|$target") }.forEach { verified.remove(it) }
        seen[target] = Seen(false, System.currentTimeMillis())
    }

    fun markUp(target: String) {
        seen[target] = Seen(true, System.currentTimeMillis())
    }

    internal fun pendingProbes(): Int = probing.size

    private fun numeric(target: String): Boolean {
        val host = target.substringBeforeLast(":").trim('[', ']')
        return ':' in host || host.matches(Regex("(?:[0-9]{1,3}\\.){3}[0-9]{1,3}"))
    }

    private fun probe(target: String): Boolean {
        val host = target.substringBeforeLast(":").trim('[', ']')
        val port = target.substringAfterLast(":").toIntOrNull() ?: return false
        // Only numeric literals: no hostname may block the global TCP hint workers in DNS.
        if (!numeric(target)) return false
        return runCatching { FastConnect.connect(host, port, PROBE_MS).close() }.isSuccess
    }
}
