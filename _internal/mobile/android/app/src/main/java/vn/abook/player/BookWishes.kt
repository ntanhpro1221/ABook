package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.Normalizer
import java.util.Locale

/**
 * Ý MUỐN của người nghe trên một cuốn không có xưởng - bản Kotlin của abook/webui/book_wishes.py (docs/EDITING.md, lớp W của
 * giai đoạn P2). Cách đọc tên, ai nói câu này (và gộp hai tên), loại đoạn / cảm xúc / chữ đem đọc của một câu, giọng và giới của
 * một nhân vật, thu lại một câu: cần Studio, mà điện thoại không có Studio. Người nghe vẫn ghi được - ý muốn nằm trong
 * `edits.json`, mục `wishes`, theo ĐÚNG hình dạng các mục của overrides.json (listener_overrides.py), đi theo file `.abook`
 * (phiên bản 4), hợp lại khi nhập lại, và chủ máy sản xuất đọc lại thành yêu cầu thật. KHÔNG BAO GIỜ áp vào audio hay chữ người
 * nghe thấy: chỉ có dấu "đang chờ Studio" (dàn nhân vật `pendingVoice`, danh sách [pendingDetails]).
 *
 * Python gọi thẳng `listener_overrides.request_*` lên một overrides.json tạm; ở đây các phép ghi ấy viết lại (từng hàm một, cùng
 * tên) - hai bên đọc chung bộ ví dụ tests/fixtures/book_edits/ nên phải ra ĐÚNG cùng JSON. Dữ liệu của người lạ: [validate] chặt
 * (đúng khoá, đúng kiểu, có trần số mục và độ dài, chữ phải đã sạch), sai một mục là từ chối cả file.
 */
object BookWishes {
    val SECTIONS = listOf("pronunciations", "speakers", "lines", "voices", "retakes")
    const val ALIASES = "aliases"
    private val MAX_ENTRIES = mapOf("pronunciations" to 2000, "speakers" to 5000, "lines" to 2000, "voices" to 2000, "retakes" to 5000, ALIASES to 2000)
    private const val SURFACE_MAX = 80
    private const val SPOKEN_FORM_MAX = 120
    private const val SPEAKER_MAX = 200
    private const val PRESET_MAX = 120
    const val SPOKEN_TEXT_MAX = 2000
    const val INTENSITY_MAX = 3
    private const val TIME_MAX = 1e11
    private const val PART_SPAN = 100_000L
    private const val ALIAS_MAX = 200
    private val LINE_ID = Regex("[A-Za-z0-9_]{1,120}")
    private val SHA256 = Regex("[0-9a-f]{64}")
    private val STABLE_ID = Regex("^c([0-9]+)_s([0-9]+)_")
    private val BY_CLICK = setOf("speakers", "retakes")
    private val ENTRY_KEYS = mapOf(
        "pronunciations" to setOf("surface", "spoken_form", "requested_at"),
        "speakers" to setOf("speaker", "text_sha256", "requested_at", "new"),
        "lines" to setOf("text_sha256", "kind", "emotion", "intensity", "spoken", "requested_at"),
        "voices" to setOf("preset", "gender", "avoid", "requested_at"),
        "retakes" to setOf("text_sha256", "requested_at"),
    )
    private val REPLACEABLE = setOf("pronunciations", "speakers", "voices")
    private val LINE_KINDS = listOf("narration", "dialogue", "thought")
    private val SPEECH_KINDS = setOf("dialogue", "thought")
    private val NEW_GENDERS = setOf("male", "female", "unknown")
    private val ALLOWED_EMOTIONS = setOf("neutral", "happy", "sad", "angry", "afraid", "surprised", "tender", "sarcastic", "excited", "tired", "whispering")

    // Mã lý do từ chối (= listener_overrides); câu chữ cho người đọc nằm ở LocalStudio.
    const val UNKNOWN_LINE = "unknown_line"
    const val SOURCE_CHANGED = "source_changed"
    const val NOT_SPEECH = "not_speech"
    const val NO_VOICE = "no_voice"
    const val UNKNOWN_CHARACTER = "unknown_character"
    const val NOT_A_CHARACTER = "not_a_character"
    const val BAD_GENDER = "bad_gender"
    const val BAD_KIND = "bad_kind"
    const val BAD_EMOTION = "bad_emotion"
    const val BAD_TEXT = "bad_text"
    const val NARRATOR = "NARRATOR"
    const val UNNAMED = "UNNAMED"

    const val BAD_WISHES = "Phần ý muốn chờ Studio trong phần sửa không hợp lệ hay quá dài."
    private val BAD_ENTRY = mapOf(
        "pronunciations" to "Một ý muốn về cách đọc tên trong phần sửa không hợp lệ.",
        "speakers" to "Một ý muốn về người nói trong phần sửa không hợp lệ.",
        "lines" to "Một ý muốn về cách đọc câu trong phần sửa không hợp lệ.",
        "voices" to "Một ý muốn về giọng nhân vật trong phần sửa không hợp lệ.",
        "retakes" to "Một ý muốn thu lại câu trong phần sửa không hợp lệ.",
        ALIASES to "Một ý muốn gộp tên trong phần sửa không hợp lệ.",
    )

    // ---- chữ ----------------------------------------------------------------------------------------------------------

    private fun words(text: String): List<String> = text.split(Regex("[\\p{Z}\\s\\u001c-\\u001f\\u0085]+")).filter { it.isNotEmpty() }

    /** `" ".join(text.split())` của Python. */
    internal fun collapse(text: String): String = words(text).joinToString(" ")

    /** listener_overrides.character_key: tên chuẩn viết hoa, gộp khoảng trắng. */
    fun characterKey(name: String): String = collapse(VietnameseReading.casefold(BookEdits.pyStrip(name))).uppercase(Locale.ROOT)

    /** aliases.key: so hai cách viết một tên - NFC, gạch dưới là khoảng trắng, hạ chữ. */
    fun aliasKey(name: String): String =
        collapse(VietnameseReading.casefold(BookEdits.pyStrip(Normalizer.normalize(name, Normalizer.Form.NFC).replace('_', ' '))))

