package vn.abook.player

import java.io.File
import java.security.MessageDigest
import org.json.JSONArray
import org.json.JSONObject

/** Explicit ranges for imported read-along rows. The package carries no scene authority. */
object PackageScriptView {
    private val speechKinds = setOf("dialogue", "thought")
    private fun title(chapter: JSONObject) = chapter.optString("fullTitle").ifEmpty { chapter.optString("title") }
    private fun revision(lines: JSONArray): String = MessageDigest.getInstance("SHA-256")
        .digest(lines.toString().toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

    fun contents(folder: File): JSONObject {
        val book = BookEdits.rawBook(folder)
        val index = BookWishes.Lines(folder, book)
        val chapters = JSONArray()
        for (chapter in index.chapters) {
            val rows = index.segments(chapter)
            chapters.put(JSONObject().put("chapterId", index.idOf(chapter)).put("index", chapter.optInt("index", index.idOf(chapter).toInt()))
                .put("title", title(chapter)).put("lines", rows.size).put("speech", rows.count { it.optString("kind") in speechKinds })
                .put("hints", 0).put("decided", 0))
        }
        return JSONObject().put("castReady", BookWishes.people(folder, book).any { BookEdits.truthy(it.opt("voice")) }).put("chapters", chapters)
    }

    fun chapter(folder: File, id: Long): JSONObject? {
        val book = BookEdits.rawBook(folder)
        val index = BookWishes.Lines(folder, book)
        val chapter = index.chapter(id) ?: return null
        val cast = BookWishes.people(folder, book)
        val wishes = BookEdits.load(folder).optJSONObject("wishes") ?: JSONObject()
        val heldSpeakers = BookEdits.holderEdits(folder)?.optJSONObject("speakers")
        val lines = JSONArray()
        val counts = HashMap<String, Int>()
        for ((seq, row) in index.segments(chapter).withIndex()) {
            val stable = row.getString("stableId")
            val sha = row.optString("textSha256")
            val shown = row.optString("speaker")
            val matches = if (shown.isEmpty()) emptyList() else cast.filter { person ->
                listOf("name", "displayName", "originalName").any { BookWishes.aliasKey(shown) == BookWishes.aliasKey(person.optString(it)) }
            }
            val current = if (matches.size == 1) BookWishes.characterKey(matches.single().getString("name")) else "line:$stable"
            val kind = row.optString("kind", "narration")
            val editable = kind in speechKinds && sha.isNotEmpty()
            if (editable) counts[current] = (counts[current] ?: 0) + 1
            val wish = wishes.optJSONObject("speakers")?.optJSONObject(stable)?.takeIf { it.optString("text_sha256") == sha }
            val held = heldSpeakers?.optJSONObject(stable)
            val delivery = wishes.optJSONObject("lines")?.optJSONObject(stable)?.takeIf { it.optString("text_sha256") == sha }
            val lineWish = delivery?.let { JSONObject().put("kind", it.optString("kind")).put("emotion", it.optString("emotion"))
                .put("intensity", it.opt("intensity") ?: JSONObject.NULL).put("spoken", it.opt("spoken") ?: JSONObject.NULL).put("state", "pending") }
            lines.put(JSONObject().put("segmentId", row.optInt("id")).put("stableId", stable).put("textSha256", sha).put("seq", seq)
                .put("paragraph", row.opt("paragraph") ?: JSONObject.NULL).put("text", row.optString("text")).put("kind", kind)
                .put("speaker", current).put("current", current).put("label", shown).put("editable", editable).put("hasAudio", false)
                .put("hint", JSONObject.NULL).put("scene", JSONObject.NULL).put("sceneBreak", false)
                .put("wish", wish?.let { JSONObject().put("value", it.getString("speaker")).put("label", it.getString("speaker")).put("state", "pending") }
                    ?: held?.let { JSONObject().put("value", it.optString("name")).put("label", it.optString("shown").ifEmpty { it.optString("name") }).put("state", "pending") } ?: JSONObject.NULL)
                .put("lineWish", lineWish ?: JSONObject.NULL).put("emotion", JSONObject.NULL).put("intensity", JSONObject.NULL).put("spoken", JSONObject.NULL))
        }
        val here = JSONArray()
        val others = JSONArray()
        for (person in cast.filter { BookEdits.truthy(it.opt("voice")) }) {
            val value = BookWishes.characterKey(person.getString("name"))
            val count = counts[value] ?: 0
            val item = JSONObject().put("value", value).put("label", person.optString("displayName").ifEmpty { person.getString("name") }).put("lines", count)
            (if (count > 0) here else others).put(item)
        }
        val order = index.chapters.map(index::idOf)
        val at = order.indexOf(id)
        return JSONObject().put("chapterId", id).put("index", chapter.optInt("index", id.toInt())).put("title", title(chapter))
            .put("previous", order.getOrNull(at - 1) ?: JSONObject.NULL).put("next", order.getOrNull(at + 1) ?: JSONObject.NULL)
            .put("castReady", here.length() + others.length() > 0).put("cast", here).put("others", others).put("firstPerson", JSONObject.NULL)
            .put("lines", lines).put("scopeRevision", revision(lines))
    }
}
