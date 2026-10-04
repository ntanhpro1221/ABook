package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.Normalizer
import java.util.Locale

/**
 * Nhạc nền cho sách nghe bằng "Nghe ngay" - bản Kotlin của abook/webui/music_playlist.py (docs/LISTEN_ANYTHING.md mục 4). Sách chỉ có
 * chữ không có không khí từng cảnh, nên người nghe chọn một DANH SÁCH PHÁT cho cả cuốn (`music.playlist` của lớp sửa - [BookEdits]):
 * mã một danh sách của danh mục ([MusicCatalog], mục `playlists` của mục lục), [MINE] = "Nhạc của tôi" ([MusicStore]), hay [OFF] = tắt.
 * Chưa chọn gì (không có khoá) thì máy TỰ CHỌN danh sách hợp với cuốn ([pick]: luật từ khoá của mục lục danh mục, không thì bản đóng kèm).
 *
 * Trình phát ([MusicBed]) chơi các bài nối nhau theo thứ tự đã trộn sẵn trên MỘT đồng hồ nhạc riêng của cuốn (không theo giây của
 * chương): sang chương mới nhạc chơi tiếp, không bắt đầu lại. Mỗi bài một khoảng trên đồng hồ ấy ([timeline]), bài sau bắt đầu
 * [OVERLAP_SECONDS] trước khi bài trước hết để hai bài chuyển mờ vào nhau như nhạc theo cảnh. Chỉ org.json: chạy trong test JVM.
 */
object Playlists {
    const val MINE = "mine"
    /** Khớp [ID] nhưng không phải mã danh sách: `music.playlist` = "off" là tắt nhạc nền. */
    const val OFF = "off"
    /** Bài không biết độ dài (thông tin danh mục thiếu): khoảng mặc định trên đồng hồ - bài vẫn lặp liền nếu ngắn hơn. */
    const val FALLBACK_SECONDS = 180.0
    /** Bằng thời gian chuyển mờ của [MusicBed]: bài sau vào lúc bài trước bắt đầu mờ đi, bài trước tắt hẳn đúng lúc nó hết. */
    const val OVERLAP_SECONDS = 2.0
    private val ID = Regex("[a-z0-9_]{1,40}")
    private const val TEXT_MAX = 200

    private fun text(value: Any?): String =
        if (value is String) value.split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ").take(TEXT_MAX) else ""

    /** `music_playlist.catalogue_playlists`: các danh sách đúng hình dạng {id, name, description, minutes, tracks}; mã lạ / trùng / "mine",
     *  hay không có link https:// nào thì bỏ. */
    fun catalogue(manifest: JSONObject): List<JSONObject> {
        val out = ArrayList<JSONObject>()
        val seen = HashSet<String>()
        val items = manifest.optJSONArray("playlists") ?: return out
        for (index in 0 until items.length()) {
            val item = items.opt(index) as? JSONObject ?: continue
            val id = item.opt("id") as? String ?: continue
            if (!ID.matches(id) || id == MINE || id == OFF || id in seen) continue
            val raw = item.optJSONArray("tracks") ?: continue
            val links = LinkedHashSet<String>()
            for (at in 0 until raw.length()) (raw.opt(at) as? String)?.takeIf { it.startsWith("https://") }?.let { links.add(it) }
            if (links.isEmpty()) continue
            seen.add(id)
            val minutes = (item.opt("minutes") as? Number)?.takeIf { it.toDouble() > 0 }?.toInt() ?: 0
            out.add(JSONObject().put("id", id).put("name", text(item.opt("name")).ifEmpty { id })
                .put("description", text(item.opt("description"))).put("minutes", minutes).put("tracks", JSONArray(links.toList())))
        }
        return out
    }

    /** Cho menu chọn (không kèm link): {id, name, description, minutes, count}. */
    fun summaries(playlists: List<JSONObject>): JSONArray = JSONArray(playlists.map { item ->
        JSONObject().put("id", item.getString("id")).put("name", item.getString("name")).put("description", item.getString("description"))
            .put("minutes", item.getInt("minutes")).put("count", item.getJSONArray("tracks").length())
    })

    /** Link của danh sách `id` đúng thứ tự trộn sẵn; danh mục không (còn) có danh sách ấy thì rỗng. */
    fun linksOf(playlists: List<JSONObject>, id: String): List<String> {
        val tracks = playlists.firstOrNull { it.getString("id") == id }?.getJSONArray("tracks") ?: return emptyList()
        return (0 until tracks.length()).map { tracks.getString(it) }
    }

    /** Một bài trong hàng phát: độ dài (giây, null = không biết) và độ khuếch đại đã tính ([MusicGain.cueGainDb], công thức Pha 4). */
    data class Track(val link: String, val duration: Double?, val gainDb: Double)

