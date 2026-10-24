package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.net.InetAddress

/** Persistent route schema shared by the main computer and every other peer. No network I/O here. */
internal object PeerAddresses {
    const val LIMIT = 8
    fun endpoint(host: String, port: Int): String = if (':' in host) "[${host.trim('[', ']')}]:$port" else "$host:$port"
    fun split(value: String): Pair<String, Int> = value.substringBeforeLast(':').trim('[', ']') to value.substringAfterLast(':').toInt()

    fun valid(value: String, advertised: Boolean = false): String? = runCatching {
        val (host, port) = split(value)
        require(port in 1..65535 && host.isNotBlank())
        require(host.all { it in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-:" })
        val numeric = ':' in host || host.matches(Regex("(?:[0-9]{1,3}\\.){3}[0-9]{1,3}"))
        val canonical = if (numeric) {
            if (':' in host) require(host.all { it in "0123456789abcdefABCDEF:." })
            else require(host.split('.').all { it.toIntOrNull()?.let { value -> value in 0..255 } == true })
            // Numeric literals only: InetAddress also maps IPv4-mapped IPv6 to IPv4.
            val ip = InetAddress.getByName(host)
            if (advertised) require(!ip.isLoopbackAddress && !ip.isLinkLocalAddress && !ip.isAnyLocalAddress && !ip.isMulticastAddress)
            canonicalIp(ip.address)
        } else {
            require(!advertised)
            host.lowercase(java.util.Locale.ROOT).trimEnd('.')
        }
        endpoint(canonical, port)
    }.getOrNull()

    private fun canonicalIp(bytes: ByteArray): String {
        if (bytes.size == 4) return bytes.joinToString(".") { (it.toInt() and 255).toString() }
        val words = (0 until 8).map { ((bytes[it * 2].toInt() and 255) shl 8) or (bytes[it * 2 + 1].toInt() and 255) }
        var best = -1
        var length = 1
        var i = 0
        while (i < words.size) {
            if (words[i] != 0) { i++; continue }
            val start = i
            while (i < words.size && words[i] == 0) i++
            if (i - start > length) { best = start; length = i - start }
        }
        if (best < 0) return words.joinToString(":") { it.toString(16) }
        return words.take(best).joinToString(":") { it.toString(16) } + "::" +
            words.drop(best + length).joinToString(":") { it.toString(16) }
    }

    fun candidates(values: List<String>): List<String> = values.map { valid(it) ?: it }.distinct().take(LIMIT)

    /** Parse the original JSON value before optInt can truncate an oversized numeric port. */
    fun discoveryEndpoint(host: String, rawPort: Any?): String? {
        val port = rawPort?.toString()?.toIntOrNull() ?: return null
        return valid(endpoint(host, port), advertised = true)
    }

    fun migrate(peer: JSONObject): Boolean {
        val missing = !peer.has("addresses")
        val before = peer.opt("addresses")?.toString()
        if (missing) {
            val host = peer.opt("host") as? String ?: ""
            val address = if (host.startsWith("bt:")) null else {
                val port = (if (peer.has("port")) peer.opt("port") else 47630)?.toString()?.toIntOrNull()
                port?.let { valid(endpoint(host, it)) }
            }
            peer.put("addresses", JSONArray().apply { if (address != null) put(JSONObject().put("address", address).put("lastSuccess", 0)) })
        }
        peer.put("addresses", records(peer.optJSONArray("addresses")))
        return missing || before != peer.getJSONArray("addresses").toString()
    }

    private fun records(array: JSONArray?): JSONArray {
        val merged = linkedMapOf<String, JSONObject>()
        if (array != null) for (i in 0 until array.length()) {
            val item = array.optJSONObject(i) ?: continue
            val address = (item.opt("address") as? String)?.let { valid(it) } ?: continue
            val raw = if (item.has("lastSuccess")) item.opt("lastSuccess") else 0
            val at = (raw as? Number)?.toDouble() ?: continue
            if (!at.isFinite() || at < 0) continue
            if (merged[address] == null || at > merged.getValue(address).getDouble("lastSuccess"))
                merged[address] = JSONObject().put("address", address).put("lastSuccess", at)
        }
        return JSONArray(merged.values.sortedByDescending { it.getDouble("lastSuccess") }.take(LIMIT))
    }

    fun ordered(peer: JSONObject): List<String> = records(peer.optJSONArray("addresses")).let { array ->
        (0 until array.length()).map { array.getJSONObject(it).getString("address") }
    }

    fun learn(peer: JSONObject, values: JSONArray?, seen: String, success: String = "", at: Double = System.currentTimeMillis() / 1000.0,
              claimed: String = seen): Boolean {
        if (seen.isBlank() || !seen.equals(peer.optString("fingerprint"), ignoreCase = true) || !seen.equals(claimed, true)) return false
        val before = peer.optJSONArray("addresses")?.toString() ?: "[]"
        val merged = linkedMapOf<String, JSONObject>()
        val old = records(peer.optJSONArray("addresses"))
        for (i in 0 until old.length()) old.optJSONObject(i)?.let { item -> valid(item.optString("address"))?.let { address ->
            val atOld = item.optDouble("lastSuccess", 0.0)
            if (merged[address] == null || atOld > merged.getValue(address).optDouble("lastSuccess", 0.0))
                merged[address] = JSONObject().put("address", address).put("lastSuccess", atOld)
        } }
        val fresh = mutableSetOf<String>()
        if (values != null) for (i in 0 until minOf(values.length(), 32)) valid(values.optString(i), true)?.let {
            fresh += it
            merged.putIfAbsent(it, JSONObject().put("address", it).put("lastSuccess", 0))
        }
        valid(success)?.let { merged.getOrPut(it) { JSONObject().put("address", it) }.put("lastSuccess", at) }
        // Keep the active route and make room for current, authenticated advertisements.
        val active = valid(success) ?: ordered(peer).firstOrNull()
        peer.put("addresses", JSONArray(merged.values.sortedWith(compareBy<JSONObject> { it.optString("address") != active }
            .thenBy { it.optString("address") !in fresh }.thenByDescending { it.optDouble("lastSuccess", 0.0) }).take(LIMIT)))
        return before != peer.getJSONArray("addresses").toString()
    }
}
