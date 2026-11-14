package vn.abook.player.ui.studio

import kotlin.math.abs
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.NameRules
import vn.abook.player.S

/** Cast actions use exactly the existing web requests, including pending-only merge withdrawal. */
object StudioPeopleEdits {
    fun rename(person: CastMember, raw: String, others: List<CastMember>): WorkDecision {
        val name = NameRules.person(raw, others.filter { it.name != person.name }.flatMap { listOf(it.name, it.displayName) }, allowEmpty = true)
        return WorkDecision("rename:${person.name}", S.s_doi_ten_a2a0dc70,
            listOf(WorkStep("characters/rename", JSONObject().put("character", person.name).put("name", name))), hold = false)
    }

    fun gender(person: CastMember, gender: String): WorkDecision {
        require(gender == "male" || gender == "female")
        return WorkDecision("gender:${person.name}", S.s_cho_ap_dung_d6fb25f0,
            listOf(WorkStep("voice", JSONObject().put("character", person.name).put("gender", gender))))
    }

    fun merge(person: CastMember, into: CastMember): WorkDecision {
        require(person.name != into.name && person.lines > 0 && into.voice != null)
        return WorkDecision("merge:${person.name}", S.s_cho_ap_dung_d6fb25f0,
            listOf(WorkStep("characters/merge", JSONObject().put("from", person.name).put("into", into.name))))
    }

    fun unmerge(person: CastMember, details: JSONObject): WorkDecision? {
        val stamp = person.mergedAt ?: return null
        val item = details.optJSONArray("items").objects().firstOrNull {
            it.optString("section") == "speakers" && abs(it.optDouble("requestedAt", -1.0) - stamp) < 1e-6
        } ?: return null
        val keys = item.optJSONArray("keys") ?: JSONArray().put(item.optString("key"))
        val lines = JSONArray()
        for (i in 0 until keys.length()) {
            val id = keys.optString(i)
            if (id.isBlank()) return null
            lines.put(JSONObject().put("stableId", id))
        }
        if (lines.length() == 0) return null
        return WorkDecision("unmerge:${person.name}", S.s_da_bo_gop_0_4a404f0a(person.displayName),
            listOf(WorkStep("speaker", JSONObject().put("lines", lines).put("withdraw", true).put("requestedAt", item.getDouble("requestedAt")))), hold = false)
    }
}
