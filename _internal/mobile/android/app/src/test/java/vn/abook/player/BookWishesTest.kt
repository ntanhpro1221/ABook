package vn.abook.player

import java.io.File
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Ý muốn chờ Studio (BookWishes, docs/EDITING.md P2a) so với bản Python (webui/book_wishes.py): bộ ví dụ dùng chung đã phủ hình
 * dạng, kiểm, hợp và từng đường (BookEditsTest, LocalStudioTest); ở đây là hành vi quanh chúng - không bao giờ áp, rút, trần, và
 * phép kiểm cách đọc (VietnameseReading) y hệt Studio.
 */
class BookWishesTest {
    private lateinit var root: File
    private val id = "f-0123456789abcdef01234567"
    private val dir get() = Store.bookDir(id)
    private val lucien = "c1_s0003_fa1fe2" to "fa1fe25f1922819e9fd94d48eeef9fddcaeb06be1653b73d618873e572498ea5"
    private val heidi = "c1_s0006_34534a" to "34534ad5d25c0cc74935800b021272b15ac53406accd068020698cea262c6ec0"
    private val narration = "c1_s0002_c58b67" to "c58b6788498e1756635f89b55a9906af2fa37a0d3ffbc49083eb56c5c5c5483c"

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-wishes")
        BookEditsFixtures.useStoreRoot(root)
        BookEditsFixtures.copyBase(dir)
        Store.rememberChapters(id, JSONObject(), imported = true)
        var tick = 0
        LocalStudio.now = { 1_790_950_256.0 + (tick++) * 0.25 }
    }

    @After
    fun tearDown() {
        LocalStudio.now = { System.currentTimeMillis() / 1000.0 }
    }

    private fun post(path: String, body: JSONObject? = null) = LocalStudio.handle("POST", "/api/books/$id$path", body)

    private fun get(path: String) = LocalStudio.handle("GET", "/api/books/$id$path", null)

    private fun line(line: Pair<String, String>) = JSONObject().put("stableId", line.first).put("textSha256", line.second)

    private fun wishes(): JSONObject = BookEdits.load(dir).optJSONObject("wishes") ?: JSONObject()

    @Test
    fun a_wish_never_changes_what_the_listener_hears_or_reads() {
        val before = dir.walkTopDown().filter { it.isFile }.associate { it.relativeTo(dir).path to it.readBytes().toList() }
        assertEquals(200, post("/pronunciation", JSONObject().put("surface", "Hailkes").put("spokenForm", "Hên-khơ")).first)
        assertEquals(200, post("/speaker", line(lucien).put("speaker", "HEIDI")).first)
        assertEquals(200, post("/line", line(heidi).put("emotion", "sad").put("spoken", "Chào.")).first)
        assertEquals(200, post("/voice", JSONObject().put("character", "HEIDI").put("gender", "male")).first)
        assertEquals(200, post("/chapters/1/retake").first)
        assertEquals(200, post("/characters/merge", JSONObject().put("from", "HEIDI").put("into", "LUCIEN")).first)
        val after = dir.walkTopDown().filter { it.isFile }.associate { it.relativeTo(dir).path to it.readBytes().toList() }
        val changed = after.keys.filter { before[it] != after[it] }.map { it.replace('\\', '/') }.toSet()
        assertEquals("chỉ lớp sửa đổi; lớp sách, audio, bìa nguyên", setOf("edits.json"), changed)
        val script = JSONObject(Store.readText(id, "scripts/1.json")!!)
        assertTrue("chữ đọc theo và người nói giữ nguyên", StrictJson.equal(BookEditsFixtures.obj("base/scripts/1.json"), script))
        val shown = Store.manifest(id)!!
        assertEquals(shown.getInt("edits"), shown.getInt("wishes"))
        assertTrue(shown.getInt("wishes") >= 5)
        assertEquals(0, (get("/edits").second as JSONObject).getInt("applied"))
    }

    @Test
    fun a_waiting_voice_is_only_a_mark_on_the_cast() {
        post("/voice", JSONObject().put("character", "HEIDI").put("gender", "male"))
        val cast = (get("/cast").second as JSONObject).getJSONArray("characters")
        val people = (0 until cast.length()).map { cast.getJSONObject(it) }.associateBy { it.getString("name") }
        assertEquals("Nam", people.getValue("HEIDI").getJSONObject("pendingVoice").getString("gender"))
        assertEquals("Nữ", people.getValue("HEIDI").getString("gender"))
        assertEquals("Thanh Bình", people.getValue("HEIDI").getJSONObject("voice").getString("preset"))
        assertTrue(people.getValue("LUCIEN").isNull("pendingVoice"))
        assertTrue("cast.json của người làm sách nguyên", BookEdits.rawCast(dir, BookEdits.rawBook(dir)).getJSONArray("characters").getJSONObject(0).isNull("pendingVoice"))
    }

    @Test
    fun withdrawing_brings_back_the_wish_it_replaced() {
        val first = (post("/voice", JSONObject().put("character", "HEIDI").put("gender", "female")).second as JSONObject).getDouble("requestedAt")
        val second = (post("/voice", JSONObject().put("character", "HEIDI").put("gender", "male")).second as JSONObject).getDouble("requestedAt")
        assertEquals("female", wishes().getJSONObject("voices").getJSONObject("HEIDI").getJSONObject("replaced").getString("gender"))
        val undone = post("/voice", JSONObject().put("character", "HEIDI").put("withdraw", true).put("requestedAt", second))
        assertEquals(200, undone.first)
        assertEquals("female", wishes().getJSONObject("voices").getJSONObject("HEIDI").getString("gender"))
        assertEquals(409, post("/voice", JSONObject().put("character", "HEIDI").put("withdraw", true).put("requestedAt", second)).first)
        assertEquals(200, post("/voice", JSONObject().put("character", "HEIDI").put("withdraw", true).put("requestedAt", first)).first)
        assertFalse("rút hết thì không còn file", File(dir, "edits.json").exists())
    }

    @Test
    fun one_click_on_many_lines_is_one_change_and_a_merge_carries_its_alias() {
        val merged = (post("/characters/merge", JSONObject().put("from", "HEIDI").put("into", "LUCIEN")).second as JSONObject).getDouble("requestedAt")
        post("/chapters/1/retake")
        assertEquals(2, BookWishes.count(wishes()))
        val aliases = wishes().getJSONArray("aliases")
        assertEquals(1, aliases.length())
        assertEquals(merged, aliases.getJSONObject(0).getDouble("at"), 0.0)
        val items = (get("/pending-changes").second as JSONObject).getJSONArray("items")
        assertEquals(listOf("speaker", "retake"), (0 until items.length()).map { items.getJSONObject(it).getString("kind") })
        assertEquals(4, items.getJSONObject(1).getJSONArray("keys").length())
        post("/pending-changes/withdraw", JSONObject().put("section", "speakers").put("key", heidi.first).put("keys", BookEditsFixtures.array(heidi.first)).put("requestedAt", merged))
        assertFalse("rút lần gộp là rút luôn bí danh", wishes().has("aliases"))
    }

    @Test
    fun a_wish_on_a_line_that_changed_or_a_person_with_no_voice_is_refused_on_the_spot() {
        assertEquals(400, post("/speaker", JSONObject().put("stableId", lucien.first).put("textSha256", heidi.second).put("speaker", "HEIDI")).first)
        assertEquals(400, post("/speaker", line(narration).put("speaker", "HEIDI")).first)
        assertEquals(400, post("/speaker", line(lucien).put("speaker", "Ai đó")).first)
        assertEquals(200, post("/speaker", line(lucien).put("speaker", "Ai đó").put("newGender", "female")).first)
        assertEquals(400, post("/speaker", line(lucien).put("speaker", "ANONYMOUS_X").put("newGender", "female")).first)
        assertEquals(400, post("/line", line(heidi).put("emotion", "bored")).first)
        assertEquals(400, post("/voice", JSONObject().put("character", "NARRATOR").put("gender", "male")).first)
        assertEquals(400, post("/pronunciation", JSONObject().put("surface", "Hai kes").put("spokenForm", "Hên-khơ")).first)
        assertEquals("không bao giờ được dùng", 400, post("/pronunciation", JSONObject().put("surface", "Mở/đóng").put("spokenForm", "mở hoặc đóng")).first)
        assertEquals(listOf("speakers"), BookEdits.names(wishes()))
    }

    @Test
    fun the_writer_never_leaves_a_file_it_could_not_read_back() {
        BookWishes.requestVoice(dir, "HEIDI", gender = "male", now = 1759400004.0)
        val before = File(dir, "edits.json").readBytes().toList()
        val longName = "N".repeat(200)
        val lines = (0 until 5000).map { "c1_s%05d".format(it) to "a".repeat(64) }
        val refused = try {
            BookWishes.requestSpeakers(dir, lines, longName, 1759400005.0)
            ""
        } catch (error: BookEdits.EditsError) {
            error.message.orEmpty()
        }
        assertTrue(refused, refused.startsWith("Quá nhiều"))
        assertEquals("file cũ nguyên", before, File(dir, "edits.json").readBytes().toList())
    }

    @Test
    fun a_merge_that_would_overflow_keeps_this_machines_wishes_whole() {
        val entry = { JSONObject().put("requested_at", 1.5).put("text_sha256", "a".repeat(64)) }
        val local = JSONObject().put("retakes", JSONObject().also { out -> for (i in 0 until 4999) out.put("c1_s%05d".format(i), entry()) })
        val incoming = JSONObject().put("retakes", JSONObject().also { out -> for (i in 0 until 5) out.put("c2_s%05d".format(i), entry()) })
        val (merged, conflicts) = BookWishes.merge(local, incoming)
        assertTrue(StrictJson.equal(local, merged))
        assertEquals(0, conflicts)
    }

    @Test
    fun an_empty_list_has_the_same_shape_as_the_servers() {
        val answer = get("/pending-changes").second as JSONObject
        assertEquals(0, answer.getJSONArray("items").length())
        assertEquals(0, answer.getInt("lines"))
        assertEquals(0, answer.getJSONArray("chapters").length())
        assertEquals(0.0, answer.getDouble("seconds"), 0.0)
    }

    @Test
    fun a_reading_is_checked_like_the_studio_checks_it() {
        assertNull(VietnameseReading.problem("Hailkes", "Hên-khơ"))
        assertEquals(VietnameseReading.MULTI_WORD, VietnameseReading.problem("Hai kes", "Hên-khơ"))
        assertEquals(VietnameseReading.NOT_VIETNAMESE, VietnameseReading.problem("Hailkes", "Xă-mon"))
        assertNull("đọc đúng như viết thì người nghe được chọn", VietnameseReading.problem("Deck", "Deck"))
        assertEquals(VietnameseReading.NOT_VIETNAMESE, VietnameseReading.problem("Aaa", "AAA bb"))
        assertEquals(VietnameseReading.NOT_VIETNAMESE, VietnameseReading.problem("X", ""))
        for (word in listOf("tiếng", "kinh", "cơ", "ăn", "gì", "nghê", "khơ", "Hên")) assertTrue(word, VietnameseReading.isSyllable(word))
        for (word in listOf("king", "cin", "kơ", "xă", "ngê", "Hailkes", "Dragon")) assertFalse(word, VietnameseReading.isSyllable(word))
    }

    @Test
    fun a_reading_typed_by_ear_is_offered_its_correct_spelling() {
        assertEquals("Hên-cơ", VietnameseReading.respelled("Hên-kơ"))
        assertEquals("Tiếng Việt viết “cơ”, không viết “kơ”.", VietnameseReading.respellingNote("Hên-kơ", "Hên-cơ"))
        assertEquals("Nghê-ra", VietnameseReading.respelled("Ngê-ra"))
        assertEquals("Tiếng Việt viết “Nghê”, không viết “Ngê”.", VietnameseReading.respellingNote("Ngê-ra", "Nghê-ra"))
        assertEquals("Hên-khơ", VietnameseReading.respelled("Hên-khơ"))
    }

    @Test
    fun keys_fold_case_like_python() {
        assertEquals("école ss", VietnameseReading.surfaceKey("  ÉCOLE  SS "))
        assertEquals("HEIDI MAI SS", BookWishes.characterKey(" heidi  Mai ß"))
        assertEquals("hây đi", BookWishes.aliasKey(" Hây_Đi "))
    }
}
