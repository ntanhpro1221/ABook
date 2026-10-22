package vn.abook.player.readaloud

import org.json.JSONObject

/** Chỗ trong chữ, độc lập với độ dài audio/cache. Offset đếm code point, giống JavaScript và Python. */
object ReadingAnchor {
    fun fingerprint(paragraphs: List<String>): String {
        var hash = 0xcbf29ce484222325UL.toLong()
        for (byte in paragraphs.joinToString("\n").toByteArray(Charsets.UTF_8)) {
            hash = (hash xor (byte.toLong() and 255)) * 0x100000001b3L
        }
        return "fnv1a64:" + java.lang.Long.toUnsignedString(hash, 16).padStart(16, '0')
    }

    fun validated(anchor: JSONObject?): JSONObject? {
        if (anchor == null || !Regex("fnv1a64:[0-9a-f]{16}").matches(anchor.optString("textHash"))) return null
        for (key in listOf("segment", "charOffset")) {
            val value = anchor.opt(key) as? Number ?: return null
            if (value.toDouble() != value.toInt().toDouble() || value.toInt() < 0) return null
        }
        return JSONObject().put("segment", anchor.getInt("segment")).put("charOffset", anchor.getInt("charOffset"))
            .put("textHash", anchor.getString("textHash"))
    }

    fun make(paragraphs: List<String>, segment: Int, word: Int): JSONObject? {
        val text = paragraphs.getOrNull(segment) ?: return null
        val tokens = WordTokens.tokens(text)
        val start = tokens.getOrNull(word.coerceIn(0, (tokens.size - 1).coerceAtLeast(0)))?.first ?: 0
        return JSONObject().put("segment", segment).put("charOffset", text.codePointCount(0, start)).put("textHash", fingerprint(paragraphs))
    }

    fun restore(paragraphs: List<String>, anchor: JSONObject?): Pair<Int, Int>? {
        val saved = validated(anchor) ?: return null
        if (saved.getString("textHash") != fingerprint(paragraphs)) return null
        val segment = saved.getInt("segment")
        val text = paragraphs.getOrNull(segment) ?: return null
        val offset = saved.getInt("charOffset")
        if (offset > text.codePointCount(0, text.length)) return null
        val tokens = WordTokens.tokens(text)
        val word = tokens.indexOfFirst { text.codePointCount(0, it.last + 1) > offset }
        return segment to if (word >= 0) word else (tokens.size - 1).coerceAtLeast(0)
    }
}
