package vn.abook.player

import java.io.File
import java.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertArrayEquals
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
        LocalStudio.musicStore = MusicStore(File(root, "music"), FakeTags)
        LocalStudio.clock = { 1_790_950_256L }
        // đồng hồ của ý muốn chạy từng bước: mỗi yêu cầu một dấu giờ riêng (rút đúng lần bấm theo `requestedAt`)
        var tick = 0
        LocalStudio.now = { 1_790_950_256.0 + (tick++) * 0.25 }
    }

    @After
    fun tearDown() {
        LocalStudio.coverCodec = null
        LocalStudio.musicStore = null
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
            // mỗi ca bắt đầu từ cuốn sạch, kho "Nhạc của tôi" trống
            BookEdits.clear(dir)
            LocalStudio.musicStore = MusicStore(File(root, "music-$name"), FakeTags)
            val case = BookEditsFixtures.obj("contract/$name.json")
            val volatile = case.getJSONArray("volatile").let { list -> (0 until list.length()).map { list.getString(it) }.toSet() }
            val steps = case.getJSONArray("steps")
            val answers = ArrayList<Any?>()
            for (index in 0 until steps.length()) {
                val step = steps.getJSONObject(index)
                if (step.has("import")) { // nhập một bài mẫu vào kho (bên Python: app.my_music.import_file)
                    LocalStudio.musicStore!!.importFile(BookEditsFixtures.file("track/${step.getString("import")}"))
                    answers.add(null)
                    continue
                }
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

    private val tone get() = BookEditsFixtures.file("track/tone.wav")
    private val toneLink = "local:" + java.security.MessageDigest.getInstance("SHA-1").digest(tone.readBytes()).joinToString("") { "%02x".format(it) }

    @Test
    fun my_music_is_listed_and_removed_with_the_servers_words() {
        val store = LocalStudio.musicStore!!
        assertEquals(JSONObject().put("tracks", JSONArray()).put("analyzer", false).toString(),
            (LocalStudio.handle("GET", "/api/music/local", null).second as JSONObject).toString())
        val (track, duplicate) = store.importFile(tone)
        assertFalse(duplicate)
        assertEquals(toneLink, track.getString("link"))
        val (status, view) = LocalStudio.handle("GET", "/api/music/local", null)
        assertEquals(200, status)
        val listed = (view as JSONObject).getJSONArray("tracks").getJSONObject(0)
        assertEquals("tone", listed.getString("title"))
        assertEquals("local", listed.getString("source"))
        assertEquals(1, listed.getInt("duration"))
        assertFalse(listed.getBoolean("analysed"))
        // máy chưa có bộ phân tích: nói rõ, không bịa số
        val (conflict, refusal) = LocalStudio.handle("POST", "/api/music/local/analyze", null)
        assertEquals(409, conflict)
        assertEquals("Chưa có bộ phân tích âm thanh - bài nhập vào vẫn ghim tay được, nhưng máy chưa tự chọn chúng.", (refusal as JSONObject).getString("error"))
        val digest = toneLink.removePrefix("local:")
        assertEquals(404, LocalStudio.handle("DELETE", "/api/music/local/${"0".repeat(40)}", null).first)
        val (removed, after) = LocalStudio.handle("DELETE", "/api/music/local/$digest", null)
        assertEquals(200, removed)
        assertEquals(0, (after as JSONObject).getJSONArray("tracks").length())
        assertEquals("Bài này không còn trong Nhạc của tôi", (LocalStudio.handle("DELETE", "/api/music/local/$digest", null).second as JSONObject).getString("error"))
        assertEquals(404, LocalStudio.handle("PUT", "/api/music/local", null).first)
    }

    @Test
    fun an_analyzer_that_gives_numbers_makes_the_track_analysed_and_one_that_fails_does_not() {
        val store = LocalStudio.musicStore!!
        store.importFile(tone)
        store.analyzer = { null }
        assertEquals("bộ phân tích không ra gì dùng được: vẫn chưa phân tích", 0, store.analyzePending())
        store.analyzer = { throw IllegalStateException("model lỗi") }
        assertEquals(0, store.analyzePending())
        store.analyzer = { JSONObject().put("valence", 3.0).put("arousal", -0.25).put("fitsUnderNarration", 0.8).put("family", "nope") }
        val (status, reply) = LocalStudio.handle("POST", "/api/music/local/analyze", null)
        assertEquals(200, status)
        assertEquals(1, (reply as JSONObject).getInt("analysed"))
        val track = reply.getJSONArray("tracks").getJSONObject(0)
        assertTrue(track.getBoolean("analysed"))
        assertEquals("kẹp -1..1", 1.0, track.getDouble("valence"), 0.0)
        assertEquals(0.8, track.getDouble("background"), 0.0)
        assertFalse("họ nhạc lạ bị bỏ", track.has("family"))
        assertNull(MusicStore.cleanAnalysis(JSONObject().put("valence", 0.2)))
    }

    @Test
    fun pinning_one_of_my_tracks_copies_its_file_into_the_book_and_the_player_gets_it() {
        val store = LocalStudio.musicStore!!
        store.importFile(tone)
        val name = "music/${toneLink.removePrefix("local:")}.wav"
        val (status, view) = call("PUT", "/music", JSONObject().put("pins", JSONObject().put("1:0", toneLink)))
        assertEquals(200, status)
        assertTrue((view as JSONObject).getJSONArray("cues").getJSONObject(0).getBoolean("pinned"))
        assertArrayEquals(tone.readBytes(), File(dir, name).readBytes())
        val music = Store.manifest(id)!!.getJSONObject("music")
        val cue = music.getJSONObject("chapters").getJSONArray("1").getJSONObject(0)
        assertEquals(name, cue.getString("track"))
        assertEquals(toneLink, music.getJSONObject("tracks").getJSONObject(name).getString("link"))
        assertTrue("cue có gainDb tính bằng công thức chung", cue.getDouble("gainDb") <= 0.0)
        assertEquals("tone", music.getJSONObject("tracks").getJSONObject(name).getString("title"))
        // lớp sách không bị đụng: file chỉ thêm vào, book.json nguyên
        assertFalse(Store.rawManifest(id)!!.getJSONObject("music").getJSONObject("tracks").has(name))
        assertEquals(1, BookEdits.count(BookEdits.load(dir)))
        // nhóm "Đổi bài" không còn đưa bài đang dùng ở đoạn này
        val alternatives = call("GET", "/music/scenes/1:0/alternatives").second as JSONObject
        assertEquals(0, alternatives.getJSONArray("mine").length())
        assertEquals(1, (call("GET", "/music/scenes/1:60000/alternatives").second as JSONObject).getJSONArray("mine").length())
        // giao diện gửi khoá mốc đã mã hoá URL ("1%3A60000"): máy chủ Python giải mã, lõi native cũng phải giải mã
        assertEquals(1, (call("GET", "/music/scenes/1%3A60000/alternatives").second as JSONObject).getJSONArray("mine").length())
        // xoá bài khỏi kho: sách vẫn giữ bản của nó
        store.remove(toneLink.removePrefix("local:"))
        assertTrue(File(dir, name).isFile)
        // bỏ ghim: file bài đi theo
        call("PUT", "/music", JSONObject().put("pins", JSONObject().put("1:0", JSONObject.NULL)))
        assertFalse(File(dir, name).exists())
        assertFalse(File(dir, "edits.json").exists())
    }

    @Test
    fun a_pin_that_does_not_fit_is_refused_with_a_sentence_and_changes_nothing() {
        LocalStudio.musicStore!!.importFile(tone)
        fun refused(body: JSONObject): String {
            val (status, reply) = call("PUT", "/music", body)
            assertEquals(body.toString(), 400, status)
            return (reply as JSONObject).getString("error")
        }
        assertEquals("Bài này không còn trong Nhạc của tôi", refused(JSONObject().put("pins", JSONObject().put("1:0", "local:" + "0".repeat(40)))))
        assertEquals("Chỉ đổi được sang bài trong Nhạc của tôi", refused(JSONObject().put("pins", JSONObject().put("1:0", "https://x/y.mp3"))))
        assertEquals("Không có đoạn nhạc này trong sách", refused(JSONObject().put("pins", JSONObject().put("7:7", toneLink))))
        assertEquals("Phần sửa nhạc nền không hợp lệ.", refused(JSONObject().put("pins", "tone")))
        assertEquals("Sách đã đóng gói chỉ chỉnh được bật/tắt nhạc, mức nhạc, im lặng từng đoạn và đổi bài", refused(JSONObject().put("volume", 3)))
        assertFalse(File(dir, "edits.json").exists())
        assertFalse(File(dir, "music/${toneLink.removePrefix("local:")}.wav").exists())
    }

    @Test
    fun clearing_all_edits_drops_the_pinned_files_but_never_a_book_layer_file() {
        LocalStudio.musicStore!!.importFile(tone)
        val name = "music/${toneLink.removePrefix("local:")}.wav"
        call("PUT", "/music", JSONObject().put("pins", JSONObject().put("1:0", toneLink).put("1:60000", toneLink)))
        assertTrue(File(dir, name).isFile)
        assertEquals(2, BookEdits.count(BookEdits.load(dir)))
        call("DELETE", "/edits")
        assertFalse(File(dir, name).exists())
        val listed = Store.rawManifest(id)!!.getJSONObject("package").getJSONObject("files")
        for (file in listed.keys().asSequence()) assertTrue("$file vẫn còn", File(dir, file).isFile)
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

        // cuốn đã tải từ máy tính (không đăng ký là mở từ file): sửa được ở đây, phần sửa gửi về máy tính (EditsSync)
        val link = "0123456789abcdef01234568"
        BookEditsFixtures.copyBase(Store.bookDir(link))
        for ((method, suffix) in listOf("GET" to "/edits", "GET" to "/music", "GET" to "/cast")) {
            assertEquals("$method $suffix", 200, LocalStudio.handle(method, "/api/books/$link$suffix", null).first)
        }
        assertEquals(200, LocalStudio.handle("PUT", "/api/books/$link/title", JSONObject().put("title", "x")).first)
        assertTrue(File(Store.bookDir(link), "edits.json").exists())
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

    @Test
    fun the_workshop_views_of_a_project_file_are_answered_read_only_and_a_plain_book_says_there_are_none() {
        // cuốn từ file .abook (base): không có bản chụp nào
        for (path in listOf("/work", "/casting", "/pronunciations", "/casting/1")) assertEquals(path, 404, call("GET", path).first)
        // cuốn từ file dự án: bản chụp trong file, cùng JSON với Studio (tests/book_edits_fixtures.py WORKSHOP_VIEWS)
        val imported = BookFileImport.importFile(BookEditsFixtures.file("written/python_workshop.abookproj"))
        fun view(path: String) = LocalStudio.handle("GET", "/api/books/${imported.id}$path", null)
        val work = view("/work")
        assertEquals(200, work.first)
        assertEquals("name:Hailkes", ((work.second as JSONObject).getJSONArray("items")).getJSONObject(0).getString("id"))
        assertEquals(1, ((view("/casting").second as JSONObject).getJSONArray("chapters")).length())
        assertEquals("Hên-khơ", ((view("/pronunciations").second as JSONObject).getJSONArray("items")).getJSONObject(0).getString("spoken"))
        assertEquals("từng câu của chương không có trong file", 404, view("/casting/1").first)
        assertEquals("chỉ đọc: không ghi được", 404, LocalStudio.handle("POST", "/api/books/${imported.id}/work", JSONObject()).first)
    }
}
