package vn.abook.player

import java.io.File
import java.io.IOException
import java.util.Base64
import java.util.zip.ZipFile
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * Cuốn tải từ máy tính chính sửa được ngay trên điện thoại, và phần sửa gửi về máy tính (EditsSync, abook/webui/edits_inbox.py):
 * gói đúng tên mục máy tính nhận, nhận xong thì gỡ đúng phần đã gửi (không mất sửa mới làm giữa chừng), lỗi thì giữ nguyên và nói lý do.
 */
class EditsSyncTest {
    private lateinit var root: File
    private val id = "0123456789abcdef01234567"
    private val dir get() = Store.bookDir(id)

    private class FakeCodec : CoverCodec {
        override fun normalize(raw: ByteArray): CoverCodec.Normalized = CoverCodec.Normalized(raw, "#aa5522", 96, 128)
    }

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-sync")
        BookEditsFixtures.useStoreRoot(root)
        BookEditsFixtures.copyBase(dir) // tải từ máy tính: có book.json, KHÔNG ghi sổ "mở từ file"
        LocalStudio.coverCodec = FakeCodec()
        LocalStudio.musicStore = MusicStore(File(root, "music"), FakeTags)
        LocalStudio.clock = { 1_790_950_256L }
        LocalStudio.now = { 1_790_950_256.0 }
        EditsSync.clock = { 1_790_960_000L }
        EditsSync.refresh = null
        EditsSync.changed = null
    }

    @After
    fun tearDown() {
        LocalStudio.coverCodec = null
        LocalStudio.musicStore = null
        LocalStudio.now = { System.currentTimeMillis() / 1000.0 }
        EditsSync.clock = { System.currentTimeMillis() / 1000 }
        EditsSync.refresh = null
        EditsSync.changed = null
    }

    private fun call(method: String, suffix: String, body: JSONObject? = null) = LocalStudio.handle(method, "/api/books/$id$suffix", body)

    private fun dataUrl(): String =
        "data:image/jpeg;base64," + Base64.getEncoder().encodeToString(BookEditsFixtures.bytes("edits/cover_set.cover.jpg"))

    private val tone get() = BookEditsFixtures.file("track/tone.wav")
    private val toneSha get() = java.security.MessageDigest.getInstance("SHA-1").digest(tone.readBytes()).joinToString("") { "%02x".format(it) }

    private fun accepted(applied: Int = 1, waiting: Int = 0, conflicts: List<String> = emptyList()): String =
        JSONObject().put("applied", applied).put("skipped", 0).put("requests", 0).put("waiting", waiting).put("skippedWishes", 0)
            .put("music", false).put("conflicts", org.json.JSONArray(conflicts.map { JSONObject().put("kind", "title").put("key", "").put("label", it) })).toString()

    // ---- sửa được trên điện thoại ----------------------------------------------------------------------------------

    @Test
    fun a_book_downloaded_from_the_computer_is_editable_and_says_it_syncs() {
        assertEquals(200, call("PUT", "/title", JSONObject().put("title", "Tên mới")).first)
        val shown = Store.manifest(id)!!
        assertEquals("Tên mới", shown.getString("title"))
        val caps = shown.getJSONObject("capabilities")
        assertTrue(caps.getBoolean("sync"))
        assertFalse(caps.getBoolean("link"))
        assertEquals(1, shown.getJSONObject("editsSync").getInt("pending"))
        assertTrue(shown.getJSONObject("editsSync").isNull("last"))
        assertEquals(caps.toString(), Store.capabilitiesOf(id).toString())
    }

    @Test
    fun a_book_of_another_paired_device_or_one_not_downloaded_is_still_edited_over_there() {
        File(dir, "book.json").writeText(BookEdits.rawBook(dir).put("source", "device-1").toString())
        assertEquals(409, call("PUT", "/title", JSONObject().put("title", "x")).first)
        assertTrue(Store.capabilitiesOf(id).getBoolean("link"))
        assertFalse(Store.capabilitiesOf(id).getBoolean("sync"))
        File(root, "books/aaaaaaaaaaaaaaaaaaaaaaaa").mkdirs()
        File(root, "books/aaaaaaaaaaaaaaaaaaaaaaaa/stream.json").writeText(JSONObject().put("id", "aaaaaaaaaaaaaaaaaaaaaaaa").toString())
        assertEquals(409, LocalStudio.handle("PUT", "/api/books/aaaaaaaaaaaaaaaaaaaaaaaa/title", JSONObject().put("title", "x")).first)
        assertTrue(Store.capabilitiesOf("aaaaaaaaaaaaaaaaaaaaaaaa").getBoolean("link"))
    }

    // ---- gói ------------------------------------------------------------------------------------------------------------

    @Test
    fun the_package_holds_exactly_the_edit_layer_the_computer_accepts() {
        call("PUT", "/title", JSONObject().put("title", "Tên mới"))
        call("PUT", "/cover", JSONObject().put("image", dataUrl()))
        LocalStudio.musicStore!!.importFile(tone)
        call("PUT", "/music", JSONObject().put("pins", JSONObject().put("1:0", "local:$toneSha")))
        val snapshot = EditsSync.snapshot(dir)!!
        val target = File(root, "goi.zip")
        EditsSync.writePackage(dir, snapshot, target)
        ZipFile(target).use { zip ->
            assertEquals(setOf("edits.json", "edits/cover.jpg", "music/$toneSha.wav"), zip.entries().asSequence().map { it.name }.toSet())
            val edits = BookEdits.parse(zip.getInputStream(zip.getEntry("edits.json")).readBytes()) // chính bộ kiểm của lớp sửa
            assertEquals("Tên mới", edits.getString("title"))
            assertTrue(zip.getInputStream(zip.getEntry("edits/cover.jpg")).readBytes().contentEquals(BookEditsFixtures.bytes("edits/cover_set.cover.jpg")))
            assertTrue(zip.getInputStream(zip.getEntry("music/$toneSha.wav")).readBytes().contentEquals(tone.readBytes()))
        }
    }

    @Test
    fun a_pinned_track_whose_file_is_gone_is_said_not_silently_dropped() {
        call("PUT", "/title", JSONObject().put("title", "Tên mới"))
        LocalStudio.musicStore!!.importFile(tone)
        call("PUT", "/music", JSONObject().put("pins", JSONObject().put("1:0", "local:$toneSha")))
        File(dir, "music/$toneSha.wav").delete()
        try {
            EditsSync.push(id) { fail("không có gì được gửi") ; "" }
            fail("phải từ chối")
        } catch (error: IllegalStateException) {
            assertTrue(error.message!!.contains("Thiếu file nhạc"))
        }
        assertEquals("error", Store.manifest(id)!!.getJSONObject("editsSync").getJSONObject("last").getString("state"))
        assertEquals("Tên mới", BookEdits.load(dir).getString("title"))
    }

    // ---- gửi --------------------------------------------------------------------------------------------------------------

    @Test
    fun once_the_computer_accepts_what_was_sent_is_removed_and_the_result_is_remembered() {
        call("PUT", "/title", JSONObject().put("title", "Tên mới"))
        call("POST", "/characters/rename", JSONObject().put("character", "LUCIEN").put("name", "Lu-xi-en"))
        call("PUT", "/cover", JSONObject().put("image", dataUrl()))
        var sentNames = emptySet<String>()
        val shown = mutableListOf<String>()
        EditsSync.changed = { shown += it }
        val view = EditsSync.push(id) { file ->
            ZipFile(file).use { zip -> sentNames = zip.entries().asSequence().map { it.name }.toSet() }
            accepted(applied = 3, conflicts = listOf("Tên sách: máy tính đã có bản riêng"))
        }
        assertEquals(setOf("edits.json", "edits/cover.jpg"), sentNames)
        assertEquals(0, view.getInt("pending"))
        val last = view.getJSONObject("last")
        assertEquals("sent", last.getString("state"))
        assertEquals(3, last.getInt("applied"))
        assertEquals(1_790_960_000L, last.getLong("at"))
        assertEquals("Tên sách: máy tính đã có bản riêng", last.getJSONArray("conflicts").getString(0))
        assertEquals(listOf(id), shown)
        // lớp sửa đã sạch: sách trở lại đúng bản của máy tính (máy tính mang sửa trong gói kế tiếp), bìa sửa cũng đã xoá
        assertTrue(BookEdits.isEmpty(BookEdits.load(dir)))
        assertFalse(File(dir, "edits/cover.jpg").exists())
        assertFalse(File(root, "edits_out_$id.zip").exists())
        assertEquals(0, Store.manifest(id)!!.getInt("edits"))
    }

    @Test
    fun a_change_made_while_sending_is_kept_for_the_next_send() {
        call("PUT", "/title", JSONObject().put("title", "Tên một"))
        call("POST", "/characters/rename", JSONObject().put("character", "LUCIEN").put("name", "Lu-xi-en"))
        call("PUT", "/chapters/1/title", JSONObject().put("title", "Chương Một"))
        val view = EditsSync.push(id) {
            call("PUT", "/title", JSONObject().put("title", "Tên hai")) // người dùng sửa tiếp khi gói đang đi
            call("PUT", "/chapters/1/title", JSONObject().put("subtitle", "Mở"))
            accepted()
        }
        assertEquals(2, view.getInt("pending"))
        val left = BookEdits.load(dir)
        assertEquals("Tên hai", left.getString("title"))
        assertFalse(left.has("characters"))
        assertEquals(JSONObject().put("subtitle", "Mở").toString(), left.getJSONObject("chapters").getJSONObject("1").toString())
        // lần sau gửi nốt phần còn lại
        EditsSync.push(id) { accepted() }
        assertTrue(BookEdits.isEmpty(BookEdits.load(dir)))
    }

    @Test
    fun a_newer_cover_is_not_lost_when_an_older_one_was_sent() {
        call("PUT", "/cover", JSONObject().put("image", dataUrl()))
        val view = EditsSync.push(id) {
            LocalStudio.clock = { 1_790_950_999L }
            call("PUT", "/cover", JSONObject().put("image", "data:image/jpeg;base64," + Base64.getEncoder().encodeToString(byteArrayOf(0xFF.toByte(), 1, 2, 3, 4))))
            accepted()
        }
        assertEquals(1, view.getInt("pending"))
        assertTrue(BookEdits.load(dir).opt("cover") is JSONObject)
        assertTrue(File(dir, "edits/cover.jpg").isFile)
    }

    @Test
    fun wishes_and_pinned_tracks_that_were_sent_are_removed_too() {
        call("POST", "/pronunciation", JSONObject().put("surface", "Hailkes").put("spokenForm", "Hên-khơ"))
        LocalStudio.musicStore!!.importFile(tone)
        call("PUT", "/music", JSONObject().put("pins", JSONObject().put("1:0", "local:$toneSha")).put("silence", JSONObject().put("1:60000", true)))
        assertTrue(File(dir, "music/$toneSha.wav").isFile)
        var names = emptySet<String>()
        val view = EditsSync.push(id) { file ->
            ZipFile(file).use { zip -> names = zip.entries().asSequence().map { it.name }.toSet() }
            accepted(applied = 2, waiting = 1)
        }
        assertEquals(setOf("edits.json", "music/$toneSha.wav"), names)
        assertEquals(0, view.getInt("pending"))
        assertEquals(1, view.getJSONObject("last").getInt("waiting"))
        assertTrue(BookEdits.isEmpty(BookEdits.load(dir)))
        assertFalse("bài đã ghim và gửi xong: file của nó trong sách bỏ đi", File(dir, "music/$toneSha.wav").exists())
        assertEquals(0, Store.manifest(id)!!.getInt("wishes"))
    }

    @Test
    fun a_refusal_or_a_lost_connection_keeps_every_edit_and_says_why() {
        call("PUT", "/title", JSONObject().put("title", "Tên mới"))
        try {
            EditsSync.push(id) { throw IllegalStateException("Gói thay đổi từ điện thoại bị hỏng.") }
            fail("phải ném lỗi")
        } catch (error: IllegalStateException) {
            assertEquals("Gói thay đổi từ điện thoại bị hỏng.", error.message)
        }
        var view = Store.manifest(id)!!.getJSONObject("editsSync")
        assertEquals(1, view.getInt("pending"))
        assertEquals("Gói thay đổi từ điện thoại bị hỏng.", view.getJSONObject("last").getString("error"))
        try {
            EditsSync.push(id) { throw IOException("connect failed") }
            fail("phải ném lỗi")
        } catch (error: IOException) {
            assertTrue(error.message!!.startsWith("Chưa tới được máy tính"))
        }
        view = Store.manifest(id)!!.getJSONObject("editsSync")
        assertEquals("error", view.getJSONObject("last").getString("state"))
        assertEquals("Tên mới", BookEdits.load(dir).getString("title"))
        // gửi lại được: thành công thì lỗi cũ không còn
        assertEquals("sent", EditsSync.push(id) { accepted() }.getJSONObject("last").getString("state"))
    }

    @Test
    fun nothing_to_send_sends_nothing_and_only_a_computer_book_can_be_sent() {
        val view = EditsSync.push(id) { fail("không có gì để gửi"); "" }
        assertEquals(0, view.getInt("pending"))
        assertNull(File(dir, EditsSync.STATE_FILE).takeIf { it.exists() })
        Store.rememberChapters(id, JSONObject(), imported = true) // mở từ file: không phải sách của máy tính
        try {
            EditsSync.push(id) { "{}" }
            fail("phải từ chối")
        } catch (error: IllegalStateException) {
            assertNotNull(error.message)
        }
    }

    @Test
    fun the_waiting_count_follows_what_the_owner_decided_on_the_computer() {
        call("POST", "/pronunciation", JSONObject().put("surface", "Hailkes").put("spokenForm", "Hên-khơ"))
        EditsSync.push(id) { accepted(applied = 0, waiting = 2) }
        val shown = mutableListOf<String>()
        EditsSync.changed = { shown += it }
        EditsSync.refreshWaiting(id) { """{"waiting": 1}""" }
        assertEquals(1, Store.manifest(id)!!.getJSONObject("editsSync").getJSONObject("last").getInt("waiting"))
        assertEquals(listOf(id), shown)
        EditsSync.refreshWaiting(id) { """{"waiting": 1}""" } // không đổi: không báo lại
        EditsSync.refreshWaiting(id) { """{"nonsense": true}""" } // không hiểu: giữ số cũ
        assertEquals(listOf(id), shown)
        EditsSync.refreshWaiting(id) { """{"waiting": 0}""" }
        val last = Store.manifest(id)!!.getJSONObject("editsSync").getJSONObject("last")
        assertEquals(0, last.getInt("waiting"))
        assertEquals("sent", last.getString("state"))
    }

    @Test
    fun an_unreadable_reply_is_a_failure_not_a_success() {
        call("PUT", "/title", JSONObject().put("title", "Tên mới"))
        try {
            EditsSync.push(id) { "<html>" }
            fail("phải ném lỗi")
        } catch (error: IllegalStateException) {
            assertEquals("Máy tính trả lời không hiểu được", error.message)
        }
        assertEquals("Tên mới", BookEdits.load(dir).getString("title"))
    }

    @Test
    fun the_book_is_refreshed_from_the_computer_before_the_overlay_goes() {
        call("PUT", "/title", JSONObject().put("title", "Tên mới"))
        var titleWhenRefreshed = ""
        EditsSync.refresh = { titleWhenRefreshed = Store.manifest(it)!!.getString("title") }
        EditsSync.push(id) { accepted() }
        assertEquals("lớp phủ còn nguyên lúc tải lại: không chớp bản cũ", "Tên mới", titleWhenRefreshed)
        assertEquals("Sách thử · Tập 1", Store.manifest(id)!!.getString("title"))
    }
}
