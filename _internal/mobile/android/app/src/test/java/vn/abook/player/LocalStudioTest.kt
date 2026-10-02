package vn.abook.player

import java.io.File
import java.util.Base64
import org.json.JSONArray
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
 * LocalStudio (điện thoại) phải đáp y hệt máy chủ Python cho từng đường "áp ngay": phát lại từng chuỗi yêu cầu của bộ ví dụ
 * tests/fixtures/book_edits/contract/ (do máy chủ THẬT ghi lại) trên một bản sao của `base/` đăng ký như cuốn đã nhập từ file.
 */
class LocalStudioTest {
    private lateinit var root: File
    private val id = "f-0123456789abcdef01234567"
    private val dir get() = Store.bookDir(id)

    /** Bìa giả: ảnh 96x128 mà bộ ví dụ khai (không cần Bitmap trong test JVM). */
    private class FakeCodec : CoverCodec {
        override fun normalize(raw: ByteArray): CoverCodec.Normalized {
            if (raw.size < 4 || raw[0] != 0xFF.toByte()) throw CoverCodec.CoverError("Không đọc được ảnh này")
            return CoverCodec.Normalized(raw, "#aa5522", 96, 128)
        }
    }

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-studio")
        BookEditsFixtures.useStoreRoot(root)
        BookEditsFixtures.copyBase(dir)
        Store.rememberChapters(id, JSONObject(), imported = true)
        LocalStudio.coverCodec = FakeCodec()
        LocalStudio.clock = { 1_790_950_256L }
        // đồng hồ của ý muốn chạy từng bước: mỗi yêu cầu một dấu giờ riêng (rút đúng lần bấm theo `requestedAt`)
        var tick = 0
        LocalStudio.now = { 1_790_950_256.0 + (tick++) * 0.25 }
    }

    @After
    fun tearDown() {
        LocalStudio.coverCodec = null
        LocalStudio.now = { System.currentTimeMillis() / 1000.0 }
    }

    private fun call(method: String, suffix: String, body: JSONObject? = null) = LocalStudio.handle(method, "/api/books/$id$suffix", body)

    private fun withoutVolatile(value: Any?, volatile: Set<String>): Any? = when (value) {
        is JSONObject -> JSONObject().also { out ->
            for (key in value.keys().asSequence().toList()) if (key !in volatile) out.put(key, withoutVolatile(value.opt(key), volatile))
        }
        is JSONArray -> JSONArray().also { out -> for (index in 0 until value.length()) out.put(withoutVolatile(value.opt(index), volatile)) }
        else -> value
    }

    private fun dataUrl(): String =
        "data:image/jpeg;base64," + Base64.getEncoder().encodeToString(BookEditsFixtures.bytes("edits/cover_set.cover.jpg"))

    @Test
    fun every_contract_case_is_answered_exactly_like_the_python_server() {
        var replayed = 0
        for (name in BookEditsFixtures.cases("contract")) {
            // mỗi ca bắt đầu từ cuốn sạch
            BookEdits.clear(dir)
            val case = BookEditsFixtures.obj("contract/$name.json")
            val volatile = case.getJSONArray("volatile").let { list -> (0 until list.length()).map { list.getString(it) }.toSet() }
            val steps = case.getJSONArray("steps")
            val answers = ArrayList<Any?>()
            for (index in 0 until steps.length()) {
                val step = steps.getJSONObject(index)
                val where = "$name #${index + 1} ${step.getString("method")} ${step.getString("path")}"
                val body = step.optJSONObject("body")?.let { sent ->
                    // "$requestedAt#N": dấu giờ lời đáp của bước N (của chính bản Kotlin) - để rút đúng lần bấm ấy
                    val text = Regex("\"\\\$requestedAt#([0-9]+)\"").replace(sent.toString().replace("\"\$cover\"", JSONObject.quote(dataUrl()))) { match ->
                        StrictJson.pyFloat(((answers[match.groupValues[1].toInt() - 1] as JSONObject).getDouble("requestedAt")))
                    }
                    JSONObject(text)
                }
                val (status, reply) = call(step.getString("method"), step.getString("path"), body)
                answers.add(reply)
                assertEquals("$where: mã trạng thái", step.getInt("status"), status)
                val expected = withoutVolatile(step.opt("response"), volatile)
                val actual = withoutVolatile(reply, volatile)
                if (!StrictJson.equal(expected, actual)) {
                    fail("$where: lời đáp khác máy chủ Python\n--- mong đợi ---\n${StrictJson.dumps(expected)}\n--- thực tế ---\n${StrictJson.dumps(actual)}")
                }
                replayed++
            }
        }
        assertTrue("đã phát lại cả bộ hợp đồng ($replayed bước)", replayed >= 120)
    }

    @Test
    fun a_cover_answer_carries_the_codec_numbers_and_the_clock() {
        val (status, reply) = call("PUT", "/cover", JSONObject().put("image", dataUrl()))
        assertEquals(200, status)
        val cover = (reply as JSONObject).getJSONObject("cover")
        assertEquals("#aa5522", cover.getString("color"))
        assertEquals(96, cover.getInt("width"))
        assertEquals(128, cover.getInt("height"))
        assertEquals(1_790_950_256L, cover.getLong("version"))
        assertTrue(File(dir, "edits/cover.jpg").isFile)
        assertEquals(File(dir, "edits/cover.jpg").canonicalPath, Store.coverFile(id)!!.canonicalPath)
        assertEquals("edits/cover.jpg", Store.manifest(id)!!.getJSONObject("cover").getString("file"))
    }

    @Test
    fun bad_cover_uploads_are_refused_with_the_server_words() {
        fun refused(image: String): String {
            val (status, reply) = call("PUT", "/cover", JSONObject().put("image", image))
            assertEquals(400, status)
            return (reply as JSONObject).getString("error")
        }
        assertEquals("Chỉ nhận ảnh PNG, JPEG, WebP, GIF hoặc BMP", refused("data:text/plain;base64,AAAA"))
        assertEquals("Chỉ nhận ảnh PNG, JPEG, WebP, GIF hoặc BMP", refused(""))
        assertEquals("Dữ liệu ảnh bị hỏng", refused("data:image/png;base64,AAA"))
        assertEquals("Dữ liệu ảnh bị hỏng", refused("data:image/png;base64,A=AA"))
        assertEquals("Không đọc được ảnh này", refused("data:image/png;base64,AAAA"))
        val big = "data:image/jpeg;base64," + Base64.getEncoder().encodeToString(ByteArray(Covers.MAX_UPLOAD_BYTES + 1) { 1 })
        assertEquals("Ảnh quá lớn (tối đa 16 MB)", refused(big))
        assertFalse("không có gì được ghi", File(dir, "edits.json").exists())
        // ảnh tải từ địa chỉ mạng chỉ có trên máy tính
        assertEquals(400, call("PUT", "/cover", JSONObject().put("url", "https://x/y.jpg")).first)
    }

    @Test
    fun a_data_url_decodes_like_python() {
        assertEquals(listOf<Byte>(0, 0, 0), Covers.decodeDataUrl("data:image/png;base64,AAAA").toList())
        assertEquals("tách dòng và khoảng trắng", 3, Covers.decodeDataUrl("  data:image/PNG;base64,AA\n AA \n").size)
        assertEquals(2, Covers.decodeDataUrl("data:image/webp;base64,AAA=").size)
        assertEquals(1, Covers.decodeDataUrl("data:image/gif;base64,AA==").size)
        assertNull(Covers.base64("AA=A"))
        assertNull(Covers.base64("AAA===")) // dài không chia hết cho 4... hay quá nhiều dấu =
        assertNull(Covers.base64("AA!A"))
    }

    @Test
    fun unknown_routes_books_and_link_books_get_the_servers_answers() {
        assertEquals(404 to "Không có đường dẫn này", call("GET", "/nothing").let { it.first to (it.second as JSONObject).getString("error") })
        assertEquals(404 to "Không có đường dẫn này", call("PATCH", "/title").let { it.first to (it.second as JSONObject).getString("error") })
        assertEquals(404, LocalStudio.handle("GET", "/api/other/$id/edits", null).first)
        val missing = LocalStudio.handle("GET", "/api/books/f-nope/edits", null)
        assertEquals(404, missing.first)
        assertEquals("Không tìm thấy sách này trong thư viện", (missing.second as JSONObject).getString("error"))
        // đường lạ thắng cuốn lạ, như bảng đường của máy chủ
        assertEquals("Không có đường dẫn này", (LocalStudio.handle("GET", "/api/books/f-nope/zzz", null).second as JSONObject).getString("error"))
        assertEquals(404, call("GET", "/chapters/9/script").first)
        assertEquals("Không có chương này", (call("GET", "/chapters/9/script").second as JSONObject).getString("error"))

        // cuốn của máy tính (không đăng ký là mở từ file): sửa ở máy ấy
        val link = "0123456789abcdef01234568"
        BookEditsFixtures.copyBase(Store.bookDir(link))
        for ((method, suffix) in listOf("GET" to "/edits", "PUT" to "/title", "PUT" to "/music", "GET" to "/cast", "DELETE" to "/cover")) {
            val (status, reply) = LocalStudio.handle(method, "/api/books/$link$suffix", JSONObject().put("title", "x"))
            assertEquals("$method $suffix", 409, status)
            assertEquals("Sách này lấy từ máy tính khác - muốn sửa thì sửa ở máy ấy", (reply as JSONObject).getString("error"))
        }
        assertFalse(File(Store.bookDir(link), "edits.json").exists())
        // cuốn của thiết bị ghép khác (gói mang `source`): cũng không phải của mình để sửa
        val peer = "p0123456789abcdef_x"
        BookEditsFixtures.copyBase(Store.bookDir(peer))
        File(Store.bookDir(peer), "book.json").writeText(JSONObject(File(Store.bookDir(peer), "book.json").readText()).put("source", "k1").toString())
        assertEquals(409, LocalStudio.handle("GET", "/api/books/$peer/edits", null).first)
        // cuốn nghe thẳng chưa tải (chỉ có stream.json): cũng 409 với đúng câu ấy, không phải 404
        val streamed = "s0123456789abcdef_y"
        Store.bookDir(streamed).mkdirs()
        File(Store.bookDir(streamed), "stream.json").writeText(JSONObject().put("title", "Từ máy tính").toString())
        val (streamStatus, streamReply) = LocalStudio.handle("PUT", "/api/books/$streamed/title", JSONObject().put("title", "x"))
        assertEquals(409, streamStatus)
        assertEquals("Sách này lấy từ máy tính khác - muốn sửa thì sửa ở máy ấy", (streamReply as JSONObject).getString("error"))
    }

    @Test
    fun repeated_edits_leave_the_edits_file_minimal() {
        fun edits() = if (File(dir, "edits.json").isFile) BookEdits.load(dir) else null
        // đổi tên rồi trả về tên sách: không còn gì
        call("PUT", "/title", JSONObject().put("title", "Tên khác"))
        assertEquals(1, BookEdits.count(edits()!!))
        call("PUT", "/title", JSONObject().put("title", "Sách thử · Tập 1"))
        assertNull("không còn thay đổi nào thì xoá cả file", edits())
        // nhân vật: đặt rồi trả về tên hiện của sách
        call("POST", "/characters/rename", JSONObject().put("character", "LUCIEN").put("name", "Lu"))
        call("POST", "/characters/rename", JSONObject().put("character", "LUCIEN").put("name", "Lucien"))
        assertNull(edits())
        // chương: tiêu đề bằng tiêu đề gốc không được lưu; tên phụ ghi đè rồi bỏ
        call("PUT", "/chapters/1/title", JSONObject().put("title", "Chương 646").put("subtitle", "Mới"))
        assertEquals("Mới", edits()!!.getJSONObject("chapters").getJSONObject("1").getString("subtitle"))
        assertFalse(edits()!!.getJSONObject("chapters").getJSONObject("1").has("title"))
        call("PUT", "/chapters/1/title", JSONObject().put("revert", true))
        assertNull(edits())
        // nhạc: bật lại, mức bằng mức gốc, bỏ im lặng - không lưu gì; ba lần sửa liên tiếp ra đúng một file nhỏ
        call("PUT", "/music", JSONObject().put("enabled", true).put("levelDb", -18))
        assertNull(edits())
        call("PUT", "/music", JSONObject().put("enabled", false))
        call("PUT", "/music", JSONObject().put("levelDb", -30))
        call("PUT", "/music", JSONObject().put("silence", JSONObject().put("1:0", true).put("1:60000", true)))
        val stored = edits()!!.getJSONObject("music")
        assertFalse("true không bao giờ được lưu", stored.optBoolean("enabled", true))
        assertEquals(-30.0, stored.getDouble("levelDb"), 0.0)
        assertEquals(2, stored.getJSONArray("silenced").length())
        assertEquals(4, BookEdits.count(edits()!!))
        call("DELETE", "/edits")
        assertNull(edits())
        assertFalse(File(dir, "edits/cover.jpg").exists())
    }

    @Test
    fun a_cover_removed_stays_removed_until_a_new_one_is_chosen() {
        call("DELETE", "/cover")
        assertNull("bìa đã bỏ: sách vẽ bìa từ tên", Store.coverFile(id))
        assertTrue(Store.manifest(id)!!.isNull("cover"))
        assertTrue(File(dir, "cover.jpg").isFile) // lớp sách không bị đụng tới
        call("PUT", "/cover", JSONObject().put("image", dataUrl()))
        assertNotNull(Store.coverFile(id))
        call("DELETE", "/cover")
        assertFalse("bìa sửa bị xoá cùng", File(dir, "edits/cover.jpg").exists())
        call("DELETE", "/edits")
        assertEquals(File(dir, "cover.jpg").canonicalPath, Store.coverFile(id)!!.canonicalPath)
    }

    @Test
    fun the_library_sees_the_edited_book_with_its_capabilities() {
        val before = Store.manifest(id)!!
        assertEquals("Sách thử · Tập 1", before.getString("title"))
        assertEquals(0, before.getInt("edits"))
        assertEquals(false, before.getJSONObject("capabilities").getBoolean("link"))
        assertEquals(false, before.getJSONObject("capabilities").getBoolean("toolchain"))
        assertEquals(false, before.getJSONObject("capabilities").getBoolean("workshop"))
        call("PUT", "/title", JSONObject().put("title", "Tên của tôi"))
        call("PUT", "/chapters/2/title", JSONObject().put("subtitle", "Hết rồi"))
        val shown = Store.manifest(id)!!
        assertEquals("Tên của tôi", shown.getString("title"))
        assertEquals(2, shown.getInt("edits"))
        assertEquals("Chương 647 · Hết rồi", shown.getJSONArray("chapters").getJSONObject(1).getString("fullTitle"))
        assertTrue(Store.books().any { it.getString("title") == "Tên của tôi" })
        assertTrue(Store.playableBooks().any { it.getString("title") == "Tên của tôi" })
        assertEquals("Tên của tôi", Store.playableManifest(id)!!.getString("title"))
        // lớp sách nguyên văn vẫn ở đó
        assertEquals("Sách thử · Tập 1", Store.rawManifest(id)!!.getString("title"))
        assertFalse(Store.rawManifest(id)!!.has("edits"))
        assertFalse(Store.rawManifest(id)!!.has("capabilities"))
    }

    @Test
    fun the_reader_gets_the_overlaid_cast_and_script_text() {
        call("POST", "/characters/rename", JSONObject().put("character", "LUCIEN").put("name", "Lu-xi-en"))
        call("PUT", "/chapters/1/title", JSONObject().put("title", "Chương Một"))
        val cast = JSONObject(Store.readText(id, "cast.json")!!)
        val lucien = (0 until cast.getJSONArray("characters").length()).map { cast.getJSONArray("characters").getJSONObject(it) }
            .first { it.getString("name") == "LUCIEN" }
        assertEquals("Lu-xi-en", lucien.getString("displayName"))
        assertEquals("Lucien", lucien.getString("originalName"))
        assertEquals("Chương Một", lucien.getString("firstChapter"))
        val script = JSONObject(Store.readText(id, "scripts/1.json")!!)
        assertEquals("Chương Một · Trở về (1)", script.getString("title"))
        assertEquals("Lu-xi-en", script.getJSONArray("segments").getJSONObject(2).getString("speaker"))
        // file khác và file không có: nguyên văn / null
        assertNull(Store.overlaidText(id, "samples/3.wav"))
        assertNull(Store.readText(id, "scripts/99.json"))
        // trả về như cũ thì đọc đúng file nguyên văn
        call("DELETE", "/edits")
        assertNull(Store.overlaidText(id, "cast.json"))
    }

    @Test
    fun the_phone_never_pretends_to_have_a_studio() {
        assertEquals(false, Store.capabilities(false).getBoolean("toolchain"))
        assertEquals(false, Store.capabilities(true).getBoolean("workshop"))
        assertTrue(Store.capabilities(true).getBoolean("link"))
        assertTrue(Store.linked(JSONObject()).getJSONObject("capabilities").getBoolean("link"))
        assertEquals(0, Store.linked(JSONObject()).getInt("edits"))
    }
}
