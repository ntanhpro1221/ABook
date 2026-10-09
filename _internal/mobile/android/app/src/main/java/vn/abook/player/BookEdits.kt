package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.readaloud.Readings
import java.io.File
import java.io.IOException
import java.math.BigDecimal
import java.math.BigInteger
import java.math.RoundingMode
import java.text.Normalizer

/**
 * Lớp SỬA của người nghe trên một cuốn mở từ file `.abook` - bản Kotlin của abook/webui/book_edits.py (docs/EDITING.md); hai
 * bản cài đọc chung bộ ví dụ tests/fixtures/book_edits/ nên phải ra ĐÚNG cùng kết quả, cùng câu báo lỗi.
 *
 * Lớp sách (book.json, cast.json, scripts/, nhạc, audio, bìa) là của người làm sách và không bao giờ bị sửa tại chỗ. Người
 * nghe đổi được tên sách, bìa, tên nhân vật, tên chương, nhạc nền (bật/tắt, mức, im lặng một đoạn, đổi một đoạn sang bài trong
 * "Nhạc của tôi" - [MusicStore]) và ghi ý muốn chờ Studio (cách
 * đọc tên, người nói, giọng... - [BookWishes], không bao giờ áp vào sách); chúng nằm ở `edits.json` (+
 * `edits/cover.jpg`) trong thư mục sách, và mọi nơi đọc lớp sách (Store.manifest, LibraryPlugin.readText, LibraryServer) đi
 * qua đây để thấy bản đã sửa.
 *
 * `edits.json` là dữ liệu của người lạ (đi theo file `.abook` phiên bản 4): [validate] chặt - đúng khoá, đúng kiểu, có trần cỡ
 * và độ dài, chữ phải đã sạch (không sửa hộ) - và file sai thì bị từ chối cả file. Không mang tên máy hay tên người nào.
 * Chỉ dùng org.json và java.io: chạy được cả trong test JVM.
 */
object BookEdits {
    const val EDITS_FILE = "edits.json"
    const val EDITS_COVER = "edits/cover.jpg"
    const val FORMAT = "abook-edits"
    const val VERSION = 1
    const val MAX_EDITS_BYTES = 1024 * 1024
    const val MAX_COVER_BYTES = 8 * 1024 * 1024
    const val TITLE_MAX = 160
    const val NAME_MAX = 80
    private const val MAX_CHARACTERS = 2000
    private const val MAX_CHAPTERS = 5000
    private const val MAX_SILENCED = 5000
    private const val MAX_PINS = 5000
    private const val MAX_SKIP_LINES = 20 // dòng bỏ khỏi phần đọc, mỗi chương (book_edits.MAX_SKIP_LINES)
    private const val SKIP_LINE_MAX = 300
    private const val TRACK_TEXT_MAX = 200 // tên bài / nghệ sĩ trong thẻ file nhạc (music_local._TAG_MAX)
    const val MAX_READINGS = 2000 // cách đọc riêng của một cuốn
    private const val READING_WORD_MAX = NAME_MAX // chữ hiện của một cách đọc (một từ)
    private const val READING_SPOKEN_MAX = 200 // chữ đọc
    private const val LEVEL_MIN = -40.0
    private const val LEVEL_MAX = -6.0
    private const val DEFAULT_LEVEL_DB = -20.0 // music_plan.DEFAULT_LEVEL_DB
    private val TOP_KEYS = setOf("format", "version", "title", "cover", "characters", "chapters", "skip", "readings", "music", "wishes")
    const val TOO_BIG = "Quá nhiều thay đổi đang chờ trong cuốn này - hãy lưu, áp bớt vào dự án rồi làm tiếp."
    private val COVER_KEYS = setOf("color", "width", "height", "version")
    private val MUSIC_KEYS = setOf("enabled", "levelDb", "silenced", "pins", "tracks", "playlist")
    private val TRACK_KEYS = setOf("ext", "title", "creator", "duration", "lufs")
    private val LOCAL_LINK = Regex("local:[0-9a-f]{40}")
    private val PLAYLIST = Regex("[a-z0-9_]{1,40}") // mã danh sách phát của danh mục, [Playlists.MINE] = "Nhạc của tôi", hay [Playlists.OFF] = tắt (không có khoá = máy tự chọn)
    private val CHAPTER_KEYS = setOf("title", "subtitle")
    private val CHAPTER_ID = Regex("[0-9]{1,9}")
    private val CUE_KEY = Regex("[0-9]{1,9}:[0-9]{1,12}")
    private val COLOR = Regex("#[0-9a-f]{6}")
    /** continuation.PART_SUFFIX: hậu tố " · Phần 2", " (phần 2)", " - phần 2" ở cuối tên. Không dùng cờ `U`: ICU của Android từ chối nó (sập khi nạp lớp); `\s` của ICU vốn đã theo Unicode. */
    private val PART_SUFFIX = Regex("""(?iu)\s*(?:\(phần\s*\d+\)|[·|:—–-]\s*phần\s*\d+)\s*$""")
    private val lock = Any()

    /** Sửa không hợp lệ, hay `edits.json` không dùng được - câu chữ để người dùng đọc. */
    class EditsError(message: String) : Exception(message)

    // ---- làm sạch chữ người gõ (cùng luật máy chủ: store.clean_title, book_edits.clean_text) ---------------------

    private fun isControl(codePoint: Int): Boolean = when (Character.getType(codePoint)) {
        Character.CONTROL.toInt(), Character.FORMAT.toInt(), Character.SURROGATE.toInt(), Character.PRIVATE_USE.toInt(),
        Character.UNASSIGNED.toInt() -> true // loại "C*" của Unicode
        else -> false
    }

    internal fun isSpace(char: Char) = Character.isWhitespace(char) || Character.isSpaceChar(char)

    private fun codePoints(text: String): List<Int> = text.codePoints().toArray().toList()

    internal fun cut(text: String, limit: Int): String =
        if (text.codePointCount(0, text.length) <= limit) text else text.substring(0, text.offsetByCodePoints(0, limit))

    /** Chữ như `str(value or "")` của Python. */
    internal fun pyText(value: Any?): String = when {
        value == null || value === JSONObject.NULL || value == false -> ""
        value is Number && value.toDouble() == 0.0 -> ""
        else -> value.toString()
    }

    /** Như `str(value)` của Python (None -> "None"). */
    internal fun pyStr(value: Any?): String = when {
        value == null || value === JSONObject.NULL -> "None"
        value is Boolean -> if (value) "True" else "False"
        value is Double -> StrictJson.pyFloat(value)
        else -> value.toString()
    }

    internal fun truthy(value: Any?): Boolean = when {
        value == null || value === JSONObject.NULL -> false
        value is Boolean -> value
        value is Number -> value.toDouble() != 0.0
        value is String -> value.isNotEmpty()
        value is JSONObject -> value.length() > 0
        value is JSONArray -> value.length() > 0
        else -> true
    }

    /** `str.strip()` của Python. */
    internal fun pyStrip(text: String): String = text.trim { isSpace(it) }

    /**
     * Chữ người gõ: NFC (trừ khi `normalize` tắt - như `store.clean_title`), ký tự điều khiển thành dấu cách, gộp khoảng
     * trắng, cắt ở `limit` ký tự (điểm mã).
     */
    fun cleanText(value: Any?, limit: Int, normalize: Boolean = true): String {
        val source = pyText(value)
        val text = if (normalize) Normalizer.normalize(source, Normalizer.Form.NFC) else source
        val spaced = StringBuilder()
        for (codePoint in codePoints(text)) spaced.appendCodePoint(if (isControl(codePoint)) ' '.code else codePoint)
        val joined = spaced.toString().split(Regex("[\\p{Z}\\s]+")).filter { it.isNotEmpty() }.joinToString(" ")
        return pyStrip(cut(joined, limit))
    }

    /**
     * Chữ đã ở dạng `cleanText` ghi ra: không ký tự điều khiển, không khoảng trắng nào ngoài dấu cách đơn, không dấu cách
     * đầu/cuối/kép, không dài quá `limit`. [validate] KHÔNG sửa chữ của người lạ - gặp chữ chưa sạch là từ chối.
     */
    internal fun isClean(text: String, limit: Int): Boolean {
        if (text.codePointCount(0, text.length) > limit || text.startsWith(' ') || text.endsWith(' ') || text.contains("  ")) return false
        return codePoints(text).none { isControl(it) || (it != ' '.code && Character.isValidCodePoint(it) && it < 0x10000 && isSpace(it.toChar())) }
    }

    private fun hasControl(text: String) = codePoints(text).any { isControl(it) }

    // ---- đọc / kiểm / ghi ------------------------------------------------------------------------------------------

    fun empty(): JSONObject = JSONObject().put("format", FORMAT).put("version", VERSION)

    fun isEmpty(edits: JSONObject) = count(edits) == 0

    /**
     * Số thay đổi "áp ngay" người nghe đã làm: tên sách, bìa, mỗi tên nhân vật, mỗi chương đổi tên, bật/tắt nhạc, mức nhạc, mỗi
     * đoạn nhạc im lặng, mỗi đoạn nhạc đổi sang bài của người nghe, danh sách phát đã chọn. Không kể ý muốn chờ Studio ([BookWishes]) - chúng chưa áp vào
     * đâu cả.
     */
    fun countApplied(edits: JSONObject): Int {
        val music = edits.optJSONObject("music")
        return (if (edits.has("title")) 1 else 0) + (if (edits.has("cover")) 1 else 0) +
            (edits.optJSONObject("characters")?.length() ?: 0) + (edits.optJSONObject("chapters")?.length() ?: 0) +
            // Một dòng bỏ ở trăm chương: một thay đổi.
            (edits.optJSONObject("skip")?.let { skip -> names(skip).flatMap { skipLines(skip, it) }.toSet().size } ?: 0) +
            (edits.optJSONObject("readings")?.length() ?: 0) +
            (if (music?.has("enabled") == true) 1 else 0) + (if (music?.has("levelDb") == true) 1 else 0) +
            (music?.optJSONArray("silenced")?.length() ?: 0) + (music?.optJSONObject("pins")?.length() ?: 0) +
            (if (music?.has("playlist") == true) 1 else 0)
    }

