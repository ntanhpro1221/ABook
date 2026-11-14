package vn.abook.player

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class CastHistoryTest {
    private val fixture = JSONObject(File("../../../tests/fixtures/cast_history.json").readText())

    @Test fun compensationIdentityMatchesPythonAndSurvivesTwoSenders() {
        val original = fixture.getString("original")
        assertEquals(fixture.getString("undoId"), CastHistory.undoId(original))
        val wishes = BookWishes.validate(fixture.getJSONObject("wishes"))
        val (merged, conflicts) = BookWishes.merge(wishes, BookWishes.validate(fixture.getJSONObject("wishes")))
        assertEquals(0, conflicts)
        assertEquals(1, BookWishes.count(merged))
    }

    @Test fun corruptOrForgedCompensationIdentityIsRefused() {
        val wishes = JSONObject(fixture.getJSONObject("wishes").toString())
        val entries = wishes.getJSONObject("cast_undos")
        val entry = entries.remove(fixture.getString("undoId"))
        entries.put("0".repeat(32), entry)
        assertThrows(BookEdits.EditsError::class.java) { BookWishes.validate(wishes) }
    }

    @Test fun wishPersistsAcrossReopenAndKeepsFirstTimestamp() {
        val folder = BookEditsFixtures.tempDir("cast-history")
        try {
            BookEditsFixtures.copyBase(folder)
            val original = fixture.getString("original")
            assertEquals(fixture.getString("undoId"), BookWishes.requestCastUndo(folder, original, 50.0))
            BookWishes.requestCastUndo(folder, original, 99.0)
            val entry = BookEdits.load(folder).getJSONObject("wishes").getJSONObject("cast_undos").getJSONObject(fixture.getString("undoId"))
            assertEquals(50.0, entry.getDouble("requested_at"), 0.0)
        } finally { folder.deleteRecursively() }
    }
}
