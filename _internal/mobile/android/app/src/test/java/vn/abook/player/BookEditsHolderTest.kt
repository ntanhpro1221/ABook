package vn.abook.player

import java.io.File
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the holder set reaches the phone ([BookEdits.withHolder]) without overriding what this phone has not sent yet, and "Save (N changes)"
 * counts only what changed after the file was opened or saved ([BookEdits.markSaved] / [BookEdits.unsaved]) - review a70, items 6 and 15.
 */
class BookEditsHolderTest {
    private fun readings(vararg pairs: Pair<String, String>) = JSONObject().also { out -> pairs.forEach { (word, spoken) -> out.put(word, spoken) } }

    @Test
    fun the_holders_readings_and_skips_apply_under_this_devices_unsent_ones() {
        val holder = JSONObject()
            .put("readings", readings("Kirito" to "Ki-ri-tô", "Asuna" to "A-su-na", "Klein" to "Clai"))
            .put("skip", JSONObject().put("1", JSONArray(listOf("Dịch: Hako"))))
        // "Asuna": changed here, not sent yet -> ours. "Klein": sent earlier as "Cờ-lai", then changed on the computer -> the computer's.
        val edits = BookEdits.empty()
            .put("readings", readings("Asuna" to "A-xu-na", "Klein" to "Cờ-lai"))
            .put("skip", JSONObject().put("2", JSONArray(listOf("Nguồn: web"))))
        val marks = JSONObject().put("readings", readings("Klein" to "Cờ-lai"))

        val seen = BookEdits.withHolder(edits, holder, marks)

        assertEquals(mapOf("Asuna" to "A-xu-na", "Kirito" to "Ki-ri-tô", "Klein" to "Clai"), BookEdits.readingsOf(seen))
        assertEquals(listOf("Dịch: Hako"), seen.getJSONObject("skip").getJSONArray("1").let { a -> List(a.length()) { a.getString(it) } })
        assertEquals(listOf("Nguồn: web"), seen.getJSONObject("skip").getJSONArray("2").let { a -> List(a.length()) { a.getString(it) } })
        // the device's own layer (what it counts and sends) is untouched
        assertEquals(2, edits.getJSONObject("readings").length())
        assertTrue(BookEdits.withHolder(edits, null, marks) === edits)
    }

    @Test
    fun save_counts_only_what_changed_after_the_file_was_opened() {
        val dir = BookEditsFixtures.tempDir("abook-saved")
        val opened = BookEdits.empty().put("readings", readings("Kirito" to "Ki-ri-tô", "Asuna" to "A-su-na"))
        File(dir, BookEdits.EDITS_FILE).writeBytes(BookEdits.dump(opened))
        assertEquals(2, BookEdits.unsaved(dir, BookEdits.load(dir)))

        BookEdits.markSaved(dir)
        assertEquals(0, BookEdits.unsaved(dir, BookEdits.load(dir)))

        // one reading changed, one removed, one added: three changes
        val now = BookEdits.empty().put("readings", readings("Kirito" to "Ki-ri-to", "Klein" to "Clai"))
        assertEquals(3, BookEdits.unsaved(dir, now))

        // a book opened with no edits gets no extra file
        val plain = BookEditsFixtures.tempDir("abook-plain")
        File(plain, BookEdits.EDITS_FILE).writeBytes(BookEdits.dump(BookEdits.empty()))
        BookEdits.markSaved(plain)
        assertFalse(File(plain, BookEdits.SAVED_FILE).exists())
    }
}
