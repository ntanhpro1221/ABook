package vn.ebookreader.player

import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

/**
 * Tự chọn đường tới máy tính chính (feat/auto-route, chủ sách 27-09: "tự nhận biết LAN hay..."): ghép một lần, lời đáp
 * ghép cho biết mọi đường (địa chỉ LAN + cổng, địa chỉ Bluetooth - sync.py `routes`), rồi mỗi yêu cầu đi Wi-Fi khi địa chỉ
 * LAN đang thông, Bluetooth khi không.
 *
 * KHÔNG BAO GIỜ CHẶN người gọi (có chỗ gọi từ luồng giao diện): chọn theo kết quả thử đã biết; kết quả cũ hơn FRESH_MS
 * hay chưa có thì thử lại ở luồng nền (nối TCP 1,5 giây) - lần gọi sau thấy kết quả mới. Yêu cầu qua LAN hỏng lúc nối
 * thì `markDown` ngay: SyncLink thử lại một lần qua Bluetooth.
 */
object Route {
    const val FRESH_MS = 60_000L
    private const val PROBE_MS = 1500

    private data class Seen(val up: Boolean, val at: Long)

    private val seen = ConcurrentHashMap<String, Seen>()
    private val probing = ConcurrentHashMap.newKeySet<String>()
    private val pool = Executors.newCachedThreadPool()

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
    fun pick(lan: List<String>, bluetooth: String?, now: Long = System.currentTimeMillis()): Choice {
        for (target in lan) {
            val last = seen[target]
            if ((last == null || now - last.at > FRESH_MS) && probing.add(target)) {
                pool.execute {
                    try {
                        seen[target] = Seen(probe(target), System.currentTimeMillis())
                    } finally {
                        probing.remove(target)
                    }
                }
            }
        }
        return choose(lan, bluetooth) { target -> seen[target]?.up }
    }

    fun markDown(target: String) {
        seen[target] = Seen(false, System.currentTimeMillis())
    }

    fun markUp(target: String) {
        seen[target] = Seen(true, System.currentTimeMillis())
    }

    private fun probe(target: String): Boolean {
        val host = target.substringBeforeLast(":")
        val port = target.substringAfterLast(":").toIntOrNull() ?: return false
        return runCatching { Socket().use { it.connect(InetSocketAddress(host, port), PROBE_MS) } }.isSuccess
    }
}
