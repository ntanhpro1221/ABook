package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject

/**
 * "Studio" nhẹ trên điện thoại: máy chủ giao diện của máy tính (abook/webui/server.py) trả lời `/api/books/<mã>/...` còn điện
 * thoại thì không có máy chủ - giao diện gọi `EbookLibrary.studio({method, path, body})` và nhận đúng JSON máy chủ sẽ trả
 * (docs/EDITING.md, bảng "Routes"). Phần L ("áp ngay", không cần Studio) cho cuốn mở từ file `.abook`: đổi tên sách, bìa, tên
 * nhân vật, tên chương, nhạc nền, xem/bỏ thay đổi; và phần W (ý muốn chờ Studio - [BookWishes]): cách đọc tên (kèm số câu nó chạm tới), ai nói câu này,
 * gộp tên, cách đọc câu, giọng/giới, thu lại, danh sách chờ và rút. Cộng "Nhạc của tôi" ([MusicStore], docs/MUSIC_IMPORT.md): danh
 * sách bài đã nhập, xoá, và - cho từng cuốn - nhóm bài của tôi trong "Đổi bài" + ghim một bài vào một đoạn nhạc (`PUT /music {pins}`).
 * Cộng "Tìm bìa trên mạng" ([CoverSearch]): `GET /cover/search?q=` và `PUT /cover {url}`. Mọi thứ khác: 404. Sửa được MỌI cuốn trên máy, kể cả
 * cuốn nghe thẳng chưa tải và cuốn của thiết bị ghép khác: lớp sửa nằm cạnh gói sách của nó; về máy giữ sách (máy tính) hay chỉ ở lại máy này
 * là việc của [Store.editDestination] và [EditsSync] - không bao giờ chặn.
 *
 * Lời đáp phải y hệt bản Python (tests/fixtures/book_edits/contract/ - LocalStudioTest phát lại từng bước), nên câu báo lỗi
 * và mã trạng thái theo đúng server.py: sửa sai (ValueError bên Python) là 400.
 */
object LocalStudio {
    private class Api(val status: Int, message: String, val extra: JSONObject? = null) : Exception(message)

    private val ROUTE = Regex("/api/books/([A-Za-z0-9_-]+)(/[^?#]*)?")
    private val CHAPTER_TITLE = Regex("/chapters/([0-9]+)/title")
    private val CHAPTER_SCRIPT = Regex("/chapters/([0-9]+)/script")
    private val CHAPTER_RETAKE = Regex("/chapters/([0-9]+)/retake")
    private val CASTING_CHAPTER = Regex("/casting/([0-9]+)")
    private val SCENE_ALTERNATIVES = Regex("/music/scenes/([^/]+)/alternatives")
    private val MY_MUSIC = Regex("/api/music/local(?:/([0-9a-f]{40})|/(analyze)|/(module)|/(reanalyse)|/(module/cancel))?")
    private val EDITS_ONLY_KEYS = setOf("enabled", "levelDb", "silence", "pins", "playlist")
    private val lock = Any()

    /** Kho "Nhạc của tôi" của điện thoại này ([AppStartup] đặt lúc dậy; test JVM đặt kho trong thư mục tạm). */
    @Volatile
    var musicStore: MusicStore? = null

    /** Danh mục nhạc nền (danh sách phát cho "Nghe ngay" - [Playlists]); [AppStartup] đặt lúc dậy, test JVM đặt danh mục trong thư mục tạm. */
    @Volatile
    var catalog: MusicCatalog? = null

    /** Mô-đun "Phân tích nhạc" (model + thư viện ONNX Runtime; điện thoại tải khi người dùng bấm - MusicStudentSetup). Null: không có việc tải (test JVM); view không kèm `module`. */
    @Volatile
    var student: MusicStudentSetup? = null

    /** Bộ chuẩn hoá ảnh bìa: máy thật dùng [AndroidCoverCodec]; test JVM đặt bản giả. */
    @Volatile
    var coverCodec: CoverCodec? = null

    /** Đồng hồ (giây, số thực) - dấu giờ của một ý muốn (`requestedAt`); test đặt đồng hồ chạy từng bước. Gọi ĐÚNG MỘT LẦN cho mỗi yêu cầu. */
    @Volatile
    var now: () -> Double = { System.currentTimeMillis() / 1000.0 }

    fun handle(method: String, path: String, body: JSONObject?): Pair<Int, Any?> = try {
        run(method.uppercase(), path, body ?: JSONObject())
    } catch (error: Api) {
        error.status to fail(error.message.orEmpty(), error.extra)
    } catch (error: BookEdits.EditsError) {
        400 to fail(error.message.orEmpty())
    }

    private fun fail(message: String, extra: JSONObject? = null): JSONObject = JSONObject().put("error", message).also { out ->
        extra?.keys()?.forEach { out.put(it, extra.opt(it)) }
    }

    /** `my_music_view` của server.py: danh sách bài đã nhập + có bộ phân tích âm thanh chưa. */
    fun musicView(): JSONObject {
        val store = musicStore ?: throw Api(404, S.s_khong_co_duong_dan_nay_9da2ede3)
        val view = JSONObject().put("tracks", JSONArray(store.entries())).put("analyzer", store.analyzerAvailable())
        // Mô-đun "Phân tích nhạc" (model + thư viện ONNX Runtime): tải một lần khi người dùng bấm, cùng hình `module` với máy tính.
        student?.let { view.put("module", it.status()) }
        return view
    }

    /** `music_playlists` của server.py: menu "Nhạc nền" của sách chỉ có chữ - các danh sách phát của danh mục + số bài trong "Nhạc của
     *  tôi". Chưa tải được danh mục (mất mạng lần đầu) thì không danh sách nào, kèm lý do. Cần mạng: chạy ngoài khoá. */
    fun playlistsView(): JSONObject {
        var error = ""
        val playlists = try {
            Playlists.summaries(catalog?.playlists() ?: emptyList())
        } catch (problem: MusicCatalog.CatalogError) {
            error = problem.message.orEmpty()
            JSONArray()
        }
        // `scene`: máy dựng được nhạc theo cảnh (menu hiện dòng "Theo cảnh"), như máy tính.
        return JSONObject().put("playlists", playlists).put("mine", musicStore?.entries()?.size ?: 0).put("error", error)
            .put("scene", JSONObject())
    }

    /** Lời đáp của một lượt nhập (`my_music_import` của server.py): bài mới, bài đã có, file lỗi kèm lý do, cộng danh sách mới. */
    fun importAnswer(added: List<JSONObject>, existing: List<JSONObject>, failed: List<String>): JSONObject =
        JSONObject().put("added", JSONArray(added)).put("existing", JSONArray(existing)).put("failed", JSONArray(failed)).also { out ->
            val view = musicView()
            for (key in listOf("tracks", "analyzer", "module")) out.put(key, view.opt(key))
        }

