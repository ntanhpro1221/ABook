package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ShareDurabilityTest {
    private fun useFile(file: File) {
        LibraryServer::class.java.getDeclaredField("devicesFile").apply { isAccessible = true }.set(LibraryServer, file)
    }

    @Test fun damaged_share_blocks_pair_and_revoke_and_keeps_original_bytes() {
        for (bad in listOf("{broken", "{}", "{\"devices\":[]}", "{\"devices\":{\"bad\":{}}}")) {
            for (pair in listOf(false, true)) {
                val root = BookEditsFixtures.tempDir("share-damaged")
                val file = File(root, "share.json").apply { writeText(bad) }
                useFile(file)
                val result = runCatching {
                    if (pair) {
                        val code = LibraryServer.startPairing().getString("code")
                        val body = JSONObject().put("code", code).put("device", "Peer").toString().toByteArray()
                        LibraryServer.route(LibraryServer.Request("POST", "/sync/v1/pair", emptyMap(), body), ByteArrayOutputStream())
                    } else LibraryServer.revoke("not-a-device")
                }
                assertTrue("wrote from unreadable share: $bad", result.isFailure)
                assertEquals(bad, file.readText())
            }
        }
    }

    @Test fun read_failure_does_not_turn_into_an_empty_share() {
        val root = BookEditsFixtures.tempDir("share-unreadable")
        val file = File(root, "share.json").apply { mkdirs() }
        File(file, "keep").writeText("old")
        useFile(file)
        assertTrue(runCatching { LibraryServer.revoke("anything") }.isFailure)
        assertEquals("old", File(file, "keep").readText())
    }
}