    private fun number(value: Any?): Double? = (value as? Number)?.toDouble()?.takeIf { it.isFinite() }

    /**
     * `music_playlist.queue` + `music_plan.apply_gain`: hàng bài theo đúng thứ tự `links`, bỏ bài máy này không dùng được (`available`);
     * mỗi bài nằm `levelDb` LU dưới giọng theo độ to (`lufs`) và độ lấn dải tiếng nói (`speechBand`) của nó trong `infos`.
     */
    fun queue(links: List<String>, infos: Map<String, JSONObject>, levelDb: Double, available: (String) -> Boolean = { true }): List<Track> =
        links.filter(available).map { link ->
            val info = infos[link]
            val duration = number(info?.opt("duration"))?.takeIf { it > 0 }
            Track(link, duration, MusicGain.cueGainDb(levelDb, number(info?.opt("lufs")), number(info?.opt("speechBand"))))
        }

    /** Khoảng của một bài trên đồng hồ nhạc của cuốn: [start, end) giây. */
    data class Span(val start: Double, val end: Double, val track: Track, val index: Int)

    /** Các bài nối nhau trên đồng hồ nhạc: mỗi bài dài (độ dài - [OVERLAP_SECONDS]), ít nhất 1 giây. */
    fun timeline(tracks: List<Track>): List<Span> {
        var at = 0.0
        return tracks.mapIndexed { index, track ->
            val length = maxOf(1.0, (track.duration ?: FALLBACK_SECONDS) - OVERLAP_SECONDS)
            Span(at, at + length, track, index).also { at += length }
        }
    }

    /** Bài đang ở giây `seconds` của đồng hồ nhạc (hết danh sách thì quay lại bài đầu) và giây trong bài ấy. Rỗng -> null. */
    fun at(spans: List<Span>, seconds: Double): Pair<Span, Double>? {
        val total = spans.lastOrNull()?.end ?: return null
        val wrapped = ((seconds % total) + total) % total
        val span = spans.firstOrNull { wrapped >= it.start && wrapped < it.end } ?: spans.last()
        return span to (wrapped - span.start)
    }

    // ---- máy tự chọn danh sách ----------------------------------------------------------------------------------------------
    // Bản Kotlin của phần "máy tự chọn" trong abook/webui/music_playlist.py (bản tham chiếu: LLM_Train/music/listen_genre). Hai bên phải
    // ra cùng mã và cùng điểm trên bộ ví dụ dùng chung tests/fixtures/playlist_picker/cases.json (PlaylistPickerTest).
    // Regex Android: KHÔNG dùng cờ UNICODE_CHARACTER_CLASS (ICU văng) - `\w` của Python viết thành lớp ký tự tường minh.

    private const val PICKER_CHARS = 6000
    private const val MIN_CHAPTER = 1500
    private val WORD = Regex("[\\p{L}\\p{N}_]+")
    // Python dùng re.IGNORECASE: ở đây so trên chữ thường của dòng đầu (cờ Unicode của Regex dễ văng trên ICU).
    private val FRONT = Regex("^(minh ho[aạ]|l[oờ]i b[aạ]t|m[uụ]c l[uụ]c|l[oờ]i t[aá]c gi[aả]|l[oờ]i d[iị]ch gi[aả]|illustration|afterword|" +
        "table of contents|extra|ngo[aạ]i truy[eệ]n|side story)")

    /** Khoảng trắng của Python `str.isspace` / `str.split()`. */
    private fun isPySpace(c: Char): Boolean = when (c) {
        '\t', '\n', '\u000b', '\u000c', '\r', ' ', '\u001c', '\u001d', '\u001e', '\u001f', '\u0085', ' ', ' ', ' ', ' ',
        ' ', ' ', '　' -> true
        in ' '..' ' -> true
        else -> false
    }

    /** Chỗ ngắt dòng của Python `str.splitlines()`. */
    private fun isLineBreak(c: Char): Boolean = c == '\n' || c == '\r' || c == '\u000b' || c == '\u000c' || c == '\u001c' || c == '\u001d' ||
        c == '\u001e' || c == '\u0085' || c == ' ' || c == ' '

    private fun pyStrip(text: String): String = text.trim { isPySpace(it) }

    private fun codePoints(text: String): Int = text.codePointCount(0, text.length)

    /** `music_playlist.words`: các từ (`\w+`, NFC, chữ thường) nối bằng một dấu cách, có dấu cách hai đầu. */
    private fun words(text: String): String =
        " " + WORD.findAll(Normalizer.normalize(text, Normalizer.Form.NFC).lowercase(Locale.ROOT)).joinToString(" ") { it.value } + " "