    private val VOICE_LABELS = mapOf("Anh Khôi" to "Thiện Minh", "Minh Quân Pro" to "Hải Đăng", "Mạnh Dũng" to "Quốc Tuấn")

    /** humanize.voice_label / voice_key: tên giọng hiển thị như VieNeu hiện hành, và ngược lại. */
    fun voiceLabel(name: String): String = VOICE_LABELS[name] ?: name

    fun voiceKey(name: String): String = VOICE_LABELS.entries.firstOrNull { it.value == name }?.key ?: name

    private val GENDER_LABELS = mapOf("male" to "Nam", "female" to "Nữ")

    private fun cutCodePoints(text: String, limit: Int): String = BookEdits.cut(text, limit)

    // ---- kiểm (dữ liệu của người lạ) -----------------------------------------------------------------------------------

    private fun time(value: Any?): Double? =
        if (BookEdits.isNumber(value) && (value as Number).toDouble() > 0 && value.toDouble() <= TIME_MAX) value.toDouble() else null

    private fun text(value: Any?, limit: Int, empty: Boolean = false): Boolean =
        value is String && (value.isNotEmpty() || empty) && BookEdits.isClean(value, limit)

    private fun entry(section: String, key: String, raw: Any?, nested: Boolean = false): JSONObject {
        val bad = BookEdits.EditsError(BAD_ENTRY.getValue(section))
        if (raw !is JSONObject) throw bad
        val allowed = ENTRY_KEYS.getValue(section) + (if (section in REPLACEABLE && !nested) setOf("replaced") else emptySet())
        if (BookEdits.names(raw).any { it !in allowed }) throw bad
        if (section in setOf("speakers", "lines", "retakes")) {
            if (!LINE_ID.matches(key)) throw bad
        } else if (!text(key, 200)) {
            throw bad
        }
        val out = JSONObject()
        out.put("requested_at", time(raw.opt("requested_at")) ?: throw bad)
        when (section) {
            "pronunciations" -> {
                val surface = raw.opt("surface")
                val spoken = raw.opt("spoken_form")
                if (!text(surface, SURFACE_MAX) || (surface as String).contains(' ') || !text(spoken, SPOKEN_FORM_MAX)) throw bad
                out.put("surface", surface).put("spoken_form", spoken)
            }
            "speakers" -> {
                val speaker = raw.opt("speaker")
                val sha = raw.opt("text_sha256")
                if (!text(speaker, SPEAKER_MAX) || sha !is String || !SHA256.matches(sha)) throw bad
                out.put("speaker", speaker).put("text_sha256", sha)
                if (raw.has("new")) {
                    val new = raw.opt("new")
                    if (new !is JSONObject || BookEdits.names(new).toSet() != setOf("gender") || new.opt("gender") !in NEW_GENDERS) throw bad
                    out.put("new", JSONObject().put("gender", new.getString("gender")))
                }
            }
            "lines" -> lineFields(raw, bad, out)
            "voices" -> {
                val preset = raw.opt("preset")
                val gender = raw.opt("gender")
                val avoid = raw.opt("avoid")
                if (!text(preset, PRESET_MAX, empty = true) || gender !in listOf("", "male", "female") || !text(avoid, SPEAKER_MAX, empty = true)) throw bad
                out.put("preset", preset).put("gender", gender).put("avoid", avoid)
            }
            else -> {
                val sha = raw.opt("text_sha256")
                if (sha !is String || !SHA256.matches(sha)) throw bad
                out.put("text_sha256", sha)
            }
        }
        if (raw.has("replaced")) out.put("replaced", entry(section, key, raw.opt("replaced"), nested = true))
        return out
    }

    private fun lineFields(raw: JSONObject, bad: BookEdits.EditsError, out: JSONObject) {
        val sha = raw.opt("text_sha256")
        val kind = raw.opt("kind")
        val emotion = raw.opt("emotion")
        val intensity = raw.opt("intensity")
        val intensityOk = intensity === JSONObject.NULL || intensity == null ||
            ((intensity is Int || intensity is Long) && (intensity as Number).toLong() in 0..INTENSITY_MAX.toLong())
        if (sha !is String || !SHA256.matches(sha) || kind !in listOf("") + LINE_KINDS || emotion !is String ||
            (emotion.isNotEmpty() && emotion !in ALLOWED_EMOTIONS) || !intensityOk
        ) throw bad
        out.put("text_sha256", sha).put("kind", kind).put("emotion", emotion)
            .put("intensity", if (intensity is Number) intensity.toLong() else JSONObject.NULL)
        if (raw.has("spoken")) {
            if (!text(raw.opt("spoken"), SPOKEN_TEXT_MAX, empty = true)) throw bad
            out.put("spoken", raw.opt("spoken"))
        }
    }

    /** Mục `wishes` của `edits.json` -> dạng chuẩn; sai thì [BookEdits.EditsError]. Mỗi mục con không rỗng, dưới trần của nó. */
    fun validate(raw: Any?): JSONObject {
        if (raw !is JSONObject || raw.length() == 0 || BookEdits.names(raw).any { it !in SECTIONS && it != ALIASES }) throw BookEdits.EditsError(BAD_WISHES)
        val out = JSONObject()
        for (section in SECTIONS) {
            if (!raw.has(section)) continue
            val entries = raw.opt(section)
            if (entries !is JSONObject || entries.length() == 0 || entries.length() > MAX_ENTRIES.getValue(section)) throw BookEdits.EditsError(BAD_WISHES)
            val kept = JSONObject()
            for (key in BookEdits.names(entries)) kept.put(key, entry(section, key, entries.opt(key)))
            out.put(section, kept)
        }
        if (raw.has(ALIASES)) out.put(ALIASES, aliases(raw.opt(ALIASES)))
        return out
    }

