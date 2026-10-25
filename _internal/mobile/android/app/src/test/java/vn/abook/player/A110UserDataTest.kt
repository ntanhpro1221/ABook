package vn.abook.player

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class A110UserDataTest {
    private lateinit var root: File
    @Before fun setup() {
        root = BookEditsFixtures.tempDir("a110-user-data")
        BookEditsFixtures.useStoreRoot(root)
    }

    @Test fun nestedIndexDamagePreservesBytesAndOtherLinks() {
        val first = Store.activeRecord("book")
        val second = Store.activeRecord("other")
        val file = File(root, "records.json")
        val raw = JSONObject(file.readText())
        raw.getJSONObject("links").getJSONObject("book").getJSONArray("records").put(JSONObject())
        file.writeText(raw.toString())
        val bytes = file.readBytes()
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        assertEquals(first, Store.knownActiveRecord("book"))
        assertEquals(second, Store.knownActiveRecord("other"))
        assertTrue(root.listFiles()!!.any { it.name.startsWith("records.json.corrupt-") && it.readBytes().contentEquals(bytes) })
        assertTrue(Store.dataNotices().length() > 0)
    }

    @Test fun badChaptersDoNotLoseTheReadablePosition() {
        val record = Store.activeRecord("book")
        Store.saveReading("book", 1, 100, 100.0)
        val file = File(root, "state/$record.json")
        file.writeText(JSONObject(file.readText()).put("chapters", JSONArray()).toString())
        val bytes = file.readBytes()
        Store.progress("book", 1, 600.0, 1000.0)
        assertEquals(100, Store.state("book").getJSONObject("reading").getInt("index"))
        assertTrue(file.parentFile!!.listFiles()!!.any { it.name.startsWith(file.name + ".corrupt-") && it.readBytes().contentEquals(bytes) })
    }

    @Test fun linksArrayDoesNotBreakLibrary() {
        File(root, "records.json").writeText("""{"version":2,"records":{},"links":[]}""")
        assertNull(Store.knownActiveRecord("book"))
        assertNotNull(Store.activeRecord("book"))
        assertTrue(Store.dataNotices().length() > 0)
    }

    @Test fun failedNoticeDoesNotBlockAnAlreadyPreservedIndex() {
        val record = Store.activeRecord("book")
        val file = File(root, "records.json")
        file.writeText(JSONObject(file.readText()).put("links", JSONArray()).toString())
        val original = file.readBytes()
        File(root, "data-notices.json").mkdirs() // cannot durably publish a recovery notice
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        assertNotNull(Store.activeRecord("book"))
        assertTrue(root.listFiles()!!.any { it.name.startsWith("records.json.corrupt-") && it.readBytes().contentEquals(original) })
        assertTrue(JSONObject(file.readText()).getJSONObject("records").has(record))
    }

    @Test fun failedNoticeStillExposesTheReadingPositionAndAllowsPreservedStateToSave() {
        val record = Store.activeRecord("book")
        Store.saveReading("book", 1, 100, 100.0)
        val file = File(root, "state/$record.json")
        file.writeText(JSONObject(file.readText()).put("chapters", JSONArray()).toString())
        val original = file.readBytes()
        File(root, "data-notices.json").mkdirs()
        assertEquals(100, Store.state("book").getJSONObject("reading").getInt("index"))
        Store.progress("book", 1, 600.0, 1000.0)
        assertTrue(file.parentFile!!.listFiles()!!.any { it.name.startsWith(file.name + ".corrupt-") && it.readBytes().contentEquals(original) })
        assertEquals(600.0, Store.state("book").getJSONObject("last").getDouble("seconds"), 0.0)
    }

    @Test fun readingSurvivesClockRollbackAndReload() {
        Store.saveReading("book", 1, 10, 2_000_000_000.0)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        Store.saveReading("book", 1, 100, 1_999_913_600.0)
        assertEquals(100, Store.state("book").getJSONObject("reading").getInt("index"))
    }

    @Test fun versionedMergeIgnoresAnOldFutureClock() {
        val ours = JSONObject("""{"last":{"chapterId":1,"seconds":600,"at":1999913600,"rev":{"counter":2,"node":"phone"}},"chapters":{},"_clock":2}""")
        val old = JSONObject("""{"last":{"chapterId":1,"seconds":10,"at":2000000000,"rev":{"counter":1,"node":"desktop"}},"chapters":{},"_clock":1}""")
        assertEquals(600.0, Store.mergeStates(ours, old).getJSONObject("last").getDouble("seconds"), 0.0)
        assertEquals(600.0, Store.mergeStates(old, ours).getJSONObject("last").getDouble("seconds"), 0.0)
    }

    @Test fun sharedPythonKotlinMergeFixturesBothDirections() {
        val cases = JSONArray(File("../../../tests/fixtures/listening_revision/merge.json").readText())
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val a = case.getJSONObject("ours")
            val b = case.getJSONObject("theirs")
            for ((ours, theirs) in listOf(a to b, b to a)) {
                val merged = Store.mergeStates(ours, theirs)
                val expected = case.get("expected")
                val actual = merged.get(case.getString("field"))
                when (expected) {
                    is JSONObject -> assertTrue(case.getString("name"), StrictJson.equal(expected, actual))
                    is JSONArray -> assertTrue(case.getString("name"), StrictJson.equal(expected, actual))
                    else -> assertEquals(case.getString("name"), expected, actual)
                }
                assertEquals(case.getLong("clock"), merged.getLong("_clock"))
            }
        }
    }

    @Test fun processDeathAfterTruncationLeavesDurableOldSaveAndJournal() {
        val work = BookEditsFixtures.tempDir("a110-save-death")
        val book = BookEditsFixtures.copyBase(File(work, "book"))
        val keep = File(work, "ban-luu-cu")
        val old = "bản lưu trước".toByteArray()
        class ProcessDeath : Error()
        try {
            BookSave.save(book, File(work, "cache"), false,
                previous = { ByteArrayInputStream(old) },
                open = {
                    val entries = OldSaves.list(keep)
                    assertEquals(1, entries.size)
                    assertArrayEquals(old, File(keep, entries.single().name).readBytes())
                    throw ProcessDeath()
                }, keepDir = keep, keepName = "Sách thử", destination = "content://test/book")
            fail("must interrupt")
        } catch (_: ProcessDeath) { }
        assertEquals(1, BookSave.recover(keep).size)
        val entry = OldSaves.list(keep).single()
        assertArrayEquals(old, File(keep, entry.name).readBytes())
        assertTrue(File(keep, ".pending").listFiles()!!.single().readText().contains("content://test/book"))
        assertEquals(listOf(entry.name), BookSave.recover(keep))
    }

    @Test fun cannotWriteDurableIntentMeansDestinationIsNeverOpened() {
        val work = BookEditsFixtures.tempDir("a110-save-journal")
        val book = BookEditsFixtures.copyBase(File(work, "book"))
        val keep = File(work, "ban-luu-cu").apply { mkdirs() }
        File(keep, ".pending").writeText("blocked")
        var opens = 0
        assertTrue(runCatching {
            BookSave.save(book, File(work, "cache"), false, { ByteArrayInputStream("old".toByteArray()) },
                { opens++; ByteArrayOutputStream() }, keep, "Book")
        }.isFailure)
        assertEquals(0, opens)
    }

    @Test fun twoInterruptedSavesAtTheSameTimeKeepBothOriginals() {
        val work = BookEditsFixtures.tempDir("a110-save-collision")
        val book = BookEditsFixtures.copyBase(File(work, "book"))
        val keep = File(work, "ban-luu-cu")
        class ProcessDeath : Error()
        for (old in listOf("first", "second")) {
            try {
                BookSave.save(book, File(work, "cache"), false, { ByteArrayInputStream(old.toByteArray()) },
                    { throw ProcessDeath() }, keep, "Book", now = { 1_700_000_000_000L })
            } catch (_: ProcessDeath) { }
        }
        val files = OldSaves.list(keep)
        assertEquals(2, files.size)
        assertEquals(setOf("first", "second"), files.map { File(keep, it.name).readText() }.toSet())
        assertEquals(2, BookSave.recover(keep).size)
        assertTrue(OldSaves.delete(keep, files.first().name))
        assertEquals(1, BookSave.recover(keep).size)
    }
}
