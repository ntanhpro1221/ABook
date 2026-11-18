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

    /** Python `book_metadata.overlay`: publish the listener's descriptive edits in book.json; a blank one removes the field. */
    fun overlay(book: JSONObject, edits: JSONObject): JSONObject {
        if (fields.none { edits.has(it) }) return book
        for (key in fields) if (edits.has(key)) {
            val value = edits.get(key)
            if (blank(value)) book.remove(key) else book.put(key, value)
        }
        return book.put("metaVersion", version(book))
    }

    /**
     * `metaVersion` of a book.json: the same digest as Python `listen_view.metadata_version` (title, author, narrator, series link,
     * chapter names, shown descriptive fields, volumes), so one edit gives one book.json whichever device writes it. Shared cases:
     * tests/fixtures/book_metadata/meta_version.json.
     */
    fun version(raw: JSONObject): String {
        fun text(value: Any?): Any = if (value == null || value == JSONObject.NULL || value == "") "" else value
        fun plain(value: Any?): Any? = if (value == JSONObject.NULL) null else value
        val series = raw.opt("series") as? JSONObject
        val chapters = (raw.optJSONArray("chapters") ?: JSONArray()).let { rows ->
            (0 until rows.length()).mapNotNull { rows.opt(it) as? JSONObject }
                .map { listOf(plain(it.opt("id")), text(it.opt("title")), text(it.opt("subtitle")), text(it.opt("fullTitle"))) }
        }
        val shown = LinkedHashMap<String, Any?>()
        for (key in fields) {
            val value = raw.opt(key)
            if (blank(value)) continue
            shown[key] = when {
                // Python `validate` keeps the non-blank items of a list; a source is written url then site everywhere.
                value is JSONArray -> (0 until value.length()).map { value.opt(it) }.filter { it.toString().isNotBlank() }
                key == "source" && value is JSONObject -> linkedMapOf("url" to plain(value.opt("url")), "site" to plain(value.opt("site")))
                else -> value
            }
        }
        val volumes = (raw.optJSONArray("volumes") ?: JSONArray()).let { rows ->
            (0 until rows.length()).mapNotNull { rows.opt(it) as? JSONObject }.map { volume ->
                val members = volume.optJSONArray("chapters") ?: JSONArray()
                listOf(plain(volume.opt("id")), plain(volume.opt("number")), plain(volume.opt("title")), plain(volume.opt("cover")),
                    (0 until members.length()).map { plain(members.getJSONObject(it).opt("id")) })
            }
        }
        val values = listOf(text(raw.opt("title")), text(raw.opt("author")), text(raw.opt("narrator")),
            series?.let { listOf(plain(it.opt("root")), plain(it.opt("part"))) }, chapters, shown, volumes)
        return java.security.MessageDigest.getInstance("SHA-256").digest(StrictJson.dumps(values, null).toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }.take(16)
    }
}
