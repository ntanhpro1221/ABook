package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject

/** Descriptive fields never participate in audio identity. */
object BookMetadata {
    val fields = listOf("author", "illustrator", "altTitles", "genres", "summary", "source")
    fun validate(raw: JSONObject): JSONObject {
        val out = JSONObject()
        for (key in raw.keys()) {
            require(key in fields) { "Invalid book metadata field" }
            val value = raw.get(key)
            val strings = when (key) {
                "altTitles", "genres" -> {
                    require(value is JSONArray) { "Invalid book metadata list" }
                    (0 until value.length()).map { value.get(it).also { text -> require(text is String) } as String }
                }
                "source" -> {
                    require(value is JSONObject && value.keys().asSequence().toSet() == setOf("url", "site")) { "Invalid book source" }
                    listOf("url", "site").map { value.get(it).also { text -> require(text is String) } as String }
                }
                else -> listOf(value.also { require(it is String) } as String)
            }
            require(strings.none { text -> text.any { it.code < 32 && it != '\n' && it != '\t' } }) { "Invalid book metadata text" }
            out.put(key, if (key == "altTitles" || key == "genres") JSONArray(strings.filter { it.isNotBlank() }) else value)
        }
        return out
    }
    /**
     * Nothing to show: absent, "", [] or a source whose url and site are both empty. The same rule as Python
     * `book_metadata.blank` (shared cases: tests/fixtures/book_metadata/set_metadata.json) - an untouched draft is no edit.
     */
    fun blank(value: Any?): Boolean = when (value) {
        null, JSONObject.NULL -> true
        is String -> value.isBlank()
        is JSONArray -> (0 until value.length()).all { value.opt(it).toString().isBlank() }
        is JSONObject -> value.keys().asSequence().all { key -> value.opt(key).let { it == null || it == JSONObject.NULL || it.toString().isBlank() } }
        else -> false
    }
    fun same(a: Any?, b: Any?): Boolean = (blank(a) && blank(b)) || StrictJson.equal(a, b)
    fun select(raw: JSONObject): JSONObject = validate(JSONObject().apply { for (key in fields) if (raw.has(key)) put(key, raw.get(key)) })

    fun version(raw: JSONObject): String {
        val values = JSONArray()
        for (key in listOf("title", "narrator", "series") + fields) values.put(raw.opt(key) ?: JSONObject.NULL)
        val chapters = JSONArray()
        raw.optJSONArray("chapters")?.let { rows -> for (index in 0 until rows.length()) {
            val row = rows.getJSONObject(index)
            chapters.put(JSONArray(listOf(row.opt("id"), row.opt("title"), row.opt("subtitle"), row.opt("fullTitle"))))
        } }
        values.put(chapters)
        return java.security.MessageDigest.getInstance("SHA-256").digest(values.toString().toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }.take(16)
    }
}
