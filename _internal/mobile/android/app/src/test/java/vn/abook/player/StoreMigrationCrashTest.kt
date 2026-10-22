package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class StoreMigrationCrashTest {
    @Test
    fun interrupted_records_commit_keeps_the_legacy_source_for_restart() {
        val root = Files.createTempDirectory("abook-migration-crash").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        val source = File(root, "state/book.json")
        source.parentFile!!.mkdirs()
        source.writeText(JSONObject().put("last", JSONObject().put("chapterId", 7).put("seconds", 55.0)).toString())
        val records = File(root, "records.json").apply { mkdirs() }
        File(records, "blocked").writeText("block replacement")
        runCatching { Store.state("book") }
        assertTrue("source must survive an interrupted records commit", source.isFile)
        records.deleteRecursively()
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        assertEquals(7, Store.state("book").getJSONObject("last").getInt("chapterId"))
        assertEquals(Store.defaultRecordId("book"), Store.knownActiveRecord("book"))
    }
}
