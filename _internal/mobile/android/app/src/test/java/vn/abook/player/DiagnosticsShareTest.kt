package vn.abook.player

import android.content.Context
import android.content.ContextWrapper
import java.io.File
import java.lang.reflect.Field
import org.json.JSONObject
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue

/** Đi thẳng vào Chẩn đoán khi chưa mở trang chia sẻ: đọc được máy đã ghép, không mở cổng. */
class DiagnosticsShareTest {
    private class FilesContext : ContextWrapper(null) {
        lateinit var directory: File
        override fun getFilesDir(): File = directory
        override fun getApplicationContext(): Context = this
    }
    private lateinit var directory: File
    private lateinit var context: FilesContext
    private val saved = linkedMapOf<Field, Any?>()
    private fun save(type: Class<*>, name: String): Field = type.getDeclaredField(name).apply {
        isAccessible = true
        saved[this] = get(null)
    }

    @Before fun prepareColdSharing() {
        directory = BookEditsFixtures.tempDir("abook-diag-cold-share")
        // android.jar chỉ có stub constructor; cùng cách cấp Context như PrepareAheadTest.
        val unsafeClass = Class.forName("sun.misc.Unsafe")
        val unsafe = unsafeClass.getDeclaredField("theUnsafe").apply { isAccessible = true }.get(null)
        context = (unsafeClass.getMethod("allocateInstance", Class::class.java).invoke(unsafe, FilesContext::class.java) as FilesContext)
            .apply { this.directory = this@DiagnosticsShareTest.directory }
        save(Store::class.java, "root").set(null, File(directory, "library").apply { mkdirs() })
        save(Remote::class.java, "context").set(null, null)
        save(LibraryServer::class.java, "devicesFile").set(null, null)
        save(LibraryServer::class.java, "appContext").set(null, null)
        save(LibraryServer::class.java, "server").set(null, null)
    }
    @After fun restoreGlobals() { saved.forEach { (field, value) -> field.set(null, value) }; saved.clear() }

    @Test fun cold_share_initializes_devices_without_starting_the_server() {
        val file = File(directory, "share.json")
        val original = JSONObject().put("devices", JSONObject().put("a".repeat(64), JSONObject().put("name", "Máy thử"))).toString()
        file.writeText(original)
        val report = Diagnostics.share(context)
        assertFalse(report.getBoolean("running"))
        assertEquals(1, report.getInt("pairedDevices"))
        assertFalse(LibraryServer.running())
        assertEquals(original, file.readText())
    }

    @Test fun cold_share_without_a_devices_file_is_empty_and_does_not_create_it() {
        val report = Diagnostics.share(context)
        assertEquals(0, report.getInt("pairedDevices"))
        assertFalse(File(directory, "share.json").exists())
        assertFalse(LibraryServer.running())
    }

    @Test fun corrupt_share_is_preserved_and_only_its_section_fails() {
        val file = File(directory, "share.json").apply { writeText("{broken") }
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
        assertTrue(directory.listFiles()!!.any { it.name.startsWith("share.json.corrupt-") && it.readText() == "{broken" })
        assertFalse(LibraryServer.running())
    }
}
