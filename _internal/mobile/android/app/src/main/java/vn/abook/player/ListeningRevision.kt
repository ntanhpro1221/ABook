package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject

/** Shared bounded clock contract with Python and readingPosition.ts. */
internal object ListeningRevision {
    const val MAX_COUNTER = 1_099_511_627_776L
    const val MAX_JUMP = 1_000_000L
    const val OLD_PEER = "Máy kia đang dùng bản ABook cũ, hãy cập nhật cả hai máy"
    const val JUMP_NOTICE = "Một phần dữ liệu từ máy kia có bước nhảy phiên bản bất thường. App giữ bản của bạn; bạn hãy kiểm tra và đồng bộ lại từ máy có dữ liệu đúng."

    fun validNumber(value: Any?, minimum: Long = 0L) =
        (value is Int || value is Long) && (value as Number).toLong() in minimum..MAX_COUNTER

    fun validEpoch(value: Any?) = value is String && Regex("1*").matches(value)

    fun revision(item: JSONObject?): Pair<Long, String> {
        val rev = item?.optJSONObject("rev") ?: return 0L to ""
        val counter = rev.opt("counter")
        val node = rev.opt("node")
        return if (validNumber(counter, 1) && validEpoch(rev.opt("epoch") ?: "") && node is String && Regex("[A-Za-z0-9_-]{1,64}").matches(node))
            (counter as Number).toLong() to node else 0L to ""
    }
    fun order(item: JSONObject?): Triple<String, Long, String> {
        val (counter, node) = revision(item)
        return Triple(if (counter > 0) item?.optJSONObject("rev")?.optString("epoch", "") ?: "" else "", counter, node)
    }
    fun newer(theirs: JSONObject, ours: JSONObject?): Boolean {
        if (ours == null) return true
        val a = order(theirs)
        val b = order(ours)
        if (a.second > 0 || b.second > 0) return a.first > b.first || a.first == b.first &&
            (a.second > b.second || a.second == b.second && a.third > b.third)
        return theirs.optDouble("at", 0.0) > ours.optDouble("at", 0.0)
    }
    private fun items(state: JSONObject): List<JSONObject> = buildList {
        for (key in listOf("last", "reading")) state.optJSONObject(key)?.let { add(it) }
        state.optJSONObject("chapters")?.let { rows -> for (key in rows.keys()) rows.optJSONObject(key)?.let { add(it) } }
        state.optJSONArray("bookmarks")?.let { rows -> for (i in 0 until rows.length()) rows.optJSONObject(i)?.let { add(it) } }
        for (field in listOf("_fieldRevs", "_deletedRevs")) state.optJSONObject(field)?.let { rows ->
            for (key in rows.keys()) add(JSONObject().put("rev", rows.opt(key)))
        }
    }
    fun epoch(state: JSONObject): String = maxOf(
        if (validEpoch(state.opt("_epoch"))) state.optString("_epoch") else "",
        items(state).maxOfOrNull { order(it).first } ?: "")

    fun clock(state: JSONObject): Long {
        val era = epoch(state)
        val marker = if (validNumber(state.opt("_clock")) && state.optString("_epoch", "") == era) state.optLong("_clock") else 0L
        return maxOf(marker, items(state).map { order(it) }.filter { it.first == era }.maxOfOrNull { it.second } ?: 0L)
    }
    fun observe(state: JSONObject, rev: JSONObject) {
        val incoming = order(JSONObject().put("rev", rev))
        val current = epoch(state)
        val tick = clock(state)
        if (incoming.first >= current) {
            if (incoming.first.isNotEmpty()) state.put("_epoch", incoming.first)
            state.put("_clock", maxOf(if (incoming.first == current) tick else 0L, incoming.second))
        }
    }
    fun advance(state: JSONObject, node: String): JSONObject {
        var era = epoch(state)
        var counter = clock(state) + 1
        if (counter > MAX_COUNTER) { era += "1"; counter = 1L }
        val rev = JSONObject().put("counter", counter).put("node", node)
        if (era.isNotEmpty()) rev.put("epoch", era)
        observe(state, rev)
        return rev
    }

    fun checkedPeer(ours: JSONObject, incoming: JSONObject, notify: (String) -> Unit): JSONObject {
        val state = JSONObject(incoming.toString())
        val era = epoch(ours)
        val tick = clock(ours)
        fun accept(item: JSONObject?): Boolean {
            require(item != null && item.has("rev") && !item.isNull("rev")) { OLD_PEER }
            val (e, c, _) = order(item)
            if (c == 0L || e > era + "1" || e == era && c > tick + MAX_JUMP || e == era + "1" && c > MAX_JUMP) {
                notify(JUMP_NOTICE)
                return false
            }
            return true
        }
        for (key in listOf("last", "reading")) if (!state.isNull(key) && !accept(state.optJSONObject(key))) state.remove(key)
        val chapters = JSONObject()
        state.optJSONObject("chapters")?.let { rows -> for (key in rows.keys()) {
            val item = rows.optJSONObject(key)
            if (accept(item)) chapters.put(key, item)
        } }
        state.put("chapters", chapters)
        val marks = JSONArray()
        state.optJSONArray("bookmarks")?.let { rows -> for (i in 0 until rows.length()) {
            val item = rows.optJSONObject(i)
            if (accept(item)) marks.put(item)
        } }
        state.put("bookmarks", marks)
        val fields = JSONObject()
        for ((field, stamp) in listOf("rate" to "rateAt", "finished" to "finishedAt", "voice" to "voiceAt")) if (state.has(field)) {
            val rev = state.optJSONObject("_fieldRevs")?.opt(field)
            if (accept(JSONObject().put("rev", rev))) fields.put(field, rev) else { state.remove(field); state.remove(stamp) }
        }
        state.put("_fieldRevs", fields)
        val gone = JSONObject()
        val goneRevs = JSONObject()
        state.optJSONObject("deleted")?.let { rows -> for (key in rows.keys()) {
            val rev = state.optJSONObject("_deletedRevs")?.opt(key)
            if (accept(JSONObject().put("rev", rev))) { gone.put(key, rows.get(key)); goneRevs.put(key, rev) }
        } }
        state.put("deleted", gone).put("_deletedRevs", goneRevs)
        state.remove("_clock")
        state.remove("_epoch")
        return state
    }
}