    /** `music_playlist.strip_marks`: bỏ dấu (đ -> d, NFD rồi bỏ dấu kết hợp Mn). */
    private fun stripMarks(text: String): String {
        val decomposed = Normalizer.normalize(text.replace('đ', 'd').replace('Đ', 'D'), Normalizer.Form.NFD)
        val out = StringBuilder()
        decomposed.codePoints().forEach { if (Character.getType(it) != Character.NON_SPACING_MARK.toInt()) out.appendCodePoint(it) }
        return out.toString()
    }

    /** `str.count` (không chồng lấn): số lần ` cụm ` xuất hiện trong chuỗi từ `haystack`. */
    private fun count(haystack: String, phrase: String): Int {
        val needle = " $phrase "
        var found = 0
        var at = haystack.indexOf(needle)
        while (at >= 0) {
            found++
            at = haystack.indexOf(needle, at + needle.length)
        }
        return found
    }

    /** `music_playlist._squash`: bỏ dòng trống, mỗi dòng gộp khoảng trắng về một dấu cách. */
    private fun squash(text: String): String {
        val out = StringBuilder()
        var start = 0
        for (end in 0..text.length) {
            if (end < text.length && !isLineBreak(text[end])) continue
            val tokens = ArrayList<String>()
            var word = -1
            for (at in start..end) {
                val space = at == end || isPySpace(text[at])
                if (space && word >= 0) {
                    tokens.add(text.substring(word, at))
                    word = -1
                } else if (!space && word < 0) {
                    word = at
                }
            }
            if (tokens.isNotEmpty()) {
                if (out.isNotEmpty()) out.append('\n')
                out.append(tokens.joinToString(" "))
            }
            start = end + 1
        }
        return out.toString()
    }

    /** `music_playlist.picker_body`: thân truyện cho bộ chọn - bỏ chương ngắn / chương phụ, mỗi dòng gộp khoảng trắng, [PICKER_CHARS] ký tự đầu.
     *  `chapters` đọc lười: đủ chữ rồi thì không đọc chương sau. */
    fun pickerBody(chapters: Sequence<String>): String {
        val parts = ArrayList<String>()
        var total = 0
        for (chapter in chapters) {
            val text = pyStrip(chapter)
            val first = text.takeWhile { !isLineBreak(it) }
            if (codePoints(text) < MIN_CHAPTER || FRONT.containsMatchIn(pyStrip(first).lowercase(Locale.ROOT))) continue
            parts.add(squash(text))
            total += codePoints(parts.last()) + 1
            if (total > PICKER_CHARS) break
        }
        val body = parts.joinToString("\n")
        return if (codePoints(body) <= PICKER_CHARS) body else body.substring(0, body.offsetByCodePoints(0, PICKER_CHARS))
    }

    private fun isNumber(value: Any?): Boolean = value is Number && value.toDouble().isFinite()

    private fun isInteger(value: Any?): Boolean = value is Int || value is Long

    /** `music_playlist.valid_picker`: luật đúng hình dạng (kiểm chặt); `ids` cho thì default và mọi mã trong `order` / `playlists` phải nằm trong đó. */
    fun validPicker(picker: JSONObject?, ids: Set<String>? = null): Boolean {
        if (picker == null || !isInteger(picker.opt("version"))) return false
        if (!listOf("cap", "title_weight", "min_score").all { isNumber(picker.opt(it)) }) return false
        val order = picker.opt("order") as? JSONArray ?: return false
        val playlists = picker.opt("playlists") as? JSONObject ?: return false
        val default = picker.opt("default") as? String ?: return false
        if (order.length() == 0 || (0 until order.length()).any { order.opt(it) !is String }) return false
        val codes = playlists.keys().asSequence().toList()
        for (code in codes) {
            val item = playlists.opt(code) as? JSONObject ?: return false
            if (item.has("title")) {
                val titles = item.opt("title") as? JSONArray ?: return false
                if ((0 until titles.length()).any { titles.opt(it) !is String }) return false
            }
            if (item.has("text")) {
                val text = item.opt("text") as? JSONObject ?: return false
                if (text.keys().asSequence().any { !isNumber(text.opt(it)) }) return false
            }
            if (item.has("prior") && !isNumber(item.opt("prior"))) return false
        }
        if (ids != null) {
            if (default !in ids || codes.any { it !in ids }) return false
            if ((0 until order.length()).any { order.getString(it) !in ids }) return false
        }
        return true
    }

    /** `music_playlist.usable_picker`: (luật, nguồn) - `manifest["playlistPicker"]` nếu hợp lệ với các danh sách của chính mục lục ấy
     *  ("manifest"), không thì bản đóng kèm `bundled` ("bundled"); không có cả hai thì (null, "none"). `manifest` null = chưa tải được danh mục. */
    fun usablePicker(manifest: JSONObject?, bundled: JSONObject?): Pair<JSONObject?, String> {
        val picker = manifest?.opt("playlistPicker") as? JSONObject
        if (manifest != null && picker != null && validPicker(picker, catalogue(manifest).map { it.getString("id") }.toSet())) return picker to "manifest"
        return if (validPicker(bundled)) bundled to "bundled" else null to "none"
    }

