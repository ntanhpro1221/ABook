package vn.abook.player.readaloud

import vn.abook.player.vieneu.VieneuUnits

/**
 * Chữ đem đọc cho giọng nhận chữ thô nhưng đọc hay hơn khi được chuẩn hoá như giọng trên máy (Edge): bản Kotlin của `abook/readaloud/spoken.py`, cùng bộ ví dụ
 * tests/fixtures/readaloud/spoken/ (SpokenTextTest) nên điện thoại và máy tính gửi Edge CÙNG một chuỗi. Đo a39 (Whisper, 74 câu bịa x 2 giọng Edge): âm tiết sai 29% với chữ
 * thô, 12% với chữ của `VieneuUnits.spokenTokens` - tên Nhật + kính ngữ, tiếng kêu, "1,500", "+50" "x2" "3-5" "100/250", viết tắt. Giọng dùng khoá (Azure, Google, FPT, Viettel)
 * chưa đo nên vẫn nhận chữ thô (+ cách đọc riêng: [Readings.spokenLayout]). Edge nói được tiếng Anh nên chữ Anh để nguyên (`spokenTokens` trên điện thoại luôn thế).
 *
 * Một chữ hiện có thể thành nhiều chữ đọc ("Aaaa" -> "a… a") hay không còn chữ nào (cụm đọc ngắn hơn, [Readings]): [layout] trả chuỗi đem đọc + khoảng chữ đọc của từng chữ hiện,
 * [expandWords] trả mốc về đủ chữ hiện.
 */
object SpokenText {
    /** Nhà cung cấp nhận chữ đã chuẩn hoá (`EdgeProvider.normalises_text`). */
    private val PROVIDERS = setOf("edge")

    /** Dấu trong khoá bộ đệm (`spoken.TAG`): clip Edge làm từ chữ thô không bao giờ trúng đệm của chữ đã chuẩn hoá. */
    const val TAG = "tn"

    fun normalises(voiceId: String): Boolean = voiceId.substringBefore(':') in PROVIDERS

    /** `spoken.tag`: gốc của cuốn khi nó làm tên đọc khác ([VieneuUnits.readingTag]) rồi [TAG], nối bằng "+". */
    fun tag(text: String, origin: String?): String = listOf(VieneuUnits.readingTag(text, origin), TAG).filter { it.isNotEmpty() }.joinToString("+")

    /** Chữ đọc đầu và cuối (số thứ tự trong chuỗi đem đọc) của một chữ hiện. */
    data class Range(val first: Int, val last: Int)

    /** (chuỗi đem đọc, khoảng của từng chữ hiện - null khi chữ ấy không còn chữ đọc nào); `spoken.layout`. */
    fun layout(text: String, origin: String?, readings: Map<String, String>? = null): Pair<String, List<Range?>> {
        val shown = VieneuUnits.tokens(text)
        val said = VieneuUnits.spokenTokens(shown, origin, readings).mapIndexed { i, word -> if (word == shown[i]) word else word.replace("_", "") }
        val flat = ArrayList<String>()
        val spans = ArrayList<Range?>()
        for (word in said) {
            val parts = VieneuUnits.tokens(word)
            spans.add(if (parts.isEmpty()) null else Range(flat.size, flat.size + parts.size - 1))
            flat.addAll(parts)
        }
        val joined = flat.joinToString(" ")
        if (WordTokens.fold(joined).isEmpty()) return text to shown.indices.map { Range(it, it) } // hết sạch chữ: đọc nguyên chữ thô
        return joined to spans
    }

    /** Mốc từng chữ ĐỌC -> mốc từng chữ HIỆN (`spoken.expand_words`): trải từ đầu chữ đọc đầu tới cuối chữ đọc cuối; chữ không còn chữ đọc nào mốc rỗng ([Readings.expandWords]). */
    fun expandWords(words: List<Span>, spans: List<Range?>): List<Span> {
        val merged = ArrayList<Span>()
        val slots = spans.map { span ->
            if (span == null || span.last >= words.size) null
            else {
                merged.add(Span(words[span.first].start, words[span.last].end))
                merged.size - 1
            }
        }
        return Readings.expandWords(merged, slots)
    }
}
