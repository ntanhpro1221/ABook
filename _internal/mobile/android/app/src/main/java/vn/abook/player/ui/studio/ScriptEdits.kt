package vn.abook.player.ui.studio

import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale
import vn.abook.player.S
import vn.abook.player.ui.data.ListenLogic

/** Request construction shared by single-line and touch batch controls. Source text is never a request field. */
object ScriptEdits {
    fun matches(text: String, query: String): Boolean = ListenLogic.fold(text).contains(ListenLogic.fold(query.trim()))
    val kinds = listOf("narration" to S.s_loi_ke_eba0761e, "dialogue" to S.s_loi_thoai_4ed83728, "thought" to S.s_noi_tam_885fce10)
    val levels = listOf(S.s_nhe_52e76ce9, S.s_vua_8af1c03b, S.s_manh_52416a97, S.s_rat_manh_bef32ca9)
    val emotions = listOf(
        "neutral" to S.s_binh_thuong_23c1bd43, "happy" to S.s_vui_2e2beffc, "sad" to S.s_buon_a1dc5853,
        "angry" to S.s_gian_19da03ba, "afraid" to S.s_so_485ed077, "surprised" to S.s_ngac_nhien_8b160295,
        "tender" to S.s_diu_dang_0d05b980, "sarcastic" to S.s_mia_mai_729f7055, "excited" to S.s_hao_hung_b8003bdb,
        "tired" to S.s_met_moi_304a36cf, "whispering" to S.s_thi_tham_ed2d29dd,
    )

    fun deliveryText(emotion: String, intensity: Int): String {
        val label = emotions.firstOrNull { it.first == emotion }?.second ?: emotion
        return if (intensity == 0) label else "$label · ${levels.getOrNull(intensity)?.lowercase(Locale.ROOT) ?: intensity}"
    }

    fun assign(lines: List<ScriptLine>, person: ScriptPerson): WorkDecision {
        require(lines.isNotEmpty() && lines.all { it.editable && it.stableId.isNotBlank() && it.textSha256.isNotBlank() })
        val unique = lines.distinctBy { it.stableId }
        val refs = JSONArray()
        val seen = JSONObject()
        unique.forEach {
            refs.put(JSONObject().put("stableId", it.stableId).put("textSha256", it.textSha256))
            seen.put(it.stableId, it.wish?.value.orEmpty())
        }
        val body = JSONObject().put("lines", refs).put("speaker", person.value).put("newGender", person.newGender).put("seen", seen)
        val summary = if (unique.size > 1) S.s_da_ghi_0_cau_cua_1_c1ccd6a7(unique.size, person.label) else S.s_da_ghi_cau_nay_cua_0_8b08302d(person.label)
        return WorkDecision("line:${unique.joinToString(",") { it.stableId }}", summary, listOf(WorkStep("speaker", body)), names = mapOf(person.value to person.label))
    }

    /** A new person requires /line before /speaker, with a receipt-bound withdrawal if the second request fails. */
    fun delivery(line: ScriptLine, kind: String, emotion: String, intensity: Int, person: ScriptPerson?): WorkDecision? {
        if (line.stableId.isBlank() || line.textSha256.isBlank()) return null
        if (kinds.none { it.first == kind } || emotions.none { it.first == emotion } || intensity !in 0..3) return null
        val needsPerson = line.kind == "narration" && kind != "narration"
        if (needsPerson && (person == null || person.value.isBlank() || person.value == ScriptLogic.NARRATOR)) return null
        val body = JSONObject().put("stableId", line.stableId).put("textSha256", line.textSha256).put("seen", ScriptLogic.seenDelivery(line.lineWish))
        if (kind != line.kind) body.put("kind", kind)
        if (line.emotion != null && emotion != line.emotion) body.put("emotion", emotion)
        if (line.intensity != null && intensity != line.intensity) body.put("intensity", intensity)
        if (needsPerson && person!!.newGender.isEmpty()) body.put("speaker", person.value)
        if (body.length() == 3 && !needsPerson) return null
        val steps = mutableListOf(WorkStep("line", body))
        if (needsPerson && person!!.newGender.isNotEmpty()) {
            steps += WorkStep("speaker", JSONObject().put("lines", JSONArray().put(JSONObject().put("stableId", line.stableId).put("textSha256", line.textSha256)))
                .put("speaker", person.value).put("newGender", person.newGender))
        }
        return WorkDecision("delivery:${line.stableId}", S.s_cho_ap_dung_d6fb25f0, steps, rollbackLine = steps.size == 2)
    }

    fun visible(script: ChapterScript, filter: ScriptFilter, query: String, person: String): List<ShownLine> {
        val folded = ListenLogic.fold(query.trim())
        return ScriptLogic.visible(script.lines, filter).filter {
            (folded.isEmpty() || ListenLogic.fold(it.line.text).contains(folded)) &&
                (person.isEmpty() || ScriptLogic.speaker(it.line) == person)
        }
    }
}
