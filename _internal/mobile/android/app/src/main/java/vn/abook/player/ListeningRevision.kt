package vn.abook.player

import org.json.JSONObject

/** Shared bounded clock contract with Python and readingPosition.ts. */
internal object ListeningRevision {
    const val MAX_COUNTER = 1_099_511_627_776L
    const val MAX_JUMP = 1_000_000L
    /** Below half the range a counter is accepted whatever the receiver's clock (a new device takes a long-lived profile); even a
     *  forged peer can only push a profile here, still 2^39 edits from the ceiling. Above it a peer may lead by MAX_JUMP. */
    const val SAFE_COUNTER = MAX_COUNTER / 2
    const val MISSING_REVISION = "Dữ liệu đồng bộ thiếu phiên bản. Bạn hãy mở lại hồ sơ trên máy gửi rồi thử lại."
    const val JUMP_NOTICE = "Phiên bản đồng bộ bất thường; giữ bản của bạn — bạn đồng bộ từ máy có bản đúng."

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
        state.optJSONObject("_fieldRevs")?.let { rows ->
            for (key in rows.keys()) add(JSONObject().put("rev", rows.opt(key)))
        }
    }
    /** Record names, moves and active choices share one clock: `_clock`/`_epoch` at the top of records.json (Python meta_items). */
    fun metaItems(data: JSONObject): List<JSONObject> = buildList {
        for ((table, keys) in listOf("records" to listOf("nameRev", "movedRev"), "links" to listOf("activeRev"))) {
            data.optJSONObject(table)?.let { rows -> for (id in rows.keys()) rows.optJSONObject(id)?.let { row ->
                for (key in keys) if (row.has(key)) add(JSONObject().put("rev", row.opt(key)))
            } }
        }
    }
    fun epoch(state: JSONObject, source: (JSONObject) -> List<JSONObject> = { items(it) }): String = maxOf(
        if (validEpoch(state.opt("_epoch"))) state.optString("_epoch") else "",
        source(state).maxOfOrNull { order(it).first } ?: "")

    fun clock(state: JSONObject, source: (JSONObject) -> List<JSONObject> = { items(it) }): Long {
        val era = epoch(state, source)
        val marker = if (validNumber(state.opt("_clock")) && state.optString("_epoch", "") == era) state.optLong("_clock") else 0L
        return maxOf(marker, source(state).map { order(it) }.filter { it.first == era }.maxOfOrNull { it.second } ?: 0L)
    }
    fun observe(state: JSONObject, rev: JSONObject, source: (JSONObject) -> List<JSONObject> = { items(it) }) {
        val incoming = order(JSONObject().put("rev", rev))
        val current = epoch(state, source)
        val tick = clock(state, source)
        if (incoming.first >= current) {
            if (incoming.first.isNotEmpty()) state.put("_epoch", incoming.first)
            state.put("_clock", maxOf(if (incoming.first == current) tick else 0L, incoming.second))
        }
    }
    fun advance(state: JSONObject, node: String, source: (JSONObject) -> List<JSONObject> = { items(it) }): JSONObject {
        var era = epoch(state, source)
        var counter = clock(state, source) + 1
        if (counter > MAX_COUNTER) { era += "1"; counter = 1L }
        val rev = JSONObject().put("counter", counter).put("node", node)
        if (era.isNotEmpty()) rev.put("epoch", era)
        observe(state, rev, source)
        return rev
    }

    /** A peer revision this receiver must not adopt: invalid, more than one epoch ahead, or a leap in the upper half. */
    fun implausible(era: String, tick: Long, item: JSONObject?): Boolean {
        val (e, c, _) = order(item)
        return c == 0L || e > era + "1" || e == era && c > SAFE_COUNTER && c > tick + MAX_JUMP || e == era + "1" && c > MAX_JUMP
    }

    /** Name, move or active choice from a peer (Python meta_newer): both sides versioned -> the revision decides, so a slow wall
     *  clock never reverts a later edit; a peer without metadata revisions (0.4.133) still compares wall-clock stamps. */
    fun metaNewer(data: JSONObject, theirs: Any?, theirAt: Double, ours: Any?, ourAt: Double, notify: (String) -> Unit): Boolean {
        val their = if (theirs == null || theirs == JSONObject.NULL) null else JSONObject().put("rev", theirs)
        if (their != null && implausible(epoch(data) { metaItems(it) }, clock(data) { metaItems(it) }, their)) {
            notify(JUMP_NOTICE)
            return false
        }
        val a = order(their)
        val b = order(if (ours == null || ours == JSONObject.NULL) null else JSONObject().put("rev", ours))
        if (a.second > 0 && b.second > 0) return a.first > b.first || a.first == b.first &&
            (a.second > b.second || a.second == b.second && a.third > b.third)
        return (theirAt.takeIf { !it.isNaN() } ?: 0.0) > (ourAt.takeIf { !it.isNaN() } ?: 0.0)
    }

    /** Store a peer's metadata revision beside the value it won with; a stamp-only value (or an implausible revision) drops ours. */
    fun adoptMeta(data: JSONObject, row: JSONObject, key: String, rev: Any?) {
        val adopted = (rev as? JSONObject)?.takeIf { candidate ->
            val item = JSONObject().put("rev", candidate)
            revision(item).first > 0 && !implausible(epoch(data) { metaItems(it) }, clock(data) { metaItems(it) }, item)
        }
        if (adopted != null) {
            row.put(key, adopted)
            observe(data, adopted) { metaItems(it) }
        } else row.remove(key)
    }

    fun checkedPeer(ours: JSONObject, incoming: JSONObject, notify: (String) -> Unit): JSONObject {
        val state = JSONObject(incoming.toString())
        val era = epoch(ours)
        val tick = clock(ours)
        fun accept(item: JSONObject?): Boolean {
            require(item != null && item.has("rev") && !item.isNull("rev")) { MISSING_REVISION }
            if (implausible(era, tick, item)) {
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
        val fields = JSONObject()
        for ((field, stamp) in listOf("rate" to "rateAt", "finished" to "finishedAt", "voice" to "voiceAt")) if (state.has(field)) {
            val rev = state.optJSONObject("_fieldRevs")?.opt(field)
            if (accept(JSONObject().put("rev", rev))) fields.put(field, rev) else { state.remove(field); state.remove(stamp) }
        }
        state.put("_fieldRevs", fields)
        state.remove("_clock")
        state.remove("_epoch")
        return state
    }
}
