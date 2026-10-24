package vn.abook.player

import android.content.SharedPreferences
import java.lang.reflect.Proxy
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PeerPrefsTest {
    private fun prefs(values: MutableMap<String, Any>): SharedPreferences {
        val changes = mutableMapOf<String, Any?>()
        val editor = Proxy.newProxyInstance(javaClass.classLoader, arrayOf(SharedPreferences.Editor::class.java)) { proxy, method, args ->
            when (method.name) {
                "putString", "putInt" -> { changes[args!![0] as String] = args[1]; proxy }
                "remove" -> { changes[args!![0] as String] = null; proxy }
                "commit", "apply" -> { changes.forEach { (key, value) -> if (value == null) values.remove(key) else values[key] = value }; changes.clear(); true }
                else -> null
            }
        } as SharedPreferences.Editor
        return Proxy.newProxyInstance(javaClass.classLoader, arrayOf(SharedPreferences::class.java)) { _, method, args ->
            when (method.name) {
                "getAll" -> values.toMap()
                "getString" -> values[args!![0]] as? String ?: args[1]
                "getInt" -> values[args!![0]] as? Int ?: args[1]
                "contains" -> values.containsKey(args!![0])
                "edit" -> editor
                else -> null
            }
        } as SharedPreferences
    }

    @Test fun corruptMainAddressesAreKeptAndDoNotCrashReads() {
        for (raw in listOf("[broken", "null", "[17]")) {
            val values = mutableMapOf<String, Any>("host" to "phone.local", "port" to 47630, "token" to "t", "addresses" to raw)
            val storage = prefs(values)
            assertTrue(PeerAddresses.ordered(PeerRouting.mainPrefs(storage)).isEmpty())
            assertTrue(values.any { (key, value) -> key.startsWith("routes.corrupt-") && JSONObject(value as String).getString("addresses") == raw })
            val count = values.size
            assertTrue(PeerAddresses.ordered(PeerRouting.mainPrefs(storage)).isEmpty())
            assertEquals(count, values.size)
        }
    }

    @Test fun corruptPeerDoesNotHideOtherPeersAndRawPreferenceSurvivesWrites() {
        val raw = """{"bad":17,"badPort":{"host":"phone.local","port":"invalid"},"good":{"host":"10.0.0.1","port":47630,"token":"t"}}"""
        val values = mutableMapOf<String, Any>("peers" to raw)
        val storage = prefs(values)
        val peers = Peers.readPrefs(storage)
        assertEquals(listOf("good"), peers.keys().asSequence().toList())
        assertEquals(listOf("10.0.0.1:47630"), PeerAddresses.ordered(peers.getJSONObject("good")))
        assertTrue(values.any { (key, value) -> key.startsWith("peers.corrupt-") && value == raw })
        val before = values.toMap()
        Peers.readPrefs(storage)
        assertEquals(before, values)
    }
}
