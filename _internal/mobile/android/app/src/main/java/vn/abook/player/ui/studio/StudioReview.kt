package vn.abook.player.ui.studio

import androidx.compose.runtime.Immutable
import org.json.JSONObject
import vn.abook.player.ClipSpec
import vn.abook.player.StudioPaths

/** Vì sao một câu cần nghe lại (webui/reviews.py): hỏng, chưa kiểm được, lệch nhiều / nhẹ về tên hay chữ. */
enum class ReviewKind(val key: String) {
    Failed("failed"), Unverified("unverified"), NameLow("name-low"), TextLow("text-low"), Name("name"), Text("text");

    companion object {
        fun of(key: String): ReviewKind = entries.firstOrNull { it.key == key } ?: Text
    }
}

/** Đoạn [start, end] giây của một câu trong file chương (khi bản thu riêng đã được dọn). */
@Immutable
data class ChapterWindow(val start: Double, val end: Double)

/** Một câu cần nghe lại (web `ReviewItem`). */
@Immutable
data class ReviewItem(
    val segmentId: Int,
    val stableId: String,
    val audioSha256: String,
    val chapterId: Int,
    val chapterTitle: String,
    val text: String,
    /** Điều máy nghe lại được ("" = đúng chữ). */
    val heard: String,
    val similarity: Double?,
    val speaker: String,
    val kind: ReviewKind,
    val reason: String,
    /** Có bản thu riêng của câu. */
    val playable: Boolean,
    val chapterClip: ChapterWindow?,
    /** "ok" | "redo" | null. */
    val verdict: String?,
    val pendingSpoken: String?,
    val spoken: String?,
)

/** Một trang `GET /api/books/<id>/review`. */
@Immutable
data class ReviewPage(
    val counts: Map<ReviewKind, Int>,
    /** Số câu chưa có cách xử lý. */
    val pending: Int,
    val redoChapters: List<Int>,
    val items: List<ReviewItem>,
    val nextCursor: String?,
    val remaining: Int,
)

internal object StudioReviewJson {
    private fun item(json: JSONObject) = ReviewItem(
        segmentId = json.optInt("segmentId"),
        stableId = json.text("stableId"),
        audioSha256 = json.text("audioSha256"),
        chapterId = json.optInt("chapterId"),
        chapterTitle = json.text("chapterTitle"),
        text = json.text("text"),
        heard = json.text("heard"),
        similarity = if (json.has("similarity") && !json.isNull("similarity")) json.optDouble("similarity").takeIf { it.isFinite() } else null,
        speaker = json.text("speaker"),
        kind = ReviewKind.of(json.text("kind")),
        reason = json.text("reason"),
        playable = json.optBoolean("playable"),
        chapterClip = json.optJSONObject("chapterClip")?.let { ChapterWindow(it.optDouble("start"), it.optDouble("end")) }?.takeIf { it.start.isFinite() && it.end.isFinite() },
        verdict = json.textOrNull("verdict")?.takeIf { it == "ok" || it == "redo" },
        pendingSpoken = json.textOrNull("pendingSpoken"),
        spoken = json.textOrNull("spoken"),
    )

    fun page(json: JSONObject): ReviewPage {
        val counts = json.optJSONObject("counts")?.let { counts -> counts.keys().asSequence().associate { ReviewKind.of(it) to counts.optInt(it) } }.orEmpty()
        return ReviewPage(
            counts = counts,
            pending = json.optInt("pending"),
            redoChapters = json.optJSONArray("redoChapters")?.let { array -> (0 until array.length()).map { array.optInt(it) } }.orEmpty(),
            items = json.optJSONArray("items").objects().map(::item),
            nextCursor = json.textOrNull("nextCursor")?.takeIf { it.isNotEmpty() },
            remaining = json.optInt("remaining"),
        )
    }
}

/** Logic thuần của tab "Cần nghe lại" - port `ReviewQueue.tsx` (`clipOf`, `handled`, `sameText`) và `reviewText.ts`. */
object ReviewLogic {
    /** Câu đã có cách xử lý: phán quyết, hay chữ đem đọc mới đang chờ áp. */
    fun handled(item: ReviewItem): Boolean = item.verdict != null || item.pendingSpoken != null

    /** Cùng chữ, bỏ qua dấu câu và hoa thường: “Tách tách tách.” và “Tách tách tách!” là một câu tượng thanh. */
    fun sameText(left: String, right: String): Boolean = letters(left) == letters(right)

    private fun letters(text: String): String {
        val out = StringBuilder()
        var gap = false
        for (c in text.lowercase()) {
            if (c.isLetterOrDigit()) {
                if (gap && out.isNotEmpty()) out.append(' ')
                gap = false
                out.append(c)
            } else {
                gap = true
            }
        }
        return out.toString()
    }

    /** Thứ để nghe một câu: bản thu riêng, hay đúng đoạn ấy trong file chương; null = chưa có gì để nghe. */
    fun clip(computer: String, bookId: String, item: ReviewItem): ClipSpec? = when {
        item.playable -> ClipSpec(computer, StudioPaths.sample(bookId, item.segmentId))
        item.chapterClip != null -> ClipSpec(computer, StudioPaths.chapterAudio(bookId, item.chapterId), (item.chapterClip.start * 1000).toInt(), (item.chapterClip.end * 1000).toInt())
        else -> null
    }

    /** Mã clip của một câu (khoá trong [vn.abook.player.ClipState]). */
    fun clipId(item: ReviewItem): String = "review-${item.segmentId}"

    /** Cuốn chưa thu câu nào: "không còn câu nào cần xem" là nói dối - phải nói là sẽ có sau khi thu âm. */
    fun notRecordedYet(book: StudioBook?): Boolean = book?.segmentsRecorded == 0

    /** Câu sau `current` (theo thứ tự danh sách) mà nghe được, hay từ đầu nếu `current` null / đã rời danh sách; null = hết. */
    fun nextPlayable(items: List<ReviewItem>, computer: String, bookId: String, after: String?): ReviewItem? {
        val start = if (after == null) 0 else items.indexOfFirst { it.stableId == after }.let { if (it < 0) 0 else it + 1 }
        return items.drop(start).firstOrNull { clip(computer, bookId, it) != null }
    }

    /** "máy nghe lại khớp 15% với chữ của câu" - bản ngắn đứng cạnh điều máy nghe được. */
    fun matchShort(percent: String): String = "khớp $percent"
}
