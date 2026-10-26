package vn.abook.player.ui.data

import org.json.JSONObject
import vn.abook.player.LibraryTree

/**
 * Gói sách (book.json / stream.json qua Store.manifest) + trạng thái nghe (Store.state) -> [ListenBook]: phần `toListenBook` của androidSource.ts,
 * đọc thẳng JSON của lõi, không qua plugin. Chạy ở luồng nền (LibraryRepo); hàm thuần nên thử được trên JVM với org.json thật.
 */
object BookJson {
    fun state(json: JSONObject?): ListenState {
        json ?: return ListenState.Empty
        val chapters = HashMap<Int, ChapterRecord>()
        json.optJSONObject("chapters")?.let { map ->
            for (key in map.keys()) {
                val id = key.toIntOrNull() ?: continue
                val record = map.optJSONObject(key) ?: continue
                chapters[id] = ChapterRecord(
                    heard = number(record, "heard") ?: 0.0,
                    done = record.optBoolean("done"),
                    duration = number(record, "duration"),
                )
            }
        }
        return ListenState(
            last = json.optJSONObject("last")?.let { last ->
                Last(last.optInt("chapterId"), number(last, "seconds") ?: 0.0, number(last, "at") ?: 0.0, rev(last.optJSONObject("rev")))
            },
            chapters = chapters,
            rate = number(json, "rate"),
            finished = json.optBoolean("finished"),
            finishedAt = number(json, "finishedAt"),
            finishedRev = rev(json.optJSONObject("_fieldRevs")?.optJSONObject("finished")),
            updatedAt = number(json, "updatedAt"),
        )
    }

    private fun number(json: JSONObject, key: String): Double? =
        if (json.has(key) && !json.isNull(key)) json.optDouble(key).takeIf { !it.isNaN() } else null

    private fun rev(json: JSONObject?): Rev? {
        json ?: return null
        val counter = json.optLong("counter", 0)
        val node = json.optString("node")
        if (counter <= 0 || node.isEmpty()) return null
        return Rev(counter, node, json.optString("epoch").takeIf { it.isNotEmpty() })
    }

    /** Chương nghe được của gói: có audio, hay chỉ có chữ (cùng bộ lọc với cây duyệt Android Auto - [LibraryTree.chapters]). */
    fun chapters(manifest: JSONObject): List<ChapterInfo> =
        LibraryTree.chapters(manifest).map { ChapterInfo(it.id, it.title, it.duration, available = !it.isText, textOnly = it.isText) }

    /** `coverOf(id)`: bìa người nghe thấy (Store.coverFile) - tách ra để hàm này không đụng đĩa. `remote`: cuốn nghe thẳng, chưa tải. */
    fun book(manifest: JSONObject, state: JSONObject?, coverOf: (String) -> CoverRef?, remote: RemoteRef? = null, addedAt: Double? = null): ListenBook {
        val id = manifest.getString("id")
        val listen = state(state)
        val all = chapters(manifest)
        val audio = all.filter { !it.textOnly }
        val entries = manifest.optJSONArray("chapters")
        val textOnly = entries != null && entries.length() > 0 &&
            (0 until entries.length()).all { LibraryTree.textEntry(entries.getJSONObject(it)).isNotEmpty() }
        val complete = manifest.optBoolean("complete", true)
        val progress = if (textOnly) ListenLogic.textBookProgress(listen, all) else ListenLogic.bookProgress(listen, audio, complete)
        val link = manifest.optJSONObject("series")?.let { s -> s.optString("root").takeIf { it.isNotEmpty() }?.let { SeriesLink(it, s.optInt("part", 1)) } }
        return ListenBook(
            id = id,
            title = manifest.optString("title"),
            author = manifest.optString("author").takeIf { it != "null" }.orEmpty(),
            narrator = manifest.optString("narrator").takeIf { it != "null" }.orEmpty(),
            duration = audio.sumOf { it.duration },
            chaptersTotal = manifest.optInt("chaptersTotal", entries?.length() ?: all.size),
            chaptersAvailable = audio.size,
            complete = complete,
            textOnly = textOnly,
            updatedAt = listen.updatedAt,
            addedAt = addedAt,
            state = listen,
            progress = progress,
            resume = ListenLogic.resumePoint(listen, complete, all),
            lastChapterTitle = all.firstOrNull { it.id == listen.last?.chapterId }?.title.orEmpty(),
            cover = coverOf(id),
            series = link,
            remote = remote,
            part = link?.part,
        )
    }
}
