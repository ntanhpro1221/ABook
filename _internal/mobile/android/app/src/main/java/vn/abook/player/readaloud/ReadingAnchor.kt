package vn.abook.player.readaloud

import org.json.JSONObject

/**
 * Chỗ trong chữ, độc lập với độ dài audio/cache. Offset đếm code point, giống JavaScript và Python. `textHash` băm cả chương; `paragraphHash` (không bắt buộc) băm riêng đoạn đang
 * nghe - sửa chữ ở đoạn khác thì băm chương lệch nhưng chỗ nghe vẫn tìm lại được (soát a79 lỗi 5). Cùng hợp đồng với listen/readingAnchor.ts và webui/reading_anchor.py.
 */
object ReadingAnchor {
    fun fingerprint(paragraphs: List<String>): String {
        var hash = 0xcbf29ce484222325UL.toLong()
        for (byte in paragraphs.joinToString("\n").toByteArray(Charsets.UTF_8)) {
            hash = (hash xor (byte.toLong() and 255)) * 0x100000001b3L
        }
        return "fnv1a64:" + java.lang.Long.toUnsignedString(hash, 16).padStart(16, '0')
    }

    private val HASH = Regex("fnv1a64:[0-9a-f]{16}")

    fun validated(anchor: JSONObject?): JSONObject? {
        if (anchor == null || !HASH.matches(anchor.optString("textHash"))) return null
        for (key in listOf("segment", "charOffset")) {
            val value = anchor.opt(key) as? Number ?: return null
            if (value.toDouble() != value.toInt().toDouble() || value.toInt() < 0) return null
        }
        val saved = JSONObject().put("segment", anchor.getInt("segment")).put("charOffset", anchor.getInt("charOffset")).put("textHash", anchor.getString("textHash"))
        if (anchor.has("paragraphHash")) {
            if (!HASH.matches(anchor.optString("paragraphHash"))) return null
            saved.put("paragraphHash", anchor.getString("paragraphHash"))
        }
        return saved
    }

    fun make(paragraphs: List<String>, segment: Int, word: Int): JSONObject? {
        val text = paragraphs.getOrNull(segment) ?: return null
        val tokens = WordTokens.tokens(text)
        val start = tokens.getOrNull(word.coerceIn(0, (tokens.size - 1).coerceAtLeast(0)))?.first ?: 0
        return JSONObject().put("segment", segment).put("charOffset", text.codePointCount(0, start)).put("textHash", fingerprint(paragraphs))
            .put("paragraphHash", fingerprint(listOf(text)))
    }

    /** Đoạn của chương hiện tại mà anchor trỏ tới khi băm chương đã lệch: đoạn cũ nếu còn nguyên, không thì đoạn gần nó nhất có đúng băm đoạn. */
    private fun movedSegment(paragraphs: List<String>, saved: JSONObject): Int? {
        val wanted = saved.optString("paragraphHash").takeIf { it.isNotEmpty() } ?: return null
        val segment = saved.getInt("segment")
        fun same(index: Int) = paragraphs.getOrNull(index)?.let { fingerprint(listOf(it)) == wanted } == true
        if (same(segment)) return segment
        var best: Int? = null
        for (index in paragraphs.indices) {
            val nearest = best
            if (nearest != null && Math.abs(index - segment) >= Math.abs(nearest - segment)) continue
            if (same(index)) best = index
        }
        return best
    }

    fun restore(paragraphs: List<String>, anchor: JSONObject?): Pair<Int, Int>? {
        val saved = validated(anchor) ?: return null
        val segment = if (saved.getString("textHash") == fingerprint(paragraphs)) saved.getInt("segment") else movedSegment(paragraphs, saved) ?: return null
        val text = paragraphs.getOrNull(segment) ?: return null
        val offset = saved.getInt("charOffset")
        if (offset > text.codePointCount(0, text.length)) return null
        val tokens = WordTokens.tokens(text)
        val word = tokens.indexOfFirst { text.codePointCount(0, it.last + 1) > offset }
        return segment to if (word >= 0) word else (tokens.size - 1).coerceAtLeast(0)
    }
}
