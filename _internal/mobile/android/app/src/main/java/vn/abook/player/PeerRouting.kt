package vn.abook.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

internal data class DiscoveryHint(val host: String, val port: Int, val claimed: String)

/** Shared admission: at most two I/O jobs and sixteen queued hints across all discoveries. */
internal class DiscoveryAdmission : java.io.Closeable {
    private val pool = java.util.concurrent.ThreadPoolExecutor(2, 2, 0L, java.util.concurrent.TimeUnit.MILLISECONDS,
        java.util.concurrent.ArrayBlockingQueue<Runnable>(16),
        { task -> Thread(task, "peer-discovery-tls").apply { isDaemon = true } })

    fun submit(task: () -> Unit): Boolean = try {
        pool.execute { runCatching(task).onFailure { AppLog.w("PeerRouting", "Chưa xác minh được địa chỉ tìm thấy", it) } }
        true
    } catch (_: java.util.concurrent.RejectedExecutionException) { false }

    override fun close() { pool.shutdownNow() }
}

/** Bounded discovery batch; receive loop owns collection, routing owns verification. */
internal class DiscoveryHints(private val admission: DiscoveryAdmission = PeerRouting.discoveryAdmission,
                              private val verify: (DiscoveryHint) -> Unit) {
    private val hints = linkedMapOf<String, DiscoveryHint>()
    private var finished = false
    fun add(host: String, port: Int, claimed: String): Boolean {
        val address = PeerAddresses.endpoint(host, port)
        if (finished || address in hints || hints.size >= 64) return false
        val hint = DiscoveryHint(host, port, claimed)
        hints[address] = hint
        return true
    }
    fun finish() {
        if (finished) return
        finished = true
        for (hint in hints.values) if (hint.claimed.isNotBlank()) admission.submit { verify(hint) }
        hints.clear()
    }
}

/** The same route store and verified TLS selection for sync, peers, downloads and diagnostics. */
internal object PeerRouting {
    internal val discoveryAdmission = DiscoveryAdmission()
    fun main(context: Context): JSONObject = mainPrefs(SyncLink.prefs(context))

    @Synchronized fun mainPrefs(prefs: android.content.SharedPreferences): JSONObject {
        val values = prefs.all
        val peer = JSONObject().put("host", values["host"] as? String ?: "").put("port", values["port"] ?: 47630)
            .put("fingerprint", values["fingerprint"] as? String ?: "").put("token", values["token"] as? String ?: "")
            .put("bt", values["bt"] as? String ?: "")
        val hasAddresses = values.containsKey("addresses")
        val original = if (hasAddresses) runCatching { JSONArray(values["addresses"] as String) }.getOrNull() else null
        if (hasAddresses) peer.put("addresses", original ?: JSONObject.NULL)
        PeerAddresses.migrate(peer)
        if (!hasAddresses) {
            val legacy = runCatching { JSONArray(values["lan"] as String) }.getOrDefault(JSONArray())
            val values = JSONArray(PeerAddresses.ordered(peer)) // preserve the original paired host as the first item
            val legacyPort = prefs.all["lanPort"] ?: 47630
            for (i in 0 until legacy.length()) (legacy.opt(i) as? String)?.let { host ->
                PeerAddresses.discoveryEndpoint(host, legacyPort)?.let(values::put)
            }
            PeerAddresses.learn(peer, values, peer.optString("fingerprint"))
        }
        val clean = peer.getJSONArray("addresses").toString()
        val badPort = values.containsKey("port") && (values["port"] !is Int || (values["port"] as Int) !in 1..65535)
        val damaged = (hasAddresses && (original == null || original.toString() != clean)) || badPort ||
            (!hasAddresses && peer.optString("token").isNotBlank() && PeerAddresses.ordered(peer).isEmpty() && bluetooth(peer).isBlank())
        if (damaged) preserve(prefs, "routes", JSONObject(values).toString())
        if (!hasAddresses || values["addresses"] != clean || damaged) {
            val port = values["port"]?.toString()?.toIntOrNull()?.takeIf { it in 1..65535 } ?: 47630
            check(prefs.edit().putString("addresses", clean).putInt("port", port).remove("lan").remove("lanPort").commit()) { "Chưa lưu được địa chỉ máy đã ghép" }
        }
        return peer
    }

    internal fun preserve(prefs: android.content.SharedPreferences, key: String, raw: Any) {
        val copy = "$key.corrupt-${System.currentTimeMillis()}-${java.util.UUID.randomUUID()}"
        check(prefs.edit().putString(copy, raw.toString()).commit()) { "Chưa giữ được bản dữ liệu máy đã ghép" }
        Store.addDataNotice("Địa chỉ máy đã ghép bị hỏng; đã giữ bản cũ ở $copy — bạn ghép lại máy không còn địa chỉ.")
    }

