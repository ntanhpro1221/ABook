package vn.abook.player

import java.io.File
import java.util.UUID
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PeerEndpointsTest {
    private fun endpoints(): JSONObject = JSONObject(File("../../../abook/webui/assets/peer_endpoints.json").readText())

    @Test fun release_endpoints_are_frozen() {
        val release = endpoints().getJSONObject("release")
        assertEquals(47630, release.getInt("port"))
        assertEquals(release.getInt("port"), BuildConfig.DEFAULT_PEER_PORT)
        assertEquals(47631, release.getInt("discoveryPort"))
        assertEquals("a1f667fe-352a-49b7-9b91-a5463677cac0", release.getString("serviceUuid"))
        assertEquals(release.getString("serviceUuid"), BluetoothLink.SERVICE.toString())
    }

    @Test fun server_and_discovery_use_the_current_variant_build_fields() {
        val dev = endpoints().getJSONObject("debug")
        val release = endpoints().getJSONObject("release")
        val current = if (BuildConfig.DEBUG) dev else release
        assertEquals(current.getInt("port"), LibraryServer.PORT)
        assertEquals(current.getInt("discoveryPort"), LibraryServer.DISCOVERY_PORT)
        assertEquals(current.getString("serviceUuid"), BuildConfig.LIBRARY_SERVICE_UUID)
        assertEquals(current.getInt("tunnelFirstPort"), BuildConfig.TUNNEL_FIRST_PORT)
        if (BuildConfig.DEBUG) {
            assertNotEquals(release.getInt("port"), LibraryServer.PORT)
            assertNotEquals(release.getInt("discoveryPort"), LibraryServer.DISCOVERY_PORT)
            assertNotEquals(BluetoothLink.SERVICE, UUID.fromString(BuildConfig.LIBRARY_SERVICE_UUID))
        } else {
            assertNotEquals(dev.getInt("port"), LibraryServer.PORT)
            assertNotEquals(dev.getInt("discoveryPort"), LibraryServer.DISCOVERY_PORT)
            assertEquals(BluetoothLink.SERVICE, UUID.fromString(BuildConfig.LIBRARY_SERVICE_UUID))
            assertEquals("com.ngdtuanh.abook", BuildConfig.APPLICATION_ID)
        }
        assertEquals(BuildConfig.DEBUG, BuildConfig.APPLICATION_ID.endsWith(".dev"))
    }
}