    /** Số ý muốn chờ Studio ([BookWishes.count]). */
    fun countWishes(edits: JSONObject): Int = BookWishes.count(edits.optJSONObject("wishes"))

    /** Số thay đổi người nghe đã làm (cho dòng "N thay đổi" và việc mời lưu): thay đổi áp ngay + ý muốn chờ Studio. */
    fun count(edits: JSONObject): Int = countApplied(edits) + countWishes(edits)

    internal fun isNumber(value: Any?) = value is Number && !(value is Double && (value.isNaN() || value.isInfinite()))

    private fun isInteger(value: Any?) = value is Int || value is Long || value is BigInteger

    internal fun names(value: JSONObject): List<String> = value.keys().asSequence().toList()

    /** `edits.json` đã đọc -> dạng chuẩn; sai thì [EditsError]. Khoá lạ, kiểu sai, chữ chưa sạch, quá trần: từ chối. */
    fun validate(raw: Any?): JSONObject {
        if (raw !is JSONObject || names(raw).any { it !in TOP_KEYS }) throw EditsError("Phần sửa của sách có mục lạ.")
        val version = raw.opt("version")
        if (raw.opt("format") != FORMAT || version !is Number || version.toDouble() != VERSION.toDouble()) {
            throw EditsError("Phần sửa của sách không đúng định dạng hay mới hơn app - hãy cập nhật app.")
        }
        val out = empty()
        if (raw.has("title")) {
            val title = raw.opt("title")
            if (title !is String || title.isEmpty() || !isClean(title, TITLE_MAX)) throw EditsError("Tên sách trong phần sửa không hợp lệ.")
            out.put("title", title)
        }
        if (raw.has("cover")) out.put("cover", validateCover(raw.opt("cover")))
        if (raw.has("characters")) {
            val people = raw.opt("characters")
            if (people !is JSONObject || people.length() > MAX_CHARACTERS) {
                throw EditsError("Phần đổi tên nhân vật không hợp lệ hay quá dài.")
            }
            val kept = JSONObject()
            for (name in names(people)) {
                val shown = people.opt(name)
                if (name.isEmpty() || name.codePointCount(0, name.length) > 200 || hasControl(name)) {
                    throw EditsError("Tên nhân vật trong phần sửa không hợp lệ.")
                }
                if (shown !is String || shown.isEmpty() || !isClean(shown, NAME_MAX)) {
                    throw EditsError("Tên hiện của một nhân vật trong phần sửa không hợp lệ.")
                }
                kept.put(name, shown)
            }
            out.put("characters", kept)
        }
        if (raw.has("chapters")) {
            val chapters = raw.opt("chapters")
            if (chapters !is JSONObject || chapters.length() > MAX_CHAPTERS) throw EditsError("Phần đổi tên chương không hợp lệ hay quá dài.")
            val kept = JSONObject()
            for (key in names(chapters)) {
                val entry = chapters.opt(key)
                if (!CHAPTER_ID.matches(key) || entry !is JSONObject || entry.length() == 0 || names(entry).any { it !in CHAPTER_KEYS }) {
                    throw EditsError("Một mục đổi tên chương không hợp lệ.")
                }
                val copy = JSONObject()
                for (field in names(entry)) {
                    val text = entry.opt(field)
                    if (text !is String || !isClean(text, TITLE_MAX) || (field == "title" && text.isEmpty())) {
                        throw EditsError("Tên một chương trong phần sửa không hợp lệ.")
                    }
                    copy.put(field, text)
                }
                kept.put(key, copy)
            }
            out.put("chapters", kept)
        }
        if (raw.has("skip")) out.put("skip", validateSkip(raw.opt("skip")))
        if (raw.has("readings")) out.put("readings", validateReadings(raw.opt("readings")))
        if (raw.has("music")) out.put("music", validateMusic(raw.opt("music")))
        if (raw.has("wishes")) out.put("wishes", BookWishes.validate(raw.opt("wishes")))
        return out
    }

    /** `skip`: {mã chương: [dòng người nghe bỏ khỏi phần đọc]} (`book_edits._validate_skip`). */
    private fun validateSkip(skip: Any?): JSONObject {
        if (skip !is JSONObject || skip.length() > MAX_CHAPTERS) throw EditsError("Phần bỏ dòng khỏi phần đọc không hợp lệ hay quá dài.")
        val out = JSONObject()
        for (key in names(skip)) {
            val lines = skip.opt(key)
            val list = (lines as? JSONArray)?.let { array -> (0 until array.length()).map { array.opt(it) } }
            if (!CHAPTER_ID.matches(key) || list == null || list.isEmpty() || list.size > MAX_SKIP_LINES || list.toSet().size != list.size ||
                list.any { it !is String || it.isEmpty() || !isClean(it, SKIP_LINE_MAX) }
            ) {
                throw EditsError("Một dòng bỏ khỏi phần đọc trong phần sửa không hợp lệ.")
            }
            out.put(key, JSONArray(list.map { it as String }.sortedWith { a, b -> byCodePoints(a, b) }))
        }
        return out
    }

    /**
     * `readings` {chữ hiện: chữ đọc} (`book_edits.validate_readings`): chữ hiện là MỘT từ hay một cụm 2..6 từ liền nhau đã sạch ([Readings.isKey]), chữ đọc sạch,
     * không rỗng, khác chữ hiện. Dùng cả cho cách đọc gửi kèm lần "Nghe thử" (chưa lưu).
     */
    fun validateReadings(readings: Any?): JSONObject {
        if (readings !is JSONObject || readings.length() == 0 || readings.length() > MAX_READINGS) {
            throw EditsError("Phần cách đọc riêng không hợp lệ hay quá dài.")
        }
        val out = JSONObject()
        for (shown in names(readings).sortedWith { a, b -> byCodePoints(a, b) }) {
            val spoken = readings.opt(shown)
            if (!isClean(shown, READING_WORD_MAX) || !Readings.isKey(shown) || spoken !is String || spoken.isEmpty() ||
                !isClean(spoken, READING_SPOKEN_MAX) || spoken == shown
            ) {
                throw EditsError("Một cách đọc riêng trong phần sửa không hợp lệ.")
            }
            out.put(shown, spoken)
        }
        return out
    }

    /** Cách đọc riêng của cuốn dưới dạng bảng (để đọc to). */
    fun readingsOf(edits: JSONObject): Map<String, String> =
        edits.optJSONObject("readings")?.let { readings -> names(readings).associateWith { readings.getString(it) } } ?: emptyMap()

    private fun validateCover(cover: Any?): Any {
        if (cover === JSONObject.NULL) return JSONObject.NULL
        val bad = EditsError("Ảnh bìa trong phần sửa không hợp lệ.")
        if (cover !is JSONObject || names(cover).any { it !in COVER_KEYS }) throw bad
        val color = if (cover.has("color")) cover.opt("color") else ""
        val numbers = listOf("width", "height", "version").map { if (cover.has(it)) cover.opt(it) else 0L }
        if (color !is String || (color.isNotEmpty() && !COLOR.matches(color))) throw bad
        if (numbers.any { !isInteger(it) || it is BigInteger || (it as Number).toLong() !in 0L..10_000_000_000L }) throw bad
        val (width, height, version) = numbers.map { (it as Number).toLong() }
        if (width > 20_000 || height > 20_000) throw bad
        return JSONObject().put("color", color).put("width", width).put("height", height).put("version", version)
    }

    private fun validateMusic(music: Any?): JSONObject {
        if (music !is JSONObject || music.length() == 0 || names(music).any { it !in MUSIC_KEYS }) {
            throw EditsError("Phần sửa nhạc nền không hợp lệ.")
        }
        val out = JSONObject()
        if (music.has("enabled")) {
            val enabled = music.opt("enabled")
            if (enabled !is Boolean) throw EditsError("Phần sửa nhạc nền không hợp lệ.")
            out.put("enabled", enabled)
        }
        if (music.has("levelDb")) {
            val level = music.opt("levelDb")
            if (!isNumber(level) || (level is Boolean) || (level as Number).toDouble() !in LEVEL_MIN..LEVEL_MAX) {
                throw EditsError("Mức nhạc nền trong phần sửa nằm ngoài khoảng cho phép.")
            }
            out.put("levelDb", level.toDouble())
        }
        if (music.has("playlist")) {
            val playlist = music.opt("playlist")
            if (playlist !is String || !PLAYLIST.matches(playlist)) throw EditsError("Danh sách nhạc nền trong phần sửa không hợp lệ.")
            out.put("playlist", playlist)
        }
        if (music.has("silenced")) {
            val silenced = music.opt("silenced")
            val bad = EditsError("Danh sách đoạn nhạc im lặng trong phần sửa không hợp lệ.")
            if (silenced !is JSONArray || silenced.length() > MAX_SILENCED) throw bad
            val keys = (0 until silenced.length()).map { silenced.opt(it) }
            if (keys.any { it !is String || !CUE_KEY.matches(it) } || keys.toSet().size != keys.size) throw bad
            out.put("silenced", JSONArray(keys.map { it as String }.sorted()))
        }
        val pins = if (music.has("pins")) {
            val raw = music.opt("pins")
            val bad = EditsError("Danh sách đoạn nhạc đã đổi bài trong phần sửa không hợp lệ.")
            if (raw !is JSONObject || raw.length() > MAX_PINS) throw bad
            val sorted = JSONObject()
            for (key in names(raw).sorted()) {
                val link = raw.opt(key)
                if (!CUE_KEY.matches(key) || link !is String || !LOCAL_LINK.matches(link)) throw bad
                sorted.put(key, link)
            }
            out.put("pins", sorted)
            sorted
        } else JSONObject()
        val wanted = names(pins).map { (pins.getString(it)).removePrefix(MusicStore.LOCAL_PREFIX) }.toSet()
        if (music.has("tracks") || wanted.isNotEmpty()) {
            val tracks = music.opt("tracks")
            if (tracks !is JSONObject || names(tracks).toSet() != wanted) {
                throw EditsError("Nhạc đã chọn trong phần sửa không khớp với các đoạn đổi bài.")
            }
            val kept = JSONObject()
            for (sha in names(tracks).sorted()) kept.put(sha, validateTrack(tracks.opt(sha)))
            out.put("tracks", kept)
        }
        return out
    }

