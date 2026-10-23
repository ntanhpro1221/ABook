package vn.abook.player

import org.json.JSONObject

/**
 * Ghi công nhạc nền trong file xuất (M4B "Kèm nhạc nền") - cùng chữ với máy tính (webui/music_export.py `credit_line` / `credit_text`): nhạc
 * CC BY đã trộn vào file thì người nhận file phải thấy tên bài, tác giả, giấy phép và lời "đã chỉnh sửa". Không bao giờ in "by" rỗng.
 */
object MusicCredits {
    /** Câu nói nhạc đã bị chỉnh (cắt vòng, trộn dưới giọng, đổi âm lượng) - CC BY đòi nói rõ; cùng câu với máy tính và giao diện. */
    const val MODIFIED_NOTE = "Nhạc đã cắt vòng, trộn nhỏ dưới giọng đọc và cân âm lượng cho sách."
    private val CC_KINDS = Regex("""^by(-(nc|nd|sa))*$""")
    private val CC_URL = Regex("""creativecommons\.org/(licenses|publicdomain)/([a-z-]+)/(\d+(?:\.\d+)?)""", RegexOption.IGNORE_CASE)

    private fun text(info: JSONObject, key: String): String = if (info.isNull(key)) "" else BookEdits.pyStrip(info.optString(key))

    /** Tên giấy phép như người đọc quen ("CC BY 4.0", "CC0"): từ đường dẫn creativecommons nếu có, không thì từ mã. */
    fun licenseLabel(code: String, url: String): String {
        CC_URL.find(url)?.let { match ->
            val (kind, slug, version) = match.destructured
            if (kind.lowercase() == "licenses") return "CC ${slug.uppercase()} $version"
            if (slug.lowercase() == "zero") return "CC0 $version"
        }
        val raw = BookEdits.pyStrip(code)
        val lower = raw.lowercase()
        if (lower == "cc0") return "CC0"
        return if (CC_KINDS.matches(lower)) "CC ${lower.uppercase()}" else raw
    }

    /** Bài có giấy phép đòi ghi công (khác cc0) và không phải nhạc người dùng nhập. */
    fun needsCredit(info: JSONObject): Boolean {
        val licence = text(info, "license").lowercase()
        return licence.isNotEmpty() && licence != "cc0" && info.optString("source") != "local"
    }

    /** Một dòng ghi công của bài; không có gì để nêu thì rỗng. */
    fun line(info: JSONObject): String {
        val title = text(info, "title")
        val creator = text(info, "creator")
        val attribution = text(info, "attribution")
        if (attribution.isNotEmpty() && creator.isNotEmpty()) return attribution
        val name = if (title.isNotEmpty()) "“$title”" else ""
        val parts = ArrayList<String>()
        if (name.isNotEmpty() || creator.isNotEmpty()) parts += name + if (creator.isNotEmpty()) " - $creator" else ""
        val foreign = info.optString("source") != "local"
        val licence = licenseLabel(text(info, "license"), text(info, "licenseUrl"))
        if (parts.isNotEmpty() && licence.isNotEmpty() && foreign) parts += "giấy phép $licence"
        val link = text(info, "licenseUrl").ifEmpty { text(info, "landing") }
        if (parts.isNotEmpty() && link.isNotEmpty() && foreign) parts += link
        return parts.joinToString(", ")
    }

    /** Ghi công của các bài (mỗi bài một dòng, bỏ trùng, theo thứ tự gặp) + lời "đã chỉnh sửa" nếu có bài đòi ghi công; không có dòng nào thì rỗng. */
    fun text(infos: Iterable<JSONObject>): String {
        val lines = ArrayList<String>()
        var credited = false
        for (info in infos) {
            val line = line(info)
            if (line.isNotEmpty() && line !in lines) {
                lines += line
                credited = credited || needsCredit(info)
            }
        }
        if (lines.isEmpty()) return ""
        return (listOf("Nhạc nền:") + lines + if (credited) listOf(MODIFIED_NOTE) else emptyList()).joinToString("\n") + "\n"
    }
}
