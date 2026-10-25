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

    @Test fun sharedRevisionMessagesMatchPython() {
        val rows = JSONArray(File("../../../tests/fixtures/listening_revision/messages.json").readText())
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            val notices = mutableListOf<String>()
            val result = runCatching {
                ListeningRevision.checkedPeer(JSONObject(), row.getJSONObject("incoming")) { notices.add(it) }
            }
            if (row.has("error")) {
                assertTrue(row.getString("name"), result.exceptionOrNull() is IllegalArgumentException)
                assertEquals(row.getString("name"), row.getString("error"), result.exceptionOrNull()?.message)
                assertTrue(notices.isEmpty())
            } else {
                assertFalse(row.getString("name"), result.getOrThrow().has("reading"))
                assertEquals(row.getString("name"), listOf(row.getString("notice")), notices)
            }
        }
    }

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
        stateFile(holder).writeText(JSONObject().put("chapters", JSONObject()).put("_clock", 1_200_000).toString())
        Store.progress(book, 3, 300.0, 600.0)
        Store.setRate(book, 1.25)
        val client = phone("client")
        sync(client, holder)
        val mine = Store.state(book)
        assertEquals(1.25, mine.getDouble("rate"), 0.0)
        assertEquals(3, mine.getJSONObject("last").getInt("chapterId"))
        Store.progress(book, 4, 50.0, 600.0)
        sync(client, holder)
        use(holder)
        assertEquals("chỗ nghe của máy mới tới được máy kia", 4, Store.state(book).getJSONObject("last").getInt("chapterId"))
    }

    @Test fun bug1ALeapInTheUpperHalfIsStillIgnored() {
        val safe = ListeningRevision.SAFE_COUNTER
        val ours = JSONObject().put("reading", JSONObject().put("chapterId", 1).put("index", 1).put("at", 1)
            .put("rev", JSONObject().put("counter", safe + 5).put("node", "a")))
        fun forged(counter: Long) = JSONObject().put("reading", JSONObject().put("chapterId", 9)
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
        val theirs = JSONObject().put("rate", 1.5)
            .put("_fieldRevs", JSONObject().put("rate", JSONObject().put("counter", 3).put("node", "peer")))
        val merged = Store.mergeStates(JSONObject().put("chapters", JSONObject()), theirs)
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

    @Test fun bug3ABrokenRowRevisionDropsTheRowSoThePeerResendsIt() {
        fun rev(counter: Int, node: String) = JSONObject().put("counter", counter).put("node", node)
        val clean = ListeningSchema.state(JSONObject()
            .put("chapters", JSONObject().put("1", JSONObject().put("heard", 5).put("duration", 9).put("at", 1).put("rev", rev(-3, "x")))
                .put("2", JSONObject().put("heard", 1).put("at", 1).put("rev", rev(2, "n"))))
            .put("last", JSONObject().put("chapterId", 1).put("seconds", 3).put("rev", rev(-3, "x")))
            .put("rate", 1.2).put("rateAt", 5).put("_fieldRevs", JSONObject().put("rate", rev(-3, "x"))))
        assertEquals(listOf("2"), clean.getJSONObject("chapters").keys().asSequence().toList())
        assertFalse(clean.has("last") || clean.has("rate") || clean.has("rateAt"))
        assertTrue(ListeningRevision.checkedPeer(JSONObject(), clean) {}.getJSONObject("chapters").has("2"))
    }

    @Test fun aRevisionTableOfTheWrongTypeDropsWhatItShouldHaveVersioned() {
        // `_fieldRevs` itself the wrong type is replaced by {}: the value has no revision left, so it goes like a broken one.
        for (table in listOf<Any>(JSONArray().put(JSONObject()), "x", 5, JSONObject.NULL)) {
            val rate = ListeningSchema.state(JSONObject().put("rate", 1.2).put("rateAt", 5).put("_fieldRevs", table))
            assertFalse(rate.has("rate") || rate.has("rateAt"))
            assertEquals(0, rate.getJSONObject("_fieldRevs").length())
        }
        val ok = JSONObject().put("counter", 2).put("node", "n")
        val kept = ListeningSchema.state(JSONObject().put("rate", 1.2).put("rateAt", 5).put("_fieldRevs", JSONObject().put("rate", ok)))
        assertEquals(1.2, kept.getDouble("rate"), 0.0)
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
}