    /**
     * Thông tin một bài người nghe đã chọn: đuôi file thật (đúng danh sách của [MusicStore.EXTENSIONS]), tên bài và nghệ sĩ nếu có,
     * độ dài và độ to đo từ chính file. Không có giấy phép / ghi công: ABook không nói gì ngoài tên + nghệ sĩ có sẵn trong file.
     */
    private fun validateTrack(entry: Any?): JSONObject {
        val bad = EditsError("Thông tin một bài nhạc trong phần sửa không hợp lệ.")
        if (entry !is JSONObject || names(entry).any { it !in TRACK_KEYS } || (entry.opt("ext") as? String) !in MusicStore.EXTENSIONS) throw bad
        val out = JSONObject().put("ext", entry.getString("ext"))
        for (key in listOf("title", "creator")) {
            if (!entry.has(key)) continue
            val text = entry.opt(key)
            if (text !is String || text.isEmpty() || !isClean(text, TRACK_TEXT_MAX)) throw bad
            out.put(key, text)
        }
        for ((key, range) in listOf("duration" to (0.0..1e6), "lufs" to (-100.0..20.0))) {
            if (!entry.has(key)) continue
            val value = entry.opt(key)
            if (!isNumber(value) || (value as Number).toDouble() !in range || (key == "duration" && value.toDouble() <= 0.0)) throw bad
            out.put(key, value.toDouble())
        }
        return out
    }

