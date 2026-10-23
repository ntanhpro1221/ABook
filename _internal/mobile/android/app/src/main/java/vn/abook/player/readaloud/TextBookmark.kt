package vn.abook.player.readaloud

import org.json.JSONObject

/** Chốt câu và chữ từ vị trí đang đọc; không suy ngược từ đồng hồ ảo. */
object TextBookmark {
    fun from(paragraphs: List<String>, anchor: JSONObject?): JSONObject? {
        val saved = ReadingAnchor.validated(anchor) ?: return null
        val (segment, _) = ReadingAnchor.restore(paragraphs, saved) ?: return null
        return JSONObject().put("index", segment).put("quote", paragraphs[segment]).put("anchor", saved)
    }
}
