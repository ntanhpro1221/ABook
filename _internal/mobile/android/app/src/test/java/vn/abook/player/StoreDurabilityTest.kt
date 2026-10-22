package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class StoreDurabilityTest {
    @Test
    fun corrupt_records_index_is_preserved_before_recreating_the_index() {
        val root = BookEditsFixtures.tempDir("store-corrupt-index")
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "records.json").writeText("{broken")
        Store.knownActiveRecord("book")
        val copies = root.listFiles()!!.filter { it.name.startsWith("records.json.corrupt-") }
        assertEquals(1, copies.size)
        assertEquals("{broken", copies.single().readText())
    }

    @Test
    fun corrupt_record_state_is_preserved_before_a_progress_update() {
        val root = BookEditsFixtures.tempDir("store-corrupt-state")
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        val record = Store.activeRecord("book")
        val file = File(root, "state/$record.json").apply { parentFile!!.mkdirs(); writeText("{broken") }
        Store.progress("book", 1, 42.0, 100.0)
        val copies = file.parentFile!!.listFiles()!!.filter { it.name.startsWith(file.name + ".corrupt-") }
        assertEquals(1, copies.size)
        assertEquals("{broken", copies.single().readText())
        assertEquals(42.0, Store.state("book").getJSONObject("last").getDouble("seconds"), 0.0)
    }

    @Test
    fun failed_replace_reports_failure_and_preserves_the_old_target() {
        val root = BookEditsFixtures.tempDir("store-replace-fail")
        val target = File(root, "state.json").apply { mkdirs() }
        File(target, "old").writeText("keep")
        assertTrue(runCatching { Store.writeAtomic(target, "new") }.isFailure)
        assertTrue(target.isDirectory)
        assertEquals("keep", File(target, "old").readText())
        assertFalse(File(root, "state.json.part").isFile)
    }
}