    /** `/api/music/local...`: kho nhạc của máy, không thuộc cuốn nào. Nhập file đi qua hộp chọn file của hệ thống. */
    private fun myMusic(method: String, digest: String?, analyze: Boolean, download: Boolean, reanalyse: Boolean, cancel: Boolean): Pair<Int, Any?> {
        val store = musicStore ?: throw Api(404, S.s_khong_co_duong_dan_nay_9da2ede3)
        return when {
            method == "POST" && download -> {
                // Người dùng bấm "Tải bộ phân tích": chạy ở luồng riêng, giao diện hỏi lại view để thấy tiến độ.
                (student ?: throw Api(404, S.s_khong_co_duong_dan_nay_9da2ede3)).start()
                200 to musicView()
            }
            method == "POST" && cancel -> {
                // Người dùng bấm Huỷ khi đang tải: dừng ở nhịp đọc kế, phần đã tải giữ để lần sau làm tiếp.
                (student ?: throw Api(404, S.s_khong_co_duong_dan_nay_9da2ede3)).cancel()
                200 to musicView()
            }
            method == "POST" && reanalyse -> {
                // Người dùng bấm "Phân tích lại N bài bằng bản mới" sau khi cập nhật Phân tích nhạc: không bao giờ tự chạy.
                if (!store.analyzerAvailable()) throw Api(409, MusicStore.NO_ANALYZER)
                (student ?: throw Api(404, S.s_khong_co_duong_dan_nay_9da2ede3)).reanalyse()
                200 to musicView()
            }
            method == "GET" && digest == null && !analyze -> 200 to musicView()
            method == "DELETE" && digest != null -> {
                if (!store.remove(digest)) throw Api(404, S.s_bai_nay_khong_con_trong_nhac_cua_toi_07833cb0)
                Playback.onMain { MusicBed.refreshMine() }
                200 to musicView()
            }
            method == "POST" && analyze -> {
                if (!store.analyzerAvailable()) throw Api(409, MusicStore.NO_ANALYZER)
                val done = store.analyzePending()
                200 to musicView().put("analysed", done)
            }
            else -> throw Api(404, S.s_khong_co_duong_dan_nay_9da2ede3)
        }
    }

    private fun run(method: String, rawPath: String, body: JSONObject): Pair<Int, Any?> {
        val path = rawPath.substringBefore('?') // tham số của GET do giao diện gửi trong `body` (android/localStudio.ts)
        if (method == "GET" && path == "/api/music/playlists") return 200 to playlistsView()
        MY_MUSIC.matchEntire(path)?.let { return myMusic(method, it.groups[1]?.value, it.groups[2] != null, it.groups[3] != null, it.groups[4] != null, it.groups[5] != null) }
        val match = ROUTE.matchEntire(path) ?: throw Api(404, S.s_khong_co_duong_dan_nay_9da2ede3)
        val id = match.groupValues[1]
        val rest = match.groupValues[2]
        // Hai đường cần MẠNG (tìm bìa, tải bìa đã chọn) chạy ngoài khoá: vài giây chờ nguồn ảnh không được chặn các lần sửa khác.
        if (method == "GET" && rest == "/cover/search") {
            editable(id)
            return 200 to CoverSearch.search(BookEdits.pyText(body.opt("q")))
        }
        if (method == "PUT" && rest == "/cover" && BookEdits.truthy(body.opt("url"))) {
            val dir = editable(id)
            val raw = try {
                CoverSearch.downloadImage(BookEdits.pyStr(body.opt("url")))
            } catch (error: CoverCodec.CoverError) {
                throw BookEdits.EditsError(error.message.orEmpty())
            }
            return synchronized(lock) { 200 to setCover(dir, raw) }
        }
        val handler = route(method, rest) ?: throw Api(404, S.s_khong_co_duong_dan_nay_9da2ede3)
        val dir = editable(id)
        // Mỗi cuốn một lần sửa một lúc: đọc-sửa-ghi của hai yêu cầu không được chen nhau.
        return synchronized(lock) { 200 to handler(dir, body) }
    }

    /** Thư mục cuốn mà người nghe sửa được: mọi cuốn trên máy (đã tải, mở từ file, hay nghe thẳng chỉ có `stream.json`); không có thì 404. */
    private fun editable(id: String): java.io.File {
        if (Store.rawManifest(id) == null && Store.streamManifest(id) == null) throw Api(404, S.s_khong_tim_thay_sach_nay_trong_thu_vien_74a995af)
        return Store.bookDir(id)
    }

    private fun route(method: String, path: String): ((java.io.File, JSONObject) -> Any?)? {
        CHAPTER_TITLE.matchEntire(path)?.takeIf { method == "PUT" }?.let { match -> return { dir, body -> chapterTitle(dir, match.groupValues[1], body) } }
        CHAPTER_SCRIPT.matchEntire(path)?.takeIf { method == "GET" }?.let { match -> return { dir, _ -> script(dir, match.groupValues[1]) } }
        CHAPTER_RETAKE.matchEntire(path)?.takeIf { method == "POST" }?.let { match -> return { dir, _ -> chapterRetake(dir, match.groupValues[1]) } }
        CASTING_CHAPTER.matchEntire(path)?.takeIf { method == "GET" }?.let {
            return { _, _ -> throw Api(404, S.s_file_du_an_khong_kem_tung_cau_cua_chuong_d_d856bdf2) }
        }
        SCENE_ALTERNATIVES.matchEntire(path)?.takeIf { method == "GET" }?.let { match -> return { dir, _ -> alternatives(dir, java.net.URLDecoder.decode(match.groupValues[1], "UTF-8")) } }
        return when (method to path) {
            "PUT" to "/title" -> ::title
            "PUT" to "/author" -> ::author
            "PUT" to "/cover" -> ::cover
            "DELETE" to "/cover" -> { dir, _ -> BookEdits.removeCover(dir); JSONObject().put("cover", JSONObject.NULL) }
            "POST" to "/characters/rename" -> ::renameCharacter
            "GET" to "/music" -> { dir, _ -> withAutoPlaylist(dir, BookEdits.musicView(BookEdits.rawBook(dir), BookEdits.load(dir))) }
            "GET" to "/suggestions" -> { dir, _ -> suggestions(dir) }
            "PUT" to "/skip" -> { dir, body -> skipLine(dir, body) }
            "GET" to "/readings" -> { dir, _ -> BookEdits.readingsView(EditsSync.experienced(dir)) }
            "PUT" to "/readings" -> ::reading
            "PUT" to "/music" -> ::music
            "GET" to "/edits" -> { dir, _ ->
                val edits = BookEdits.load(dir)
                JSONObject().put("applied", BookEdits.countApplied(edits)).put("waiting", 0).put("wishes", BookEdits.countWishes(edits))
            }
            "GET" to "/pending-changes" -> { dir, _ -> BookWishes.pendingDetails(dir, BookEdits.rawBook(dir), BookEdits.load(dir).optJSONObject("wishes")) }
            "GET" to "/wishes" -> { dir, _ -> withHolderSpeakers(dir, BookWishes.byLine(dir, BookEdits.rawBook(dir), BookEdits.load(dir).optJSONObject("wishes"))) }
            "POST" to "/pending-changes/withdraw" -> ::pendingWithdraw
            "POST" to "/characters/merge" -> ::mergeCharacters
            "POST" to "/pronunciation" -> ::pronunciation
            "POST" to "/pronunciation/check" -> ::pronunciationCheck
            "GET" to "/pronunciations/reach" -> ::readingReach
            "POST" to "/speaker" -> ::speaker
            "POST" to "/line" -> ::line
            "POST" to "/voice" -> ::voice
            "POST" to "/review" -> ::review
            "DELETE" to "/edits" -> { dir, _ -> BookEdits.clear(dir); JSONObject().put("applied", 0).put("waiting", 0) }
            "GET" to "/cast" -> { dir, _ -> BookEdits.cast(dir, BookEdits.rawBook(dir)) }
            // Bản chụp chỉ đọc của xưởng trong file dự án (ProjectDocument.view, project_views.py): cùng JSON với đường của Studio.
            "GET" to "/work" -> { dir, _ -> projectView(dir, "work") }
            "GET" to "/casting" -> { dir, _ -> projectView(dir, "casting") }
            "GET" to "/narrator-mode" -> { dir, _ -> narratorMode(dir) }
            "GET" to "/pronunciations" -> { dir, _ -> projectView(dir, "names") }
            else -> null
        }
    }

    /** PUT /title {title}: `App.rename` - làm sạch như `store.clean_title` rồi lớp sửa ghi lại (NFC) hay bỏ khi đúng tên sách. */
    private fun title(dir: java.io.File, body: JSONObject): Any? {
        val cleaned = BookEdits.cleanText(BookEdits.pyText(body.opt("title")), BookEdits.TITLE_MAX, normalize = false)
        if (cleaned.isEmpty()) throw BookEdits.EditsError(S.s_ten_sach_khong_duoc_de_trong_5c7b1ef8)
        return JSONObject().put("title", BookEdits.setTitle(dir, cleaned))
    }

