package vn.abook.player.ui.editbook

import vn.abook.player.S

import org.json.JSONObject
import vn.abook.player.ui.data.Fmt

object SyncText {
    fun note(sync: JSONObject, where: String): String {
        val pending = sync.optInt("pending")
        val last = sync.optJSONObject("last")
        if (pending > 0 && last?.optString("state") == "error")
            return listOf(last.optString("error").ifBlank { S.s_chua_gui_duoc_se_thu_lai_b33d9601 }, S.s_tu_gui_khi_0_tra_loi_lai_bam_gui_ve_1_de_g_47a67376(where, where)).joinToString(" ")
        if (pending > 0) return S.s_tu_gui_khi_toi_duoc_0_bam_gui_ve_1_de_gui_68533698(where, where)
        if (last?.optString("state") != "sent") return ""
        val lines = mutableListOf(S.s_da_gui_ve_0_1_f817fbb4(where, Fmt.whenText(last.optDouble("at"))).trim())
        fun count(key: String, say: (Int) -> String) { last.optInt(key).takeIf { it > 0 }?.let { lines += say(it) } }
        count("applied") { S.s_0_thay_doi_da_ap_ngay_tren_1_0baf0321(it, where) }
        count("studio") { S.s_0_viec_can_thu_lai_giong_da_ghi_tren_1_stu_3eb16c54(it, where, where) }
        count("requests") { S.s_0_viec_da_thanh_yeu_cau_tren_1_cho_ap_dung_8d86b57b(it, where) }
        count("waiting") { S.s_0_viec_dang_cho_duyet_tren_1_chua_lam_gi_c_71360040(it, where, where) }
        val skipped = last.optInt("skipped") + last.optInt("skippedWishes")
        if (skipped > 0) lines += S.s_0_thay_doi_khong_con_cho_trong_sach_tren_1_88b8a366(skipped, where)
        val conflicts = last.optJSONArray("conflicts")
        for (i in 0 until (conflicts?.length() ?: 0)) lines += conflicts!!.optString(i)
        return lines.joinToString("\n")
    }
    fun sent(pending: Int, where: String): String = listOfNotNull(S.s_da_gui_ve_0_c5d9f5e1(where),
        if (pending > 0) S.s_con_0_thay_doi_chua_gui_duoc_se_thu_lai_kh_a2ab7e32(pending, where) else null).joinToString(". ")
}