    /** Byte của `edits.json` -> dạng chuẩn ([validate]); quá cỡ hay không phải JSON: [EditsError]. */
    fun parse(data: ByteArray): JSONObject {
        if (data.size > MAX_EDITS_BYTES) throw EditsError("Phần sửa của sách quá lớn.")
        val raw = try {
            val decoder = Charsets.UTF_8.newDecoder()
                .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT)
            StrictJson.parse(decoder.decode(java.nio.ByteBuffer.wrap(data)).toString())
        } catch (error: StrictJson.ParseError) {
            throw EditsError("Phần sửa của sách bị hỏng.")
        } catch (error: java.nio.charset.CharacterCodingException) {
            throw EditsError("Phần sửa của sách bị hỏng.")
        }
        return validate(raw)
    }

    /** Byte ghi ra `edits.json`: khoá xếp cố định, UTF-8, xuống dòng LF - cùng nội dung thì cùng byte. */
    fun dump(edits: JSONObject): ByteArray = (StrictJson.dumps(ordered(edits), 1) + "\n").toByteArray(Charsets.UTF_8)

    internal fun byCodePoints(first: String, second: String): Int {
        val a = codePoints(first)
        val b = codePoints(second)
        for (index in 0 until minOf(a.size, b.size)) if (a[index] != b[index]) return a[index].compareTo(b[index])
        return a.size.compareTo(b.size)
    }

    private fun ordered(edits: JSONObject): Map<String, Any?> {
        val out = LinkedHashMap<String, Any?>()
        out["format"] = FORMAT
        out["version"] = VERSION
        for (key in listOf("title", "cover")) if (edits.has(key)) out[key] = edits.opt(key).let { if (key == "cover") orderedCover(it) else it }
        edits.optJSONObject("characters")?.takeIf { it.length() > 0 }?.let { people ->
            out["characters"] = names(people).sortedWith { a, b -> byCodePoints(a, b) }.associateWith { people.opt(it) }
        }
        edits.optJSONObject("chapters")?.takeIf { it.length() > 0 }?.let { chapters ->
            out["chapters"] = names(chapters).sortedBy { it.toLong() }.associateWith { key ->
                val entry = chapters.getJSONObject(key)
                listOf("title", "subtitle").filter { entry.has(it) }.associateWith { entry.opt(it) }
            }
        }
        edits.optJSONObject("skip")?.takeIf { it.length() > 0 }?.let { skip ->
            out["skip"] = names(skip).sortedBy { it.toLong() }.associateWith { key -> skipLines(skip, key) }
        }
        edits.optJSONObject("readings")?.takeIf { it.length() > 0 }?.let { readings ->
            out["readings"] = names(readings).sortedWith { a, b -> byCodePoints(a, b) }.associateWith { readings.opt(it) }
        }
        edits.optJSONObject("music")?.takeIf { it.length() > 0 }?.let { music ->
            val shown = LinkedHashMap<String, Any?>()
            for (key in listOf("enabled", "levelDb", "playlist", "silenced")) if (music.has(key)) shown[key] = music.opt(key)
            music.optJSONObject("pins")?.takeIf { it.length() > 0 }?.let { pins ->
                shown["pins"] = names(pins).sorted().associateWith { pins.opt(it) }
                val tracks = music.getJSONObject("tracks")
                shown["tracks"] = names(tracks).sorted().associateWith { sha ->
                    val entry = tracks.getJSONObject(sha)
                    listOf("ext", "title", "creator", "duration", "lufs").filter { entry.has(it) }.associateWith { entry.opt(it) }
                }
            }
            out["music"] = shown
        }
        edits.optJSONObject("wishes")?.takeIf { it.length() > 0 }?.let { out["wishes"] = BookWishes.ordered(it) }
        return out
    }

    /** Các dòng đang bỏ khỏi phần đọc của chương `key`, xếp theo điểm mã (như `sorted` của Python). */
    private fun skipLines(skip: JSONObject?, key: String): List<String> {
        val array = skip?.optJSONArray(key) ?: return emptyList()
        return (0 until array.length()).map { array.getString(it) }.sortedWith { a, b -> byCodePoints(a, b) }
    }

    private fun orderedCover(cover: Any?): Any? =
        if (cover is JSONObject) listOf("color", "width", "height", "version").filter { cover.has(it) }.associateWith { cover.opt(it) } else cover

    /** Phần sửa của một cuốn đã nhập; không có file hay file hỏng thì rỗng (thư viện không được hỏng vì nó). */
    fun load(folder: File): JSONObject {
        val file = File(folder, EDITS_FILE)
        if (!file.isFile || file.length() > MAX_EDITS_BYTES) return empty()
        return try {
            parse(file.readBytes())
        } catch (error: IOException) {
            empty()
        } catch (error: EditsError) {
            empty()
        }
    }

    /** Ghi `edits.json` nguyên tử; không còn thay đổi nào thì xoá cả file lẫn bìa sửa. */
    fun save(folder: File, edits: JSONObject) = synchronized(lock) {
        if (isEmpty(edits)) {
            File(folder, EDITS_FILE).delete()
            File(folder, EDITS_COVER).delete()
            return@synchronized
        }
        Store.writeAtomic(File(folder, EDITS_FILE), dump(edits))
        if (edits.opt("cover") !is JSONObject) File(folder, EDITS_COVER).delete()
    }

    // ---- hợp hai lớp sửa (nhập lại cùng một cuốn) ------------------------------------------------------------------

    /**
     * Hợp phần sửa đã có trên máy (`local`) với phần sửa trong file vừa mở (`incoming`): khoá nào cả hai cùng có thì THẮNG BÊN
     * MÁY NÀY (người nghe đã làm nó ở đây), còn lại lấy cả hai. Nhạc im lặng: hợp. Trả (kết quả, báo cáo): {adopted: số thay đổi
     * lấy từ file, kept: số thay đổi của máy này, conflicts: số khoá hai bên khác nhau (đã theo máy này), cover: "local" |
     * "incoming" | null - bìa sửa lấy từ đâu}.
     */
    fun merge(local: JSONObject, incoming: JSONObject): Pair<JSONObject, JSONObject> {
        val out = empty()
        var conflicts = 0
        for (key in listOf("title", "cover")) {
            if (local.has(key)) {
                out.put(key, deepCopy(local.opt(key)))
                if (incoming.has(key) && !StrictJson.equal(incoming.opt(key), local.opt(key))) conflicts++
            } else if (incoming.has(key)) {
                out.put(key, deepCopy(incoming.opt(key)))
            }
        }
        val ourPeople = local.optJSONObject("characters") ?: JSONObject()
        val theirPeople = incoming.optJSONObject("characters") ?: JSONObject()
        val people = JSONObject()
        for (name in names(theirPeople)) people.put(name, theirPeople.opt(name))
        for (name in names(ourPeople)) {
            people.put(name, ourPeople.opt(name))
            if (theirPeople.has(name) && theirPeople.opt(name) != ourPeople.opt(name)) conflicts++
        }
        if (people.length() > 0) out.put("characters", people)
        val ourChapters = local.optJSONObject("chapters") ?: JSONObject()
        val theirChapters = incoming.optJSONObject("chapters") ?: JSONObject()
        val chapters = JSONObject()
        for (key in (names(theirChapters) + names(ourChapters)).distinct()) {
            val theirs = theirChapters.optJSONObject(key) ?: JSONObject()
            val ours = ourChapters.optJSONObject(key) ?: JSONObject()
            val entry = JSONObject()
            for (field in names(theirs)) entry.put(field, theirs.opt(field))
            for (field in names(ours)) {
                entry.put(field, ours.opt(field))
                if (theirs.has(field) && theirs.opt(field) != ours.opt(field)) conflicts++
            }
            chapters.put(key, entry)
        }
        if (chapters.length() > 0) out.put("chapters", chapters)
        // Dòng bỏ khỏi phần đọc: hợp (không có "đọc lại dòng này" để thắng), như nhạc im lặng.
        val ourSkip = local.optJSONObject("skip")
        val theirSkip = incoming.optJSONObject("skip")
        val skip = JSONObject()
        for (key in ((theirSkip?.let(::names) ?: emptyList()) + (ourSkip?.let(::names) ?: emptyList())).distinct()) {
            skip.put(key, JSONArray((skipLines(theirSkip, key) + skipLines(ourSkip, key)).distinct().sortedWith { a, b -> byCodePoints(a, b) }))
        }
        if (skip.length() > 0) out.put("skip", skip)
        // Cách đọc riêng: như tên nhân vật - từ nào cả hai cùng đặt thì cách của máy này thắng.
        val ourReadings = local.optJSONObject("readings") ?: JSONObject()
        val theirReadings = incoming.optJSONObject("readings") ?: JSONObject()
        val readings = JSONObject()
        for (word in names(theirReadings)) readings.put(word, theirReadings.opt(word))
        for (word in names(ourReadings)) {
            readings.put(word, ourReadings.opt(word))
            if (theirReadings.has(word) && theirReadings.opt(word) != ourReadings.opt(word)) conflicts++
        }
        if (readings.length() > 0) out.put("readings", readings)
        val music = JSONObject()
        val ourMusic = local.optJSONObject("music") ?: JSONObject()
        val theirMusic = incoming.optJSONObject("music") ?: JSONObject()
        for (field in listOf("enabled", "levelDb", "playlist")) {
            if (ourMusic.has(field)) {
                music.put(field, ourMusic.opt(field))
                if (theirMusic.has(field) && !StrictJson.equal(theirMusic.opt(field), ourMusic.opt(field))) conflicts++
            } else if (theirMusic.has(field)) {
                music.put(field, theirMusic.opt(field))
            }
        }
        val silenced = (strings(ourMusic.optJSONArray("silenced")) + strings(theirMusic.optJSONArray("silenced"))).toSortedSet().toList()
        if (silenced.isNotEmpty()) music.put("silenced", JSONArray(silenced))
        // Đổi bài: mốc nào cả hai cùng đổi thì bài của máy này thắng; thông tin bài chỉ giữ cho các bài còn được ghim.
        val ourPins = ourMusic.optJSONObject("pins") ?: JSONObject()
        val theirPins = theirMusic.optJSONObject("pins") ?: JSONObject()
        val pins = JSONObject()
        for (key in names(theirPins)) pins.put(key, theirPins.opt(key))
        for (key in names(ourPins)) {
            pins.put(key, ourPins.opt(key))
            if (theirPins.has(key) && theirPins.opt(key) != ourPins.opt(key)) conflicts++
        }
        if (pins.length() > 0) {
            val known = JSONObject()
            theirMusic.optJSONObject("tracks")?.let { for (sha in names(it)) known.put(sha, it.opt(sha)) }
            ourMusic.optJSONObject("tracks")?.let { for (sha in names(it)) known.put(sha, it.opt(sha)) }
            val kept = JSONObject()
            for (link in names(pins).map { pins.getString(it).removePrefix(MusicStore.LOCAL_PREFIX) }.toSortedSet()) {
                kept.put(link, deepCopy(known.opt(link)))
            }
            music.put("pins", pins).put("tracks", kept)
        }
        if (music.length() > 0) out.put("music", music)
        val (wishes, wishConflicts) = BookWishes.merge(local.optJSONObject("wishes"), incoming.optJSONObject("wishes"))
        conflicts += wishConflicts
        if (wishes.length() > 0) out.put("wishes", wishes)
        val cover = if (out.opt("cover") is JSONObject) (if (local.opt("cover") is JSONObject) "local" else "incoming") else null
        val taken = count(out) - count(local)
        val report = JSONObject().put("adopted", maxOf(0, taken)).put("kept", count(local)).put("conflicts", conflicts)
            .put("cover", cover ?: JSONObject.NULL)
        return out to report
    }

    private fun strings(array: JSONArray?): List<String> = array?.let { (0 until it.length()).map { index -> it.getString(index) } } ?: emptyList()

    fun deepCopy(value: Any?): Any? = when (value) {
        is JSONObject -> JSONObject().also { out -> for (key in names(value)) out.put(key, deepCopy(value.opt(key))) }
        is JSONArray -> JSONArray().also { out -> for (index in 0 until value.length()) out.put(deepCopy(value.opt(index))) }
        else -> value
    }

    private fun shallowCopy(value: JSONObject): JSONObject = JSONObject().also { out -> for (key in names(value)) out.put(key, value.opt(key)) }

    // ---- lớp phủ lên lớp sách ---------------------------------------------------------------------------------------

    /** Khoá một mốc nhạc của sách đã đóng gói: "<mã chương>:<mili giây đầu mốc>" (làm tròn nửa-chẵn như `round` của Python). */
    fun cueKey(chapterId: Any?, start: Double): String {
        val chapter = chapterId.toString().toLongOrNull() ?: return ""
        return "$chapter:${Math.rint(start * 1000).toLong()}"
    }

    private fun idText(value: Any?): String = pyStr(value)

    /** Một mục `chapters` của book.json sau khi đổi tên: `title`, `subtitle`, `fullTitle`. */
    fun applyChapter(chapter: JSONObject, edit: JSONObject?): JSONObject {
        if (edit == null || edit.length() == 0) return chapter
        val name = if (edit.has("title")) edit.getString("title") else pyText(chapter.opt("title"))
        val subtitle = if (edit.has("subtitle")) edit.getString("subtitle") else pyText(chapter.opt("subtitle"))
        return shallowCopy(chapter).put("title", name).put("subtitle", subtitle).put("fullTitle", if (subtitle.isNotEmpty()) "$name · $subtitle" else name)
    }

    /** continuation.base_title: tên cuốn không có hậu tố phần ("Tên · Phần 2" -> "Tên"). */
    fun baseTitle(title: String): String = pyStrip(PART_SUFFIX.replace(title, "")).ifEmpty { pyStrip(title) }

    /** continuation.continued_title: "Tên · Phần 3", không chồng hậu tố cũ. */
    fun continuedTitle(title: String, part: Int): String = "${baseTitle(title)} · Phần $part"

    /** `book.json` (lớp sách) -> bản người nghe thấy: tên sách (và tên các phần của cả bộ), tên chương, bìa, nhạc. */
    fun applyManifest(book: JSONObject, edits: JSONObject): JSONObject {
        if (isEmpty(edits)) return book
        val out = shallowCopy(book)
        if (edits.has("title")) {
            val title = edits.getString("title")
            out.put("title", title)
            book.optJSONArray("parts")?.let { parts ->
                val renamed = JSONArray()
                for (index in 0 until parts.length()) {
                    val part = parts.opt(index)
                    val number = (part as? JSONObject)?.opt("part")
                    renamed.put(if (part is JSONObject && (number is Int || number is Long)) {
                        shallowCopy(part).put("title", continuedTitle(title, (number as Number).toInt()))
                    } else part)
                }
                out.put("parts", renamed)
            }
        }
        val renamed = edits.optJSONObject("chapters")
        val skip = edits.optJSONObject("skip")
        val chapters = book.optJSONArray("chapters")
        if (((renamed?.length() ?: 0) > 0 || (skip?.length() ?: 0) > 0) && chapters != null) {
            val shown = JSONArray()
            for (index in 0 until chapters.length()) {
                val chapter = chapters.opt(index)
                if (chapter !is JSONObject) {
                    shown.put(chapter)
                    continue
                }
                val id = idText(chapter.opt("id"))
                val named = applyChapter(chapter, renamed?.optJSONObject(id))
                // `skip` của chương: dòng người nghe bỏ khỏi phần đọc (màn đọc và đọc to - Paragraphs.withoutLines); chữ của sách không đổi.
                shown.put(if (skip?.has(id) == true) shallowCopy(named).put("skip", JSONArray(skipLines(skip, id))) else named)
            }
            out.put("chapters", shown)
        }
        if (edits.has("cover")) {
            val cover = edits.opt("cover")
            out.put("cover", if (cover is JSONObject) JSONObject().put("file", EDITS_COVER).also { shown ->
                for (key in names(cover)) shown.put(key, cover.opt(key))
            } else JSONObject.NULL)
        }
        val existing = book.opt("music")
        if (edits.has("music") || (existing != null && existing !== JSONObject.NULL)) {
            val music = applyMusic(existing.takeIf { it !== JSONObject.NULL }, edits)
            if (music == null) out.remove("music") else out.put("music", music)
        }
        return out
    }

    private fun renamedChapters(base: JSONObject?, edits: JSONObject): Map<String, String> {
        val renamed = edits.optJSONObject("chapters")
        if (renamed == null || renamed.length() == 0 || base == null) return emptyMap()
        val out = LinkedHashMap<String, String>()
        val chapters = base.optJSONArray("chapters") ?: return out
        for (index in 0 until chapters.length()) {
            val chapter = chapters.optJSONObject(index) ?: continue
            val edit = renamed.optJSONObject(idText(chapter.opt("id")))
            if (edit != null && edit.has("title") && truthy(chapter.opt("title"))) out[pyStr(chapter.opt("title"))] = edit.getString("title")
        }
        return out
    }

    private val PEOPLE = listOf("characters", "extras", "carried")

    private fun peopleOf(cast: JSONObject): List<JSONObject> =
        PEOPLE.flatMap { kind -> cast.optJSONArray(kind)?.let { list -> (0 until list.length()).mapNotNull { list.optJSONObject(it) } } ?: emptyList() }

    /**
     * `cast.json` -> bản người nghe thấy: tên nhân vật đã đổi (`displayName`, và `originalName` khi khác tên gốc), và
     * `firstChapter` theo tên chương mới. `base`: book.json lớp sách (để biết tên chương gốc).
     */
    fun applyCast(cast: JSONObject, edits: JSONObject, base: JSONObject? = null): JSONObject {
        val people = edits.optJSONObject("characters") ?: JSONObject()
        val chapterNames = renamedChapters(base, edits)
        val waiting = BookWishes.pendingVoices(edits.optJSONObject("wishes"))
        if (people.length() == 0 && chapterNames.isEmpty() && waiting.isEmpty()) return cast
        val out = deepCopy(cast) as JSONObject
        for (person in peopleOf(out)) {
            val name = person.opt("name")
            // Ý muốn đổi giọng/giới chờ Studio: chỉ một dấu "đang chờ" - giọng và audio của người ấy giữ nguyên.
            if (name is String) waiting[BookWishes.characterKey(name)]?.let { person.put("pendingVoice", BookEdits.deepCopy(it)) }
            if (name is String && people.has(name)) {
                val original = listOf(person.opt("originalName"), person.opt("displayName")).firstOrNull { truthy(it) } ?: name
                val shown = people.getString(name)
                person.put("displayName", shown)
                if (shown != original) person.put("originalName", original) else person.remove("originalName")
            }
            val first = person.opt("firstChapter")
            if (first is String && first in chapterNames) person.put("firstChapter", chapterNames.getValue(first))
        }
        return out
    }

    /**
     * `scripts/<n>.json` -> bản người nghe thấy: tên người nói theo tên nhân vật mới, tên chương. `cast`: cast.json GỐC (câu
     * ghi người nói bằng `displayName` lúc đóng gói).
     */
    fun applyScript(script: JSONObject, cast: JSONObject, edits: JSONObject, chapter: JSONObject?): JSONObject {
        val people = edits.optJSONObject("characters") ?: JSONObject()
        val swap = LinkedHashMap<String, String>()
        for (person in peopleOf(cast)) {
            val name = person.opt("name")
            if (name is String && people.has(name) && truthy(person.opt("displayName"))) swap[pyStr(person.opt("displayName"))] = people.getString(name)
        }
        val edit = edits.optJSONObject("chapters")?.optJSONObject(idText(script.opt("chapterId")))
        if (swap.none { (old, shown) -> shown != old } && (edit == null || edit.length() == 0)) return script
        val out = shallowCopy(script)
        val segments = script.optJSONArray("segments")
        if (swap.isNotEmpty() && segments != null) {
            val renamed = JSONArray()
            for (index in 0 until segments.length()) {
                val segment = segments.opt(index)
                val speaker = (segment as? JSONObject)?.opt("speaker")
                renamed.put(if (segment is JSONObject && speaker is String && speaker in swap) {
                    shallowCopy(segment).put("speaker", swap.getValue(speaker))
                } else segment)
            }
            out.put("segments", renamed)
        }
        if (edit != null && edit.length() > 0 && chapter != null) out.put("title", applyChapter(chapter, edit).opt("fullTitle"))
        return out
    }

    private fun trackNumber(info: Any?, key: String): Double? {
        val value = (info as? JSONObject)?.opt(key)
        return if (isNumber(value) && value !is Boolean) (value as Number).toDouble() else null
    }

    /** Tên file trong sách của một bài người nghe đã ghim: `music/<sha1>.<đuôi>`, đúng chỗ bài của người làm sách nằm. */
    fun pinnedName(sha: String, entry: JSONObject): String = "music/$sha.${entry.getString("ext")}"

    /** Tên file (`music/<sha1>.<đuôi>`) của mọi bài người nghe đã ghim trong phần sửa. */
    fun pinnedFiles(edits: JSONObject): List<String> {
        val tracks = edits.optJSONObject("music")?.optJSONObject("tracks") ?: return emptyList()
        return names(tracks).sorted().map { pinnedName(it, tracks.getJSONObject(it)) }
    }

    /** Mục `music.tracks[tên]` của một bài đã ghim, như bài người làm sách tự nhập: file, link, tên, nghệ sĩ, độ to - không giấy phép. */
    private fun pinnedTrack(link: String, name: String, entry: JSONObject): JSONObject {
        val info = JSONObject().put("file", name).put("link", link)
        for (key in listOf("title", "creator", "lufs")) if (entry.has(key)) info.put(key, entry.opt(key))
        return info
    }

    /**
     * Mục `music` của book.json sau khi người nghe sửa: mốc đổi sang bài của họ (`pins`: bài nằm ở music/<sha1>.<đuôi>, gắn vào
     * `tracks`), tắt hết, mức khác (tính lại `gainDb` từng mốc bằng đúng công thức của người làm sách - [MusicGain.cueGainDb]),
     * bỏ các mốc đã cho im lặng.
     */
    fun applyMusic(music: Any?, edits: JSONObject): Any? {
        if (music == null || music === JSONObject.NULL) return null
        val changes = edits.optJSONObject("music")
        if (changes == null || changes.length() == 0 || music !is JSONObject) return music
        val out = deepCopy(music) as JSONObject
        if (out.optJSONObject("tracks") == null) out.put("tracks", JSONObject())
        val tracks = out.getJSONObject("tracks")
        val chapters = out.optJSONObject("chapters") ?: JSONObject()
        val pins = changes.optJSONObject("pins") ?: JSONObject()
        val shown = changes.optJSONObject("tracks") ?: JSONObject()
        val baseLevel = out.opt("levelDb").takeIf { isNumber(it) }?.let { (it as Number).toDouble() } ?: DEFAULT_LEVEL_DB
        val level = if (changes.has("levelDb")) changes.getDouble("levelDb") else baseLevel
        for (key in names(chapters)) {
            val cues = chapters.optJSONArray(key) ?: continue
            for (index in 0 until cues.length()) {
                val cue = cues.optJSONObject(index) ?: continue
                val link = pins.optString(cueKey(key, cue.optDouble("start", 0.0)), "")
                if (link.isEmpty()) continue
                val sha = link.removePrefix(MusicStore.LOCAL_PREFIX)
                val name = pinnedName(sha, shown.getJSONObject(sha))
                if (!tracks.has(name)) tracks.put(name, pinnedTrack(link, name, shown.getJSONObject(sha)))
                cue.put("track", name)
                val info = tracks.opt(name)
                cue.put("gainDb", MusicGain.cueGainDb(level, trackNumber(info, "lufs"), trackNumber(info, "speechBand")))
            }
        }
        if (changes.has("levelDb")) {
            out.put("levelDb", level)
            for (key in names(chapters)) {
                val cues = chapters.optJSONArray(key) ?: continue
                for (index in 0 until cues.length()) {
                    val cue = cues.optJSONObject(index) ?: continue
                    val info = (cue.opt("track") as? String)?.let { tracks.opt(it) }
                    cue.put("gainDb", MusicGain.cueGainDb(level, trackNumber(info, "lufs"), trackNumber(info, "speechBand")))
                }
            }
        }
        if (changes.opt("enabled") == false) {
            out.put("chapters", JSONObject())
            return out
        }
        val silenced = strings(changes.optJSONArray("silenced")).toSet()
        if (silenced.isNotEmpty()) {
            val kept = JSONObject()
            for (key in names(chapters)) {
                val cues = chapters.optJSONArray(key) ?: continue
                val rest = JSONArray()
                for (index in 0 until cues.length()) {
                    val cue = cues.opt(index)
                    if (cue !is JSONObject || cueKey(key, cue.optDouble("start", 0.0)) !in silenced) rest.put(cue)
                }
                if (rest.length() > 0) kept.put(key, rest)
            }
            out.put("chapters", kept)
        }
        return out
    }

    /**
     * Màn "Nhạc nền" của sách đóng gói: bật/tắt, mức, và từng mốc (đã im lặng hay chưa) - kể cả mốc đã im lặng, để bật lại.
     * `book`: book.json GỐC. Sách không có nhạc: `hasMusic` false.
     */
    fun musicView(book: JSONObject, edits: JSONObject): JSONObject {
        val music = book.optJSONObject("music")
        val changes = edits.optJSONObject("music") ?: JSONObject()
        val baseLevel = music?.opt("levelDb")?.takeIf { isNumber(it) && it !is Boolean }?.let { (it as Number).toDouble() } ?: DEFAULT_LEVEL_DB
        val silenced = strings(changes.optJSONArray("silenced")).toSet()
        val pins = changes.optJSONObject("pins") ?: JSONObject()
        val cues = JSONArray()
        val tracks = music?.optJSONObject("tracks") ?: JSONObject()
        val chapters = book.optJSONArray("chapters")
        for (index in 0 until (chapters?.length() ?: 0)) {
            val chapter = chapters?.optJSONObject(index) ?: continue
            val chapterId = idText(chapter.opt("id"))
            val shown = applyChapter(chapter, edits.optJSONObject("chapters")?.optJSONObject(chapterId))
            val list = music?.optJSONObject("chapters")?.optJSONArray(chapterId) ?: continue
            for (item in 0 until list.length()) {
                val cue = list.optJSONObject(item) ?: continue
                var info = (cue.opt("track") as? String)?.let { tracks.optJSONObject(it) } ?: JSONObject()
                val key = cueKey(chapterId, cue.optDouble("start", 0.0))
                val pinned = pins.optString(key, "").takeIf { it.isNotEmpty() }
                if (pinned != null) info = changes.optJSONObject("tracks")?.optJSONObject(pinned.removePrefix(MusicStore.LOCAL_PREFIX)) ?: JSONObject()
                val item = JSONObject().put("key", key).put("chapterId", chapterId.toLongOrNull() ?: 0L)
                    .put("chapter", listOf(shown.opt("fullTitle"), shown.opt("title")).firstOrNull { truthy(it) }?.toString() ?: "")
                    .put("start", cue.optDouble("start", 0.0)).put("end", cue.optDouble("end", 0.0))
                    .put("title", pyText(info.opt("title"))).put("creator", pyText(info.opt("creator")))
                    .put("silenced", key in silenced)
                if (pinned != null) item.put("pinned", true)
                cues.put(item)
            }
        }
        return JSONObject().put("package", true).put("hasMusic", cues.length() > 0)
            .put("enabled", if (changes.has("enabled")) changes.opt("enabled") else true)
            .put("levelDb", if (changes.has("levelDb")) changes.opt("levelDb") else baseLevel)
            .put("defaultLevelDb", baseLevel).put("cues", cues)
            .apply { if (changes.has("playlist")) put("playlist", changes.opt("playlist")) }
    }

    // ---- bìa ----------------------------------------------------------------------------------------------------

    /** File ảnh bìa người nghe thấy: bìa sửa, hay bìa của sách; null khi đã bỏ bìa hoặc sách không có. */
    fun coverFile(folder: File): File? {
        val edits = load(folder)
        if (edits.has("cover")) {
            val path = File(folder, EDITS_COVER)
            return if (edits.opt("cover") is JSONObject && path.isFile) path else null
        }
        return File(folder, "cover.jpg").takeIf { it.isFile }
    }

    // ---- chữ trong gói qua lớp sửa -----------------------------------------------------------------------------------

    private fun readObject(file: File?): JSONObject? =
        if (file != null && file.isFile) runCatching { JSONObject(file.readText()) }.getOrNull() else null

    private fun inside(folder: File, relative: Any?): File? {
        if (relative !is String || relative.isEmpty()) return null
        val file = runCatching { Store.contained(folder, relative) }.getOrNull()
        return file?.takeIf { it.isFile }
    }

    /** Gói sách nguyên văn của thư mục sách: `book.json` (đã tải / mở từ file), không có thì `stream.json` (cuốn nghe thẳng chưa tải -
     *  lớp sửa nằm cạnh nó, cùng hình dạng); không có cả hai thì null. */
    fun rawBookOrNull(folder: File): JSONObject? =
        listOf("book.json", "stream.json").map { File(folder, it) }.firstOrNull { it.isFile }?.let { JSONObject(it.readText()) }

    /** Như [rawBookOrNull] nhưng ném lỗi khi thư mục không có sách. */
    fun rawBook(folder: File): JSONObject = rawBookOrNull(folder) ?: throw IOException("Thư mục không có gói sách")

    /** Tên file dàn nhân vật theo book.json (mặc định cast.json). */
    private fun castName(book: JSONObject): String = listOf(book.opt("cast"), "cast.json").first { truthy(it) }.toString()

    /** `cast.json` của lớp sách, chưa qua lớp sửa; không có file thì dàn rỗng. */
    fun rawCast(folder: File, book: JSONObject): JSONObject {
        return readObject(inside(folder, castName(book))) ?: JSONObject().put("characters", JSONArray()).put("extras", JSONArray())
    }

    /** Dàn nhân vật như người nghe thấy (tên đã đổi, chương đầu theo tên chương mới). */
    fun cast(folder: File, book: JSONObject): JSONObject {
        val raw = rawCast(folder, book)
        val edits = load(folder)
        return if (isEmpty(edits)) raw else applyCast(raw, edits, book)
    }

    /** Chữ đọc theo của một chương đã qua lớp sửa; null khi chương hay file không có. */
    fun script(folder: File, book: JSONObject, chapterId: Long): JSONObject? {
        val chapters = book.optJSONArray("chapters") ?: return null
        val chapter = (0 until chapters.length()).mapNotNull { chapters.optJSONObject(it) }
            .firstOrNull { (it.opt("id") as? Number)?.toLong() == chapterId } ?: return null
        val script = readObject(inside(folder, chapter.opt("script"))) ?: return null
        val edits = load(folder)
        return if (isEmpty(edits)) script else applyScript(script, rawCast(folder, book), edits, chapter)
    }

    /** Chữ của file `relative` trong gói khi lớp sửa làm nó khác đi (cast.json, scripts/<n>.json); null = giữ nguyên file. */
    fun overlaidText(folder: File, book: JSONObject, edits: JSONObject, relative: String): String? {
        if (relative == castName(book)) {
            val raw = readObject(File(folder, relative)) ?: return null
            return applyCast(raw, edits, book).toString()
        }
        val chapters = book.optJSONArray("chapters") ?: return null
        val chapter = (0 until chapters.length()).mapNotNull { chapters.optJSONObject(it) }.firstOrNull { it.opt("script") == relative } ?: return null
        val raw = readObject(File(folder, relative)) ?: return null
        return applyScript(raw, rawCast(folder, book), edits, chapter).toString()
    }

    // ---- sửa (ghi) ---------------------------------------------------------------------------------------------------

    internal fun <T> locked(block: () -> T): T = synchronized(lock) { block() }

    internal fun write(folder: File, edits: JSONObject): JSONObject {
        // File quá cỡ thì lần đọc sau từ chối cả file: không ghi ra thứ chính mình không đọc lại được.
        if (dump(edits).size > MAX_EDITS_BYTES) throw EditsError(TOO_BIG)
        save(folder, edits)
        return edits
    }

    /** Đặt lại tên sách (người nghe). Tên rỗng: [EditsError]. Trả tên đã làm sạch. */
    fun setTitle(folder: File, title: String): String {
        val cleaned = cleanText(title, TITLE_MAX)
        if (cleaned.isEmpty()) throw EditsError("Tên sách không được để trống")
        synchronized(lock) {
            val edits = load(folder)
            if (cleaned == pyText(rawBook(folder).opt("title"))) edits.remove("title") else edits.put("title", cleaned)
            write(folder, edits)
        }
        return cleaned
    }

    /**
     * Đặt ảnh bìa từ byte ảnh thô: chuẩn hoá như bìa dự án (`codec`), cất ở edits/cover.jpg. `now`: số làm phiên bản (giây) để
     * giao diện không giữ ảnh cũ. Trả mô tả bìa {color, width, height, version}.
     */
    fun setCover(folder: File, raw: ByteArray, now: Long, codec: CoverCodec): JSONObject {
        if (raw.size > Covers.MAX_UPLOAD_BYTES) throw EditsError(Covers.tooLarge().message.orEmpty())
        val normalized = try {
            codec.normalize(raw)
        } catch (error: CoverCodec.CoverError) {
            throw EditsError(error.message.orEmpty())
        }
        synchronized(lock) {
            val edits = load(folder)
            val cover = JSONObject().put("color", normalized.color).put("width", normalized.width.toLong())
                .put("height", normalized.height.toLong()).put("version", now)
            edits.put("cover", cover)
            Store.writeAtomic(File(folder, EDITS_COVER), normalized.jpeg)
            write(folder, edits)
            return deepCopy(cover) as JSONObject
        }
    }

    /** Bỏ bìa: sách dùng bìa vẽ từ tên (kể cả khi lớp sách có ảnh bìa). */
    fun removeCover(folder: File) = synchronized(lock) {
        val edits = load(folder)
        edits.put("cover", JSONObject.NULL)
        File(folder, EDITS_COVER).delete()
        write(folder, edits)
        Unit
    }

    private fun personOf(cast: JSONObject, character: String): JSONObject? = peopleOf(cast).firstOrNull { it.opt("name") == character }

    /**
     * Đổi tên hiện của một nhân vật (như tab Nhân vật của Studio): tên rỗng hay đúng tên gốc là trở về tên gốc. Trả đúng hình
     * dạng của `POST /characters/rename`: {character, name, original, renamed}.
     */
    fun setCharacterName(folder: File, character: String, name: String): JSONObject {
        val wanted = cut(pyStrip(character), 200)
        val book = rawBook(folder)
        val person = personOf(rawCast(folder, book), wanted)
        if (wanted.isEmpty() || wanted.uppercase(java.util.Locale.ROOT) == "NARRATOR" || person == null) {
            throw EditsError("Không có nhân vật này trong sách")
        }
        val baseShown = listOf(person.opt("displayName"), wanted).first { truthy(it) }.toString()
        val original = listOf(person.opt("originalName"), baseShown).first { truthy(it) }.toString()
        val newName = cleanText(name, NAME_MAX).ifEmpty { original }
        val shown: String
        synchronized(lock) {
            val edits = load(folder)
            val people = edits.optJSONObject("characters")?.let { deepCopy(it) as JSONObject } ?: JSONObject()
            if (newName == baseShown) people.remove(wanted) else people.put(wanted, newName)
            if (people.length() > 0) edits.put("characters", people) else edits.remove("characters")
            write(folder, edits)
            shown = if (people.has(wanted)) people.getString(wanted) else baseShown
        }
        return JSONObject().put("character", wanted).put("name", shown).put("original", original).put("renamed", shown != original)
    }

    /**
     * Đặt lại tên chương `chapterId`: `title` (nhãn như "Chương 12") và/hoặc `subtitle` (tên phụ, "" là bỏ tên phụ). Cả hai trống
     * (`title` rỗng/null và `subtitle` null) là trở về tên của người làm sách. Trả {chapterId, title, subtitle, fullTitle} đang hiện.
     */
    /**
     * Bỏ (`skip`) hay đọc lại dòng `line` trong phần đọc của các chương `chapterIds` - gợi ý dòng ghi công mà người nghe chấp nhận
     * (`book_edits.set_skip_line`). Chỉ là biến đổi để đọc: chữ của sách không đổi. Trả {mã chương: các dòng đang bỏ} của các chương ấy.
     */
    fun setSkipLine(folder: File, chapterIds: List<Long>, line: String, skip: Boolean): JSONObject {
        val list = rawBook(folder).optJSONArray("chapters")
        val known = (0 until (list?.length() ?: 0)).mapNotNull { (list?.optJSONObject(it)?.opt("id") as? Number)?.toLong() }.toSet()
        val wanted = chapterIds.toSortedSet()
        if (wanted.isEmpty() || wanted.any { it !in known }) throw EditsError("Không có chương này trong sách")
        val clean = cleanText(line, SKIP_LINE_MAX)
        if (clean.isEmpty()) throw EditsError("Dòng cần bỏ trống.")
        val out = JSONObject()
        synchronized(lock) {
            val edits = load(folder)
            val skipped = edits.optJSONObject("skip")?.let { deepCopy(it) as JSONObject } ?: JSONObject()
            for (chapterId in wanted) {
                val key = chapterId.toString()
                val lines = skipLines(skipped, key).toMutableSet()
                if (skip) {
                    if (clean !in lines && lines.size >= MAX_SKIP_LINES) throw EditsError("Mỗi chương bỏ được tối đa $MAX_SKIP_LINES dòng.")
                    lines.add(clean)
                } else {
                    lines.remove(clean)
                }
                val sorted = lines.sortedWith { a, b -> byCodePoints(a, b) }
                if (sorted.isNotEmpty()) skipped.put(key, JSONArray(sorted)) else skipped.remove(key)
                out.put(key, JSONArray(sorted))
            }
            if (skipped.length() > 0) edits.put("skip", skipped) else edits.remove("skip")
            write(folder, edits)
        }
        return out
    }

    /** Danh sách "Cách đọc tên" của hộp sửa sách: {readings: [{surface, spoken}]} theo thứ tự chữ hiện (`book_edits.readings_view`). */
    fun readingsView(edits: JSONObject): JSONObject {
        val readings = edits.optJSONObject("readings") ?: JSONObject()
        val list = JSONArray()
        for (shown in names(readings).sortedWith { a, b -> byCodePoints(a, b) }) {
            list.put(JSONObject().put("surface", shown).put("spoken", readings.opt(shown)))
        }
        return JSONObject().put("readings", list)
    }

    /** Chữ người gõ ở "Đọc từ này là…" -> (chữ hiện, chữ đọc) đã làm sạch; chữ hiện không phải một từ hay cụm 2..6 từ liền nhau: [EditsError]. Chữ đọc rỗng là bỏ. */
    fun cleanReading(shown: Any?, spoken: Any?): Pair<String, String> {
        var word = cleanText(shown, READING_WORD_MAX)
        if (!Readings.isKey(word)) {
            // Người chạm vào "Haruto," - cách đọc đặt cho chính từ ấy, không dính dấu câu.
            val (start, end) = Readings.coreSpan(word)
            word = word.substring(start, end)
        }
        if (word.isEmpty() || !Readings.isKey(word)) throw EditsError("Chỉ đặt được cách đọc cho một từ hay tối đa 6 từ liền nhau, không có dấu câu ở giữa.")
        return word to cleanText(spoken, READING_SPOKEN_MAX)
    }

    /**
     * Đặt (hay bỏ - chữ đọc rỗng / đúng chữ hiện) cách đọc riêng của một từ cho cả cuốn (`book_edits.set_reading`): chỉ giọng đọc của
     * "Nghe ngay" đổi, chữ của sách không đổi. Trả [readingsView].
     */
    fun setReading(folder: File, shown: Any?, spoken: Any?): JSONObject {
        val (word, said) = cleanReading(shown, spoken)
        synchronized(lock) {
            val edits = load(folder)
            val readings = edits.optJSONObject("readings")?.let { deepCopy(it) as JSONObject } ?: JSONObject()
            if (said.isEmpty() || said == word) {
                readings.remove(word)
            } else {
                if (!readings.has(word) && readings.length() >= MAX_READINGS) throw EditsError("Mỗi cuốn đặt được tối đa $MAX_READINGS cách đọc.")
                readings.put(word, said)
            }
            if (readings.length() > 0) edits.put("readings", readings) else edits.remove("readings")
            write(folder, edits)
            return readingsView(edits)
        }
    }

    fun setChapterTitle(folder: File, chapterId: Long, title: String?, subtitle: String? = null): JSONObject {
        val book = rawBook(folder)
        val list = book.optJSONArray("chapters")
        val chapter = (0 until (list?.length() ?: 0)).mapNotNull { list?.optJSONObject(it) }
            .firstOrNull { (it.opt("id") as? Number)?.toLong() == chapterId } ?: throw EditsError("Không có chương này trong sách")
        val newTitle = if (title != null) cleanText(title, TITLE_MAX) else ""
        val newSubtitle = if (subtitle != null) cleanText(subtitle, TITLE_MAX) else null
        val entry = JSONObject()
        if (newTitle.isNotEmpty() && newTitle != pyText(chapter.opt("title"))) entry.put("title", newTitle)
        if (newSubtitle != null && newSubtitle != pyText(chapter.opt("subtitle"))) entry.put("subtitle", newSubtitle)
        synchronized(lock) {
            val edits = load(folder)
            val chapters = edits.optJSONObject("chapters")?.let { deepCopy(it) as JSONObject } ?: JSONObject()
            if (entry.length() > 0) chapters.put(chapterId.toString(), entry) else chapters.remove(chapterId.toString())
            if (chapters.length() > 0) edits.put("chapters", chapters) else edits.remove("chapters")
            write(folder, edits)
        }
        val shown = applyChapter(chapter, entry)
        return JSONObject().put("chapterId", chapterId).put("title", pyText(shown.opt("title")))
            .put("subtitle", pyText(shown.opt("subtitle")))
            .put("fullTitle", listOf(shown.opt("fullTitle"), shown.opt("title")).firstOrNull { truthy(it) }?.toString() ?: "")
    }

    /** {khoá mốc: link bài người làm sách đã gắn} của book.json GỐC. */
    fun baseLinks(book: JSONObject): Map<String, String> {
        val music = book.optJSONObject("music") ?: return emptyMap()
        val tracks = music.optJSONObject("tracks") ?: JSONObject()
        val chapters = music.optJSONObject("chapters") ?: return emptyMap()
        val out = LinkedHashMap<String, String>()
        for (chapterId in names(chapters)) {
            val cues = chapters.optJSONArray(chapterId) ?: continue
            for (index in 0 until cues.length()) {
                val cue = cues.optJSONObject(index) ?: continue
                val link = tracks.optJSONObject(cue.optString("track"))?.opt("link")
                if (link is String) out[cueKey(chapterId, cue.optDouble("start", 0.0))] = link
            }
        }
        return out
    }

    /**
     * Mục `music.tracks[<sha1>]` của phần sửa cho một bài trong kho "Nhạc của tôi" (`info`: [MusicStore.info]; `file`: file của nó).
     * Tên bài / nghệ sĩ làm sạch như mọi chữ người gõ; số đo ngoài khoảng cho phép thì bỏ.
     */
    private fun trackEntry(info: JSONObject, file: File): JSONObject {
        val extension = file.extension.lowercase()
        if (extension !in MusicStore.EXTENSIONS) throw EditsError("Định dạng bài nhạc này chưa dùng được")
        val entry = JSONObject().put("ext", extension)
        for (key in listOf("title", "creator")) cleanText(info.opt(key), TRACK_TEXT_MAX).takeIf { it.isNotEmpty() }?.let { entry.put(key, it) }
        val duration = info.opt("duration")
        val lufs = info.opt("lufs")
        if (isNumber(duration) && (duration as Number).toDouble() > 0 && duration.toDouble() <= 1e6) entry.put("duration", duration.toDouble())
        if (isNumber(lufs) && (lufs as Number).toDouble() in -100.0..20.0) {
            entry.put("lufs", BigDecimal(lufs.toDouble()).setScale(2, RoundingMode.HALF_EVEN).toDouble())
        }
        return entry
    }

    /** Chép file bài đã ghim vào thư mục sách (music/<sha1>.<đuôi>) - nguyên tử, không ghi đè file cùng cỡ đã có. */
    private fun place(folder: File, name: String, source: File) {
        val target = File(folder, name)
        if (target.isFile && target.length() == source.length()) return
        target.parentFile?.mkdirs()
        val part = File(target.parentFile, ".${target.name}.part")
        try {
            source.copyTo(part, overwrite = true)
            if (!part.renameTo(target)) {
                target.delete()
                if (!part.renameTo(target)) throw IOException("không đổi tên được file tạm")
            }
        } catch (error: IOException) {
            throw EditsError("Không chép được bài nhạc vào sách (${error.message ?: error.javaClass.simpleName}).")
        } finally {
            part.delete()
        }
    }

    /** Xoá file các bài đã bỏ ghim - trừ file nằm trong danh sách của lớp sách (không bao giờ đụng lớp sách). */
    private fun dropUnused(folder: File, book: JSONObject, names: Collection<String>) {
        val listed = book.optJSONObject("package")?.optJSONObject("files")
        for (name in names) if (listed == null || !listed.has(name)) File(folder, name).delete()
    }

    /**
     * Sửa nhạc nền của sách đóng gói: `enabled`, `levelDb` (kẹp -40..-6 như `music_plan.write_overrides`), `silence` {khoá mốc:
     * true/false}, `pins` {khoá mốc: "local:<sha1>" | null} (đổi bài một mốc sang bài trong "Nhạc của tôi", null = về bài người
     * làm sách gắn). `track(link)` -> (thông tin, file) của bài trong kho của máy này; file được chép vào thư mục sách
     * (music/<sha1>.<đuôi>) để việc lưu mang đi. Khoá lạ: [EditsError]. Trả [musicView].
     */
    fun setMusic(folder: File, body: JSONObject, track: ((String) -> Pair<JSONObject, File>?)? = null): JSONObject {
        val book = rawBook(folder)
        synchronized(lock) {
            val edits = load(folder)
            val music = edits.optJSONObject("music")?.let { deepCopy(it) as JSONObject } ?: JSONObject()
            val before = music.optJSONObject("tracks")?.let { deepCopy(it) as JSONObject } ?: JSONObject()
            val base = musicView(book, empty())
            if (body.has("enabled")) {
                if (truthy(body.opt("enabled"))) music.remove("enabled") else music.put("enabled", false)
            }
            if (body.has("levelDb")) {
                val value = body.opt("levelDb")
                if (!isNumber(value) || value is Boolean) throw EditsError("Mức nhạc nền không hợp lệ")
                val level = Math.max(LEVEL_MIN, Math.min(LEVEL_MAX, (value as Number).toDouble()))
                if (level == base.getDouble("levelDb")) music.remove("levelDb") else music.put("levelDb", level)
            }
            if (body.has("playlist")) {
                val playlist = body.opt("playlist")
                when {
                    !truthy(playlist) -> music.remove("playlist")
                    playlist is String && PLAYLIST.matches(playlist) -> music.put("playlist", playlist)
                    else -> throw EditsError("Không có danh sách nhạc nền này")
                }
            }
            if (truthy(body.opt("silence"))) {
                val wanted = body.opt("silence") as? JSONObject ?: throw EditsError("Phần sửa nhạc nền không hợp lệ.")
                val known = (0 until base.getJSONArray("cues").length()).map { base.getJSONArray("cues").getJSONObject(it).getString("key") }.toSet()
                val silenced = strings(music.optJSONArray("silenced")).toMutableSet()
                for (key in names(wanted)) {
                    if (key !in known) throw EditsError("Không có đoạn nhạc này trong sách")
                    if (truthy(wanted.opt(key))) silenced.add(key) else silenced.remove(key)
                }
                if (silenced.isNotEmpty()) music.put("silenced", JSONArray(silenced.sorted())) else music.remove("silenced")
            }
            val placing = ArrayList<Pair<String, File>>()
            if (truthy(body.opt("pins"))) {
                val wanted = body.opt("pins") as? JSONObject ?: throw EditsError("Phần sửa nhạc nền không hợp lệ.")
                val known = (0 until base.getJSONArray("cues").length()).map { base.getJSONArray("cues").getJSONObject(it).getString("key") }.toSet()
                val original = baseLinks(book)
                val pins = music.optJSONObject("pins")?.let { deepCopy(it) as JSONObject } ?: JSONObject()
                val shown = deepCopy(before) as JSONObject
                for (key in names(wanted)) {
                    if (key !in known) throw EditsError("Không có đoạn nhạc này trong sách")
                    val link = wanted.opt(key)
                    if (!truthy(link)) {
                        pins.remove(key)
                        continue
                    }
                    val sha = (link as? String)?.takeIf { LOCAL_LINK.matches(it) }?.removePrefix(MusicStore.LOCAL_PREFIX)
                        ?: throw EditsError("Chỉ đổi được sang bài trong Nhạc của tôi")
                    if (link == original[key]) {
                        pins.remove(key)
                        continue
                    }
                    if (!shown.has(sha)) {
                        val (info, file) = track?.invoke(link as String) ?: throw EditsError("Bài này không còn trong Nhạc của tôi")
                        shown.put(sha, trackEntry(info, file))
                        placing.add(pinnedName(sha, shown.getJSONObject(sha)) to file)
                    }
                    pins.put(key, link)
                }
                if (pins.length() > 0) {
                    val used = names(pins).map { pins.getString(it).removePrefix(MusicStore.LOCAL_PREFIX) }.toSortedSet()
                    val kept = JSONObject()
                    for (sha in used) kept.put(sha, shown.getJSONObject(sha))
                    music.put("pins", pins).put("tracks", kept)
                } else {
                    music.remove("pins")
                    music.remove("tracks")
                }
            }
            if (music.length() > 0) edits.put("music", music) else edits.remove("music")
            for ((name, file) in placing) place(folder, name, file)
            try {
                write(folder, edits)
            } catch (error: EditsError) {
                dropUnused(folder, book, placing.map { it.first })
                throw error
            }
            val after = edits.optJSONObject("music")?.optJSONObject("tracks") ?: JSONObject()
            dropUnused(folder, book, names(before).filter { !after.has(it) }.map { pinnedName(it, before.getJSONObject(it)) })
            return musicView(book, edits)
        }
    }

    /** Bỏ mọi thay đổi của người nghe: sách trở về đúng như người làm sách đã đóng gói (kể cả file các bài đã ghim). */
    fun clear(folder: File) = synchronized(lock) {
        val pinned = pinnedFiles(load(folder))
        save(folder, empty())
        if (pinned.isNotEmpty()) dropUnused(folder, rawBook(folder), pinned)
    }

    // ---- phần sửa đã gửi về máy tính (EditsSync) ---------------------------------------------------------------------

    /**
     * Gỡ khỏi lớp sửa của máy này đúng những gì đã gửi cho máy tính (`sent`: ảnh chụp lớp sửa lúc đóng gói; `sentCover`: byte bìa
     * lúc ấy). Khoá nào người nghe đã đổi tiếp trong lúc gửi (giá trị khác giá trị đã gửi) thì GIỮ - lần sau gửi nốt. Nhạc im
     * lặng đã gửi thì bỏ; bài đã ghim và gửi xong thì file của nó trong sách cũng bỏ (máy tính đã nhập vào kho của nó). Trả số
     * thay đổi còn lại (chưa gửi).
     */
    fun subtract(folder: File, sent: JSONObject, sentCover: ByteArray?): Int = synchronized(lock) {
        val edits = load(folder)
        val book = rawBookOrNull(folder)
        val before = pinnedFiles(edits)
        for (key in listOf("title", "cover")) {
            if (!sent.has(key) || !edits.has(key) || !StrictJson.equal(edits.opt(key), sent.opt(key))) continue
            if (key == "cover" && sent.opt(key) is JSONObject && !File(folder, EDITS_COVER).let { it.isFile && sentCover != null && it.readBytes().contentEquals(sentCover) }) continue
            edits.remove(key)
        }
        removeEqual(edits.optJSONObject("characters"), sent.optJSONObject("characters"))
        edits.optJSONObject("chapters")?.let { chapters ->
            val gone = sent.optJSONObject("chapters") ?: JSONObject()
            for (id in names(chapters)) {
                val entry = chapters.getJSONObject(id)
                removeEqual(entry, gone.optJSONObject(id))
                if (entry.length() == 0) chapters.remove(id)
            }
        }
        val music = edits.optJSONObject("music")
        val sentMusic = sent.optJSONObject("music")
        if (music != null && sentMusic != null) {
            for (field in listOf("enabled", "levelDb")) {
                if (sentMusic.has(field) && music.has(field) && StrictJson.equal(music.opt(field), sentMusic.opt(field))) music.remove(field)
            }
            val gone = strings(sentMusic.optJSONArray("silenced")).toSet()
            val kept = strings(music.optJSONArray("silenced")).filter { it !in gone }
            if (kept.isEmpty()) music.remove("silenced") else music.put("silenced", JSONArray(kept))
            removeEqual(music.optJSONObject("pins"), sentMusic.optJSONObject("pins"))
            val pins = music.optJSONObject("pins")
            if (pins == null || pins.length() == 0) {
                music.remove("pins")
                music.remove("tracks")
            } else {
                val tracks = music.optJSONObject("tracks") ?: JSONObject()
                val wanted = names(pins).map { pins.getString(it).removePrefix(MusicStore.LOCAL_PREFIX) }.toSet()
                for (sha in names(tracks)) if (sha !in wanted) tracks.remove(sha)
            }
            if (music.length() == 0) edits.remove("music")
        }
        edits.optJSONObject("wishes")?.let { wishes ->
            val sentWishes = sent.optJSONObject("wishes") ?: JSONObject()
            for (section in BookWishes.SECTIONS) removeEqual(wishes.optJSONObject(section), sentWishes.optJSONObject(section))
            for (section in BookWishes.SECTIONS) if (wishes.optJSONObject(section)?.length() == 0) wishes.remove(section)
            val aliases = wishes.optJSONArray(BookWishes.ALIASES)
            if (aliases != null) {
                val gone = sentWishes.optJSONArray(BookWishes.ALIASES)
                val kept = JSONArray()
                for (index in 0 until aliases.length()) {
                    val item = aliases.get(index)
                    if (gone == null || (0 until gone.length()).none { StrictJson.equal(gone.get(it), item) }) kept.put(item)
                }
                if (kept.length() == 0) wishes.remove(BookWishes.ALIASES) else wishes.put(BookWishes.ALIASES, kept)
            }
            if (wishes.length() == 0) edits.remove("wishes")
        }
        if (edits.opt("cover") !is JSONObject) File(folder, EDITS_COVER).delete()
        save(folder, edits)
        val after = pinnedFiles(edits).toSet()
        val dropped = before.filter { it !in after }
        if (dropped.isNotEmpty() && book != null) dropUnused(folder, book, dropped)
        count(edits)
    }

    /** Bỏ khỏi `mine` mọi khoá mà `sent` cũng có với đúng giá trị ấy. */
    private fun removeEqual(mine: JSONObject?, sent: JSONObject?) {
        if (mine == null || sent == null) return
        for (key in names(mine)) if (sent.has(key) && StrictJson.equal(mine.opt(key), sent.opt(key))) mine.remove(key)
    }

    // ---- file `.abook` mang phần sửa theo ---------------------------------------------------------------------------

    /**
     * Nhập lại một file sách ĐÃ có trên máy mà file mang phần sửa: hợp vào phần sửa của máy ([merge]: máy này thắng) - không
     * giải nén lại audio. `cover`: byte edits/cover.jpg của file (nếu có). Trả báo cáo của [merge].
     */
    fun adopt(folder: File, incoming: JSONObject, cover: ByteArray?, member: ((String, File) -> Unit)? = null): JSONObject = synchronized(lock) {
        val (merged, report) = merge(load(folder), incoming)
        if (report.opt("cover") == "incoming" && cover != null) Store.writeAtomic(File(folder, EDITS_COVER), cover)
        if (member != null) for (name in pinnedFiles(merged)) File(folder, name).let { if (!it.isFile) member(name, it) }
        save(folder, merged)
        report
    }
}
