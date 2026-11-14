package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject

/** The tree owns order; playback always uses a projection across every volume. */
object BookVolumes {
    /** First `.abook` version whose book.json may carry `volumes` (book_volumes.py TREE_VERSION). */
    const val TREE_VERSION = 6

    /** Several volumes, or a volume with its own cover, are written as a tree; one plain volume stays a flat chapter list. */
    fun needsTree(book: JSONObject): Boolean {
        val volumes = book.optJSONArray("volumes") ?: return false
        if (volumes.length() > 1) return true
        return (0 until volumes.length()).any { volumes.getJSONObject(it).optJSONObject("cover") != null }
    }

    fun project(book: JSONObject): JSONObject {
        val volumes = book.optJSONArray("volumes") ?: return book
        require(volumes.length() in 1..99)
        val chapters = JSONArray()
        val volumeIds = HashSet<Int>()
        val chapterIds = HashSet<Int>()
        for (i in 0 until volumes.length()) {
            val volume = volumes.getJSONObject(i)
            val id = volume.getInt("id")
            require(id > 0 && volumeIds.add(id) && volume.getInt("number") > 0 && volume.getString("title").isNotBlank())
            volume.optJSONObject("cover")?.let { require(Regex("covers/[1-9][0-9]{0,8}\\.jpg").matches(it.getString("file"))) }
            val rows = volume.getJSONArray("chapters")
            require(rows.length() > 0)
            // A series file numbers chapters inside each part: the index only ascends within one volume (as book_volumes.py).
            var previousIndex = Int.MIN_VALUE
            for (j in 0 until rows.length()) {
                val row = rows.getJSONObject(j)
                require(chapterIds.add(row.getInt("id")))
                if (row.has("index")) {
                    val index = row.getInt("index")
                    require(index > previousIndex)
                    previousIndex = index
                }
                chapters.put(row.put("volumeId", id))
            }
        }
        return book.put("chapters", chapters)
    }

    fun nested(book: JSONObject): JSONObject {
        val result = JSONObject(book.toString())
        val rows = result.optJSONArray("chapters") ?: JSONArray()
        val definitions = result.optJSONArray("volumes") ?: JSONArray().put(JSONObject()
            .put("id", 1).put("number", 1).put("title", S.s_volume_number(1)))
        for (i in 0 until definitions.length()) {
            val volume = definitions.getJSONObject(i)
            val selected = JSONArray()
            for (j in 0 until rows.length()) {
                val chapter = rows.getJSONObject(j)
                if (chapter.optInt("volumeId", 1) == volume.getInt("id")) selected.put(chapter)
            }
            volume.put("chapters", selected)
        }
        result.put("volumes", definitions)
        if (!needsTree(result)) {
            result.remove("volumes")
            for (j in 0 until rows.length()) rows.getJSONObject(j).remove("volumeId")
            return result.put("chapters", rows)
        }
        project(result)
        result.remove("chapters")
        return result
    }
}