    private fun aliases(raw: Any?): JSONArray {
        val bad = BookEdits.EditsError(BAD_ENTRY.getValue(ALIASES))
        if (raw !is JSONArray || raw.length() == 0 || raw.length() > MAX_ENTRIES.getValue(ALIASES)) throw BookEdits.EditsError(BAD_WISHES)
        val out = JSONArray()
        val seen = HashSet<String>()
        for (index in 0 until raw.length()) {
            val item = raw.opt(index)
            if (item !is JSONObject || BookEdits.names(item).toSet() != setOf("alias", "person", "at")) throw bad
            val alias = item.opt("alias")
            val person = item.opt("person")
            val at = time(item.opt("at"))
            if (!text(alias, ALIAS_MAX) || !text(person, ALIAS_MAX) || at == null || !seen.add(alias as String)) throw bad
            out.put(JSONObject().put("alias", alias).put("person", person).put("at", at))
        }
        return out
    }

    // ---- thứ tự ghi, đếm, hợp -------------------------------------------------------------------------------------------

    private fun orderedEntry(value: JSONObject): Map<String, Any?> {
        val out = LinkedHashMap<String, Any?>()
        for (key in BookEdits.names(value).sorted()) {
            val item = value.opt(key)
            out[key] = if (item is JSONObject) orderedEntry(item) else item
        }
        return out
    }

    /** Dạng ghi ra `edits.json`: mục xếp theo khoá, khoá của mục xếp theo chữ - cùng nội dung thì cùng byte. */
    fun ordered(wishes: JSONObject): Map<String, Any?> {
        val out = LinkedHashMap<String, Any?>()
        for (section in SECTIONS) {
            val entries = wishes.optJSONObject(section)?.takeIf { it.length() > 0 } ?: continue
            out[section] = BookEdits.names(entries).sortedWith { a, b -> BookEdits.byCodePoints(a, b) }.associateWith { orderedEntry(entries.getJSONObject(it)) }
        }
        wishes.optJSONArray(ALIASES)?.takeIf { it.length() > 0 }?.let { list ->
            out[ALIASES] = (0 until list.length()).map { orderedEntry(list.getJSONObject(it)) }
        }
        return out
    }

    private fun clicks(entries: JSONObject?): Int =
        if (entries == null) 0 else BookEdits.names(entries).map { entries.getJSONObject(it).optDouble("requested_at") }.toSet().size

    /**
     * Số thay đổi chờ Studio (cho dòng "N thay đổi"): mỗi cách đọc, mỗi câu đổi cách đọc, mỗi giọng; nhiều câu cùng một lần bấm
     * (gán người nói cả nhóm, gộp tên, thu lại cả chương) tính là MỘT. Bí danh đi theo lần gộp nên không đếm riêng.
     */
    fun count(wishes: JSONObject?): Int {
        if (wishes == null) return 0
        return (wishes.optJSONObject("pronunciations")?.length() ?: 0) + (wishes.optJSONObject("lines")?.length() ?: 0) +
            (wishes.optJSONObject("voices")?.length() ?: 0) + clicks(wishes.optJSONObject("speakers")) + clicks(wishes.optJSONObject("retakes"))
    }

    /** Số mục từng loại trong trần ([merge] kiểm sau khi hợp: file hợp ra mà [validate] từ chối thì người nghe mất sạch). */
    fun fits(wishes: JSONObject): Boolean = MAX_ENTRIES.all { (name, cap) ->
        (wishes.optJSONObject(name)?.length() ?: wishes.optJSONArray(name)?.length() ?: 0) <= cap
    }

    /**
     * Hợp ý muốn trên máy (`local`) với ý muốn trong file vừa mở (`incoming`): theo khoá mục; khoá cả hai cùng có mà khác nhau thì
     * THẮNG BÊN MÁY NÀY. Rút một ý muốn chỉ ở máy này (không có "bia mộ"): file còn mang nó thì nhập lại mang nó về. Trả (ý muốn
     * đã hợp, số khoá hai bên khác nhau); quá trần thì giữ nguyên của máy này.
     */
    fun merge(local: JSONObject?, incoming: JSONObject?): Pair<JSONObject, Int> {
        val ours = local ?: JSONObject()
        val theirs = incoming ?: JSONObject()
        val out = JSONObject()
        var conflicts = 0
        for (section in SECTIONS) {
            val mine = ours.optJSONObject(section) ?: JSONObject()
            val other = theirs.optJSONObject(section) ?: JSONObject()
            val merged = JSONObject()
            for (key in BookEdits.names(other)) merged.put(key, BookEdits.deepCopy(other.opt(key)))
            for (key in BookEdits.names(mine)) {
                merged.put(key, BookEdits.deepCopy(mine.opt(key)))
                if (other.has(key) && !StrictJson.equal(other.opt(key), mine.opt(key))) conflicts++
            }
            if (merged.length() > 0) out.put(section, merged)
        }
        val ourAliases = list(ours.optJSONArray(ALIASES))
        val theirAliases = list(theirs.optJSONArray(ALIASES))
        val taken = ourAliases.map { it.getString("alias") }.toSet()
        conflicts += theirAliases.count { it.getString("alias") in taken && ourAliases.none { mine -> StrictJson.equal(mine, it) } }
        val mergedAliases = JSONArray()
        for (item in ourAliases) mergedAliases.put(BookEdits.deepCopy(item))
        for (item in theirAliases) if (item.getString("alias") !in taken) mergedAliases.put(BookEdits.deepCopy(item))
        if (mergedAliases.length() > 0) out.put(ALIASES, mergedAliases)
        if (!fits(out)) return (BookEdits.deepCopy(ours) as JSONObject) to 0
        return out to conflicts
    }

    private fun list(array: JSONArray?): List<JSONObject> = array?.let { (0 until it.length()).map { index -> it.getJSONObject(index) } } ?: emptyList()

    /** {khoá tên chuẩn: giọng/giới đang chờ} - dòng nhân vật hiện "chờ áp dụng" (như store.pending_voices của dự án). */
    fun pendingVoices(wishes: JSONObject?): Map<String, JSONObject> {
        val out = LinkedHashMap<String, JSONObject>()
        val voices = wishes?.optJSONObject("voices") ?: return out
        for (key in BookEdits.names(voices)) {
            val item = voices.getJSONObject(key)
            val preset = item.optString("preset", "")
            val gender = item.optString("gender", "")
            if (preset.isNotEmpty() || gender.isNotEmpty()) {
                out[key] = JSONObject().put("preset", voiceLabel(preset)).put("gender", GENDER_LABELS[gender] ?: "")
            }
        }
        return out
    }

