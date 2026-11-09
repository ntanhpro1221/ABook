package vn.abook.player.ui.nowplaying

import androidx.compose.runtime.Immutable
import org.json.JSONArray
import org.json.JSONObject

@Immutable
data class WordTiming(val startMs: Long, val endMs: Long, val from: Int, val until: Int)

@Immutable
data class ReadParagraph(
    val id: Int, val text: String, val startMs: Long, val endMs: Long,
    val timed: Boolean, val words: List<WordTiming> = emptyList(),
)

@Immutable
data class ReadAlongState(
    val bookId: String = "", val chapterId: Int? = null,
    val paragraphs: List<ReadParagraph> = emptyList(), val loading: Boolean = false, val error: String = "",
)

/**
 * Luật đi theo giọng (cùng ý với ui/src/listen/follow.ts và ReadAlongView.qml): dòng chứa từ đang đọc đứng ở [PLACE_AT] từ trên khung, từ xuống dòng mới thì cuộn
 * mượt một dòng. Người tự cuộn là thôi theo; thôi cuộn [SETTLE_MS] mà câu đang đọc còn trong khung thì theo lại.
 */
object ReadFollow {
    const val PLACE_AT = 0.3f
    const val SETTLE_MS = 1500L

    /** Chỗ cần đứng đúng: đổi giá trị này mới là lý do để cuộn. */
    data class Target(val sentence: Int, val line: Int)

    /**
     * Dòng chứa từ đang đọc ở [ms]; câu chưa có mốc từ hay chưa tới từ đầu: dòng đầu của câu. Từ cuối đã tắt ([ReadAlongLookup.word] -1 khi quãng nghỉ dài) vẫn tính
     * dòng của nó: danh sách đứng yên chờ câu sau, không lùi về đầu câu.
     */
    fun lineAt(words: List<WordTiming>, ms: Long, lineForOffset: (Int) -> Int): Int {
        val word = ReadAlongLookup.word(words, ms)
        val at = if (word < 0 && words.isNotEmpty() && ms > words.last().endMs) words.last() else words.getOrNull(word)
        return at?.let { lineForOffset(it.from) } ?: 0
    }
}

/** Binary searches match listen/words.ts: sentence lead 50 ms, word lead 40 ms, last word hold 400 ms. */
object ReadAlongLookup {
    // JS's \S+ (words.ts), spelled out: Java's default \s omits NBSP, and (?U) / UNICODE_CHARACTER_CLASS crashes Android's ICU regex.
    private val token = Regex("[^\\t\\n\\u000B\\f\\r \\u00A0\\u1680\\u2000-\\u200A\\u2028\\u2029\\u202F\\u205F\\u3000\\uFEFF]+")

    fun sentence(paragraphs: List<ReadParagraph>, ms: Long): Int {
        var low = 0
        var high = paragraphs.lastIndex
        var found = -1
        while (low <= high) {
            val middle = (low + high) ushr 1
            if (paragraphs[middle].startMs <= ms + 50) { found = middle; low = middle + 1 } else high = middle - 1
        }
        return if (found >= 0 && paragraphs[found].timed) found else -1
    }

    fun word(words: List<WordTiming>, ms: Long): Int {
        var low = 0
        var high = words.lastIndex
        var found = -1
        while (low <= high) {
            val middle = (low + high) ushr 1
            if (words[middle].startMs <= ms + 40) { found = middle; low = middle + 1 } else high = middle - 1
        }
        return if (found == words.lastIndex && found >= 0 && ms > words[found].endMs + 400) -1 else found
    }

    fun words(text: String, raw: JSONArray?): List<WordTiming> {
        val matches = token.findAll(text).toList()
        if (raw == null || raw.length() == 0 || raw.length() != matches.size) return emptyList()
        val out = ArrayList<WordTiming>(matches.size)
        var last = 0.0
        for (i in matches.indices) {
            val pair = raw.optJSONArray(i) ?: return emptyList()
            if (pair.length() != 2 || pair.opt(0) !is Number || pair.opt(1) !is Number) return emptyList()
            val start = pair.optDouble(0)
            val end = pair.optDouble(1)
            if (!start.isFinite() || !end.isFinite() || start < last || end < start) return emptyList()
            last = start
            val range = matches[i].range
            out += WordTiming(start.toLong(), end.toLong(), range.first, range.last + 1)
        }
        return out.toList()
    }

    /** Audio script carries text itself; ReadAloud.script carries the currently loaded paragraph snapshot separately. */
    fun parse(json: JSONObject, textParagraphs: List<String> = emptyList()): List<ReadParagraph> {
        val segments = json.optJSONArray("segments") ?: JSONArray()
        val texts = json.optJSONArray("paragraphs")
        val count = maxOf(segments.length(), texts?.length() ?: textParagraphs.size)
        return List(count) { i ->
            val segment = segments.optJSONObject(i) ?: JSONObject()
            val text = texts?.optString(i) ?: textParagraphs.getOrNull(i) ?: segment.optString("text")
            // An active virtual timeline deliberately has estimates for unfinished clips, as the web reader does.
            val timed = (json.optBoolean("active") || segment.optBoolean("timed", json.optBoolean("timed"))) && !segment.isNull("start")
            ReadParagraph(i, text, (segment.optDouble("start", 0.0) * 1000).toLong(),
                (segment.optDouble("end", 0.0) * 1000).toLong(), timed, words(text, segment.optJSONArray("words")))
        }
    }
}
