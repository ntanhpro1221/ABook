package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject

/**
 * "Studio" nhẹ trên điện thoại: máy chủ giao diện của máy tính (abook/webui/server.py) trả lời `/api/books/<mã>/...` còn điện
 * thoại thì không có máy chủ - giao diện gọi `EbookLibrary.studio({method, path, body})` và nhận đúng JSON máy chủ sẽ trả
 * (docs/EDITING.md, bảng "Routes"). Phần L ("áp ngay", không cần Studio) cho cuốn mở từ file `.abook`: đổi tên sách, bìa, tên
 * nhân vật, tên chương, nhạc nền, xem/bỏ thay đổi; và phần W (ý muốn chờ Studio - [BookWishes]): cách đọc tên, ai nói câu này,
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
    private val MY_MUSIC = Regex("/api/music/local(?:/([0-9a-f]{40})|/(analyze)|/(module)|/(reanalyse))?")
    private val EDITS_ONLY_KEYS = setOf("enabled", "levelDb", "silence", "pins", "playlist")
    private val lock = Any()

    /** Kho "Nhạc của tôi" của điện thoại này (LibraryPlugin đặt khi nạp; test JVM đặt kho trong thư mục tạm). */
    @Volatile
    var musicStore: MusicStore? = null

    /** Danh mục nhạc nền (danh sách phát cho "Nghe ngay" - [Playlists]); LibraryPlugin đặt khi nạp, test JVM đặt danh mục trong thư mục tạm. */
    @Volatile
    var catalog: MusicCatalog? = null

    /** Luật chọn danh sách phát đóng kèm app ([DeviceMusic.bundledPicker]): dùng khi chưa có danh mục hay danh mục mang luật hỏng. LibraryPlugin đặt; test JVM đặt từ file asset. */
    @Volatile
    var bundledPicker: JSONObject? = null

    /** Mô-đun "Phân tích nhạc" (model + thư viện ONNX Runtime; điện thoại tải khi người dùng bấm - MusicStudentSetup). Null: không có việc tải (test JVM); view không kèm `module`. */
    @Volatile
    var student: MusicStudentSetup? = null

    /** Bộ chuẩn hoá ảnh bìa: máy thật dùng [AndroidCoverCodec]; test JVM đặt bản giả. */
    @Volatile
    var coverCodec: CoverCodec? = null

    /** Đồng hồ (giây) - làm số phiên bản cho bìa; test đặt số cố định. */
    @Volatile
    var clock: () -> Long = { System.currentTimeMillis() / 1000 }

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
        val store = musicStore ?: throw Api(404, "Không có đường dẫn này")
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
        return JSONObject().put("playlists", playlists).put("mine", musicStore?.entries()?.size ?: 0).put("error", error)
    }

    /** Lời đáp của một lượt nhập (`my_music_import` của server.py): bài mới, bài đã có, file lỗi kèm lý do, cộng danh sách mới. */
    fun importAnswer(added: List<JSONObject>, existing: List<JSONObject>, failed: List<String>): JSONObject =
        JSONObject().put("added", JSONArray(added)).put("existing", JSONArray(existing)).put("failed", JSONArray(failed)).also { out ->
            val view = musicView()
            for (key in listOf("tracks", "analyzer", "module")) out.put(key, view.opt(key))
        }

    /** `/api/music/local...`: kho nhạc của máy, không thuộc cuốn nào. Nhập file đi qua hộp chọn file của hệ thống (LibraryPlugin.pickMusic). */
    private fun myMusic(method: String, digest: String?, analyze: Boolean, download: Boolean, reanalyse: Boolean): Pair<Int, Any?> {
        val store = musicStore ?: throw Api(404, "Không có đường dẫn này")
        return when {
            method == "POST" && download -> {
                // Người dùng bấm "Tải bộ phân tích": chạy ở luồng riêng, giao diện hỏi lại view để thấy tiến độ.
                (student ?: throw Api(404, "Không có đường dẫn này")).start()
                200 to musicView()
            }
            method == "POST" && reanalyse -> {
                // Người dùng bấm "Phân tích lại N bài bằng bản mới" sau khi cập nhật Phân tích nhạc: không bao giờ tự chạy.
                if (!store.analyzerAvailable()) throw Api(409, MusicStore.NO_ANALYZER)
                (student ?: throw Api(404, "Không có đường dẫn này")).reanalyse()
                200 to musicView()
            }
            method == "GET" && digest == null && !analyze -> 200 to musicView()
            method == "DELETE" && digest != null -> {
                if (!store.remove(digest)) throw Api(404, "Bài này không còn trong Nhạc của tôi")
                200 to musicView()
            }
            method == "POST" && analyze -> {
                if (!store.analyzerAvailable()) throw Api(409, MusicStore.NO_ANALYZER)
                val done = store.analyzePending()
                200 to musicView().put("analysed", done)
            }
            else -> throw Api(404, "Không có đường dẫn này")
        }
    }

    private fun run(method: String, rawPath: String, body: JSONObject): Pair<Int, Any?> {
        val path = rawPath.substringBefore('?') // tham số của GET do giao diện gửi trong `body` (android/localStudio.ts)
        if (method == "GET" && path == "/api/music/playlists") return 200 to playlistsView()
        MY_MUSIC.matchEntire(path)?.let { return myMusic(method, it.groups[1]?.value, it.groups[2] != null, it.groups[3] != null, it.groups[4] != null) }
        val match = ROUTE.matchEntire(path) ?: throw Api(404, "Không có đường dẫn này")
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
        val handler = route(method, rest) ?: throw Api(404, "Không có đường dẫn này")
        val dir = editable(id)
        // Mỗi cuốn một lần sửa một lúc: đọc-sửa-ghi của hai yêu cầu không được chen nhau.
        return synchronized(lock) { 200 to handler(dir, body) }
    }

    /** Thư mục cuốn mà người nghe sửa được: mọi cuốn trên máy (đã tải, mở từ file, hay nghe thẳng chỉ có `stream.json`); không có thì 404. */
    private fun editable(id: String): java.io.File {
        if (Store.rawManifest(id) == null && Store.streamManifest(id) == null) throw Api(404, "Không tìm thấy sách này trong thư viện")
        return Store.bookDir(id)
    }

    private fun route(method: String, path: String): ((java.io.File, JSONObject) -> Any?)? {
        CHAPTER_TITLE.matchEntire(path)?.takeIf { method == "PUT" }?.let { match -> return { dir, body -> chapterTitle(dir, match.groupValues[1], body) } }
        CHAPTER_SCRIPT.matchEntire(path)?.takeIf { method == "GET" }?.let { match -> return { dir, _ -> script(dir, match.groupValues[1]) } }
        CHAPTER_RETAKE.matchEntire(path)?.takeIf { method == "POST" }?.let { match -> return { dir, _ -> chapterRetake(dir, match.groupValues[1]) } }
        CASTING_CHAPTER.matchEntire(path)?.takeIf { method == "GET" }?.let {
            return { _, _ -> throw Api(404, "File dự án không kèm từng câu của chương - đọc chữ trong sách") }
        }
        SCENE_ALTERNATIVES.matchEntire(path)?.takeIf { method == "GET" }?.let { match -> return { dir, _ -> alternatives(dir, java.net.URLDecoder.decode(match.groupValues[1], "UTF-8")) } }
        return when (method to path) {
            "PUT" to "/title" -> ::title
            "PUT" to "/cover" -> ::cover
            "DELETE" to "/cover" -> { dir, _ -> BookEdits.removeCover(dir); JSONObject().put("cover", JSONObject.NULL) }
            "POST" to "/characters/rename" -> ::renameCharacter
            "GET" to "/music" -> { dir, _ -> withAutoPlaylist(dir, BookEdits.musicView(BookEdits.rawBook(dir), BookEdits.load(dir))) }
            "GET" to "/suggestions" -> { dir, _ -> suggestions(dir) }
            "PUT" to "/skip" -> { dir, body -> skipLine(dir, body) }
            "GET" to "/readings" -> { dir, _ -> BookEdits.readingsView(BookEdits.load(dir)) }
            "PUT" to "/readings" -> ::reading
            "PUT" to "/music" -> ::music
            "GET" to "/edits" -> { dir, _ ->
                val edits = BookEdits.load(dir)
                JSONObject().put("applied", BookEdits.countApplied(edits)).put("waiting", 0).put("wishes", BookEdits.countWishes(edits))
            }
            "GET" to "/pending-changes" -> { dir, _ -> BookWishes.pendingDetails(dir, BookEdits.rawBook(dir), BookEdits.load(dir).optJSONObject("wishes")) }
            "GET" to "/wishes" -> { dir, _ -> BookWishes.byLine(dir, BookEdits.rawBook(dir), BookEdits.load(dir).optJSONObject("wishes")) }
            "POST" to "/pending-changes/withdraw" -> ::pendingWithdraw
            "POST" to "/characters/merge" -> ::mergeCharacters
            "POST" to "/pronunciation" -> ::pronunciation
            "POST" to "/speaker" -> ::speaker
            "POST" to "/line" -> ::line
            "POST" to "/voice" -> ::voice
            "POST" to "/review" -> ::review
            "DELETE" to "/edits" -> { dir, _ -> BookEdits.clear(dir); JSONObject().put("applied", 0).put("waiting", 0) }
            "GET" to "/cast" -> { dir, _ -> BookEdits.cast(dir, BookEdits.rawBook(dir)) }
            // Bản chụp chỉ đọc của xưởng trong file dự án (ProjectDocument.view, project_views.py): cùng JSON với đường của Studio.
            "GET" to "/work" -> { dir, _ -> projectView(dir, "work") }
            "GET" to "/casting" -> { dir, _ -> projectView(dir, "casting") }
            "GET" to "/pronunciations" -> { dir, _ -> projectView(dir, "names") }
            else -> null
        }
    }

    /** PUT /title {title}: `App.rename` - làm sạch như `store.clean_title` rồi lớp sửa ghi lại (NFC) hay bỏ khi đúng tên sách. */
    private fun title(dir: java.io.File, body: JSONObject): Any? {
        val cleaned = BookEdits.cleanText(BookEdits.pyText(body.opt("title")), BookEdits.TITLE_MAX, normalize = false)
        if (cleaned.isEmpty()) throw BookEdits.EditsError("Tên sách không được để trống")
        return JSONObject().put("title", BookEdits.setTitle(dir, cleaned))
    }

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
        return JSONObject().put("cover", BookEdits.setCover(dir, raw, clock(), codec))
    }

    /** POST /characters/rename {character, name}. */
    private fun renameCharacter(dir: java.io.File, body: JSONObject): Any? {
        val character = BookEdits.pyStrip(BookEdits.pyStr(if (body.has("character")) body.opt("character") else "")).let {
            if (it.codePointCount(0, it.length) > 200) it.substring(0, it.offsetByCodePoints(0, 200)) else it
        }
        if (character.isEmpty() || character.uppercase(java.util.Locale.ROOT) == "NARRATOR") throw BookEdits.EditsError("Thiếu nhân vật")
        return BookEdits.setCharacterName(dir, character, BookEdits.pyStr(if (body.has("name")) body.opt("name") else ""))
    }

    /** PUT /chapters/<n>/title {title?, subtitle?, revert?}. */
    private fun chapterTitle(dir: java.io.File, chapter: String, body: JSONObject): Any? {
        val revert = BookEdits.truthy(body.opt("revert"))
        val title = if (revert) null else body.opt("title")
        val subtitle = if (revert) null else body.opt("subtitle")
        fun text(value: Any?): String? = when {
            value == null || value === JSONObject.NULL -> null
            value is String -> value
            else -> throw BookEdits.EditsError("Tên chương phải là chữ")
        }
        val (newTitle, newSubtitle) = text(title) to text(subtitle)
        return BookEdits.setChapterTitle(dir, chapter.toLongOrNull() ?: throw BookEdits.EditsError("Không có chương này trong sách"), newTitle, newSubtitle)
    }

    /**
     * GET /suggestions: gợi ý của bộ nhập sách cho cuốn chỉ-chữ (dòng ghi công ở đầu chương), kèm đang bỏ khỏi phần đọc hay chưa -
     * trang sách hiện những gợi ý còn chờ (`server.get_suggestions`).
     */
    private fun suggestions(dir: java.io.File): JSONObject {
        val out = JSONArray()
        val chapters = BookEdits.applyManifest(BookEdits.rawBook(dir), BookEdits.load(dir)).optJSONArray("chapters") ?: JSONArray()
        for (index in 0 until chapters.length()) {
            val chapter = chapters.optJSONObject(index) ?: continue
            val id = chapter.opt("id") as? Int ?: continue
            val entry = chapter.optString("text").takeIf { it.startsWith("texts/") } ?: continue
            val file = java.io.File(dir, entry).takeIf { it.isFile } ?: continue
            val skipped = chapter.optJSONArray("skip")?.let { array -> (0 until array.length()).map { array.getString(it) }.toSet() } ?: emptySet()
            for (line in BookImport.creditSuggestions(file.readText(Charsets.UTF_8))) {
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
        if (surface !is String || spoken !is String) throw BookEdits.EditsError("Thiếu từ hoặc cách đọc")
        return BookEdits.setReading(dir, surface, spoken)
    }

    /** PUT /skip {line, chapters, skip}: người nghe chấp nhận (hay bỏ chấp nhận) một gợi ý - dòng bị bỏ khỏi phần đọc của các chương ấy,
     *  chữ không đổi (`server.put_skip_line`). */
    private fun skipLine(dir: java.io.File, body: JSONObject): JSONObject {
        val line = body.opt("line") as? String ?: throw BookEdits.EditsError("Dòng cần bỏ phải là chữ.")
        val chapters = body.opt("chapters") as? JSONArray
        val ids = chapters?.let { array -> (0 until array.length()).map { array.opt(it) } }
        if (ids == null || ids.any { it !is Int && it !is Long }) throw BookEdits.EditsError("Không có chương này trong sách")
        return JSONObject().put("skip", BookEdits.setSkipLine(dir, ids.map { (it as Number).toLong() }, line, body.opt("skip") != false))
    }

    /** PUT /music {enabled?, levelDb?, silence?, pins?, playlist?}: sách đã đóng gói chỉ chỉnh được năm thứ ấy (playlist: mã, "mine", "off" = tắt, null = để máy chọn). */
    private fun music(dir: java.io.File, body: JSONObject): Any? {
        if (body.keys().asSequence().any { it !in EDITS_ONLY_KEYS }) {
            throw BookEdits.EditsError("Sách đã đóng gói chỉ chỉnh được bật/tắt nhạc, mức nhạc, im lặng từng đoạn, đổi bài và danh sách nhạc nền")
        }
        return withAutoPlaylist(dir, BookEdits.setMusic(dir, body, musicStore?.let { store -> { link: String -> store.track(link) } }))
    }

    /** `_with_auto_playlist` của server.py: màn "Nhạc nền" + danh sách máy chọn - sách chưa có lựa chọn nào (`playlist` không có khoá) và không có
     *  nhạc của người làm sách thì `playlist` là mã máy chọn, kèm `playlistAuto` true. Đã chọn (kể cả "off") thì giữ nguyên. */
    private fun withAutoPlaylist(dir: java.io.File, view: JSONObject): JSONObject {
        if (view.has("playlist") || BookEdits.truthy(BookEdits.rawBook(dir).opt("music"))) return view
        // Mục lục danh mục chưa tải được (máy mới, chưa có mạng) thì dùng luật đóng kèm: chọn được tên danh sách ngay, bài tải sau.
        val manifest = runCatching { catalog?.manifest() }.getOrNull()
        val auto = Playlists.autoPlaylist(dir, manifest, bundledPicker) ?: return view
        return view.put("playlist", auto).put("playlistAuto", true)
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
        if ((0 until cues.length()).none { cues.getJSONObject(it).getString("key") == key }) throw Api(404, "Không thấy đoạn nhạc này trong sách.")
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
        VietnameseReading.MULTI_WORD to "Chỉ sửa được cách đọc của MỘT từ - cách đọc lưu theo từng từ.",
        VietnameseReading.NOT_VIETNAMESE to "Cách đọc phải là các âm tiết tiếng Việt nối bằng gạch nối, ví dụ Hên-khơ.",
    )
    private val LINE_PROBLEMS = mapOf(
        BookWishes.UNKNOWN_LINE to "Không còn câu này trong sách.",
        BookWishes.SOURCE_CHANGED to "Chữ của câu này đã đổi - tải lại chương.",
        BookWishes.BAD_KIND to "Loại đoạn phải là lời kể, lời thoại hay nội tâm.",
        BookWishes.BAD_EMOTION to "Cảm xúc này không có trong bộ giọng.",
        BookWishes.NOT_SPEECH to "Lời kể không có người nói - đổi thành lời thoại trước.",
        BookWishes.NO_VOICE to "Người này chưa có giọng trong sách (chưa nói câu nào) - chưa gán được.",
        BookWishes.BAD_TEXT to "Chữ đem đọc phải có chữ cái, không ký tự lạ, và không dài quá bốn lần câu gốc.",
    )
    private val VOICE_PROBLEMS = mapOf(
        BookWishes.UNKNOWN_CHARACTER to "Không có nhân vật này trong sách.",
        BookWishes.NOT_A_CHARACTER to "Giọng người kể chọn khi tạo sách, không đổi ở đây.",
        BookWishes.NO_VOICE to "Nhân vật này chưa có giọng (chưa qua bước phân vai) - chưa đổi được.",
        BookWishes.BAD_GENDER to "Giới phải là nam hoặc nữ.",
    )
    private val SPEAKER_PROBLEMS = mapOf(
        BookWishes.UNKNOWN_LINE to "Không còn câu này trong sách.",
        BookWishes.SOURCE_CHANGED to "Chữ của câu này đã đổi từ lúc máy chấm - tải lại danh sách việc.",
        BookWishes.NOT_SPEECH to "Câu này là lời kể, không có người nói để đổi.",
        BookWishes.NO_VOICE to "Người này chưa có giọng trong sách (chưa nói câu nào) - chưa gán được.",
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
        if (keys.isEmpty() || at <= 0) throw Api(400, "Thiếu quyết định cần hoàn tác")
        val mine = BookWishes.madeAt(dir, section, keys, at)
        if (mine.isEmpty()) throw Api(409, "Quyết định này đã được thay bằng một lựa chọn sau - không còn gì để hoàn tác.")
        val removed = BookWishes.withdraw(dir, section, mine.keys.toList(), at)
        return JSONObject().put("undone", removed.size).put("restored", false)
    }

    /** `_checked_reading`: cách đọc người nghe gửi, sau phép kiểm của Studio - nghe được là lưu được. */
    private fun checkedReading(body: JSONObject, surface: String): String {
        val spoken = BookEdits.cut(BookWishes.collapse(field(body, "spokenForm")), 120)
        if (surface.isEmpty() || spoken.isEmpty()) throw Api(400, "Thiếu tên hoặc cách đọc")
        val problem = VietnameseReading.problem(surface, spoken) ?: return spoken
        // Gõ theo tai mà sai chính tả ("Hên-kơ"): nói đúng âm tiết sai và mời dùng bản sửa - bản sửa qua đúng phép kiểm vừa từ chối.
        val fixed = VietnameseReading.respelled(spoken)
        if (problem == VietnameseReading.NOT_VIETNAMESE && fixed != spoken && VietnameseReading.problem(surface, fixed) == null) {
            throw Api(400, "${VietnameseReading.respellingNote(spoken, fixed)} Viết: “$fixed”.", JSONObject().put("suggestion", fixed))
        }
        throw Api(400, PRONUNCIATION_PROBLEMS[problem] ?: "Cách đọc này không dùng được")
    }

    /** POST /pronunciation {surface, spokenForm} / {surface, withdraw, requestedAt}. */
    private fun pronunciation(dir: java.io.File, body: JSONObject): Any? {
        val surface = clip(field(body, "surface"), 80)
        if (BookEdits.truthy(body.opt("withdraw"))) {
            return withdraw(dir, "pronunciations", if (surface.isNotEmpty()) listOf(VietnameseReading.surfaceKey(surface)) else emptyList(), body)
        }
        val spoken = checkedReading(body, surface)
        val at = now()
        BookWishes.requestPronunciation(dir, surface, spoken, at)
        return JSONObject().put("surface", surface).put("spokenForm", spoken).put("requestedAt", at)
    }

    /** POST /speaker {stableId, textSha256, speaker, newGender?, alias?} hay {lines: [...], speaker} / {withdraw, lines, requestedAt}. */
    private fun speaker(dir: java.io.File, body: JSONObject): Any? {
        val speaker = clip(field(body, "speaker"), 200)
        val raw = body.opt("lines")
        val sources: List<Any?> = if (raw is JSONArray) (0 until raw.length()).map { raw.opt(it) } else listOf(body)
        val lines = sources.take(2000).filterIsInstance<JSONObject>().map { clip(field(it, "stableId"), 120) to clip(field(it, "textSha256"), 64) }
        if (BookEdits.truthy(body.opt("withdraw"))) return withdraw(dir, "speakers", lines.map { it.first }.filter { it.isNotEmpty() }, body)
        if (speaker.isEmpty() || lines.isEmpty() || !lines.all { it.first.isNotEmpty() && it.second.isNotEmpty() }) throw Api(400, "Thiếu câu hoặc người nói")
        val newGender = BookEdits.pyStrip(field(body, "newGender"))
        if (newGender.isNotEmpty() && newGender !in NEW_GENDERS) throw Api(400, "Giới của người mới không hợp lệ")
        val (_, index, cast) = fresh(dir)
        for ((stableId, sha) in lines) {
            val problem = BookWishes.speakerProblem(index, cast, stableId, sha, speaker, newGender)
            if (problem != null) throw Api(400, SPEAKER_PROBLEMS[problem] ?: "Không đổi được người nói câu này")
        }
        val at = now()
        BookWishes.requestSpeakers(dir, lines, speaker, at, newGender)
        val alias = clip(orText(body, "alias"), 200)
        val remembered = alias.isNotEmpty() && BookWishes.requestAlias(dir, alias, speaker, at)
        return JSONObject().put("lines", lines.size).put("speaker", speaker).put("new", newGender.isNotEmpty())
            .put("alias", remembered).put("requestedAt", at)
    }

    /** POST /line {stableId, textSha256, kind?, emotion?, intensity?, speaker?, spoken?}. */
    private fun line(dir: java.io.File, body: JSONObject): Any? {
        val stableId = clip(field(body, "stableId"), 120)
        val sha = clip(field(body, "textSha256"), 64)
        val kind = clip(orText(body, "kind"), 20)
        val emotion = clip(orText(body, "emotion"), 20)
        val speaker = clip(orText(body, "speaker"), 200)
        val rawIntensity = body.opt("intensity")
        val intensity: Long? = if (rawIntensity is Number) rawIntensity.toLong() else null
        val spoken: String? = (body.opt("spoken") as? String)?.let { BookEdits.cut(it, 2200) }
        if (stableId.isEmpty() || sha.isEmpty() || !(kind.isNotEmpty() || emotion.isNotEmpty() || intensity != null || speaker.isNotEmpty() || spoken != null)) {
            throw Api(400, "Thiếu câu hoặc thay đổi")
        }
        if (intensity != null && intensity !in 0..BookWishes.INTENSITY_MAX.toLong()) throw Api(400, "Cường độ phải từ 0 tới ${BookWishes.INTENSITY_MAX}")
        val (_, index, cast) = fresh(dir)
        val problem = BookWishes.lineProblem(index, cast, stableId, sha, kind, emotion, speaker, spoken)
        if (problem != null) throw Api(400, LINE_PROBLEMS[problem] ?: "Không đổi được cách đọc câu này")
        BookWishes.requestLine(dir, stableId, sha, kind, emotion, intensity, speaker, spoken, now())
        return JSONObject().put("stableId", stableId).put("kind", kind).put("emotion", emotion)
            .put("intensity", intensity ?: JSONObject.NULL).put("spoken", spoken ?: JSONObject.NULL)
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
        if (character.isEmpty()) throw Api(400, "Thiếu nhân vật")
        if (preset.isEmpty() && gender.isEmpty() && avoid.isEmpty()) throw Api(400, "Thiếu giọng hoặc giới tính")
        val (_, _, cast) = fresh(dir)
        val problem = BookWishes.voiceProblem(cast, character, gender)
        if (problem != null) throw Api(400, VOICE_PROBLEMS[problem] ?: "Không đổi được giọng nhân vật này")
        val at = now()
        BookWishes.requestVoice(dir, character, preset, gender, avoid, at)
        return JSONObject().put("character", character).put("preset", preset).put("gender", gender)
            .put("avoid", avoid).put("requestedAt", at)
    }

    /** POST /review {verdict, stableId}: chưa có hàng đợi "Cần nghe lại" - chỉ phần "Cần thu lại" (ý muốn chờ Studio). */
    private fun review(dir: java.io.File, body: JSONObject): Any? {
        val verdict = body.opt("verdict")
        val none = verdict == null || verdict === JSONObject.NULL
        if (!none && verdict != "ok" && verdict != "redo") throw Api(400, "Phán quyết không hợp lệ")
        val stableId = BookEdits.cut(field(body, "stableId"), 80)
        val (_, index, _) = fresh(dir)
        val found = index.get(stableId)
        if (verdict == "redo" && found != null && BookEdits.truthy(found.second.opt("textSha256"))) {
            BookWishes.requestRetakes(dir, listOf(stableId to BookEdits.pyText(found.second.opt("textSha256"))), now())
        } else if (verdict != "redo") {
            BookWishes.cancelRetake(dir, stableId)
        }
        return JSONObject().put("ok", true)
    }

    /** POST /characters/merge {from, into}: mọi câu nói của người này thành ý muốn "là lời của người kia" + bí danh. */
    private fun mergeCharacters(dir: java.io.File, body: JSONObject): Any? {
        val source = clip(field(body, "from"), 200)
        val target = clip(field(body, "into"), 200)
        if (source.isEmpty() || target.isEmpty() || BookWishes.aliasKey(source) == BookWishes.aliasKey(target)) throw Api(400, "Chọn hai người khác nhau")
        val (_, index, cast) = fresh(dir)
        val found = BookWishes.speakerLines(index, cast, source)
        if (found.isEmpty()) throw Api(400, "Người này không còn câu nói nào để gộp")
        val problem = BookWishes.speakerProblem(index, cast, found[0].first, found[0].second, target)
        if (problem != null) throw Api(400, SPEAKER_PROBLEMS[problem] ?: "Không gộp được vào người này")
        val at = now()
        BookWishes.requestSpeakers(dir, found, target, at)
        BookWishes.requestAlias(dir, source, target, at)
        return JSONObject().put("lines", found.size).put("requestedAt", at)
    }

    /** POST /chapters/<n>/retake: thu lại MỌI câu của chương - một lần bấm, bỏ thì bỏ cả nhóm. */
    private fun chapterRetake(dir: java.io.File, chapter: String): Any? {
        val (_, index, _) = fresh(dir)
        val found = BookWishes.chapterLines(index, chapter.toLongOrNull() ?: -1L)
        if (found.isEmpty()) throw Api(400, "Chương này chưa có câu nào đã thu để thu lại.")
        val at = now()
        BookWishes.requestRetakes(dir, found, at)
        return JSONObject().put("lines", found.size).put("requestedAt", at)
    }

    /** POST /pending-changes/withdraw {section, key, keys?, requestedAt}: bỏ một thay đổi khỏi danh sách chờ. */
    private fun pendingWithdraw(dir: java.io.File, body: JSONObject): Any? {
        val section = orText(body, "section")
        val key = orText(body, "key")
        val at = requestedAt(body)
        if (section !in BookWishes.SECTIONS || key.isEmpty() || at <= 0) throw Api(400, "Thiếu thay đổi cần bỏ")
        val group = if (section in BookWishes.byClick) {
            (body.opt("keys") as? JSONArray)?.let { list -> (0 until list.length()).mapNotNull { list.opt(it) as? String } }?.take(5000) ?: emptyList()
        } else emptyList()
        val mine = BookWishes.madeAt(dir, section, group.ifEmpty { listOf(key) }, at)
        if (mine.isEmpty()) throw Api(409, "Thay đổi này vừa được thay bằng một lựa chọn sau - mở lại hộp để xem.")
        BookWishes.withdraw(dir, section, mine.keys.toList(), at)
        return JSONObject().put("withdrawn", mine.size)
    }

    /** GET /work, /casting, /pronunciations: bản chụp trong file dự án; 404 khi cuốn không có (cuốn từ file `.abook`, hay file không kèm). */
    private fun projectView(dir: java.io.File, name: String): Any? =
        ProjectDocument.view(dir, name) ?: throw Api(404, "File dự án này không kèm bản chụp của màn đó")

    /** GET /chapters/<n>/script: chữ đọc theo đã qua lớp sửa. */
    private fun script(dir: java.io.File, chapter: String): Any? =
        chapter.toLongOrNull()?.let { BookEdits.script(dir, BookEdits.rawBook(dir), it) } ?: throw Api(404, "Không có chương này")
}