    // ---- đọc sách để kiểm một ý muốn trước khi ghi -------------------------------------------------------------------------

    /**
     * Tra một câu theo mã ổn định trong chữ đọc theo của cuốn đã nhập (chữ qua lớp sửa: tên người nói là tên đang hiện). Tìm
     * chương mang số đó trước (mã `c<chương>_s...`), không thấy mới duyệt hết; đã đọc chương nào thì nhớ lại.
     */
    class Lines(private val folder: File, private val book: JSONObject) {
        val chapters: List<JSONObject>
        private val read = HashSet<Long>()
        private val segmentsOf = HashMap<Long, List<JSONObject>>()
        private val byId = HashMap<String, Pair<JSONObject, JSONObject>>()

        init {
            val shown = BookEdits.applyManifest(book, BookEdits.load(folder))
            chapters = shown.optJSONArray("chapters")?.let { list ->
                (0 until list.length()).mapNotNull { list.optJSONObject(it) }.filter { it.opt("id") is Int || it.opt("id") is Long }
            } ?: emptyList()
        }

        fun idOf(chapter: JSONObject): Long = (chapter.opt("id") as Number).toLong()

        private fun load(chapter: JSONObject): List<JSONObject> {
            val number = idOf(chapter)
            if (read.add(number)) {
                val script = BookEdits.script(folder, book, number)
                val found = ArrayList<JSONObject>()
                val segments = script?.optJSONArray("segments")
                for (index in 0 until (segments?.length() ?: 0)) {
                    val segment = segments?.optJSONObject(index) ?: continue
                    val stableId = segment.opt("stableId")
                    if (stableId is String) {
                        found.add(segment)
                        byId[stableId] = chapter to segment
                    }
                }
                segmentsOf[number] = found
            }
            return segmentsOf[number] ?: emptyList()
        }

        /** Mọi câu có mã ổn định của một chương, theo thứ tự trong chữ đọc theo. */
        fun segments(chapter: JSONObject): List<JSONObject> = load(chapter)

        fun get(stableId: String): Pair<JSONObject, JSONObject>? {
            byId[stableId]?.let { return it }
            val hint = STABLE_ID.find(stableId)?.groupValues?.get(1)?.toLongOrNull() ?: -1L
            for (chapter in chapters.sortedBy { idOf(it) % PART_SPAN != hint }) {
                if (idOf(chapter) !in read) {
                    load(chapter)
                    byId[stableId]?.let { return it }
                }
            }
            return byId[stableId]
        }

        fun chapter(number: Long): JSONObject? = chapters.firstOrNull { idOf(it) == number }
    }

    /** Nhân vật của cuốn như người nghe thấy (tên đã đổi): characters + extras + carried. */
    fun people(folder: File, book: JSONObject): List<JSONObject> {
        val cast = BookEdits.cast(folder, book)
        return listOf("characters", "extras", "carried").flatMap { kind ->
            cast.optJSONArray(kind)?.let { list -> (0 until list.length()).mapNotNull { list.optJSONObject(it) } } ?: emptyList()
        }.filter { it.opt("name") is String }
    }

    private fun person(cast: List<JSONObject>, raw: String): JSONObject? {
        val key = characterKey(raw)
        return cast.firstOrNull { characterKey(it.getString("name")) == key }
    }

    /** listener_overrides.spoken_problem: chữ đem đọc dùng được cho câu có văn bản `original` chưa. Rỗng = trả về chữ của sách. */
    fun spokenProblem(original: String, spoken: String): String? {
        val text = BookEdits.pyStrip(spoken)
        if (text.isEmpty()) return null
        val length = text.codePointCount(0, text.length)
        if (length > SPOKEN_TEXT_MAX || length > 4 * BookEdits.pyStrip(original).let { it.codePointCount(0, it.length) } + 40) return BAD_TEXT
        if (text.codePoints().toArray().any { it < 32 } || text.codePoints().toArray().none { Character.isLetter(it) }) return BAD_TEXT
        return null
    }

    /**
     * Mã lý do Studio sẽ từ chối "ai nói câu này", hay null - như `speaker_target`: câu còn đó, chữ chưa đổi, là lời nói, người ấy
     * có giọng (hay người nghe TẠO người mới), trên chữ đọc theo của cuốn.
     */
    fun speakerProblem(lines: Lines, cast: List<JSONObject>, stableId: String, textSha256: String, speaker: String, newGender: String = "", asKind: String = ""): String? {
        val segment = lines.get(stableId)?.second ?: return UNKNOWN_LINE
        if (BookEdits.pyText(segment.opt("textSha256")) != textSha256) return SOURCE_CHANGED
        if ((asKind.ifEmpty { BookEdits.pyText(segment.opt("kind")) }) !in SPEECH_KINDS) return NOT_SPEECH
        if (speaker == UNNAMED || characterKey(speaker) == NARRATOR) return null
        val who = person(cast, speaker)
        if (who != null && BookEdits.truthy(who.opt("voice"))) return null
        if (newGender in NEW_GENDERS) {
            val display = collapse(speaker).uppercase(Locale.ROOT)
            if (display.isEmpty() || display == "NARRATOR" || display == "UNKNOWN" || display.startsWith("ANONYMOUS_")) return NO_VOICE
            return null
        }
        return NO_VOICE
    }

