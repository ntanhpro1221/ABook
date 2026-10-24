package vn.abook.player

import java.io.File
import org.json.JSONObject
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue

/** Diagnostics may inspect cold sharing, but must never initialize or repair storage. */
class DiagnosticsShareTest {
    private lateinit var fixture: ColdStoreFixture
    private val directory get() = fixture.directory
    private val context get() = fixture.context

    @Before fun prepareColdSharing() {
        fixture = ColdStoreFixture()
        fixture.setRoot(File(directory, "library").apply { mkdirs() })
    }
    @After fun restoreGlobals() { fixture.restore() }

    @Test fun cold_share_reads_devices_without_initializing_the_server() {
        val file = File(directory, "share.json")
        val original = JSONObject().put("devices", JSONObject().put("a".repeat(64), JSONObject().put("name", "Máy thử"))).toString()
        file.writeText(original)
        val before = fixture.files()
        val report = Diagnostics.share(context)
        assertFalse(report.getBoolean("running"))
        assertEquals(1, report.getInt("pairedDevices"))
        assertFalse(LibraryServer.running())
        assertEquals(original, file.readText())
        assertEquals(before, fixture.files())
        assertEquals(null, fixture.field(LibraryServer::class.java, "devicesFile"))
        assertEquals(null, fixture.field(LibraryServer::class.java, "appContext"))
        assertEquals(null, fixture.field(Remote::class.java, "context"))
    }

    @Test fun cold_share_without_a_devices_file_is_empty_and_does_not_create_it() {
        val before = fixture.files()
        val report = Diagnostics.share(context)
        assertEquals(0, report.getInt("pairedDevices"))
        assertEquals(before, fixture.files())
        assertFalse(File(directory, "share.json").exists())
        assertFalse(LibraryServer.running())
    }

    @Test fun corrupt_share_is_read_only_and_only_its_section_fails() {
        val file = File(directory, "share.json").apply { writeText("{broken") }
        val before = fixture.files()
        val report = Diagnostics.assemble(listOf(
            "share" to { Diagnostics.share(context) },
            "playback" to { JSONObject().put("error", "").put("playing", false) },
            "battery" to { JSONObject().put("percent", 50) },
        ))
        assertTrue(report.getJSONObject("share").getBoolean("collectionFailed"))
        assertTrue(report.getJSONObject("share").getString("error").isNotBlank())
        assertEquals("", report.getJSONObject("playback").getString("error"))
        assertEquals(50, report.getJSONObject("battery").getInt("percent"))
        assertEquals("{broken", file.readText())
        assertEquals(before, fixture.files())
        assertFalse(LibraryServer.running())
    }

    @Test fun cold_store_reports_not_ready_without_recovery_or_new_files() {
        fixture.setRoot(null)
        val interrupted = File(directory, "library/books/.book.123.old").apply { mkdirs() }
        File(interrupted, "book.json").writeText("{}")
        val before = fixture.files()
        var recoveries = 0
        val recover = Store.initRecovery
        Store.initRecovery = { recoveries++; recover(it) }
        val report = Diagnostics.assemble(listOf(
            "share" to { Diagnostics.share(context) },
            "dataRecovery" to { Store.dataDiagnostics() },
        ))
        assertEquals(0, recoveries)
        assertEquals(before, fixture.files())
        assertTrue(interrupted.isDirectory)
        assertEquals(null, fixture.field(Store::class.java, "root"))
        for (key in listOf("share", "dataRecovery")) {
            assertTrue(report.getJSONObject(key).getBoolean("collectionFailed"))
            assertTrue(report.getJSONObject(key).getString("error").contains("chưa sẵn", ignoreCase = true))
        }
    }

    @Test fun corrupt_share_writer_still_preserves_bytes_and_refuses_to_overwrite() {
        LibraryServer.init(context)
        val file = File(directory, "share.json").apply { writeText("{broken") }
        assertTrue(runCatching { LibraryServer.revoke("a".repeat(12)) }.isFailure)
        assertEquals("{broken", file.readText())
        val copies = directory.listFiles()!!.filter { it.name.startsWith("share.json.corrupt-") }
        assertEquals(1, copies.size)
        assertEquals("{broken", copies.single().readText())
    }
}
