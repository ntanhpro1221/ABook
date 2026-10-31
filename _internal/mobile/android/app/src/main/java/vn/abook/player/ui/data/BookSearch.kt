package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap

/** Một đoạn chữ của chương: câu của kịch bản sách nói (kèm giây bắt đầu), hay câu của chương chỉ có chữ (không có mốc). */
@Immutable
class Passage(val text: String, val start: Double? = null)

/** Chữ một chương đã chuẩn hoá để so khớp (giữ trong lúc bảng tìm mở, gõ thêm chữ không phải đọc lại đĩa). `failed`: chương không đọc được. */
class FoldedChapter(val passages: List<Passage>, val folded: List<String>, val failed: Boolean = false)

/** Một chỗ khớp: chương, thứ tự đoạn, cả đoạn (không cắt) và khoảng [matchStart, matchEnd) để tô; `start` = giây của câu nếu có mốc. */
@Immutable
data class FindHit(val chapterId: Int, val index: Int, val text: String, val matchStart: Int, val matchEnd: Int, val start: Double?)

/** Tình hình một lần tìm: kết quả đầu (tối đa [BookSearch.RESULT_LIMIT]), tổng số chỗ khớp, đã xem bao nhiêu chương. */
@Immutable
class FindProgress(val hits: List<FindHit>, val total: Int, val scanned: Int, val chapters: Int, val failed: Int, val done: Boolean)

/**
 * "Tìm trong sách" (viết lại từ listen/findText.ts + bookSearch.ts, cùng quy tắc): khớp không phân biệt hoa thường và dấu trên CHỮ GỐC của sách,
 * mỗi đoạn tính một lần. Hàm thuần trừ [run] (chạy lần lượt các chương, nạp qua `load`) - thử trên JVM (BookSearchTest).
 */
object BookSearch {
    /** Ít nhất chừng này ký tự mới tìm: một ký tự khớp gần như mọi câu. */
    const val MIN_QUERY = 2
    const val RESULT_LIMIT = 200

    /** Số chương đọc trong một lượt nền trước khi báo kết quả. */
    private const val LOT = 16

    private val folds = ConcurrentHashMap<Char, String>()

    /** Một ký tự đã chuẩn hoá (có thể rỗng - dấu rời - hay vài ký tự). ASCII đi đường tắt, ký tự khác nhớ lại sau lần đầu. */
    private fun foldOther(c: Char): String = folds.getOrPut(c) { if (c.isWhitespace()) " " else ListenLogic.fold(c.toString()) }

    /** Chữ đã chuẩn hoá để so khớp: bỏ dấu, chữ thường, mọi kiểu khoảng trắng thành dấu cách. */
    fun fold(text: String): String {
        val out = StringBuilder(text.length)
        for (c in text) {
            if (c < '\u0080') out.append(if (c.isWhitespace()) ' ' else c.lowercaseChar()) else out.append(foldOther(c))
        }
        return out.toString()
    }

    /** Từ khoá đã chuẩn hoá ("  Nguyễn   An " -> "nguyen an"); rỗng khi chưa đủ dài. */
    fun foldedQuery(query: String): String {
        val folded = fold(query).trim().replace(Regex(" +"), " ")
        return if (folded.length >= MIN_QUERY) folded else ""
    }

    /** Khoảng của chữ gốc ứng với chỗ khớp ở `at` dài `length` của `fold(text)`; dấu rời ngay sau chữ cuối vẫn thuộc chữ ấy. null khi lệch. */
    fun span(text: String, at: Int, length: Int): IntArray? {
        if (at < 0 || length <= 0) return null
        var position = 0
        var start = -1
        for (i in text.indices) {
            val c = text[i]
            val width = if (c < '\u0080') 1 else foldOther(c).length
            if (width == 0) continue
            if (start < 0 && position + width > at) start = i
            position += width
            if (start >= 0 && position >= at + length) {
                // Dấu rời ngay sau chữ cuối.
                var stop = i + 1
                while (stop < text.length && text[stop] >= '\u0080' && foldOther(text[stop]).isEmpty()) stop++
                return intArrayOf(start, stop)
            }
        }
        return null
    }

    // ---- chữ của chương -----------------------------------------------------------------------------------

    private val sentenceEnd = Regex("""(?<=[.!?\u2026])\s+""")

