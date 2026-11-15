package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject

/** The tree owns order; playback always uses a projection across every volume. */
object BookVolumes {
    /** First `.abook` version whose book.json may carry `volumes` (book_volumes.py TREE_VERSION). */
    const val TREE_VERSION = 6

    fun selected(book: JSONObject, volumeId: Int?): JSONObject? {
        if (volumeId == null) return null
        project(book)
        val volumes = book.optJSONArray("volumes") ?: throw Mp3Export.Refused(S.s_volume_invalid)
        return (0 until volumes.length()).map { volumes.getJSONObject(it) }.firstOrNull { it.getInt("id") == volumeId }
            ?: throw Mp3Export.Refused(S.s_volume_invalid)
    }

    private fun integer(value: JSONObject, key: String): Int {
        val raw = value.get(key)
        require(raw is Int || (raw is Long && raw in Int.MIN_VALUE.toLong()..Int.MAX_VALUE.toLong()))
        return (raw as Number).toInt()
    }

    fun project(book: JSONObject): JSONObject {
        val volumes = book.optJSONArray("volumes") ?: return book
        require(volumes.length() in 1..99)
        val projection = book.optJSONArray("chapters")
        if (projection != null) {
            val membership = HashMap<Int, Int>()
            val grouped = LinkedHashMap<Int, JSONArray>()
            for (i in 0 until volumes.length()) {
                val volume = volumes.getJSONObject(i)
                val id = integer(volume, "id")
                grouped[id] = JSONArray()
                val rows = volume.optJSONArray("chapters") ?: JSONArray()
                for (j in 0 until rows.length()) membership[integer(rows.getJSONObject(j), "id")] = id
            }
            for (i in 0 until projection.length()) {
                val row = projection.getJSONObject(i)
                val id = if (row.has("volumeId")) integer(row, "volumeId") else membership[integer(row, "id")] ?: grouped.keys.last()
                require(grouped.containsKey(id))
                grouped.getValue(id).put(row)
            }
            for (i in 0 until volumes.length()) {
                val volume = volumes.getJSONObject(i)
                volume.put("chapters", grouped.getValue(integer(volume, "id")))
            }
        }
        val chapters = JSONArray()
        val volumeIds = HashSet<Int>()
        val chapterIds = HashSet<Int>()
        for (i in 0 until volumes.length()) {
            val volume = volumes.getJSONObject(i)
            val id = integer(volume, "id")
            val title = volume.get("title")
            require(id in 1..999999999 && volumeIds.add(id) && integer(volume, "number") in 1..9999
                && title is String && title.isNotBlank() && title.length <= 240)
            require(!volume.has("cover") || volume.isNull("cover") || volume.opt("cover") is JSONObject)
            volume.optJSONObject("cover")?.let { require(Regex("covers/[1-9][0-9]{0,8}\\.jpg").matches(it.getString("file"))) }
            val rows = volume.getJSONArray("chapters")
            require(rows.length() > 0 || volumes.length() == 1)
            // A series file numbers chapters inside each part: the index only ascends within one volume (as book_volumes.py).
            var previousIndex = Int.MIN_VALUE
            for (j in 0 until rows.length()) {
                val row = rows.getJSONObject(j)
                require(chapterIds.add(integer(row, "id")))
                if (row.has("index")) {
                    val index = integer(row, "index")
                    require(index > previousIndex)
                    previousIndex = index
                }
                chapters.put(row.put("volumeId", id))
            }
        }
        if (projection != null) require((0 until projection.length()).map { integer(projection.getJSONObject(it), "id") } ==
            (0 until chapters.length()).map { integer(chapters.getJSONObject(it), "id") })
        return book.put("chapters", chapters)
    }

    fun nested(book: JSONObject): JSONObject {
        val result = JSONObject(book.toString())
        val rows = result.optJSONArray("chapters") ?: JSONArray()
        val definitions = result.optJSONArray("volumes") ?: JSONArray().put(JSONObject()
            .put("id", 1).put("number", 1).put("title", S.s_volume_number(1)).put("cover", JSONObject.NULL))
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
        val before = (0 until rows.length()).map { rows.getJSONObject(it).getInt("id") }
        project(result)
        val projected = result.getJSONArray("chapters")
        require(before == (0 until projected.length()).map { projected.getJSONObject(it).getInt("id") })
        result.remove("chapters")
        return result
    }
}