    /** PUT /author {author}: tác giả người nghe đặt (lớp sửa); tên trống là "không rõ tác giả" (book_edits.set_author). */
    private fun author(dir: java.io.File, body: JSONObject): Any? = JSONObject().put("author", BookEdits.setAuthor(dir, BookEdits.pyText(body.opt("author"))))

    /**
     * PUT /cover {image: data URL} (hay {url} - ảnh chọn từ "Tìm bìa trên mạng", tải ở [run] qua [CoverSearch]): bìa người nghe đặt
     * nằm ở edits/cover.jpg, bìa của sách giữ nguyên.
     */
    private fun cover(dir: java.io.File, body: JSONObject): Any? {
        val raw = try {
            Covers.decodeDataUrl(BookEdits.pyText(body.opt("image")))
        } catch (error: CoverCodec.CoverError) {
            throw BookEdits.EditsError(error.message.orEmpty())
        }
        return setCover(dir, raw)
    }

    private fun setCover(dir: java.io.File, raw: ByteArray): JSONObject {
        val codec = coverCodec ?: AndroidCoverCodec
        return JSONObject().put("cover", BookEdits.setCover(dir, raw, codec))
    }

    /** POST /characters/rename {character, name}. */
    private fun renameCharacter(dir: java.io.File, body: JSONObject): Any? {
        val character = BookEdits.pyStrip(BookEdits.pyStr(if (body.has("character")) body.opt("character") else "")).let {
            if (it.codePointCount(0, it.length) > 200) it.substring(0, it.offsetByCodePoints(0, 200)) else it
        }
        if (character.isEmpty() || character.uppercase(java.util.Locale.ROOT) == "NARRATOR") throw BookEdits.EditsError(S.s_thieu_nhan_vat_1605a34d)
        // Tên gõ qua phép kiểm của máy tính (`_checked_name`): NFC, bỏ ký tự vô hình, báo khi quá dài / trùng người khác / tên dành riêng; rỗng = trở về tên gốc.
        val (_, _, cast) = fresh(dir)
        val mine = BookWishes.characterKey(character)
        val others = cast.filter { BookWishes.characterKey(it.getString("name")) != mine }.map { BookEdits.pyText(it.opt("displayName")).ifEmpty { it.getString("name") } }
        val name = typed { NameRules.person(body.opt("name") as? String ?: "", others, allowEmpty = true) }
        return BookEdits.setCharacterName(dir, character, name)
    }

    /** Chữ người gõ không qua phép kiểm của [NameRules] thì 400 kèm lời tiếng Việt (server `_typed`). */
    private fun <T> typed(block: () -> T): T =
        try {
            block()
        } catch (problem: NameRules.Problem) {
            throw Api(400, problem.message ?: "")
        }

    /** PUT /chapters/<n>/title {title?, subtitle?, revert?}. */
    private fun chapterTitle(dir: java.io.File, chapter: String, body: JSONObject): Any? {
        val revert = BookEdits.truthy(body.opt("revert"))
        val title = if (revert) null else body.opt("title")
        val subtitle = if (revert) null else body.opt("subtitle")
        fun text(value: Any?): String? = when {
            value == null || value === JSONObject.NULL -> null
            value is String -> value
            else -> throw BookEdits.EditsError(S.s_ten_chuong_phai_la_chu_5920fb22)
        }
        val (newTitle, newSubtitle) = text(title) to text(subtitle)
        return BookEdits.setChapterTitle(dir, chapter.toLongOrNull() ?: throw BookEdits.EditsError(S.s_khong_co_chuong_nay_trong_sach_11e1c7d3), newTitle, newSubtitle)
    }

    /**
     * GET /suggestions: gợi ý của bộ nhập sách cho cuốn chỉ-chữ (dòng ghi công ở đầu chương), kèm đang bỏ khỏi phần đọc hay chưa -
     * trang sách hiện những gợi ý còn chờ (`server.get_suggestions`).
     */
    private fun suggestions(dir: java.io.File): JSONObject {
        val out = JSONArray()
        val chapters = BookEdits.applyManifest(BookEdits.rawBook(dir), EditsSync.experienced(dir)).optJSONArray("chapters") ?: JSONArray()
        for (index in 0 until chapters.length()) {
            val chapter = chapters.optJSONObject(index) ?: continue
            val id = chapter.opt("id") as? Int ?: continue
            val entry = chapter.optString("text").takeIf { it.startsWith("texts/") } ?: continue
            val file = java.io.File(dir, entry).takeIf { it.isFile } ?: continue
            val skipped = chapter.optJSONArray("skip")?.let { array -> (0 until array.length()).map { array.getString(it) }.toSet() } ?: emptySet()
            for ((line, _) in BookImport.chapterCreditSuggestions(file.readText(Charsets.UTF_8))) {
                out.put(JSONObject().put("chapter", id).put("title", listOf(chapter.opt("fullTitle"), chapter.opt("title")).firstOrNull { BookEdits.truthy(it) }?.toString() ?: "")
                    .put("line", line).put("skipped", line in skipped))
            }
        }
        return JSONObject().put("suggestions", out)
    }

    /** PUT /readings {surface, spoken}: "Đọc từ này là…" - đặt (hay bỏ, `spoken` rỗng) cách đọc riêng của một từ cho cả cuốn; chỉ giọng đọc
     *  đổi, chữ của sách không đổi (`server.put_readings`). */
    private fun reading(dir: java.io.File, body: JSONObject): JSONObject {
        val surface = body.opt("surface")
        val spoken = if (body.has("spoken")) body.opt("spoken") else ""
        if (surface !is String || spoken !is String) throw BookEdits.EditsError(S.s_thieu_tu_hoac_cach_doc_e8396cca)
        BookEdits.setReading(dir, surface, spoken)
        vn.abook.player.readaloud.ReadAloud.readingsChanged(dir.name)
        return BookEdits.readingsView(EditsSync.experienced(dir))
    }

    /**
     * Speakers waiting for Studio that the holder set (or another device sent there - BookEdits.HOLDER_FILE) show on the sentence here too,
     * under the ones this phone set and has not sent yet (review a70: set on the computer, the phone never knew).
     */
    private fun withHolderSpeakers(dir: java.io.File, view: JSONObject): JSONObject {
        val theirs = BookEdits.holderEdits(dir)?.optJSONObject("speakers") ?: return view
        val lines = view.optJSONObject("lines") ?: JSONObject().also { view.put("lines", it) }
        for (stableId in theirs.keys()) {
            val line = lines.optJSONObject(stableId) ?: JSONObject().also { lines.put(stableId, it) }
            // `held`: already at the holder - changed by picking again here, not withdrawn like an unsent wish.
            if (!line.has("speaker")) theirs.optJSONObject(stableId)?.let { line.put("speaker", JSONObject(it.toString()).put("held", true)) }
        }
        return view
    }

    /** PUT /skip {line, chapters, skip}: người nghe chấp nhận (hay bỏ chấp nhận) một gợi ý - dòng bị bỏ khỏi phần đọc của các chương ấy,
     *  chữ không đổi (`server.put_skip_line`). */
    private fun skipLine(dir: java.io.File, body: JSONObject): JSONObject {
        val line = body.opt("line") as? String ?: throw BookEdits.EditsError(S.s_dong_can_bo_phai_la_chu_b5c011ca)
        val chapters = body.opt("chapters") as? JSONArray
        val ids = chapters?.let { array -> (0 until array.length()).map { array.opt(it) } }
        if (ids == null || ids.any { it !is Int && it !is Long }) throw BookEdits.EditsError(S.s_khong_co_chuong_nay_trong_sach_11e1c7d3)
        return JSONObject().put("skip", BookEdits.setSkipLine(dir, ids.map { (it as Number).toLong() }, line, body.opt("skip") != false))
    }

