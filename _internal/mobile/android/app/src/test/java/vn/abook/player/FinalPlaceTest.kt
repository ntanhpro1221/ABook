package vn.abook.player

import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class FinalPlaceTest {
    private lateinit var fixture: ColdStoreFixture

    @Before fun prepare() {
        fixture = ColdStoreFixture()
        Store.init(fixture.context)
    }

    @After fun cleanup() { fixture.restore() }

    private fun coldOpen() {
        fixture.setRoot(null)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        Store.init(fixture.context)
    }

    @Test fun coldOpenRecoversTheFinalPlaceWhenTheProcessNeverRanItsWriter() {
        val record = Store.activeRecord("journal-book")
        Store.progress("journal-book", 1, 10.0, 100.0, recordId = record)
        val journal = FinalPlace.persist(Store.root, 1, "journal-book", record, 2, 43_210, 200.0, null)
        coldOpen()
        val last = Store.state("journal-book").getJSONObject("last")
        assertEquals(2, last.getInt("chapterId"))
        assertEquals(43.21, last.getDouble("seconds"), 0.001)
        assertFalse(journal.exists())
        coldOpen()
        assertEquals(43.21, Store.state("journal-book").getJSONObject("last").getDouble("seconds"), 0.001)
    }

    @Test fun recoveryDoesNotResurrectADeletedProfileOrWriteIntoItsReplacement() {
        val record = Store.activeRecord("journal-book")
        val journal = FinalPlace.persist(Store.root, 1, "journal-book", record, 2, 43_210, 200.0, null)
        Store.deleteRecord("journal-book", record)
        val replacement = Store.activeRecord("journal-book")
        Store.progress("journal-book", 1, 7.0, 100.0, recordId = replacement)
        coldOpen()
        assertEquals(7.0, Store.state("journal-book").getJSONObject("last").getDouble("seconds"), 0.001)
        assertFalse(Store.hasRecord(record))
        assertFalse(journal.exists())
    }

    @Test fun recoveryKeepsAFailedJournalAndRefusesToPublishAnIncompleteStore() {
        val journal = java.io.File(Store.root, ".final-place-broken.json").apply { writeText("{") }
        fixture.setRoot(null)
        assertTrue(runCatching { Store.init(fixture.context) }.isFailure)
        assertEquals(null, fixture.field(Store::class.java, "root"))
        assertTrue(journal.exists())
    }

    @Test fun aJournalLeftAfterACommittedWriteCannotRewindANewerCheckpoint() {
        val record = Store.activeRecord("journal-book")
        val journal = FinalPlace.persist(Store.root, 1, "journal-book", record, 1, 10_000, 100.0, null)
        Store.progress("journal-book", 1, 10.0, 100.0, recordId = record, localCheckpoint = FinalPlace.token(1))
        Store.progress("journal-book", 1, 35.0, 100.0, recordId = record, localCheckpoint = FinalPlace.token(2))
        val revision = Store.state("journal-book").getJSONObject("last").getJSONObject("rev").toString()
        coldOpen()
        val last = Store.state("journal-book").getJSONObject("last")
        assertEquals(35.0, last.getDouble("seconds"), 0.001)
        assertEquals(revision, last.getJSONObject("rev").toString())
        assertFalse(Store.syncBody("journal-book").has("_localPlace"))
        assertFalse(journal.exists())
    }
}