    /** Kịch bản sách nói (`scripts/<mã>.json`): các câu theo thứ tự, bỏ dòng ngăn cảnh. null khi hỏng. */
    fun scriptPassages(raw: String): List<Passage>? = try {
        val segments = JSONObject(raw).optJSONArray("segments")
        if (segments == null) null else (0 until segments.length()).mapNotNull { index ->
            val segment = segments.optJSONObject(index) ?: return@mapNotNull null
            if (segment.optBoolean("sceneBreak")) return@mapNotNull null
            val start = if (segment.has("start") && !segment.isNull("start")) segment.optDouble("start").takeIf { it.isFinite() } else null
            Passage(segment.optString("text"), start)
        }
    } catch (_: org.json.JSONException) {
        null
    }

    /** Chương chỉ có chữ (`texts/<mã>.txt`): mỗi đoạn văn tách thành câu - kết quả hiện cả câu, không phải cả đoạn dài. */
    fun textPassages(raw: String): List<Passage> =
        raw.split('\n').asSequence().map { it.trim() }.filter { it.isNotEmpty() }
            .flatMap { paragraph -> paragraph.split(sentenceEnd).asSequence() }
            .filter { it.isNotBlank() }.map { Passage(it) }.toList()

    fun folded(passages: List<Passage>): FoldedChapter = FoldedChapter(passages, passages.map { fold(it.text) })

    /** Chỗ khớp ĐẦU của từ khoá trong từng đoạn (một đoạn một kết quả, như bản React). */
    fun find(chapterId: Int, chapter: FoldedChapter, needle: String): List<FindHit> {
        if (chapter.failed || needle.isEmpty()) return emptyList()
        val hits = ArrayList<FindHit>()
        for (index in chapter.folded.indices) {
            val at = chapter.folded[index].indexOf(needle)
            if (at < 0) continue
            val passage = chapter.passages[index]
            val range = span(passage.text, at, needle.length)
            // Cả đoạn, một dòng chữ liền (xuống dòng thành dấu cách - giữ nguyên chỉ số ký tự để tô đúng chỗ).
            val flat = passage.text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            hits += FindHit(chapterId, index, flat, range?.get(0) ?: 0, range?.get(1) ?: 0, passage.start)
        }
        return hits
    }

    /**
     * Tìm trong CẢ cuốn, theo thứ tự chương: nạp chữ từng lô (`load`, gọi ở luồng nền của nơi gọi), báo tiến độ sau mỗi lô qua `onUpdate`.
     * `cache` giữ chương đã chuẩn hoá giữa các lần gõ. Huỷ coroutine là dừng.
     */
    suspend fun run(
        chapters: List<ChapterLine>,
        query: String,
        cache: MutableMap<Int, FoldedChapter>,
        load: suspend (List<ChapterLine>) -> Unit,
        onUpdate: (FindProgress) -> Unit,
    ) {
        val needle = foldedQuery(query)
        if (needle.isEmpty()) return
        val hits = ArrayList<FindHit>()
        var total = 0
        var failed = 0
        var scanned = 0
        var from = 0
        while (from < chapters.size) {
            val lot = chapters.subList(from, minOf(chapters.size, from + LOT))
            val missing = lot.filter { it.id !in cache }
            if (missing.isNotEmpty()) load(missing)
            for (chapter in lot) {
                val text = cache[chapter.id]
                if (text == null || text.failed) {
                    failed++
                } else {
                    val found = find(chapter.id, text, needle)
                    total += found.size
                    for (hit in found) if (hits.size < RESULT_LIMIT) hits += hit
                }
                scanned++
            }
            from += lot.size
            onUpdate(FindProgress(hits.toList(), total, scanned, chapters.size, failed, done = from >= chapters.size))
        }
    }

    /** Câu nói tình hình tìm cho người nghe (FindInBook.tsx `findStatus`). */
    fun status(query: String, progress: FindProgress?): String {
        if (query.isBlank()) return "Gõ chữ hay câu cần tìm - không cần gõ dấu, hoa hay thường đều được."
        if (foldedQuery(query).isEmpty()) return "Gõ ít nhất $MIN_QUERY ký tự."
        if (progress == null) return "Đang tìm"
        val failed = if (progress.failed > 0) " ${progress.failed} chương chưa đọc được nên chưa tìm trong đó." else ""
        if (!progress.done) return "Đang tìm - đã xem ${progress.scanned}/${progress.chapters} chương, thấy ${progress.total} chỗ."
        if (progress.total == 0) return "Không thấy “${query.trim()}” trong sách.$failed"
        val more = if (progress.total > progress.hits.size) {
            " Đang hiện ${progress.hits.size} kết quả đầu, còn ${progress.total - progress.hits.size} kết quả - gõ thêm chữ để thu hẹp."
        } else {
            ""
        }
        return "${progress.total} kết quả.$more$failed"
    }
}