    fun bluetooth(peer: JSONObject): String = peer.optString("host").let { if (it.startsWith("bt:")) it.removePrefix("bt:") else peer.optString("bt") }

    /** Cached, non-blocking choice for UI callers. Network workers resolve it before HTTP. */
    fun base(context: Context, peer: JSONObject): String {
        val choice = Route.pick(PeerAddresses.ordered(peer), bluetooth(peer))
        return choice.lan?.let { "https://$it" } ?: BluetoothLink.base(context, choice.bluetooth ?: throw IllegalStateException("Máy đã ghép chưa có địa chỉ; bạn hãy ghép lại"))
    }

    private fun find(context: Context, token: String): Pair<String?, JSONObject>? {
        val main = main(context)
        if (token.isNotBlank() && main.optString("token") == token) return null to main
        val peers = Peers.all(context)
        for (key in peers.keys()) peers.getJSONObject(key).let { if (token.isNotBlank() && it.optString("token") == token) return key to it }
        return null
    }

    @Synchronized fun remember(context: Context, token: String, reply: JSONObject?, seen: String, success: String = "") {
        val (key, peer) = find(context, token) ?: return
        if (seen.isBlank() || !seen.equals(peer.optString("fingerprint"), true)) return
        if (reply != null && !reply.optString("fingerprint", seen).equals(seen, true)) return
        PeerAddresses.learn(peer, reply?.optJSONArray("addresses"), seen, if (success == "bluetooth") "" else success)
        Route.invalidate(seen)
        reply?.optJSONObject("routes")?.optString("bluetooth")?.takeIf { it.isNotBlank() }?.let { peer.put("bt", it) }
        if (success.isNotBlank()) peer.put("connectedVia", success)
        if (key == null) {
            val editor = SyncLink.prefs(context).edit().putString("addresses", peer.getJSONArray("addresses").toString())
                .putString("bt", peer.optString("bt"))
            if (success.isNotBlank()) editor.putString("connectedVia", success)
            editor.commit()
        } else Peers.updateRoutes(context, key, peer)
    }

    fun expected(context: Context, token: String): String? = find(context, token)?.second?.optString("fingerprint")

    fun resolve(context: Context, root: String, token: String): String {
        val (_, peer) = find(context, token) ?: return root
        Route.noteNetwork(runCatching {
            (context.getSystemService(Context.CONNECTIVITY_SERVICE) as android.net.ConnectivityManager).activeNetwork?.toString().orEmpty()
        }.getOrDefault(""))
        val fingerprint = peer.optString("fingerprint")
        val lan = PeerAddresses.ordered(peer)
        val bt = bluetooth(peer)
        // Keep the existing immediate Bluetooth choice while all known IP routes are down; background probes retry them.
        val choice = Route.pick(lan, bt)
        if (choice.lan == null && bt.isNotBlank()) return BluetoothLink.base(context, bt)
        val preferred = listOfNotNull(choice.lan) + lan.filter { it != choice.lan }
        val chosen = Route.resolve(preferred, identity = fingerprint) { target ->
            Pin.probe(target, fingerprint) { throw Pin.ChangedException(it) }
        }
        if (chosen != null) {
            remember(context, token, null, fingerprint, chosen)
            return "https://$chosen"
        }
        if (bt.isNotBlank()) {
            val base = BluetoothLink.base(context, bt)
            // Still pinned by the actual request; never learn addresses from a TCP-only probe.
            return base
        }
        throw java.io.IOException("Không kết nối được máy kia; bạn hãy kiểm tra Wi-Fi hoặc Tailscale")
    }

    /** Discovery is only a hint: verify the socket against each stored pin before saving a new route. */
    fun discovered(context: Context, host: String, port: Int, claimed: String) {
        if (claimed.isBlank()) return
        val address = PeerAddresses.valid(PeerAddresses.endpoint(host, port), true) ?: return
        val candidates = mutableListOf(main(context))
        val peers = Peers.all(context)
        for (key in peers.keys()) candidates += peers.getJSONObject(key)
        for (peer in candidates) {
            val fingerprint = peer.optString("fingerprint")
            if (fingerprint.isNotBlank() && fingerprint.equals(claimed, true) && Pin.probe(address, fingerprint)) {
                remember(context, peer.optString("token"), JSONObject().put("addresses", JSONArray().put(address)), fingerprint, address)
                return
            }
        }
    }
}