    /** Mã lý do Studio sẽ từ chối sửa cách đọc một câu (và người nói đi kèm), hay null - như `line_target` + `speaker_target`. */
    fun lineProblem(lines: Lines, cast: List<JSONObject>, stableId: String, textSha256: String, kind: String = "", emotion: String = "",
                    speaker: String = "", spoken: String? = null): String? {
        val segment = lines.get(stableId)?.second ?: return UNKNOWN_LINE
        if (BookEdits.pyText(segment.opt("textSha256")) != textSha256) return SOURCE_CHANGED
        if (kind.isNotEmpty() && kind !in LINE_KINDS) return BAD_KIND
        if (emotion.isNotEmpty() && emotion !in ALLOWED_EMOTIONS) return BAD_EMOTION
        if (spoken != null && spokenProblem(BookEdits.pyText(segment.opt("text")), spoken) != null) return BAD_TEXT
        if (speaker.isNotEmpty()) {
            return speakerProblem(lines, cast, stableId, textSha256, speaker, asKind = kind.ifEmpty { BookEdits.pyText(segment.opt("kind")) })
        }
        return null
    }

    /** Mã lý do Studio sẽ từ chối giọng/giới của một nhân vật, hay null. Tên giọng không kiểm ở đây - bước áp kiểm lại. */
    fun voiceProblem(cast: List<JSONObject>, character: String, gender: String = ""): String? {
        if (gender !in listOf("", "male", "female")) return BAD_GENDER
        if (characterKey(character) == NARRATOR) return NOT_A_CHARACTER
        val who = person(cast, character) ?: return UNKNOWN_CHARACTER
        return if (BookEdits.truthy(who.opt("voice"))) null else NO_VOICE
    }

    /** Mọi câu nói (lời thoại, nội tâm) của người `source` - [(mã câu, băm chữ)] - để gộp họ vào người khác. */
    fun speakerLines(lines: Lines, cast: List<JSONObject>, source: String): List<Pair<String, String>> {
        val who = person(cast, source)
        val labels = HashSet<String>().also { it.add(aliasKey(source)) }
        if (who != null) for (field in listOf("name", "displayName", "originalName")) if (BookEdits.truthy(who.opt(field))) labels.add(aliasKey(who.opt(field).toString()))
        val found = ArrayList<Pair<String, String>>()
        for (chapter in lines.chapters) {
            for (segment in lines.segments(chapter)) {
                if (BookEdits.pyText(segment.opt("kind")) in SPEECH_KINDS && BookEdits.truthy(segment.opt("textSha256")) &&
                    aliasKey(BookEdits.pyText(segment.opt("speaker"))) in labels
                ) found.add(segment.getString("stableId") to BookEdits.pyText(segment.opt("textSha256")))
            }
        }
        return found
    }

    /** Mọi câu có mã ổn định của một chương - [(mã câu, băm chữ)] - cho "Thu lại cả chương". */
    fun chapterLines(lines: Lines, chapterId: Long): List<Pair<String, String>> {
        val chapter = lines.chapter(chapterId) ?: return emptyList()
        return lines.segments(chapter).filter { BookEdits.truthy(it.opt("textSha256")) }
            .map { it.getString("stableId") to BookEdits.pyText(it.opt("textSha256")) }
    }

    // ---- ghi: các phép của listener_overrides, viết lại trên mục `wishes` ---------------------------------------------------

    private fun entriesOf(wishes: JSONObject, section: String): JSONObject =
        wishes.optJSONObject(section)?.let { BookEdits.deepCopy(it) as JSONObject } ?: JSONObject()

    /** Yêu cầu mới giữ yêu cầu nó thay (một tầng) trong `replaced` - "Hoàn tác" trả đúng yêu cầu cũ về chỗ. */
    private fun replacing(previous: Any?, entry: JSONObject): JSONObject {
        if (previous is JSONObject) {
            val kept = JSONObject()
            for (key in BookEdits.names(previous)) if (key != "replaced") kept.put(key, previous.opt(key))
            entry.put("replaced", kept)
        }
        return entry
    }

    private fun requestPronunciation(wishes: JSONObject, surface: String, spokenForm: String, now: Double) {
        val entries = entriesOf(wishes, "pronunciations")
        val key = VietnameseReading.surfaceKey(surface)
        entries.put(key, replacing(entries.opt(key), JSONObject().put("surface", BookEdits.pyStrip(surface))
            .put("spoken_form", collapse(spokenForm)).put("requested_at", now)))
        wishes.put("pronunciations", entries)
    }

    private fun requestSpeakers(wishes: JSONObject, lines: List<Pair<String, String>>, speaker: String, now: Double, newGender: String) {
        val entries = entriesOf(wishes, "speakers")
        for ((stableId, sha) in lines) {
            val entry = replacing(entries.opt(stableId), JSONObject().put("speaker", BookEdits.pyStrip(speaker))
                .put("text_sha256", BookEdits.pyStrip(sha)).put("requested_at", now))
            if (newGender in NEW_GENDERS) entry.put("new", JSONObject().put("gender", newGender))
            entries.put(stableId, entry)
        }
        wishes.put("speakers", entries)
    }

    private fun requestLine(wishes: JSONObject, stableId: String, sha: String, kind: String, emotion: String, intensity: Long?,
                            speaker: String, spoken: String?, now: Double) {
        val lines = entriesOf(wishes, "lines")
        val before = lines.opt(stableId)
        val previous = if (before is JSONObject && before.opt("text_sha256") == BookEdits.pyStrip(sha)) before else JSONObject()
        val entry = JSONObject().put("text_sha256", BookEdits.pyStrip(sha))
            .put("kind", BookEdits.pyStrip(kind).ifEmpty { BookEdits.pyText(previous.opt("kind")) })
            .put("emotion", BookEdits.pyStrip(emotion).ifEmpty { BookEdits.pyText(previous.opt("emotion")) })
            .put("intensity", intensity ?: previous.opt("intensity").takeIf { it is Number }?.let { (it as Number).toLong() } ?: JSONObject.NULL)
            .put("requested_at", now)
        if (spoken != null) entry.put("spoken", collapse(spoken)) else if (previous.opt("spoken") is String) entry.put("spoken", previous.getString("spoken"))
        lines.put(stableId, entry)
        wishes.put("lines", lines)
        if (speaker.isNotEmpty()) {
            val speakers = entriesOf(wishes, "speakers")
            speakers.put(stableId, JSONObject().put("speaker", BookEdits.pyStrip(speaker)).put("text_sha256", BookEdits.pyStrip(sha)).put("requested_at", now))
            wishes.put("speakers", speakers)
        }
    }

