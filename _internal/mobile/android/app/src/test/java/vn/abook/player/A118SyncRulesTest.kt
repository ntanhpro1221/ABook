package vn.abook.player

import java.io.File
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

/**
 * Soát a118: sáu lỗi đồng bộ dữ liệu nghe có phiên bản, cùng các ca với tests/test_a118_sync_rules.py (fixture chung
 * tests/fixtures/listening_revision/a118_meta.json; luật nhảy: boundary.json trong A110gUserDataTest). Hai "máy" là hai thư mục
 * Store: khách syncBody -> máy giữ sách mergeRecord -> khách applySync.
 */
class A118SyncRulesTest {
    private val book = "book"

    private fun phone(name: String): File = BookEditsFixtures.tempDir("a118-$name").also {
        BookEditsFixtures.useStoreRoot(it)
        File(it, "state").mkdirs()
    }

    private fun use(root: File) = BookEditsFixtures.useStoreRoot(root)

    private fun sync(client: File, holder: File): JSONObject {
        use(client)
        val body = JSONObject(Store.syncBody(book).toString())
        use(holder)
        val reply = JSONObject(Store.mergeRecord(book, body, onGone = {}).toString())
        use(client)
        Store.applySync(book, reply, { "" to false }, {})
        return reply
    }

    private fun stateFile(root: File) = File(root, "state/${Store.defaultRecordId(book)}.json")

    private fun node(root: File) = JSONObject(File(root, "listening-node.json").readText()).getString("node")

    /** Đồng hồ tường của máy chậm: viết lùi mốc giờ trong records.json rồi bỏ bộ nhớ đệm. */
    private fun slowClock(root: File, edit: (JSONObject) -> Unit) {
        val file = File(root, "records.json")
        file.writeText(JSONObject(file.readText()).also(edit).toString())
        use(root)
    }

    @Test fun bug1NewDeviceTakesAProfileWithMoreThanAMillionSaves() {
        val holder = phone("holder")
        Store.activeRecord(book)
        stateFile(holder).writeText(JSONObject().put("chapters", JSONObject()).put("bookmarks", JSONArray()).put("_clock", 1_200_000).toString())
        Store.progress(book, 3, 300.0, 600.0)
        Store.setRate(book, 1.25)
        val mark = Store.addBookmark(book, 3, 120.0, "quan trọng")
        val client = phone("client")
        sync(client, holder)
        val mine = Store.state(book)
        assertEquals(1.25, mine.getDouble("rate"), 0.0)
        assertEquals(3, mine.getJSONObject("last").getInt("chapterId"))
        assertEquals(mark.getString("id"), mine.getJSONArray("bookmarks").getJSONObject(0).getString("id"))
        Store.progress(book, 4, 50.0, 600.0)
        sync(client, holder)
        use(holder)
        assertEquals("chỗ nghe của máy mới tới được máy kia", 4, Store.state(book).getJSONObject("last").getInt("chapterId"))
    }

    @Test fun bug1ALeapInTheUpperHalfIsStillIgnored() {
        val safe = ListeningRevision.SAFE_COUNTER
        val ours = JSONObject().put("reading", JSONObject().put("chapterId", 1).put("index", 1).put("at", 1)
            .put("rev", JSONObject().put("counter", safe + 5).put("node", "a")))
        fun forged(counter: Long) = JSONObject().put("listeningRevision", 1).put("reading", JSONObject().put("chapterId", 9)
            .put("index", 9).put("at", 9).put("rev", JSONObject().put("counter", counter).put("node", "z")))
        val seen = mutableListOf<String>()
        assertFalse(ListeningRevision.checkedPeer(ours, forged(safe + 5 + ListeningRevision.MAX_JUMP + 1)) { seen.add(it) }.has("reading"))
        assertEquals(listOf(ListeningRevision.JUMP_NOTICE), seen)
        assertFalse(ListeningRevision.checkedPeer(JSONObject(), forged(safe + 1)) { seen.add(it) }.has("reading"))
        assertTrue(ListeningRevision.checkedPeer(JSONObject(), forged(safe)) { seen.add(it) }.has("reading"))
    }

    @Test fun bug2ARecoveredProfileTakesANewNode() {
        val root = phone("recovered")
        Store.setRate(book, 1.5)
        val first = node(root)
        stateFile(root).writeText(stateFile(root).readText().take(20))  // cắt ngắn: Store giữ bản .corrupt-*, hồ sơ bắt đầu trống
        Store.setRate(book, 2.0)
        val second = node(root)
        assertNotEquals("hồ sơ dựng lại từ bản hỏng thì máy lấy mã mới", first, second)
        assertEquals(second, Store.state(book).getJSONObject("_fieldRevs").getJSONObject("rate").getString("node"))
        val partial = JSONObject(stateFile(root).readText()).put("_clock", "hỏng")
        stateFile(root).writeText(partial.toString())
        Store.setChapterDone(book, 4, true)
        assertNotEquals("đọc được một phần cũng lấy mã mới", second, node(root))
        assertEquals(node(root), Store.state(book).getJSONObject("chapters").getJSONObject("4").getJSONObject("rev").getString("node"))
    }

