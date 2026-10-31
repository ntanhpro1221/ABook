package vn.abook.player.ui.editbook

import org.json.JSONObject
import vn.abook.player.ui.data.Fmt

object SyncText {
    fun note(sync: JSONObject, where: String): String {
        val pending = sync.optInt("pending")
        val last = sync.optJSONObject("last")
        if (pending > 0 && last?.optString("state") == "error")
            return listOf(last.optString("error").ifBlank { "Chưa gửi được - sẽ thử lại." }, "Tự gửi khi $where trả lời lại; bấm “Gửi về $where” để gửi ngay.").joinToString(" ")
        if (pending > 0) return "Tự gửi khi tới được $where; bấm “Gửi về $where” để gửi ngay."
        if (last?.optString("state") != "sent") return ""
        val lines = mutableListOf("Đã gửi về $where ${Fmt.whenText(last.optDouble("at"))}".trim())
        fun count(key: String, say: (Int) -> String) { last.optInt(key).takeIf { it > 0 }?.let { lines += say(it) } }
        count("applied") { "$it thay đổi đã áp ngay trên $where" }
        count("studio") { "$it việc cần thu lại giọng đã ghi trên $where - Studio sẽ thu lại khi bạn mở dự án trên $where" }
        count("requests") { "$it việc đã thành yêu cầu trên $where, chờ áp dụng ở Studio" }
        count("waiting") { "$it việc đang chờ duyệt trên $where - chưa làm gì cho tới khi bạn đồng ý trên $where" }
        val skipped = last.optInt("skipped") + last.optInt("skippedWishes")
        if (skipped > 0) lines += "$skipped thay đổi không còn chỗ trong sách trên $where nên bị bỏ qua"
        val conflicts = last.optJSONArray("conflicts")
        for (i in 0 until (conflicts?.length() ?: 0)) lines += conflicts!!.optString(i)
        return lines.joinToString("\n")
    }
    fun sent(pending: Int, where: String): String = listOfNotNull("Đã gửi về $where",
        if (pending > 0) "Còn $pending thay đổi chưa gửi được - sẽ thử lại khi tới được $where." else null).joinToString(". ")
}
