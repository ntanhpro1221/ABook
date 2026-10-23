package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject

/** Known nested profile types. Store preserves the original bytes before publishing a repaired copy. */
internal object ListeningSchema {
    private fun number(value: Any?) = value is Number && value.toDouble().isFinite()
    private fun fields(raw: JSONObject, numbers: List<String> = emptyList(), strings: List<String> = emptyList(), booleans: List<String> = emptyList()): JSONObject {
        val result = JSONObject(raw.toString())
        numbers.filter { result.has(it) && !number(result.opt(it)) }.forEach { result.remove(it) }
        strings.filter { result.has(it) && result.opt(it) !is String }.forEach { result.remove(it) }
        booleans.filter { result.has(it) && result.opt(it) !is Boolean }.forEach { result.remove(it) }
        if (result.has("rev") && ListeningRevision.revision(result).first == 0L) result.remove("rev")
        return result
    }

    fun state(raw: JSONObject): JSONObject {
        val state = fields(raw, listOf("updatedAt", "rate", "rateAt", "finishedAt", "voiceAt", "_clock"), listOf("voice"), listOf("finished"))
        if (state.has("_clock") && !ListeningRevision.validNumber(state.opt("_clock"))) state.remove("_clock")
        if (state.has("_epoch") && !ListeningRevision.validEpoch(state.opt("_epoch"))) state.remove("_epoch")
        for (key in listOf("_fieldRevs", "_deletedRevs")) if (state.has(key)) {
            val clean = JSONObject()
            state.optJSONObject(key)?.let { rows -> for (id in rows.keys()) {
                if (ListeningRevision.revision(JSONObject().put("rev", rows.opt(id))).first > 0) clean.put(id, rows.get(id))
            } }
            state.put(key, clean)
        }
        for ((field, stamp) in listOf("rate" to "rateAt", "finished" to "finishedAt", "voice" to "voiceAt")) {
            // Value + stamp + revision are one unit (Python clean_state): a broken part drops all three and the other device resends
            // it - keeping the value and revision without the stamp broke every merge on the peer (a118 bug 3). A broken revision
            // alone is re-stamped by ListeningRevision.upgradeLocal.
            if (raw.has(field) && !state.has(field) || raw.has(stamp) && !state.has(stamp)) {
                state.remove(field)
                state.remove(stamp)
                state.optJSONObject("_fieldRevs")?.remove(field)
            }
        }
        for ((key, required) in listOf("last" to listOf("chapterId", "seconds"), "reading" to listOf("chapterId", "index"))) {
            if (!state.has(key)) continue
            val item = state.optJSONObject(key)
            if (item == null || required.any { !number(item.opt(it)) }) state.remove(key)
            else state.put(key, fields(item, required + "at"))
        }
        val chapters = JSONObject()
        state.optJSONObject("chapters")?.let { rows ->
            for (key in rows.keys()) rows.optJSONObject(key)?.let {
                chapters.put(key, fields(it, listOf("heard", "duration", "at"), booleans = listOf("done")))
            }
        }
        state.put("chapters", chapters)
        val marks = JSONArray()
        state.optJSONArray("bookmarks")?.let { rows ->
            for (i in 0 until rows.length()) rows.optJSONObject(i)?.let {
                if (it.opt("id") is String && number(it.opt("chapterId")) && number(it.opt("seconds")))
                    marks.put(fields(it, listOf("seconds", "at", "createdAt", "index"), listOf("note", "quote")))
            }
        }
        state.put("bookmarks", marks)
        for (key in listOf("chapters", "bookmarks")) if (!raw.has(key)) state.remove(key)
        if (state.has("deleted")) state.put("deleted", numericMap(state.optJSONObject("deleted")))
        if (state.has("sessions")) {
            val sessions = JSONArray()
            state.optJSONArray("sessions")?.let { rows ->
                for (i in 0 until rows.length()) rows.optJSONObject(i)?.takeIf { it.opt("id") is String }?.let {
                    sessions.put(fields(it, listOf("startedAt", "endedAt", "listened")))
                }
            }
            state.put("sessions", sessions)
        }
        if (state.has("night")) {
            val rawNight = state.optJSONObject("night")
            if (rawNight == null) state.remove("night") else {
                val night = fields(rawNight, listOf("startedAt"), listOf("id", "device", "bookTitle"), listOf("dismissed"))
                if (!night.isNull("endedAt") && !number(night.opt("endedAt"))) night.remove("endedAt")
                for (key in listOf("events", "timeline")) if (night.has(key)) {
                    val items = JSONArray()
                    night.optJSONArray(key)?.let { rows -> for (i in 0 until rows.length()) rows.optJSONObject(i)?.let(items::put) }
                    night.put(key, items)
                }
                state.put("night", night)
            }
        }
        return state
    }

    /** Broken name / move / active-choice revisions are dropped; the wall-clock stamp still merges like a peer without them. */
    private fun metaRevisions(row: JSONObject, vararg keys: String): JSONObject {
        for (key in keys) if (row.has(key) && ListeningRevision.revision(JSONObject().put("rev", row.opt(key))).first == 0L) row.remove(key)
        return row
    }

    private fun numericMap(raw: JSONObject?): JSONObject = JSONObject().also { clean ->
        raw?.let { for (key in it.keys()) if (number(it.opt(key))) clean.put(key, it.get(key)) }
    }

    fun index(raw: JSONObject): JSONObject {
        val clean = JSONObject(raw.toString())
        if (clean.has("_clock") && !ListeningRevision.validNumber(clean.opt("_clock"))) clean.remove("_clock")
        if (clean.has("_epoch") && !ListeningRevision.validEpoch(clean.opt("_epoch"))) clean.remove("_epoch")
        val records = JSONObject()
        raw.optJSONObject("records")?.let { rows -> for (key in rows.keys()) rows.optJSONObject(key)?.let {
            records.put(key, metaRevisions(fields(it, listOf("createdAt", "nameAt", "movedAt"), listOf("name")), "nameRev", "movedRev"))
        } }
        clean.put("records", records)
        val links = JSONObject()
        raw.optJSONObject("links")?.let { rows -> for (key in rows.keys()) rows.optJSONObject(key)?.let { rawLink ->
            val link = metaRevisions(fields(rawLink, listOf("activeAt")), "activeRev")
            val ids = linkedSetOf<String>()
            link.optJSONArray("records")?.let { array -> for (i in 0 until array.length()) {
                val id = array.opt(i)
                if (id is String && records.has(id)) ids.add(id)
            } }
            link.put("records", JSONArray(ids.toList()))
            if (link.opt("active") !is String || link.optString("active") !in ids) link.put("active", ids.firstOrNull().orEmpty())
            links.put(key, link)
        } }
        clean.put("links", links)
        if (clean.has("deleted")) clean.put("deleted", numericMap(clean.optJSONObject("deleted")))
        return clean
    }
}