    private fun requestVoice(wishes: JSONObject, character: String, preset: String, gender: String, avoid: String, now: Double) {
        val entries = entriesOf(wishes, "voices")
        val key = characterKey(character)
        entries.put(key, replacing(entries.opt(key), JSONObject().put("preset", BookEdits.pyStrip(preset)).put("gender", BookEdits.pyStrip(gender))
            .put("avoid", BookEdits.pyStrip(avoid)).put("requested_at", now)))
        wishes.put("voices", entries)
    }

    private fun requestRetake(wishes: JSONObject, stableId: String, sha: String, now: Double) {
        val entries = entriesOf(wishes, "retakes")
        entries.put(stableId, JSONObject().put("text_sha256", BookEdits.pyStrip(sha)).put("requested_at", now))
        wishes.put("retakes", entries)
    }

    private fun cancelRetake(wishes: JSONObject, stableId: String) {
        val entries = entriesOf(wishes, "retakes")
        if (entries.has(stableId)) {
            entries.remove(stableId)
            wishes.put("retakes", entries)
        }
    }

    /** Những ý muốn trong `section` do CHÍNH một lần bấm ghi: khoá thuộc `keys` và `requested_at` khớp (listener_overrides.requests_made_at). */
    private fun requestsMadeAt(wishes: JSONObject, section: String, keys: List<String>, requestedAt: Double): LinkedHashMap<String, JSONObject> {
        val found = LinkedHashMap<String, JSONObject>()
        val entries = wishes.optJSONObject(section) ?: return found
        for (key in keys.distinct()) {
            val item = entries.opt(key)
            if (item is JSONObject && Math.abs(item.optDouble("requested_at", 0.0) - requestedAt) < 1e-6) found[key] = item
        }
        return found
    }

    private fun withdrawRequests(wishes: JSONObject, section: String, keys: List<String>, requestedAt: Double): List<String> {
        val mine = requestsMadeAt(wishes, section, keys, requestedAt)
        if (mine.isNotEmpty()) {
            val current = wishes.getJSONObject(section)
            val entries = JSONObject()
            for (key in BookEdits.names(current)) if (key !in mine) entries.put(key, current.opt(key))
            for ((key, item) in mine) item.optJSONObject("replaced")?.let { entries.put(key, it) }
            wishes.put(section, entries)
        }
        return mine.keys.toList()
    }

    private fun change(folder: File, aliases: ((List<JSONObject>) -> List<JSONObject>)? = null, action: (JSONObject) -> Unit) = BookEdits.locked {
        val edits = BookEdits.load(folder)
        val current = edits.optJSONObject("wishes") ?: JSONObject()
        val wishes = BookEdits.deepCopy(current) as JSONObject
        wishes.remove(ALIASES)
        action(wishes)
        for (section in SECTIONS) if (wishes.optJSONObject(section)?.length() == 0) wishes.remove(section)
        val kept = if (aliases != null) aliases(list(current.optJSONArray(ALIASES))) else list(current.optJSONArray(ALIASES))
        if (kept.isNotEmpty()) wishes.put(ALIASES, JSONArray(kept.map { BookEdits.deepCopy(it) }))
        if (!fits(wishes)) throw BookEdits.EditsError(BookEdits.TOO_BIG)
        if (wishes.length() > 0) edits.put("wishes", wishes) else edits.remove("wishes")
        BookEdits.write(folder, edits)
    }

    fun requestPronunciation(folder: File, surface: String, spokenForm: String, now: Double) {
        val shown = BookEdits.cleanText(surface, SURFACE_MAX)
        val reading = BookEdits.cleanText(spokenForm, SPOKEN_FORM_MAX)
        change(folder) { requestPronunciation(it, shown, reading, now) }
    }

    fun requestSpeakers(folder: File, lines: List<Pair<String, String>>, speaker: String, now: Double, newGender: String = "") {
        val shown = BookEdits.cleanText(speaker, SPEAKER_MAX)
        change(folder) { requestSpeakers(it, lines, shown, now, newGender) }
    }

    fun requestLine(folder: File, stableId: String, textSha256: String, kind: String = "", emotion: String = "", intensity: Long? = null,
                    speaker: String = "", spoken: String? = null, now: Double) {
        val shown = BookEdits.cleanText(speaker, SPEAKER_MAX)
        val reading = spoken?.let { BookEdits.cleanText(it, SPOKEN_TEXT_MAX) }
        change(folder) { requestLine(it, stableId, textSha256, kind, emotion, intensity, shown, reading, now) }
    }

    fun requestVoice(folder: File, character: String, preset: String = "", gender: String = "", avoid: String = "", now: Double) {
        val shown = BookEdits.cleanText(character, SPEAKER_MAX)
        change(folder) { requestVoice(it, shown, BookEdits.cleanText(preset, PRESET_MAX), gender, BookEdits.cleanText(avoid, SPEAKER_MAX), now) }
    }

    /** Một lần bấm cho nhiều câu (cả chương) - cùng một `requested_at`, một lần ghi file. */
    fun requestRetakes(folder: File, lines: List<Pair<String, String>>, now: Double) {
        change(folder) { wishes -> for ((stableId, sha) in lines) requestRetake(wishes, stableId, sha, now) }
    }

    fun cancelRetake(folder: File, stableId: String) {
        change(folder) { cancelRetake(it, stableId) }
    }

    /** "`alias` là `person`": cất để chủ máy sản xuất ghi vào aliases.json của dự án. Cùng tên bí danh thì mới thay cũ. Trả true khi có gì mới được ghi. */
    fun requestAlias(folder: File, alias: String, person: String, now: Double): Boolean {
        val from = BookEdits.cleanText(alias, ALIAS_MAX)
        val to = BookEdits.cleanText(person, ALIAS_MAX)
        if (from.isEmpty() || to.isEmpty() || aliasKey(from) == aliasKey(to)) return false
        var wrote = false
        change(folder, aliases = { entries ->
            if (entries.any { it.getString("alias") == from && it.getString("person") == to }) {
                entries
            } else {
                wrote = true
                entries.filter { it.getString("alias") != from } + JSONObject().put("alias", from).put("person", to).put("at", now)
            }
        }) { }
        return wrote
    }

