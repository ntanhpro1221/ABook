package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.LibraryTree

/**
 * Một hàng của danh sách chương ở trang sách - tính sẵn lúc đọc (luồng nền), cuộn danh sách không tính gì.
 * `heard`: phần đã nghe 0..1 (model.ts `chapterHeard`); `playable`: có audio, hay chỉ có chữ (lõi native luôn đọc to được).
 */
@Immutable
data class ChapterLine(
    val id: Int,
    val title: String,
    val duration: Double,
    val available: Boolean,
    val textOnly: Boolean,
    val heard: Float,
    val done: Boolean,
    /** Chương chỉ có chữ: tên mục chữ trong gói (`texts/<mã>.txt`) - "Tìm trong sách" đọc nó. */
    val textPath: String = "",
    /** Giây bắt đầu khi chạm chương: chỗ đã nghe tới nếu chương đang nghe dở, không thì đầu chương (BookScreen.tsx ChapterRow). */
    val resumeAt: Double = 0.0,
    /** Tên ngắn của chương (`title` của gói, không kèm tên phụ): dàn nhân vật ghi "từ <chương>" bằng tên này hay [title]. */
    val shortTitle: String = "",
) {
    val playable: Boolean get() = available || textOnly
}

/**
 * Trang sách: cuốn ([ListenBook] - cùng dữ liệu với ô ở Thư viện) + MỌI chương của gói (cả chương chưa có audio, để người nghe biết sách dài bao nhiêu)
 * + việc làm được trên máy này. Bất biến; đọc lại cả khối khi có gì đổi (dừng phát, đánh dấu, sửa tên).
 */
@Immutable
class BookDetail(
    val book: ListenBook,
    val chapters: List<ChapterLine>,
    /** Gửi được thành file sách (cuốn mở từ file / làm trên máy - BookActions.canShare). */
    val canShare: Boolean = false,
    /** Hồ sơ nghe gắn với cuốn này (chưa nghe lần nào thì rỗng). */
    val records: List<ListenRecord> = emptyList(),
    /** Lịch sử nghe của hồ sơ đang dùng, cũ trước. */
    val sessions: List<ListenSession> = emptyList(),
    /** Số thay đổi của người nghe chưa vào file sách đã lưu (menu "Lưu thay đổi" chỉ bấm được khi khác 0). */
    val unsaved: Int = 0,
    /** Việc đang chờ máy làm sách (đổi giới tính ...) đi theo file; "Lưu thành" nói số này. */
    val wishes: Int = 0,
    /** Cuốn đến từ file dự án (.abookproj): "present" = mang cả xưởng, "pending" = chờ dựng xưởng; null = từ file sách nghe (.abook). */
    val workshop: String? = null,
) {
    companion object {
        /** Hàm thuần: gói sách (như người nghe thấy) + trạng thái nghe -> trang sách. */
        fun of(
            manifest: JSONObject,
            state: JSONObject?,
            coverOf: (String) -> CoverRef?,
            remote: RemoteRef? = null,
            canShare: Boolean = false,
            records: JSONArray? = null,
            imported: Boolean = false,
        ): BookDetail {
            val book = BookJson.book(manifest, state, coverOf, remote, imported = imported)
            return BookDetail(
                book, lines(manifest, book.state), canShare, Records.parse(records), History.sessions(state),
                unsaved = manifest.optInt("unsaved", manifest.optInt("edits")), wishes = manifest.optInt("wishes"),
                workshop = manifest.optJSONObject("projectFile")?.optString("workshop")?.takeIf { it.isNotEmpty() },
            )
        }

        /** Mọi chương của gói theo thứ tự trong sách. Chương chỉ có chữ: độ dài là độ dài trình phát đã ghi lúc nghe (0 khi chưa nghe). */
        fun lines(manifest: JSONObject, state: ListenState): List<ChapterLine> {
            val entries = manifest.optJSONArray("chapters") ?: return emptyList()
            val out = ArrayList<ChapterLine>(entries.length())
            for (index in 0 until entries.length()) {
                val entry = entries.optJSONObject(index) ?: continue
                if (!entry.has("id")) continue
                val id = entry.optInt("id")
                val textPath = LibraryTree.textEntry(entry)
                val isText = textPath.isNotEmpty()
                val hasFile = entry.optString("file").let { it.isNotBlank() && it != "null" }
                val length = entry.optDouble("duration", 0.0)
                val info = ChapterInfo(
                    id = id,
                    title = field(entry, "fullTitle").ifEmpty { field(entry, "title") }.ifEmpty { "Chương $id" },
                    duration = if (isText || !length.isFinite()) 0.0 else length,
                    available = !isText && hasFile && entry.optBoolean("available"),
                    textOnly = isText,
                )
                val heard = ListenLogic.chapterHeard(state, info)
                out += ChapterLine(
                    id = info.id,
                    title = info.title,
                    duration = ListenLogic.knownDuration(state, info),
                    available = info.available,
                    textOnly = info.textOnly,
                    heard = heard,
                    done = heard >= 1f,
                    textPath = textPath,
                    resumeAt = if (heard > 0f && heard < 1f) state.chapters[id]?.heard ?: 0.0 else 0.0,
                    shortTitle = field(entry, "title"),
                )
            }
            return out
        }

        private fun field(entry: JSONObject, key: String): String = entry.optString(key).takeIf { it != "null" }.orEmpty().trim()
    }
}

/**
 * Chữ của trang sách (viết lại từ listen/labels.ts + BookScreen.tsx, cùng quy tắc). Hàm thuần - thử trên JVM (BookDetailTest).
 */