    /** GET /music của giao diện (ui/music): gọi thẳng, không qua chuỗi đường dẫn. */
    fun bookMusic(id: String): JSONObject = synchronized(lock) {
        val dir = editable(id)
        withAutoPlaylist(dir, BookEdits.musicView(BookEdits.rawBook(dir), BookEdits.load(dir)))
    }

    /** PUT /music của giao diện native; lỗi sửa ném [BookEdits.EditsError] (câu cho người nghe). */
    fun setBookMusic(id: String, body: JSONObject): JSONObject = synchronized(lock) { music(editable(id), body) }

    /** "Đổi bài" của một đoạn nhạc gắn sẵn (giao diện native): như GET /music/scenes/<khoá>/alternatives - các bài trong "Nhạc của tôi" trừ bài đang ở đoạn ấy. */
    fun musicAlternatives(id: String, key: String): JSONObject = synchronized(lock) {
        try {
            alternatives(editable(id), key) as JSONObject
        } catch (error: Api) {
            throw BookEdits.EditsError(error.message ?: S.s_khong_thay_doan_nhac_nay_trong_sach_cbf90189)
        }
    }

    /** PUT /music {enabled?, levelDb?, silence?, pins?, playlist?}: sách đã đóng gói chỉ chỉnh được năm thứ ấy (playlist: mã, "mine", "off" = tắt, null = để máy chọn). */
    private fun music(dir: java.io.File, body: JSONObject): JSONObject {
        if (body.keys().asSequence().any { it !in EDITS_ONLY_KEYS }) {
            throw BookEdits.EditsError(S.s_sach_dong_goi_chi_doi_duoc_bat_tat_muc_nha_5b4dae4f)
        }
        return withAutoPlaylist(dir, BookEdits.setMusic(dir, body, musicStore?.let { store -> { link: String -> store.track(link) } },
            musicStore?.let { store -> { store.entries().reversed().mapNotNull { info -> store.file(info.getString("link"))?.let { info to it } } } }))
    }

    /** `_with_auto_playlist` của server.py: màn "Nhạc nền" + nhạc theo cảnh mặc định - sách chưa có lựa chọn nào (`playlist` không có khoá) và không có
     *  nhạc của người làm sách thì `playlist` là "scene", kèm `playlistAuto` true. Đã chọn (kể cả "off") thì giữ nguyên. */
    private fun withAutoPlaylist(dir: java.io.File, view: JSONObject): JSONObject = withOfflineNotice(dir, withAutoChoice(dir, view))

    /** `error` của màn "Nhạc nền" như `_music_payload` của server.py: danh sách phát đang dùng mà có bài bị giữ lại vì mất mạng ([MusicCatalog.degraded])
     *  thì nói "mất mạng" (cùng chữ với máy tính) - nhạc đang kêu giữ nguyên, bài còn lại tải khi có mạng. Nhạc của người làm sách / đã tắt: không. */
    private fun withOfflineNotice(dir: java.io.File, view: JSONObject): JSONObject {
        val playlist = view.optString("playlist")
        if (playlist.isEmpty() || playlist == Playlists.OFF || playlist == Playlists.MINE || BookEdits.truthy(BookEdits.rawBook(dir).opt("music"))) return view
        val notice = catalog?.offlineNotice().orEmpty()
        return if (notice.isEmpty()) view else view.put("error", notice)
    }

    private fun withAutoChoice(dir: java.io.File, view: JSONObject): JSONObject {
        val book = BookEdits.rawBook(dir)
        if (view.has("playlist") || BookEdits.truthy(book.opt("music"))) return view
        // Chưa chọn gì ("Để máy chọn") và "Tự chọn nhạc nền" còn bật: máy dựng nhạc theo cảnh từ chữ (DeviceScenes) - `_with_auto_playlist` của server.py.
        if (Playlists.sceneMode(book, "", Playlists.autoEnabled)) return view.put("playlist", Playlists.SCENE).put("playlistAuto", true)
        return if (!Playlists.autoEnabled && Playlists.isTextBook(book)) view.put("autoOff", true) else view
    }

    /**
     * GET /music/scenes/<khoá mốc>/alternatives ("Đổi bài" của sách đóng gói, `_packaged_alternatives` của server.py): mốc nhạc người
     * làm sách gắn không có "không khí" để chấm điểm nên danh mục không đề xuất bài nào - chỉ có nhóm "Nhạc của tôi" (mọi bài đã nhập
     * trừ bài đang dùng ở mốc này; bài chưa phân tích đi sau bài đã phân tích).
     */
    private fun alternatives(dir: java.io.File, key: String): Any? {
        val book = BookEdits.rawBook(dir)
        val edits = BookEdits.load(dir)
        val cues = BookEdits.musicView(book, edits).getJSONArray("cues")
        if ((0 until cues.length()).none { cues.getJSONObject(it).getString("key") == key }) throw Api(404, S.s_khong_thay_doan_nhac_nay_trong_sach_cbf90189)
        val current = edits.optJSONObject("music")?.optJSONObject("pins")?.optString(key, "")?.ifEmpty { null } ?: BookEdits.baseLinks(book)[key]
        val items = (musicStore?.entries() ?: emptyList()).filter { it.getString("link") != current }.map { track ->
            JSONObject().put("link", track.getString("link")).put("title", track.getString("title")).put("creator", track.getString("creator"))
                .put("attribution", "").put("duration", track.get("duration")).put("analysed", track.getBoolean("analysed")).put("fits", false)
                // Như music_local.auto_keys: nhãn "Có vẻ có lời" ở "Đổi bài" giống ở Cài đặt (điện thoại không có công tắc `auto`).
                .also { item -> if (track.has("vocalsLikely")) item.put("vocalsLikely", track.get("vocalsLikely")) }
        }.sortedWith(compareBy({ it.getBoolean("analysed").not() }, { it.getString("title").lowercase() }))
        return JSONObject().put("key", key).put("alternatives", JSONArray()).put("mine", JSONArray(items))
    }

    // ---- ý muốn chờ Studio (docs/EDITING.md, P2a): từng đường theo đúng server.py, câu báo lỗi và mã trạng thái y hệt -------------

    private val PRONUNCIATION_PROBLEMS = mapOf(
        VietnameseReading.MULTI_WORD to S.s_chi_sua_duoc_cach_doc_cua_mot_tu_cach_doc_2369cd55,
        VietnameseReading.NOT_VIETNAMESE to S.s_cach_doc_phai_la_cac_am_tiet_tieng_viet_no_74ea3ba7,
    )
    private val LINE_PROBLEMS = mapOf(
        BookWishes.UNKNOWN_LINE to S.s_khong_con_cau_nay_trong_sach_2d609e4e,
        BookWishes.SOURCE_CHANGED to S.s_chu_cua_cau_nay_da_doi_tai_lai_chuong_a8666675,
        BookWishes.BAD_KIND to S.s_loai_doan_phai_la_loi_ke_loi_thoai_hay_noi_69b997f9,
        BookWishes.BAD_EMOTION to S.s_cam_xuc_nay_khong_co_trong_bo_giong_4e27fd3e,
        BookWishes.NOT_SPEECH to S.s_loi_ke_khong_co_nguoi_noi_doi_thanh_loi_th_fd8a4f85,
        BookWishes.NO_VOICE to S.s_nguoi_nay_chua_co_giong_trong_sach_chua_no_60892cd0,
        BookWishes.BAD_TEXT to S.s_chu_dem_doc_phai_co_chu_cai_khong_ky_tu_la_599ae6ba,
    )
    private val VOICE_PROBLEMS = mapOf(
        BookWishes.UNKNOWN_CHARACTER to S.s_khong_co_nhan_vat_nay_trong_sach_7f5f7050,
        BookWishes.NARRATOR_VOICE_ONLY to S.s_nguoi_ke_chi_doi_duoc_giong_khong_co_gioi_cdaa071d,
        BookWishes.NO_VOICE to S.s_nhan_vat_nay_chua_co_giong_chua_qua_buoc_p_728f8be5,
        BookWishes.BAD_GENDER to S.s_gioi_phai_la_nam_hoac_nu_bd1b754b,
    )
    private val SPEAKER_PROBLEMS = mapOf(
        BookWishes.UNKNOWN_LINE to S.s_khong_con_cau_nay_trong_sach_2d609e4e,
        BookWishes.SOURCE_CHANGED to S.s_chu_cua_cau_nay_da_doi_tu_luc_may_cham_tai_1b334526,
        BookWishes.NOT_SPEECH to S.s_cau_nay_la_loi_ke_khong_co_nguoi_noi_de_do_1d659a5d,
        BookWishes.NO_VOICE to S.s_nguoi_nay_chua_co_giong_trong_sach_chua_no_60892cd0,
    )
    private val NEW_GENDERS = setOf("male", "female", "unknown")

