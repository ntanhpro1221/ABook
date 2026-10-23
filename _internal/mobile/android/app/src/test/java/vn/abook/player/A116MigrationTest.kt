package vn.abook.player

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class A116MigrationTest {
    private fun legacy() = JSONObject(File("../../../tests/fixtures/listening_revision/legacy132.json").readText())

    @Test fun failedMigrationKeepsReadableDataButCannotSyncAnUncommittedRevision() {
        val root = BookEditsFixtures.tempDir("a116-migration-blocked")
        BookEditsFixtures.useStoreRoot(root)
        val record = Store.activeRecord("book")
        val file = File(root, "state/$record.json").apply { parentFile!!.mkdirs(); writeText(legacy().toString()) }
        val original = file.readText()
        File(file.path + ".part").mkdirs()
        assertEquals("kept", Store.state("book").getJSONArray("bookmarks").getJSONObject(0).getString("id"))
        assertTrue(runCatching { Store.syncBody("book") }.isFailure)
        assertEquals(original, file.readText())
    }

    @Test fun twoLegacyStoresPersistAndExchangeWithoutLosingItems() {
        val roots = listOf(BookEditsFixtures.tempDir("a116-left"), BookEditsFixtures.tempDir("a116-right"))
        val bodies = roots.map { root ->
            BookEditsFixtures.useStoreRoot(root)
            val record = Store.activeRecord("book")
            val file = File(root, "state/$record.json").apply { parentFile!!.mkdirs(); writeText(legacy().toString()) }
            val body = Store.syncBody("book")
            val saved = file.readText()
            BookEditsFixtures.useStoreRoot(root)
            Store.state("book")
            assertEquals(saved, file.readText())
            body
        }
        assertNotEquals(bodies[0].getJSONObject("last").getJSONObject("rev").getString("node"),
            bodies[1].getJSONObject("last").getJSONObject("rev").getString("node"))
        for (i in roots.indices) {
            BookEditsFixtures.useStoreRoot(roots[i])
            val merged = Store.mergeRecord("book", bodies[1 - i], onGone = {})
            assertEquals(2, merged.getJSONObject("chapters").length())
            assertEquals("kept", merged.getJSONArray("bookmarks").getJSONObject(0).getString("id"))
            assertEquals(12, merged.getJSONObject("deleted").getInt("gone"))
        }
    }

    @Test fun migrationIsOrderedAndIdempotentAndMissingRevIsNotOldPeer() {
        val state = legacy()
        assertTrue(ListeningRevision.upgradeLocal(state, "phone"))
        assertEquals(1, state.getJSONObject("chapters").getJSONObject("1").getJSONObject("rev").getInt("counter"))
        assertEquals(2, state.getJSONObject("chapters").getJSONObject("2").getJSONObject("rev").getInt("counter"))
        assertEquals(9, state.getJSONObject("reading").getJSONObject("rev").getInt("counter"))
        val saved = state.toString()
        assertFalse(ListeningRevision.upgradeLocal(state, "other"))
        assertEquals(saved, state.toString())
        val missing = runCatching { ListeningRevision.checkedPeer(JSONObject(), JSONObject().put("rate", 1.5)) {} }.exceptionOrNull()
        assertEquals(ListeningRevision.MISSING_REVISION, missing?.message)
        val old = runCatching { ListeningRevision.checkedPeer(JSONObject(), JSONObject().put("listeningRevision", 0)) {} }.exceptionOrNull()
        assertEquals(ListeningRevision.OLD_PEER, old?.message)
    }
}