    @Test fun bug3AMissingFieldStampNeverBreaksAMerge() {
        phone("stamp")
        val theirs = JSONObject().put("listeningRevision", 1).put("rate", 1.5)
            .put("_fieldRevs", JSONObject().put("rate", JSONObject().put("counter", 3).put("node", "peer")))
        val merged = Store.mergeStates(JSONObject().put("chapters", JSONObject()).put("bookmarks", JSONArray()), theirs)
        assertEquals(1.5, merged.getDouble("rate"), 0.0)
        assertFalse(merged.has("rateAt"))
        val nulled = Store.mergeStates(JSONObject().put("rateAt", 5), JSONObject(theirs.toString()).put("rateAt", JSONObject.NULL))
        assertFalse(nulled.has("rateAt"))
        for ((field, value, stamp) in listOf(Triple("rate", 1.5, "rateAt"), Triple("voice", "edge:x", "voiceAt"), Triple("finished", true, "finishedAt"))) {
            val clean = ListeningSchema.state(JSONObject().put(field, value).put(stamp, JSONObject.NULL)
                .put("_fieldRevs", JSONObject().put(field, JSONObject().put("counter", 1).put("node", "n"))))
            assertFalse(field, clean.has(field) || clean.has(stamp) || clean.optJSONObject("_fieldRevs")?.has(field) == true)
        }
    }

    @Test fun bug4SelfRepairedEntriesGetNewRevisionsAndStillSync() {
        val holder = phone("selfrepair-holder")
        Store.setChapterDone(book, 3, true)
        val mark = Store.addBookmark(book, 2, 30.0, "")
        Store.deleteBookmark(book, mark.getString("id"))
        val raw = JSONObject(stateFile(holder).readText())
        raw.getJSONObject("chapters").getJSONObject("3").getJSONObject("rev").put("counter", "1")
        raw.getJSONObject("_deletedRevs").put(mark.getString("id"), JSONObject().put("counter", -4).put("node", "x"))
        stateFile(holder).writeText(raw.toString())
        val body = Store.syncBody(book)
        assertTrue(ListeningRevision.revision(body.getJSONObject("chapters").getJSONObject("3")).first > 0)
        assertTrue(ListeningRevision.revision(JSONObject().put("rev", body.getJSONObject("_deletedRevs").get(mark.getString("id")))).first > 0)
        Store.setRate(book, 1.75)
        val client = phone("selfrepair-client")
        sync(client, holder)
        sync(client, holder)
        val mine = Store.state(book)
        assertEquals(1.75, mine.getDouble("rate"), 0.0)
        assertTrue(mine.getJSONObject("chapters").getJSONObject("3").getBoolean("done"))
        assertTrue(mine.getJSONObject("deleted").has(mark.getString("id")))
    }

    @Test fun bug5RecordMetadataFollowsCausalityNotTheWallClock() {
        val holder = phone("meta-holder")
        val record = Store.activeRecord(book)
        Store.renameRecord(book, record, "Lần nghe đầu")
        val client = phone("meta-client")
        sync(client, holder)
        assertEquals("Lần nghe đầu", Store.records(book).getJSONObject(0).getString("name"))
        Store.renameRecord(book, record, "Nghe lại cùng con")
        slowClock(client) { it.getJSONObject("records").getJSONObject(record).put("nameAt", 1.0) }  // đồng hồ máy khách chậm
        use(holder)
        Store.createRecord(book, "Hồ sơ phụ")
        sync(client, holder)
        Store.activateRecord(book, record)  // chọn lại hồ sơ chính SAU khi đã thấy lựa chọn của máy kia
        slowClock(client) { it.getJSONObject("links").getJSONObject(book).put("activeAt", 1.0) }
        sync(client, holder)
        sync(client, holder)
        for (root in listOf(holder, client)) {
            use(root)
            val rows = Store.records(book)
            val main = (0 until rows.length()).map { rows.getJSONObject(it) }.single { it.getString("id") == record }
            assertEquals("Nghe lại cùng con", main.getString("name"))
            assertTrue("hồ sơ khách chọn sau cùng là hồ sơ đang chọn", main.getBoolean("active"))
        }
    }

    @Test fun bug5SharedMetadataOrderFixture() {
        val rows = JSONArray(File("../../../tests/fixtures/listening_revision/a118_meta.json").readText())
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            val theirs = row.getJSONObject("theirs")
            val ours = row.getJSONObject("ours")
            val seen = mutableListOf<String>()
            val newer = ListeningRevision.metaNewer(row.getJSONObject("data"), theirs.opt("rev"), theirs.getDouble("at"),
                ours.opt("rev"), ours.getDouble("at")) { seen.add(it) }
            assertEquals(row.getString("name"), row.getBoolean("newer"), newer)
            assertEquals(row.getString("name"), row.optBoolean("notice", false), seen.isNotEmpty())
        }
    }

    @Test fun bug6UndoingABookmarkDeleteKeepsTheTombstoneAndConverges() {
        val holder = phone("undo-holder")
        val mark = Store.addBookmark(book, 1, 30.0, "")
        Store.deleteBookmark(book, mark.getString("id"))
        val client = phone("undo-client")
        sync(client, holder)
        use(holder)
        Store.restoreBookmark(book, mark)
        repeat(3) { sync(client, holder) }
        val states = listOf(holder, client).map { use(it); Store.state(book) }
        for (state in states) {
            assertEquals(mark.getString("id"), state.getJSONArray("bookmarks").getJSONObject(0).getString("id"))
            assertEquals(listOf(mark.getString("id")), state.getJSONObject("deleted").keys().asSequence().toList())
        }
        assertTrue(StrictJson.equal(states[0].getJSONObject("_deletedRevs"), states[1].getJSONObject("_deletedRevs")))
    }
}