    /** `str(body.get(key, default))` của Python: khoá có mà null thì là chữ "None". */
    private fun field(body: JSONObject, key: String, default: String = ""): String = BookEdits.pyStr(if (body.has(key)) body.opt(key) else default)

    /** `str(body.get(key) or "")` của Python. */
    private fun orText(body: JSONObject, key: String): String = BookEdits.pyText(body.opt(key))

    /** `.strip()[:limit]` của Python. */
    private fun clip(text: String, limit: Int): String = BookEdits.cut(BookEdits.pyStrip(text), limit)

    /** `float(body.get("requestedAt") or 0)` của Python; không đọc được thì 0. */
    private fun requestedAt(body: JSONObject): Double {
        val raw = body.opt("requestedAt")
        return when (val value = if (BookEdits.truthy(raw)) raw else 0L) {
            is Boolean -> if (value) 1.0 else 0.0
            is Number -> value.toDouble()
            is String -> value.trim().toDoubleOrNull() ?: 0.0
            else -> 0.0
        }
    }

    private fun fresh(dir: java.io.File): Triple<JSONObject, BookWishes.Lines, List<JSONObject>> {
        val book = BookEdits.rawBook(dir)
        return Triple(book, BookWishes.Lines(dir, book), BookWishes.people(dir, book))
    }

    /** `_withdraw` của server.py cho ý muốn chờ Studio: rút đúng lần bấm ấy, ý muốn nó thay (`replaced`) trở lại. */
    private fun withdraw(dir: java.io.File, section: String, keys: List<String>, body: JSONObject): Any? {
        val at = requestedAt(body)
        if (keys.isEmpty() || at <= 0) throw Api(400, S.s_thieu_quyet_dinh_can_hoan_tac_e1037df2)
        val mine = BookWishes.madeAt(dir, section, keys, at)
        if (mine.isEmpty()) {
            // Đã gửi về máy giữ sách (gửi xong là gỡ khỏi lớp sửa): nhờ máy ấy rút đúng thao tác này, lần gửi kế mang đi.
            val asked = EditsSync.retract(dir, section, keys, at)
            if (asked.isNotEmpty()) return JSONObject().put("undone", asked.size).put("restored", false).put("sent", true)
            throw Api(409, S.s_quyet_dinh_nay_da_duoc_thay_bang_mot_lua_c_52d7dad8)
        }
        val removed = BookWishes.withdraw(dir, section, mine.keys.toList(), at)
        return JSONObject().put("undone", removed.size).put("restored", false)
    }

    /** `_checked_reading`: cách đọc người nghe gửi, sau phép kiểm của Studio - nghe được là lưu được. */
    private fun checkedReading(body: JSONObject, surface: String): String {
        val raw = field(body, "spokenForm")
        if (surface.isEmpty() || BookEdits.pyStrip(raw).isEmpty()) throw Api(400, S.s_thieu_ten_hoac_cach_doc_55cefe36)
        val spoken = typed { NameRules.spoken(raw) }
        val problem = VietnameseReading.problem(surface, spoken) ?: return spoken
        // Gõ theo tai mà sai chính tả ("Hên-kơ"): nói đúng âm tiết sai và mời dùng bản sửa - bản sửa qua đúng phép kiểm vừa từ chối.
        val fixed = VietnameseReading.respelled(spoken)
        if (problem == VietnameseReading.NOT_VIETNAMESE && fixed != spoken && VietnameseReading.problem(surface, fixed) == null) {
            throw Api(400, S.s_0_viet_1_c61c4bca(VietnameseReading.respellingNote(spoken, fixed), fixed), JSONObject().put("suggestion", fixed))
        }
        if (problem == VietnameseReading.NOT_VIETNAMESE) throw Api(400, notVietnameseNote(surface, spoken))
        throw Api(400, PRONUNCIATION_PROBLEMS[problem] ?: S.s_cach_doc_nay_khong_dung_duoc_1ac16408)
    }

    /** `spelling.not_vietnamese_note`: the refusal says why - a reading that only differs from the word by its marks ("Tám" -> "Tâm"), or a syllable
     *  the check does not know. */
    private fun notVietnameseNote(surface: String, spoken: String): String {
        fun unmarked(text: String) = java.text.Normalizer.normalize(text.lowercase().replace(S.s_d_bf502a39, "d"), java.text.Normalizer.Form.NFD)
            .filter { Character.getType(it) != Character.NON_SPACING_MARK.toInt() }
        return if (unmarked(BookWishes.collapse(spoken)) == unmarked(surface)) {
            S.s_0_chi_khac_dau_voi_1_ban_viet_khac_hoac_gi_f19b1351(spoken, surface)
        } else {
            S.s_chua_nhan_duoc_0_ban_viet_tung_am_tieng_vi_629aa9cc(spoken)
        }
    }

    /** POST /pronunciation/check {surface, spokenForm}: "Nghe thử" by the device voice runs the same checks as saving (a70). Writes nothing. */
    private fun pronunciationCheck(dir: java.io.File, body: JSONObject): Any? {
        val surface = typed { NameRules.typedSurface(field(body, "surface")) }
        val spoken = checkedReading(body, surface)
        if ((readingReach(dir, JSONObject().put("surface", surface)) as JSONObject).optBoolean("never")) throw Api(400, neverText(surface))
        return JSONObject().put("surface", surface).put("spokenForm", spoken)
    }

    /** POST /pronunciation {surface, spokenForm} / {surface, withdraw, requestedAt}. */
    private fun pronunciation(dir: java.io.File, body: JSONObject): Any? {
        val surface = typed { NameRules.typedSurface(field(body, "surface")) }
        if (BookEdits.truthy(body.opt("withdraw"))) {
            return withdraw(dir, "pronunciations", if (surface.isNotEmpty()) listOf(VietnameseReading.surfaceKey(surface)) else emptyList(), body)
        }
        val spoken = checkedReading(body, surface)
        // Cách đọc không bao giờ được dùng ("Mở/đóng"): giao diện tắt nút Lưu, gửi thẳng cũng không được - như máy chủ (`never_text` của name_readings.py).
        if ((readingReach(dir, JSONObject().put("surface", surface)) as JSONObject).optBoolean("never")) throw Api(400, neverText(surface))
        val at = now()
        BookWishes.requestPronunciation(dir, surface, spoken, at)
        return JSONObject().put("surface", surface).put("spokenForm", spoken).put("requestedAt", at)
    }

    /** Vì sao không lưu được cách đọc cho chữ có ký hiệu bị xé đôi - cùng lời với giao diện (`neverText` của readingReach.ts). */
    private fun neverText(surface: String): String =
        S.s_ky_hieu_trong_0_ngan_ap_cach_doc_ban_sua_c_a20d7d87(surface)