    /** `music_playlist.pick_scores`: điểm từng danh sách của `picker` cho cuốn tên `title` với các chương `chapters`; luật hỏng thì null. */
    fun pickScores(picker: JSONObject?, title: String, chapters: Sequence<String>): Map<String, Double>? {
        if (picker == null || !validPicker(picker)) return null
        val bodyWords = words(pickerBody(chapters))
        val titleWords = words(stripMarks(title))
        val cap = picker.getDouble("cap")
        val titleWeight = picker.getDouble("title_weight")
        val playlists = picker.getJSONObject("playlists")
        val out = LinkedHashMap<String, Double>()
        for (code in playlists.keys().asSequence().toList()) {
            val item = playlists.getJSONObject(code)
            val text = LinkedHashMap<String, Double>() // cụm trùng sau chuẩn hoá: cụm sau đè trọng số, giữ chỗ cụm đầu (như dict của Python)
            item.optJSONObject("text")?.let { raw -> for (key in raw.keys()) text[words(key).trim(' ')] = raw.getDouble(key) }
            val titles = item.optJSONArray("title")?.let { raw -> (0 until raw.length()).map { words(stripMarks(raw.getString(it))).trim(' ') } } ?: emptyList()
            var score = 0.0
            for ((key, weight) in text) score += weight * minOf(count(bodyWords, key).toDouble(), cap)
            score += titleWeight * titles.count { count(titleWords, it) > 0 }
            out[code] = score + item.optDouble("prior", 0.0)
        }
        return out
    }

    /** `music_playlist.pick`: mã danh sách hợp với cuốn - điểm cao nhất (hoà thì theo `order`), dưới `min_score` thì `default`. Luật hỏng thì null. */
    fun pick(picker: JSONObject?, title: String, chapters: Sequence<String>): String? {
        val scores = pickScores(picker, title, chapters) ?: return null
        val order = picker!!.getJSONArray("order")
        var best = order.getString(0)
        for (index in 1 until order.length()) {
            val code = order.getString(index)
            if ((scores[code] ?: 0.0) > (scores[best] ?: 0.0)) best = code
        }
        return if ((scores[best] ?: 0.0) >= picker.getDouble("min_score")) best else picker.getString("default")
    }

    private val autoCache = HashMap<Triple<String, String, Long>, String?>()

    /** Sách CHỈ CÓ CHỮ (`packages.text_book`): có chương và mọi chương là chữ không audio. */
    private fun isTextBook(book: JSONObject): Boolean {
        val chapters = book.optJSONArray("chapters") ?: return false
        val items = (0 until chapters.length()).mapNotNull { chapters.optJSONObject(it) }
        return items.isNotEmpty() && items.all { BookEdits.truthy(it.opt("text")) && !BookEdits.truthy(it.opt("file")) }
    }

    /**
     * `server._auto_playlist`: danh sách máy chọn cho sách CHỈ CÓ CHỮ ở thư mục `dir` khi người nghe chưa chọn gì (`music.playlist` không có
     * khoá): luật của mục lục danh mục (`manifest`, null = chưa tải được) nếu hợp lệ, không thì bản đóng kèm `bundled`; đầu vào là tên sách +
     * chữ các chương. Đệm theo (mã sách, nguồn luật, version luật). Không chọn được (không phải sách chữ, luật hỏng) thì null. Chặn - chạy ở luồng nền.
     */
    fun autoPlaylist(dir: File, manifest: JSONObject?, bundled: JSONObject?): String? {
        val book = BookEdits.rawBook(dir)
        if (!isTextBook(book)) return null
        val (picker, source) = usablePicker(manifest, bundled)
        if (picker == null) return null
        val key = Triple(dir.name, source, picker.getLong("version"))
        synchronized(autoCache) { if (autoCache.containsKey(key)) return autoCache[key] }
        var unread = false
        val chapters = sequence {
            val items = book.getJSONArray("chapters")
            for (index in 0 until items.length()) {
                val entry = items.optJSONObject(index)?.optString("text").orEmpty()
                val file = runCatching { Store.contained(dir, entry) }.getOrNull()?.takeIf { it.isFile }
                if (file == null) {
                    unread = true // chữ chưa có ở máy này: lần sau thử lại, đừng đệm
                } else {
                    // Python đọc chữ với newline phổ quát (\r\n, \r thành \n): độ dài chương phải đếm như nhau.
                    yield(file.readText(Charsets.UTF_8).replace("\r\n", "\n").replace('\r', '\n'))
                }
            }
        }
        val code = pick(picker, BookEdits.pyText(book.opt("title")), chapters)
        if (!unread) synchronized(autoCache) { autoCache[key] = code }
        return code
    }
}