    fun madeAt(folder: File, section: String, keys: List<String>, requestedAt: Double): Map<String, JSONObject> =
        requestsMadeAt(BookEdits.load(folder).optJSONObject("wishes") ?: JSONObject(), section, keys, requestedAt)

    /**
     * Rút ý muốn của đúng một lần bấm: ý muốn nó thay (`replaced`) trở lại, hoặc biến mất. "Gộp vào…" ghi cả bí danh cùng mốc ấy -
     * rút lần gộp là rút luôn bí danh. Trả các khoá đã rút.
     */
    fun withdraw(folder: File, section: String, keys: List<String>, requestedAt: Double): List<String> {
        var removed: List<String> = emptyList()
        change(folder, aliases = { entries ->
            if (section == "speakers" && removed.isNotEmpty()) entries.filter { Math.abs(it.optDouble("at", 0.0) - requestedAt) >= 1e-6 } else entries
        }) { wishes ->
            removed = if (section == "retakes") {
                val mine = requestsMadeAt(wishes, section, keys, requestedAt).keys.toList()
                for (stableId in mine) cancelRetake(wishes, stableId)
                mine
            } else {
                withdrawRequests(wishes, section, keys, requestedAt)
            }
        }
        return removed
    }

    // ---- danh sách "đang chờ Studio" --------------------------------------------------------------------------------------

    private val QUOTE_OPENERS = mapOf('“' to '”', '"' to '"', '‘' to '’', '\'' to '\'', '«' to '»', '「' to '」', '『' to '』')
    private val EMOTIONS = mapOf("neutral" to "Bình thường", "happy" to "Vui", "sad" to "Buồn", "angry" to "Giận", "afraid" to "Sợ",
        "surprised" to "Ngạc nhiên", "tender" to "Dịu dàng", "sarcastic" to "Mỉa mai", "excited" to "Hào hứng", "tired" to "Mệt mỏi",
        "whispering" to "Thì thầm")
    private val KIND_LABELS = mapOf("narration" to "lời kể", "dialogue" to "lời thoại", "thought" to "nội tâm")

    /** store.quote_line: một câu trích cắt ở 70 ký tự; câu đã có ngoặc của sách thì không bọc thêm một lớp nữa. */
    fun quoteLine(raw: String): String {
        val text = collapse(raw)
        val long = text.codePointCount(0, text.length) > 70
        val first = text.firstOrNull()
        if (first != null && first in QUOTE_OPENERS) return if (long) cutCodePoints(text, 70) + "…" + QUOTE_OPENERS.getValue(first) else text
        return if (long) "“" + cutCodePoints(text, 70) + "…”" else "“$text”"
    }

    private fun labelLine(text: String, entry: JSONObject): String {
        val what = ArrayList<String>()
        val kind = BookEdits.pyText(entry.opt("kind"))
        if (kind.isNotEmpty()) what.add("đọc là ${KIND_LABELS[kind] ?: kind}")
        val emotion = BookEdits.pyText(entry.opt("emotion"))
        if (emotion.isNotEmpty()) what.add("cảm xúc ${(EMOTIONS[emotion] ?: emotion).lowercase(Locale.ROOT)}")
        val spoken = entry.opt("spoken")
        if (spoken is String) what.add(if (spoken.isNotEmpty()) "chữ đem đọc “${cutCodePoints(spoken, 50)}”" else "đọc lại theo chữ sách")
        return quoteLine(text) + ": " + (if (what.isEmpty()) "cách đọc mới" else what.joinToString(", "))
    }

    private fun labelVoice(name: String, entry: JSONObject): String {
        val preset = BookEdits.pyText(entry.opt("preset"))
        val change = preset.ifEmpty { mapOf("male" to "giọng nam", "female" to "giọng nữ")[BookEdits.pyText(entry.opt("gender"))] ?: "giọng khác" }
        return "Giọng của $name: $change"
    }

    /** `shown_name` của Python: tên người nghe thấy của một người trong ý muốn ("người kể", tên đã đổi, hay chính chữ gõ). */
    private fun shownName(cast: List<JSONObject>, raw: String): String {
        if (characterKey(raw) == NARRATOR) return "người kể"
        val found = person(cast, raw) ?: return raw
        return listOf(found.opt("displayName"), found.opt("name")).first { BookEdits.truthy(it) }.toString()
    }

    /** `by_line` của Python: ý muốn theo từng câu cho trang đọc - {pronunciations: [...], lines: {mã câu: {speaker?, delivery?, retake?}}}. */
    fun byLine(folder: File, book: JSONObject, wishes: JSONObject?): JSONObject {
        fun keys(section: String): List<String> =
            wishes?.optJSONObject(section)?.let { entries -> BookEdits.names(entries).sortedWith { a, b -> BookEdits.byCodePoints(a, b) } } ?: emptyList()
        fun entry(section: String, key: String): JSONObject = wishes!!.getJSONObject(section).getJSONObject(key)
        val cast = if (keys("speakers").isNotEmpty()) people(folder, book) else emptyList()
        val pronunciations = JSONArray()
        for (key in keys("pronunciations")) {
            val item = entry("pronunciations", key)
            pronunciations.put(JSONObject().put("key", key).put("surface", item.getString("surface")).put("spokenForm", item.getString("spoken_form"))
                .put("requestedAt", item.getDouble("requested_at")))
        }
        val lines = JSONObject()
        fun slot(stableId: String): JSONObject = lines.optJSONObject(stableId) ?: JSONObject().also { lines.put(stableId, it) }
        for (stableId in keys("speakers")) {
            val item = entry("speakers", stableId)
            slot(stableId).put("speaker", JSONObject().put("name", item.getString("speaker")).put("shown", shownName(cast, item.getString("speaker")))
                .put("requestedAt", item.getDouble("requested_at")))
        }
        for (stableId in keys("lines")) {
            val item = entry("lines", stableId)
            val delivery = JSONObject().put("kind", item.getString("kind")).put("emotion", item.getString("emotion"))
                .put("intensity", item.opt("intensity") ?: JSONObject.NULL).put("requestedAt", item.getDouble("requested_at"))
            if (item.has("spoken")) delivery.put("spoken", item.getString("spoken"))
            slot(stableId).put("delivery", delivery)
        }
        for (stableId in keys("retakes")) slot(stableId).put("retake", JSONObject().put("requestedAt", entry("retakes", stableId).getDouble("requested_at")))
        return JSONObject().put("pronunciations", pronunciations).put("lines", lines)
    }