    private const val CHAPTERS_SHOWN = 6
    private const val NOT_RECORDED = S.s_chua_thu_nen_khong_phai_thu_lai_413c146b
    private const val WORD_CHAR = "[\\p{L}\\p{N}_]" // `\w` của Python (chữ, số, gạch dưới) - không dùng UNICODE_CHARACTER_CLASS: ICU của Android văng

    /**
     * GET /pronunciations/reach {surface} (`package_reading_reach` của name_readings.py): "Đọc từ này là…" trên cuốn này chạm tới bao nhiêu
     * câu - khớp nguyên từ, không phân biệt hoa thường, trên chữ đọc theo đã qua lớp sửa - bao nhiêu câu đã thu (có mốc thời gian trong
     * chương có audio) sẽ phải thu lại, ở chương nào, một câu mẫu. Trước khi tra cách đọc, ký hiệu máy không nói được đã thành quãng nghỉ
     * ([SpokenSymbols.toWords] = `spoken_symbols_to_words`): chữ nào bị xé đôi ("Mở/đóng") thì cách đọc không bao giờ khớp - `blocked` đếm các câu đó,
     * không tính vào `reached`, `recorded`, chương hay câu mẫu.
     */
    private fun readingReach(dir: java.io.File, body: JSONObject): Any? {
        val surface = typed { NameRules.typedSurface(BookEdits.pyText(body.opt("surface"))) }
        if (surface.isEmpty()) throw Api(400, S.s_thieu_chu_can_xem_921fffab)
        val book = BookEdits.rawBook(dir)
        val chapters = BookEdits.applyManifest(book, BookEdits.load(dir)).optJSONArray("chapters")?.let { list ->
            (0 until list.length()).mapNotNull { list.optJSONObject(it) }.filter { it.opt("id") is Int || it.opt("id") is Long }
        } ?: emptyList()
        val pattern = Regex("(?<!$WORD_CHAR)" + Regex.escape(surface) + "(?!$WORD_CHAR)", RegexOption.IGNORE_CASE)
        var matched = 0
        val reached = ArrayList<JSONObject>() // câu mẫu đã dựng sẵn (hình `_example` của work_items.py)
        val perChapter = LinkedHashMap<Long, IntArray>()
        for (chapter in chapters) {
            val chapterId = (chapter.opt("id") as Number).toLong()
            val title = listOf(chapter.opt("fullTitle"), chapter.opt("title")).firstOrNull { BookEdits.truthy(it) }?.toString() ?: ""
            val heard = BookEdits.truthy(chapter.opt("available")) && BookEdits.truthy(chapter.opt("file"))
            val segments = BookEdits.script(dir, book, chapterId)?.optJSONArray("segments") ?: continue
            for (index in 0 until segments.length()) {
                val segment = segments.optJSONObject(index) ?: continue
                val text = segment.opt("text") as? String ?: continue
                if (!pattern.containsMatchIn(text)) continue
                matched++
                if (!pattern.containsMatchIn(SpokenSymbols.toWords(text))) continue
                val recorded = heard && segment.opt("start") is Number
                val id = segment.opt("id")
                reached.add(JSONObject().put("segmentId", if (id is Int || id is Long) (id as Number).toLong() else (index + 1).toLong())
                    .put("chapterId", chapterId).put("chapterTitle", title).put("seq", index + 1).put("text", text)
                    .put("speaker", BookEdits.pyText(segment.opt("speaker"))).put("hasAudio", recorded))
                val counts = perChapter.getOrPut(chapterId) { IntArray(2) }
                counts[0]++
                if (recorded) counts[1]++
            }
        }
        val recorded = reached.count { it.getBoolean("hasAudio") }
        val titles = reached.associate { it.getLong("chapterId") to it.getString("chapterTitle") }
        // Cách đọc không bao giờ được dùng (`never_used` của name_readings.py): mọi câu có chữ ấy bị xé đôi - hay chưa câu nào có mà chính chữ ấy bị xé đôi.
        val never = if (matched > 0) reached.isEmpty() else !pattern.containsMatchIn(SpokenSymbols.toWords(surface))
        return JSONObject().put("surface", surface).put("lines", matched).put("reached", reached.size).put("recorded", recorded).put("blocked", matched - reached.size)
            .put("never", never)
            .put("cost", if (recorded > 0) S.s_thu_lai_0_cau_07a28f8d(recorded) else NOT_RECORDED)
            .put("chapters", JSONArray(perChapter.entries.take(CHAPTERS_SHOWN).map { (chapterId, counts) ->
                JSONObject().put("chapterId", chapterId).put("title", titles[chapterId] ?: "").put("lines", counts[0]).put("recorded", counts[1])
            }))
            .put("example", reached.firstOrNull { it.getBoolean("hasAudio") } ?: reached.firstOrNull() ?: JSONObject.NULL)
    }

    /** POST /speaker {stableId, textSha256, speaker, newGender?, alias?} hay {lines: [...], speaker} / {withdraw, lines, requestedAt}. */
    private fun speaker(dir: java.io.File, body: JSONObject): Any? {
        val speaker = clip(field(body, "speaker"), 200)
        val raw = body.opt("lines")
        val sources: List<Any?> = if (raw is JSONArray) (0 until raw.length()).map { raw.opt(it) } else listOf(body)
        val lines = sources.filterIsInstance<JSONObject>().map { clip(field(it, "stableId"), 120) to clip(field(it, "textSha256"), 64) }
        if (BookEdits.truthy(body.opt("withdraw"))) return withdraw(dir, "speakers", lines.map { it.first }.filter { it.isNotEmpty() }, body)
        if (speaker.isEmpty() || lines.isEmpty() || !lines.all { it.first.isNotEmpty() && it.second.isNotEmpty() }) throw Api(400, S.s_thieu_cau_hoac_nguoi_noi_cf80e04b)
        val newGender = BookEdits.pyStrip(field(body, "newGender"))
        if (newGender.isNotEmpty() && newGender !in NEW_GENDERS) throw Api(400, S.s_gioi_cua_nguoi_moi_khong_hop_le_3219a3d2)
        val (_, index, cast) = fresh(dir)
        // "Người mới…": tên qua cùng phép kiểm với "Đổi tên" (server `_checked_name`).
        val person = if (newGender.isEmpty()) speaker else typed {
            NameRules.person(speaker, cast.map { BookEdits.pyText(it.opt("displayName")).ifEmpty { it.getString("name") } })
        }
        // Câu vừa được đổi từ lời kể thành lời thoại và còn chờ: người nói đi kèm xét theo loại đoạn ấy (server `book_wishes.pending_line_kind`).
        val waiting = BookEdits.load(dir).optJSONObject("wishes")
        for ((stableId, sha) in lines) {
            val problem = BookWishes.speakerProblem(index, cast, stableId, sha, person, newGender, BookWishes.pendingLineKind(waiting, stableId, sha))
            if (problem != null) throw Api(400, SPEAKER_PROBLEMS[problem] ?: S.s_chua_doi_duoc_nguoi_noi_cau_nay_82bcc30b)
        }
        val at = now()
        // Máy/cửa sổ khác vừa sửa chính câu này khác điều giao diện đã thấy (`seen`): vẫn ghi, báo lại - chỉ khi lệch (server `_edited_elsewhere`).
        val elsewhere = speakerElsewhere(dir, lines, body.opt("seen"))
        BookWishes.requestSpeakers(dir, lines, person, at, newGender)
        val alias = clip(orText(body, "alias"), 200)
        val remembered = alias.isNotEmpty() && BookWishes.requestAlias(dir, alias, person, at)
        return withElsewhere(JSONObject().put("lines", lines.size).put("speaker", person).put("new", newGender.isNotEmpty())
            .put("alias", remembered).put("requestedAt", at), elsewhere)
    }

