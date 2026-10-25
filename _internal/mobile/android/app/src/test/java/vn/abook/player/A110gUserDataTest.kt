package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.ByteArrayInputStream
import java.io.File
import java.io.FileNotFoundException
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class A110gUserDataTest {
    private lateinit var root: File
    @Before fun setup() {
        root = BookEditsFixtures.tempDir("a110g-user-data")
        BookEditsFixtures.useStoreRoot(root)
    }

    @Test fun hugePeerCounterCannotBlockFutureEdits() {
        Store.progress("book", 1, 10.0, 1000.0)
        val peer = JSONObject("""{"last":{"chapterId":1,"seconds":50,"at":100,"rev":{"counter":1099511627776,"node":"peer"}},"_clock":1099511627776}""")
        Store.mergeRemote("book", peer)
        assertEquals(10.0, Store.state("book").getJSONObject("last").getDouble("seconds"), 0.0)
        assertTrue(Store.dataNotices().toString().contains("Phiên bản đồng bộ"))
        Store.progress("book", 1, 600.0, 1000.0)
        Store.saveReading("book", 1, 100)
    }

    @Test fun ceilingRollsEpochAndPreservesOtherFields() {
        val state = JSONObject("""{"_clock":1099511627776,"chapters":{}}""")
        val rev = ListeningRevision.advance(state, "phone")
        assertEquals("1", rev.getString("epoch"))
        assertEquals(1L, rev.getLong("counter"))
        state.put("reading", JSONObject().put("rev", rev))
        assertEquals(2L, ListeningRevision.advance(state, "phone").getLong("counter"))
        assertTrue(ListeningRevision.newer(JSONObject().put("rev", rev), JSONObject("""{"rev":{"counter":1099511627776,"node":"old"}}""")))
    }

    @Test fun missingRevisionIsRejectedBeforeAnyStateChangeAndEditsAdvance() {
        Store.saveReading("book", 1, 100, 100.0)
        val before = Store.state("book").toString()
        for (body in listOf(
            """{"last":{"chapterId":1,"seconds":600,"at":200}}""",
            """{"rate":1.5,"rateAt":200}"""
        )) {
            val failure = runCatching { Store.mergeRemote("book", JSONObject(body)) }.exceptionOrNull()
            assertTrue(failure is IllegalArgumentException)
            assertEquals(ListeningRevision.MISSING_REVISION, failure?.message)
            assertEquals(before, Store.state("book").toString())
        }
        val counter = Store.state("book").getJSONObject("reading").getJSONObject("rev").getLong("counter")
        Store.saveReading("book", 1, 200, 200.0)
        assertTrue(Store.state("book").getJSONObject("reading").getJSONObject("rev").getLong("counter") > counter)
    }

    @Test fun clonedLibraryWithoutInstallIdentityConvergesBothWays() {
        Store.progress("book", 1, 10.0, 1000.0)
        val cloned = BookEditsFixtures.tempDir("a110g-clone")
        // Android backup excludes the install identity in both backup XML files.
        root.walkTopDown().filter { it.isFile && it.name != "listening-node.json" }.forEach {
            val target = File(cloned, it.relativeTo(root).path)
            target.parentFile!!.mkdirs()
            it.copyTo(target, overwrite = true)
        }
        Store.saveReading("book", 1, 100, 100.0)
        val a = Store.state("book")
        BookEditsFixtures.useStoreRoot(cloned)
        Store.saveReading("book", 1, 200, 100.0)
        val b = Store.state("book")
        assertNotEquals(a.getJSONObject("reading").getJSONObject("rev").getString("node"), b.getJSONObject("reading").getJSONObject("rev").getString("node"))
        assertTrue(StrictJson.equal(Store.mergeStates(a, b).getJSONObject("reading"), Store.mergeStates(b, a).getJSONObject("reading")))
    }

    @Test fun corruptNoticeFileDoesNotHideBooksOrPreventStateRepair() {
        val record = Store.activeRecord("book")
        Store.saveReading("book", 1, 100, 100.0)
        val file = File(root, "state/$record.json")
        file.writeText(JSONObject(file.readText()).put("chapters", JSONArray()).toString())
        val original = file.readBytes()
        val notice = File(root, "data-notices.json")
        notice.writeText("{\"notices\":")
        val noticeBytes = notice.readBytes()
        Store.progress("book", 1, 600.0, 1000.0)
        assertTrue(Store.dataNotices().length() > 0)
        assertEquals(100, Store.state("book").getJSONObject("reading").getInt("index"))
        assertTrue(root.listFiles()!!.any { it.name.startsWith("data-notices.json.corrupt-") && it.readBytes().contentEquals(noticeBytes) })
        assertTrue(file.parentFile!!.listFiles()!!.any { it.name.startsWith(file.name + ".corrupt-") && it.readBytes().contentEquals(original) })
        val blocked = Store::class.java.getDeclaredField("unpreservedData").apply { isAccessible = true }.get(null) as Set<*>
        assertFalse(file.absolutePath in blocked)
    }

    @Test fun brokenNoticeFileAloneStartsAFreshReadableList() {
        val file = File(root, "data-notices.json")
        file.writeText("{\"notices\":")
        val bytes = file.readBytes()
        assertTrue(Store.dataNotices().length() > 0)
        assertTrue(JSONObject(file.readText()).getJSONArray("notices").length() > 0)
        assertTrue(root.listFiles()!!.any { it.name.startsWith(file.name + ".corrupt-") && it.readBytes().contentEquals(bytes) })
    }

    @Test fun malformedFixturesMatchPythonAndUi() {
        val rows = JSONArray(File("../../../tests/fixtures/listening_revision/malformed.json").readText())
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            assertEquals(row.getString("name"), row.getBoolean("valid"), ListeningRevision.revision(JSONObject().put("rev", row.get("rev"))).first > 0)
        }
    }

    @Test fun sharedBoundaryFixturesMatchPython() {
        val rows = JSONArray(File("../../../tests/fixtures/listening_revision/boundary.json").readText())
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            val merged = Store.mergeStates(row.getJSONObject("ours"), row.getJSONObject("theirs"))
            assertTrue(row.getString("name"), StrictJson.equal(row.getJSONObject("expected"), merged.getJSONObject("reading")))
            assertEquals(row.getString("name"), row.getLong("clock"), merged.getLong("_clock"))
        }
    }

    @Test fun badActiveStateIsRejectedBeforeDeletingRecordsOrWritingState() {
        Store.progress("book", 1, 10.0, 1000.0)
        val record = Store.activeRecord("book")
        val original = File(root, "state/$record.json").readBytes()
        val peer = JSONObject().put("record", record).put("deletedRecords", JSONObject().put(record, 100))
            .put("activeState", JSONObject("""{"reading":{"chapterId":1,"index":200,"at":100}}"""))
        assertTrue(runCatching { Store.applySync("book", peer, { "" to false }, {}) }.exceptionOrNull() is IllegalArgumentException)
        assertArrayEquals(original, File(root, "state/$record.json").readBytes())
        assertEquals(record, Store.activeRecord("book"))
    }

    @Test fun lostSafAccessAsksForAnotherLocationBeforeOpeningOldUriForWriting() {
        val work = BookEditsFixtures.tempDir("a110g-uri")
        val book = BookEditsFixtures.copyBase(File(work, "book"))
        for (error in listOf(FileNotFoundException("gone"), SecurityException("revoked"), BookSave.DestinationUnavailable())) {
            var opens = 0
            val failure = runCatching {
                BookSave.save(book, File(work, "cache"), false, { throw error },
                    { opens++; ByteArrayOutputStream() }, File(work, "kept"), "Book")
            }.exceptionOrNull()!!
            assertEquals(0, opens)
            assertTrue(BookSave.shouldChooseAnotherLocation(true, failure))
            assertFalse(BookSave.shouldChooseAnotherLocation(false, failure))
        }
        assertFalse(BookSave.shouldChooseAnotherLocation(true, BookSave.Failed("backup failed", FileNotFoundException())))
    }

    @Test fun inaccessibleOutputKeepsTheDurableBackupWithoutRetryingTheOldUri() {
        val work = BookEditsFixtures.tempDir("a110g-output-uri")
        val book = BookEditsFixtures.copyBase(File(work, "book"))
        val keep = File(work, "kept")
        var opens = 0
        val failure = runCatching {
            BookSave.save(book, File(work, "cache"), false, { ByteArrayInputStream("old".toByteArray()) },
                { opens++; throw SecurityException("revoked") }, keep, "Book")
        }.exceptionOrNull()!!
        assertEquals(1, opens)
        assertTrue(BookSave.shouldChooseAnotherLocation(true, failure))
        assertEquals("old", File(keep, OldSaves.list(keep).single().name).readText())
        assertEquals(1, BookSave.recover(keep).size)
    }

    @Test fun failedBackupIsNotMistakenForLostSafAccess() {
        val work = BookEditsFixtures.tempDir("a110g-backup-failed")
        val book = BookEditsFixtures.copyBase(File(work, "book"))
        val keep = File(work, "blocked").apply { writeText("not a folder") }
        var opens = 0
        val failure = runCatching {
            BookSave.save(book, File(work, "cache"), false, { ByteArrayInputStream("old".toByteArray()) },
                { opens++; ByteArrayOutputStream() }, keep, "Book")
        }.exceptionOrNull()!!
        assertEquals(0, opens)
        assertTrue(failure is BookSave.Failed)
        assertFalse(BookSave.shouldChooseAnotherLocation(true, failure))
    }
}
