package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject

/**
 * Luật gói người nghe của điện thoại - đúng `bookfile.listener_package_problems` bên Python, cùng một nguồn luật
 * (abook/webui/assets/listener_package.json, nạp vào BuildConfig.LISTENER_PACKAGE_RULES): chữ người nghe thấy không mang dấu nội bộ
 * (QA, mã câu, mã lỗi máy, nhãn vai cục bộ thô, dấu NPC trên tên người), và `book.json` chỉ có trường trong danh sách trắng (trạng thái
 * QA chỉ thuộc dự án). [BookDocumentWriter.seal] từ chối gói vi phạm - không lặng lẽ bỏ. Ca thử chung với Python:
 * tests/fixtures/book_files/listener_package_cases.json.
 */
object ListenerPackage {
    private val rules = JSONObject(BuildConfig.LISTENER_PACKAGE_RULES)
    private val internalMarker = Regex(rules.getString("internalMarker"))
    private val npcShown = Regex(rules.getString("npcShown"), RegexOption.IGNORE_CASE)
    private val scriptSpeaker = Regex(""""speaker":\s*"((?:[^"\\]|\\.)*)"""")
    private fun list(name: String): List<String> = rules.getJSONArray(name).let { array -> (0 until array.length()).map { array.getString(it) } }
    private val bookFields = list("listenerBookFields")
    private val chapterFields = list("listenerChapterFields")
    private val personFields = list("listenerPersonFields")
    private val nameFields = list("listenerNameFields")
    private val keys = rules.getJSONObject("keys").let { all -> all.keys().asSequence().associateWith { name -> all.getJSONArray(name).let { a -> (0 until a.length()).map { a.getString(it) }.toSet() } } }

    /** (chữ người nghe thấy có dấu nội bộ, trường book.json ngoài danh sách trắng) - rỗng cả hai là sạch. `read(tên mục)`: byte của mục trong gói. */
    fun problems(book: JSONObject, names: Collection<String>, read: (String) -> ByteArray): Pair<List<String>, List<String>> {
        val cast = if ("cast.json" in names) runCatching { JSONObject(String(read("cast.json"), Charsets.UTF_8)) }.getOrNull() else null
        val leaked = textProblems(book, cast).toMutableList()
        for (name in names) {
            if (name.startsWith("scripts/") && name.endsWith(".json") && leaked.isEmpty()) leaked += speakerProblems(name, read(name))
        }
        val withoutPackage = JSONObject(book.toString()).apply { remove("package") }
        return leaked to fieldProblems(withoutPackage)
    }

    private fun marked(value: Any?) = value is String && internalMarker.containsMatchIn(value)

    fun textProblems(book: JSONObject, cast: JSONObject?): List<String> {
        val found = ArrayList<String>()
        fun check(where: String, value: Any?) {
            if (marked(value)) found += "$where: $value"
        }
        for (field in bookFields) check("book.$field", book.opt(field))
        for (group in listOf("chapters", "volumes", "parts")) {
            for (item in objects(book.optJSONArray(group))) {
                val id = item.opt("id") ?: item.opt("number")
                for (field in chapterFields) check("$group[$id].$field", item.opt(field))
                for (chapter in objects(item.optJSONArray("chapters"))) {
                    for (field in chapterFields) check("chapters[${chapter.opt("id")}].$field", chapter.opt(field))
                }
            }
        }
        if (cast != null) {
            val narrator = cast.optJSONObject("narrator") ?: JSONObject()
            check("cast.narrator.voice", narrator.opt("voice"))
            for (voice in objects(narrator.optJSONArray("chapterVoices"))) {
                check("cast.narrator.chapterVoices.voice", voice.opt("voice"))
                for (chapter in objects(voice.optJSONArray("chapters"))) check("cast.narrator.chapterVoices.chapters", chapter.opt("title"))
            }
            for (chapter in objects(narrator.optJSONArray("exceptChapters"))) check("cast.narrator.exceptChapters", chapter.opt("title"))
            for (group in listOf("characters", "extras", "carried")) {
                for (person in objects(cast.optJSONArray(group))) {
                    for (field in personFields) check("cast.$group.$field", person.opt(field))
                    for (field in nameFields) {
                        val value = person.opt(field)
                        if (value is String && npcShown.containsMatchIn(value)) found += "cast.$group.$field: $value"
                    }
                }
            }
        }
        return found
    }

    /** Người nói trên dòng đọc theo (`scripts/<chương>.json`) có dấu nội bộ hay dấu NPC. */
    fun speakerProblems(name: String, data: ByteArray): List<String> =
        scriptSpeaker.findAll(String(data, Charsets.UTF_8)).map { JSONArray("[\"${it.groupValues[1]}\"]").getString(0) }.toSet()
            .filter { internalMarker.containsMatchIn(it) || npcShown.containsMatchIn(it) }.map { "$name.speaker: $it" }

    /** Trường của `book.json` ngoài danh sách trắng, dạng "chỗ.trường". */
    fun fieldProblems(book: JSONObject): List<String> {
        val found = ArrayList<String>()
        fun keep(where: String, item: JSONObject?, allowed: String) {
            if (item == null) return
            val set = keys.getValue(allowed)
            for (key in item.keys()) if (key !in set) found += "$where.$key"
        }
        keep("book", book, "book")
        for (chapter in objects(book.optJSONArray("chapters"))) keep("chapters[${chapter.opt("id")}]", chapter, "chapter")
        for (volume in objects(book.optJSONArray("volumes"))) {
            keep("volumes", volume, "volume")
            for (chapter in objects(volume.optJSONArray("chapters"))) keep("chapters[${chapter.opt("id")}]", chapter, "chapter")
        }
        for (part in objects(book.optJSONArray("parts"))) keep("parts", part, "part")
        val coverage = book.optJSONObject("audioCoverage")
        keep("audioCoverage", coverage, "coverage")
        for (item in objects(coverage?.optJSONArray("expected"))) keep("audioCoverage.expected", item, "expected")
        for (item in objects(coverage?.optJSONArray("missing"))) keep("audioCoverage.missing", item, "missing")
        return found
    }

    private fun objects(array: JSONArray?): List<JSONObject> = (0 until (array?.length() ?: 0)).mapNotNull { array!!.optJSONObject(it) }
}