    // ---- hai máy sửa cùng một chỗ (soát a27 lỗi 4, uxfix28): `seen` = điều giao diện đã thấy; lệch thì lời đáp mang `elsewhere` ----

    /** Ý muốn đang ghi của mục `section` (lớp sửa, hình dạng mục của overrides.json) - server `_requests_here`. */
    private fun wished(dir: java.io.File, section: String): JSONObject =
        BookEdits.load(dir).optJSONObject("wishes")?.optJSONObject(section) ?: JSONObject()

    private fun withElsewhere(reply: JSONObject, elsewhere: JSONObject): JSONObject =
        if (elsewhere.length() > 0) reply.put("elsewhere", elsewhere) else reply

    /** {mã câu: người đang được ghi ("" = chưa ai quyết)} cho những câu mà điều đang ghi khác `seen` (server `_edited_elsewhere`). */
    private fun speakerElsewhere(dir: java.io.File, lines: List<Pair<String, String>>, seen: Any?): JSONObject {
        val out = JSONObject()
        if (seen !is JSONObject) return out
        val recorded = wished(dir, "speakers")
        for ((stableId, sha) in lines) {
            if (!seen.has(stableId)) continue
            val entry = recorded.optJSONObject(stableId)
            val actual = if (entry != null && BookEdits.pyText(entry.opt("text_sha256")) == sha) BookEdits.pyText(entry.opt("speaker")) else ""
            if (actual != BookEdits.pyText(seen.opt(stableId))) out.put(stableId, actual)
        }
        return out
    }

    /** Cách đọc một câu để so (server `_delivery`); NULL = chưa ai sửa câu này. */
    private fun delivery(entry: Any?): Any {
        if (entry !is JSONObject) return JSONObject.NULL
        val intensity = entry.opt("intensity")
        return JSONObject().put("kind", BookEdits.pyText(entry.opt("kind"))).put("emotion", BookEdits.pyText(entry.opt("emotion")))
            .put("intensity", if (intensity is Number) intensity.toLong() else JSONObject.NULL)
            .put("spoken", entry.opt("spoken") as? String ?: JSONObject.NULL)
    }

    /** {"delivery": cách đọc đang ghi} khi nó khác `seen` (server `_line_elsewhere`); không gửi `seen` thì rỗng. */
    private fun lineElsewhere(dir: java.io.File, stableId: String, sha: String, body: JSONObject): JSONObject {
        if (!body.has("seen")) return JSONObject()
        val entry = wished(dir, "lines").optJSONObject(stableId)
        val actual = delivery(if (entry != null && BookEdits.pyText(entry.opt("text_sha256")) == sha) entry else null)
        return if (StrictJson.equal(actual, delivery(body.opt("seen")))) JSONObject() else JSONObject().put("delivery", actual)
    }

    /** {"voice", "gender"} của lựa chọn đang chờ khi mốc của nó khác `seen` - mốc lựa chọn hộp đã thấy, 0 = không có (server `_voice_elsewhere`). */
    private fun voiceElsewhere(dir: java.io.File, character: String, body: JSONObject): JSONObject {
        val seen = (body.opt("seen") as? Number)?.toDouble() ?: return JSONObject()
        val entry = wished(dir, "voices").optJSONObject(BookWishes.characterKey(character))
        val recordedAt = (entry?.opt("requested_at") as? Number)?.toDouble() ?: 0.0
        if (Math.abs(recordedAt - seen) < 1e-6 || (seen == 0.0 && entry == null)) return JSONObject()
        return JSONObject().put("voice", VoiceLabels.label(BookEdits.pyText(entry?.opt("preset")))).put("gender", BookEdits.pyText(entry?.opt("gender")))
    }

    /** POST /line {stableId, textSha256, kind?, emotion?, intensity?, speaker?, spoken?}. */
    private fun line(dir: java.io.File, body: JSONObject): Any? {
        val stableId = clip(field(body, "stableId"), 120)
        val sha = clip(field(body, "textSha256"), 64)
        // "Hoàn tác" trên thông báo: rút đúng lần sửa ấy (`requestedAt`), yêu cầu nó thay trở lại (server `post_line`, soát a89 V7).
        if (BookEdits.truthy(body.opt("withdraw"))) return withdraw(dir, "lines", if (stableId.isNotEmpty()) listOf(stableId) else emptyList(), body)
        val kind = clip(orText(body, "kind"), 20)
        val emotion = clip(orText(body, "emotion"), 20)
        val speaker = clip(orText(body, "speaker"), 200)
        val rawIntensity = body.opt("intensity")
        val intensity: Long? = if (rawIntensity is Number) rawIntensity.toLong() else null
        val spoken: String? = (body.opt("spoken") as? String)?.let { BookEdits.cut(it, 2200) }
        if (stableId.isEmpty() || sha.isEmpty() || !(kind.isNotEmpty() || emotion.isNotEmpty() || intensity != null || speaker.isNotEmpty() || spoken != null)) {
            throw Api(400, S.s_thieu_cau_hoac_thay_doi_98756156)
        }
        if (intensity != null && intensity !in 0..BookWishes.INTENSITY_MAX.toLong()) throw Api(400, S.s_cuong_do_phai_tu_0_toi_0_14da1ba0(BookWishes.INTENSITY_MAX))
        val (_, index, cast) = fresh(dir)
        val problem = BookWishes.lineProblem(index, cast, stableId, sha, kind, emotion, speaker, spoken)
        if (problem != null) throw Api(400, LINE_PROBLEMS[problem] ?: S.s_chua_doi_duoc_cach_doc_cau_nay_028c6d96)
        val elsewhere = lineElsewhere(dir, stableId, sha, body)
        val at = now()
        BookWishes.requestLine(dir, stableId, sha, kind, emotion, intensity, speaker, spoken, at)
        return withElsewhere(JSONObject().put("stableId", stableId).put("kind", kind).put("emotion", emotion)
            .put("intensity", intensity ?: JSONObject.NULL).put("spoken", spoken ?: JSONObject.NULL).put("requestedAt", at), elsewhere)
    }

    /** POST /voice {character, gender?, preset?, avoid?} / {character, withdraw, requestedAt}. */
    private fun voice(dir: java.io.File, body: JSONObject): Any? {
        val character = clip(field(body, "character"), 200)
        if (BookEdits.truthy(body.opt("withdraw"))) {
            return withdraw(dir, "voices", if (character.isNotEmpty()) listOf(BookWishes.characterKey(character)) else emptyList(), body)
        }
        val preset = clip(orText(body, "preset"), 120)
        val gender = clip(orText(body, "gender"), 10)
        val avoid = clip(orText(body, "avoid"), 200)
        if (character.isEmpty()) throw Api(400, S.s_thieu_nhan_vat_1605a34d)
        if (preset.isEmpty() && gender.isEmpty() && avoid.isEmpty()) throw Api(400, S.s_thieu_giong_hoac_gioi_tinh_fb23e2a7)
        val (_, _, cast) = fresh(dir)
        val problem = BookWishes.voiceProblem(cast, character, gender, avoid)
        if (problem != null) throw Api(400, VOICE_PROBLEMS[problem] ?: S.s_chua_doi_duoc_giong_nhan_vat_nay_0b88253d)
        val at = now()
        val elsewhere = voiceElsewhere(dir, character, body)
        BookWishes.requestVoice(dir, character, preset, gender, avoid, at)
        return withElsewhere(JSONObject().put("character", character).put("preset", preset).put("gender", gender)
            .put("avoid", avoid).put("requestedAt", at), elsewhere)
    }