    /**
     * Cùng hình dạng với `store.pending_details` của dự án ({items, lines, chapters, seconds}) - từng ý muốn nói bằng lời, đủ để rút
     * đúng nó (`section`, `key`, `requestedAt`) - nhưng không có câu nào "đã thu" để đếm: cuốn này chưa thu lại gì.
     */
    fun pendingDetails(folder: File, book: JSONObject, wishes: JSONObject?): JSONObject {
        val out = JSONObject().put("items", JSONArray()).put("lines", 0).put("chapters", JSONArray()).put("seconds", 0.0)
        if (wishes == null || SECTIONS.none { (wishes.optJSONObject(it)?.length() ?: 0) > 0 }) return out
        val lines = Lines(folder, book)
        val cast = people(folder, book)
        val titles = lines.chapters.associate { lines.idOf(it) to (listOf(it.opt("fullTitle"), it.opt("title")).firstOrNull { v -> BookEdits.truthy(v) }?.toString() ?: "") }
        val items = out.getJSONArray("items")

        fun who(raw: String): String = shownName(cast, raw)

        fun handle(item: JSONObject, section: String, key: String, entry: JSONObject): JSONObject =
            item.put("section", section).put("key", key).put("requestedAt", entry.optDouble("requested_at", 0.0))

        fun sortedKeys(section: String): List<String> =
            wishes.optJSONObject(section)?.let { entries -> BookEdits.names(entries).sortedWith { a, b -> BookEdits.byCodePoints(a, b) } } ?: emptyList()

        for (key in sortedKeys("pronunciations")) {
            val entry = wishes.getJSONObject("pronunciations").getJSONObject(key)
            items.put(handle(JSONObject().put("kind", "pronunciation")
                .put("label", "“${entry.getString("surface")}” đọc là “${entry.getString("spoken_form")}”").put("lines", 0), "pronunciations", key, entry))
        }
        val clicks = LinkedHashMap<Double, MutableList<String>>()
        for (stableId in sortedKeys("speakers")) {
            if (lines.get(stableId) != null) clicks.getOrPut(wishes.getJSONObject("speakers").getJSONObject(stableId).getDouble("requested_at")) { ArrayList() }.add(stableId)
        }
        for ((at, ids) in clicks) {
            val entry = wishes.getJSONObject("speakers").getJSONObject(ids[0])
            val (chapter, segment) = lines.get(ids[0])!!
            val speaker = who(entry.getString("speaker"))
            if (ids.size == 1) {
                items.put(handle(JSONObject().put("kind", "speaker")
                    .put("label", quoteLine(BookEdits.pyText(segment.opt("text"))) + " là lời của " + speaker)
                    .put("chapter", titles[lines.idOf(chapter)] ?: "").put("lines", 0), "speakers", ids[0], entry))
                continue
            }
            val places = ids.map { lines.idOf(lines.get(it)!!.first) }.toSortedSet().toList()
            items.put(JSONObject().put("kind", "speaker").put("label", "${ids.size} câu là lời của $speaker")
                .put("chapter", (titles[places[0]] ?: "") + (if (places.size > 1) " và ${places.size - 1} chương khác" else ""))
                .put("lines", 0).put("section", "speakers").put("key", ids[0]).put("keys", JSONArray(ids)).put("requestedAt", at))
        }
        for (stableId in sortedKeys("lines")) {
            val (chapter, segment) = lines.get(stableId) ?: continue
            val entry = wishes.getJSONObject("lines").getJSONObject(stableId)
            items.put(handle(JSONObject().put("kind", "line").put("label", labelLine(BookEdits.pyText(segment.opt("text")), entry))
                .put("chapter", titles[lines.idOf(chapter)] ?: "").put("lines", 0), "lines", stableId, entry))
        }
        for (key in sortedKeys("voices")) {
            val entry = wishes.getJSONObject("voices").getJSONObject(key)
            items.put(handle(JSONObject().put("kind", "voice").put("label", labelVoice(who(key), entry)).put("lines", 0), "voices", key, entry))
        }
        val retakeClicks = LinkedHashMap<Double, MutableList<String>>()
        for (stableId in sortedKeys("retakes")) {
            retakeClicks.getOrPut(wishes.getJSONObject("retakes").getJSONObject(stableId).getDouble("requested_at")) { ArrayList() }.add(stableId)
        }
        for ((at, ids) in retakeClicks) {
            val known = ids.filter { lines.get(it) != null }
            if (known.isEmpty()) continue
            val (chapter, segment) = lines.get(known[0])!!
            val where = titles[lines.idOf(chapter)] ?: ""
            if (ids.size == 1) {
                items.put(handle(JSONObject().put("kind", "retake").put("label", "Thu lại " + quoteLine(BookEdits.pyText(segment.opt("text"))))
                    .put("chapter", where).put("lines", 0), "retakes", known[0], wishes.getJSONObject("retakes").getJSONObject(known[0])))
            } else {
                items.put(JSONObject().put("kind", "retake").put("label", "Thu lại cả chương (${ids.size} câu)").put("chapter", where).put("lines", 0)
                    .put("section", "retakes").put("key", ids[0]).put("keys", JSONArray(ids)).put("requestedAt", at))
            }
        }
        return out
    }

    internal val byClick: Set<String> get() = BY_CLICK
}
