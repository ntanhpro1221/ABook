package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PairingObserverTest {
    @Test fun `successful pairing notifies after persisting the device and removing the code`() {
        val file = File(Files.createTempDirectory("pairing-events").toFile(), "share.json")
        file.writeText("{\"devices\":{}}")
        val field = LibraryServer::class.java.getDeclaredField("devicesFile").apply { isAccessible = true }
        val before = field.get(LibraryServer)
        field.set(LibraryServer, file)
        var events = 0
        val stop = LibraryServer.watchPairing { events++ }
        try {
            val code = LibraryServer.startPairing().getString("code")
            assertEquals(1, events)
            val pair = LibraryServer::class.java.getDeclaredMethod("pair", String::class.java, String::class.java, String::class.java).apply { isAccessible = true }
            assertNotNull(pair.invoke(LibraryServer, code, "Other phone", ""))
            assertEquals(2, events)
            assertNull(LibraryServer.pairingCode())
            assertEquals(1, LibraryServer.devices().length())
            assertTrue(file.readText().contains("Other phone"))
            stop()
            LibraryServer.cancelPairing()
            assertEquals(2, events)
        } finally {
            stop()
            LibraryServer.cancelPairing()
            field.set(LibraryServer, before)
        }
    }
}