    /**
     * POST /review {verdict, stableId} hay cả nhóm {verdict, lines: [{stableId}...]} (Shift-chọn ở tab Kịch bản): chưa có hàng đợi
     * "Cần nghe lại" - chỉ phần "Cần thu lại" (ý muốn chờ Studio). Cả nhóm cùng một mốc - một lần bấm là một thay đổi, bỏ được cả
     * nhóm. Một câu đáp `{ok}`; nhóm đáp thêm số câu đã xin thu lại + mốc (`server.post_review`).
     */
    private fun review(dir: java.io.File, body: JSONObject): Any? {
        val verdict = body.opt("verdict")
        val none = verdict == null || verdict === JSONObject.NULL
        if (!none && verdict != "ok" && verdict != "redo") throw Api(400, S.s_phan_quyet_khong_hop_le_d05dc9da)
        val refs = body.opt("lines") as? JSONArray
        val stableIds = refs?.let { list ->
            (0 until minOf(list.length(), 2000)).mapNotNull { list.opt(it) as? JSONObject }
                .map { BookEdits.cut(BookEdits.pyStr(if (it.has("stableId")) it.opt("stableId") else ""), 80) }
        } ?: listOf(BookEdits.cut(field(body, "stableId"), 80))
        val (_, index, _) = fresh(dir)
        val at = now()
        // "Cần thu lại" máy/cửa sổ khác vừa xin hay bỏ khác điều giao diện đã thấy (`seen`: {mã câu: "redo" | ""}): báo lại (server post_review).
        val seen = body.opt("seen") as? JSONObject
        val retakes = wished(dir, "retakes")
        val elsewhere = JSONObject()
        for (stableId in stableIds) {
            val before = if (retakes.has(stableId)) "redo" else ""
            if (seen != null && seen.has(stableId) && before != BookEdits.pyText(seen.opt(stableId))) elsewhere.put(stableId, before)
        }
        val asked = ArrayList<Pair<String, String>>()
        val sent = ArrayList<String>()
        for (stableId in stableIds) {
            val found = index.get(stableId)
            if (verdict == "redo" && found != null && BookEdits.truthy(found.second.opt("textSha256"))) {
                asked.add(stableId to BookEdits.pyText(found.second.opt("textSha256")))
            } else if (verdict != "redo") {
                BookWishes.cancelRetake(dir, stableId)
                if (!retakes.has(stableId)) sent.addAll(EditsSync.retract(dir, "retakes", listOf(stableId))) // đã gửi đi rồi: nhờ máy giữ sách rút
            }
        }
        if (asked.isNotEmpty()) BookWishes.requestRetakes(dir, asked, at)
        val reply = JSONObject().put("ok", true)
        if (sent.isNotEmpty()) reply.put("sent", true)
        return withElsewhere(if (refs == null) reply else reply.put("lines", asked.size).put("requestedAt", at), elsewhere)
    }

    /** POST /characters/merge {from, into}: mọi câu nói của người này thành ý muốn "là lời của người kia" + bí danh. */
    private fun mergeCharacters(dir: java.io.File, body: JSONObject): Any? {
        val source = clip(field(body, "from"), 200)
        val target = clip(field(body, "into"), 200)
        if (source.isEmpty() || target.isEmpty() || BookWishes.aliasKey(source) == BookWishes.aliasKey(target)) throw Api(400, S.s_chon_hai_nguoi_khac_nhau_947a4e1f)
        val (_, index, cast) = fresh(dir)
        val found = BookWishes.speakerLines(index, cast, source)
        if (found.isEmpty()) throw Api(400, S.s_nguoi_nay_khong_con_cau_noi_nao_de_gop_7841c6a8)
        val problem = BookWishes.speakerProblem(index, cast, found[0].first, found[0].second, target)
        if (problem != null) throw Api(400, SPEAKER_PROBLEMS[problem] ?: S.s_chua_gop_duoc_vao_nguoi_nay_287693ea)
        val at = now()
        BookWishes.requestSpeakers(dir, found, target, at)
        BookWishes.requestAlias(dir, source, target, at)
        return JSONObject().put("lines", found.size).put("requestedAt", at)
    }

    /** POST /chapters/<n>/retake: thu lại MỌI câu của chương - một lần bấm, bỏ thì bỏ cả nhóm. */
    private fun chapterRetake(dir: java.io.File, chapter: String): Any? {
        val (_, index, _) = fresh(dir)
        val found = BookWishes.chapterLines(index, chapter.toLongOrNull() ?: -1L)
        if (found.isEmpty()) throw Api(400, S.s_chuong_nay_chua_co_cau_nao_da_thu_de_thu_l_70c44bee)
        val at = now()
        BookWishes.requestRetakes(dir, found, at)
        return JSONObject().put("lines", found.size).put("requestedAt", at)
    }

    /** POST /pending-changes/withdraw {section, key, keys?, requestedAt}: bỏ một thay đổi khỏi danh sách chờ. */
    private fun pendingWithdraw(dir: java.io.File, body: JSONObject): Any? {
        val section = orText(body, "section")
        val key = orText(body, "key")
        val at = requestedAt(body)
        if (section !in BookWishes.SECTIONS || key.isEmpty() || at <= 0) throw Api(400, S.s_thieu_thay_doi_can_bo_51103463)
        val group = if (section in BookWishes.byClick) {
            (body.opt("keys") as? JSONArray)?.let { list -> (0 until list.length()).mapNotNull { list.opt(it) as? String } }?.take(5000) ?: emptyList()
        } else emptyList()
        val mine = BookWishes.madeAt(dir, section, group.ifEmpty { listOf(key) }, at)
        if (mine.isEmpty()) throw Api(409, S.s_thay_doi_nay_vua_duoc_thay_bang_mot_lua_ch_321ad0a7)
        BookWishes.withdraw(dir, section, mine.keys.toList(), at)
        return JSONObject().put("withdrawn", mine.size)
    }

    /** GET /work, /casting, /pronunciations: bản chụp trong file dự án; 404 khi cuốn không có (cuốn từ file `.abook`, hay file không kèm). */
    private fun projectView(dir: java.io.File, name: String): Any? =
        ProjectDocument.view(dir, name) ?: throw Api(404, S.s_file_du_an_nay_khong_kem_ban_chup_cua_man_2c1c8244)

    /**
     * GET /narrator-mode: công tắc B "Người kể xưng “tôi” tự kể chuyện" CHỈ ĐỌC. Việc đổi nó ghi thẳng vào sổ dự án và đặt lại bản thu
     * (webui/teller_mode.py) nên chỉ làm được ở máy có Studio - không mang `teller_voice` sang đây. Sổ `studio_narrator.json` nằm trong
     * `project/` của file dự án (copy nguyên byte); chưa có thì không biết sách có người kể "tôi" hay không → `available: false`
     * (công tắc ẩn, như sách ngôi ba). `editableHere: false` để giao diện hiện công tắc khoá kèm lời chỉ sang máy tính.
     */
    private fun narratorMode(dir: java.io.File): Any? {
        val record = runCatching { JSONObject(java.io.File(dir, "project/studio_narrator.json").readText()) }.getOrNull() ?: JSONObject()
        val mode = record.optString("mode").takeIf { it == "narrator" || it == "teller" } ?: "narrator"
        val applied = record.optJSONObject("applied") ?: JSONObject()
        // Sổ chỉ có dấu vết A+/B khi sách thật sự có người kể "tôi".
        val available = mode == "teller" || applied.has("teller") || applied.has("narrator") || applied.has("thoughts")
        return JSONObject().put("available", available).put("mode", mode).put("castLocked", true).put("applied", applied.has("teller"))
            .put("plan", JSONObject.NULL).put("editableHere", false)
    }

    /** GET /chapters/<n>/script: chữ đọc theo đã qua lớp sửa. */
    private fun script(dir: java.io.File, chapter: String): Any? =
        chapter.toLongOrNull()?.let { BookEdits.script(dir, BookEdits.rawBook(dir), it) } ?: throw Api(404, S.s_khong_co_chuong_nay_87338800)
}