object BookPage {
    /**
     * Nhãn nút chính - một động từ ngắn: đang phát cuốn này = "Tạm dừng"; nghe hết = "Nghe lại từ đầu"; đã nghe = "Nghe tiếp"; chưa nghe = "Nghe".
     * Tên chương KHÔNG ghép vào nhãn (tên dài làm nhãn chảy ba dòng): nó là dòng phụ riêng của nút ([primaryDetail]).
     */
    fun primaryLabel(playingHere: Boolean, finished: Boolean, resume: ResumeSpot?, heardSeconds: Double): String = when {
        playingHere -> "Tạm dừng"
        finished -> "Nghe lại từ đầu"
        resume != null && (resume.at > 0 || heardSeconds > 0) -> "Nghe tiếp"
        heardSeconds > 0 -> "Nghe tiếp"
        else -> "Nghe"
    }

    /** Dòng phụ dưới nhãn nút chính: chương mà "Nghe tiếp" sẽ phát (giờ phút đã ở dòng tiến độ ngay trên); null khi nhãn tự đủ nghĩa. */
    fun primaryDetail(playingHere: Boolean, finished: Boolean, resume: ResumeSpot?, heardSeconds: Double): String? =
        if (!playingHere && !finished && resume != null && (resume.at > 0 || heardSeconds > 0)) resume.chapterTitle else null

    /** Dòng dưới tên sách: tác giả · giọng · số chương · thời lượng (thiếu phần nào thì bỏ phần ấy). */
    fun metaLine(book: ListenBook): String {
        val parts = ArrayList<String>(4)
        if (book.author.isNotBlank()) parts += book.author.trim()
        if (book.narrator.isNotBlank()) parts += "Giọng ${book.narrator.trim()}"
        when {
            book.textOnly -> parts += "${book.chaptersTotal} chương"
            book.complete -> {
                parts += "${book.chaptersTotal} chương"
                parts += Fmt.length(book.duration)
            }
            else -> {
                parts += "${book.chaptersAvailable}/${book.chaptersTotal} chương có audio"
                parts += Fmt.length(book.duration)
            }
        }
        return parts.dotJoined()
    }

    /** Dòng tình trạng dưới dòng trên (không hộp, không viên thuốc): sách chỉ có chữ, sách chưa đủ chương, sách nghe thẳng. null = không có gì để nói. */
    fun statusLine(book: ListenBook): String? = when {
        book.textOnly -> "Chỉ có chữ · nghe bằng giọng đọc"
        book.producing && book.pauseReason != null -> ProductionText.upcoming(book)
        book.producing -> "Đang thu; chương mới tự hiện khi xong."
        !book.complete && book.remote != null -> "Chưa đủ chương; đang dừng thu."
        !book.complete && book.imported -> "Chưa đủ chương; mở file sách mới hơn để nghe tiếp."
        !book.complete -> "Sách này có ${book.chaptersAvailable}/${book.chaptersTotal} chương đã thu - các chương sau chưa có audio"
        book.remote != null -> "Nghe thẳng từ ${book.remote.deviceName} - chương nghe tới được giữ lại trên máy này"
        else -> null
    }

    /**
     * Dòng dưới vạch tiến độ: nghe xong / hết phần đã có thì nói thế; đã nghe thì "Đã nghe X · còn Y chưa nghe" ("còn" theo phần ĐÃ PHỦ - chỗ tua qua vẫn là
     * chưa nghe, nên nói rõ "chưa nghe"); chưa nghe thì thời lượng cả cuốn.
     */
    fun progressLine(book: ListenBook, listening: Boolean = false, failed: Boolean = false): String {
        val progress = book.progress
        if (progress.finished || progress.caughtUp) return ListenLogic.progressText(book)
        val heard = progress.heardSeconds
        // Chưa nghe gì mà trình phát đang giữ cuốn này: nói đang nghe (hay không phát được), đừng nói "Chưa nghe".
        if (heard <= 0 && listening) return if (failed) "Chưa phát được" else "Đang nghe"
        if (heard <= 0) return "Chưa nghe · ${Fmt.length(book.duration)}"
        return "Đã nghe ${Fmt.length(heard)} · còn ${Fmt.length(maxOf(0.0, book.duration - heard))} chưa nghe"
    }

    /** Dòng phụ của một chương: thời lượng (chương chữ chưa nghe thì không có) + đã nghe bao nhiêu phần trăm; chưa có audio thì nói thế. */
    fun chapterLine(chapter: ChapterLine, producing: Boolean = false): String {
        if (!chapter.playable) return if (producing) "Đang thu âm" else "Chưa có audio"
        val parts = ArrayList<String>(2)
        if (chapter.duration > 0) parts += Fmt.length(chapter.duration)
        when {
            chapter.done -> parts += "đã nghe hết"
            chapter.heard > 0f -> parts += "đã nghe ${percent(chapter.heard)}"
        }
        return parts.dotJoined().replaceFirstChar { it.uppercase() }
    }

    /** "1%".."99%": chưa hết thì không làm tròn lên 100, đã nghe chút ít thì không về 0. */
    fun percent(fraction: Float): String = "${(fraction * 100).toInt().coerceIn(1, 99)}%"

    /** Chương "Nghe tiếp" chỉ vào: chương trình phát đang ở nếu đang nạp cuốn này, không thì chỗ nghe tiếp của cuốn. */
    fun currentChapter(book: ListenBook, player: PlayerState): Int? =
        if (player.bookId == book.id && player.chapterId != null) player.chapterId else book.resume?.chapterId
}
