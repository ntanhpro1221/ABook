package vn.abook.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** The same route store and verified TLS selection for sync, peers, downloads and diagnostics. */
internal object PeerRouting {
    fun main(context: Context): JSONObject = mainPrefs(SyncLink.prefs(context))

    @Synchronized fun mainPrefs(prefs: android.content.SharedPreferences): JSONObject {
        val peer = JSONObject().put("host", prefs.getString("host", "")).put("port", prefs.getInt("port", 47630))
            .put("fingerprint", prefs.getString("fingerprint", "")).put("token", prefs.getString("token", ""))
            .put("bt", prefs.getString("bt", ""))
        if (prefs.contains("addresses")) peer.put("addresses", JSONArray(prefs.getString("addresses", "[]") ?: "[]"))
        else {
            PeerAddresses.migrate(peer)
            val legacy = runCatching { JSONArray(prefs.getString("lan", "[]") ?: "[]") }.getOrDefault(JSONArray())
            val values = JSONArray(PeerAddresses.ordered(peer)) // preserve the original paired host as the first item
            val legacyPort = prefs.getInt("lanPort", 47630).takeIf { it in 1..65535 } ?: 47630
            for (i in 0 until legacy.length()) values.put(PeerAddresses.endpoint(legacy.optString(i), legacyPort))
            PeerAddresses.learn(peer, values, peer.optString("fingerprint"))
            prefs.edit().putString("addresses", peer.getJSONArray("addresses").toString()).remove("lan").remove("lanPort").commit()
        }
        return peer
    }

    fun bluetooth(peer: JSONObject): String = peer.optString("host").let { if (it.startsWith("bt:")) it.removePrefix("bt:") else peer.optString("bt") }

    /** Cached, non-blocking choice for UI callers. Network workers resolve it before HTTP. */
    fun base(context: Context, peer: JSONObject): String {
        val choice = Route.pick(PeerAddresses.ordered(peer), bluetooth(peer))
        return choice.lan?.let { "https://$it" } ?: BluetoothLink.base(context, choice.bluetooth ?: throw IllegalStateException("Bạn chưa ghép máy này"))
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
