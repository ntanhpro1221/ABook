package vn.abook.player

import java.io.File
import org.json.JSONArray
import org.json.JSONObject

/** Sổ bền của từng bản xuất: bản mới không xoá lời nhắc thay file cũ đã gửi. */
object ExportHistory {
    const val FILE = "export_history.json"

    fun snapshot(plan: Mp3Export.Plan): JSONObject = JSONObject().apply {
        for (chapter in plan.chapters) put(chapter.id.toString(), Store.audioSha256(chapter.file))
    }

    fun snapshot(folder: File): JSONObject {
        val book = JSONObject(File(folder, "book.json").readText(Charsets.UTF_8))
        val chapters = book.optJSONArray("chapters") ?: JSONArray()
        return JSONObject().apply {
            for (index in 0 until chapters.length()) {
                val chapter = chapters.getJSONObject(index)
                if (!chapter.optBoolean("available")) continue
                val file = Store.contained(folder, chapter.getString("file"))
                if (file.isFile) put(chapter.getInt("id").toString(), Store.audioSha256(file))
            }
        }
    }

    private fun read(folder: File): JSONArray = File(folder, FILE).let {
        if (it.isFile) JSONArray(it.readText(Charsets.UTF_8)) else JSONArray()
    }

    @Synchronized fun remember(folder: File, kind: String, target: String, chapters: JSONObject) {
        val old = read(folder)
        val next = JSONArray()
        for (index in 0 until old.length()) old.getJSONObject(index).takeIf { it.getString("target") != target }?.let(next::put)
        next.put(JSONObject().put("kind", kind).put("target", target).put("chapters", chapters).put("createdAt", System.currentTimeMillis() / 1000.0))
        Store.writeAtomic(File(folder, FILE), next.toString())
    }

    @Synchronized fun view(folder: File): JSONArray {
        val records = read(folder)
        if (records.length() == 0) return records
        val current = snapshot(folder)
        for (index in 0 until records.length()) {
            val record = records.getJSONObject(index)
            val chapters = record.getJSONObject("chapters")
            record.put("changed", JSONArray(chapters.keys().asSequence().filter { chapters.optString(it) != current.optString(it) }.map { it.toInt() }.toList()))
        }
        return records
    }
}
