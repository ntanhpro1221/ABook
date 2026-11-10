package vn.abook.player.ui.data

import vn.abook.player.S

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
                    title = LibraryTree.chapterTitle(entry),
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
     * Tên chương ([primaryDetail]) đi sau nhãn trên CÙNG một dòng ("Nghe tiếp · Chương 4", như Qt), cắt "…" phía tên chương - nút luôn cao 48.
     */
    fun primaryLabel(playingHere: Boolean, finished: Boolean, resume: ResumeSpot?, heardSeconds: Double): String = when {
        playingHere -> S.s_tam_dung_67635815
        finished -> S.s_nghe_lai_tu_dau_e251d632
        resume != null && (resume.at > 0 || heardSeconds > 0) -> S.s_nghe_tiep_403b90a5
        heardSeconds > 0 -> S.s_nghe_tiep_403b90a5
        else -> S.s_nghe_a43aafef
    }

    /** Phần sau " · " của nút chính: chương mà "Nghe tiếp" sẽ phát (giờ phút đã ở dòng tiến độ ngay trên); null khi nhãn tự đủ nghĩa. */
    fun primaryDetail(playingHere: Boolean, finished: Boolean, resume: ResumeSpot?, heardSeconds: Double): String? =
        if (!playingHere && !finished && resume != null && (resume.at > 0 || heardSeconds > 0)) resume.chapterTitle else null

    /** Dòng dưới tên sách: tác giả · giọng · số chương · thời lượng (thiếu phần nào thì bỏ phần ấy). */
    fun metaLine(book: ListenBook): String {
        val parts = ArrayList<String>(4)
        if (book.author.isNotBlank()) parts += book.author.trim()
        if (book.narrator.isNotBlank()) parts += S.s_giong_0_c554bb1b(book.narrator.trim())
        when {
            book.textOnly -> parts += S.s_0_chuong_04093412(book.chaptersTotal)
            book.complete -> {
                parts += S.s_0_chuong_04093412(book.chaptersTotal)
                parts += Fmt.length(book.duration)
            }
            else -> {
                parts += S.s_0_1_chuong_co_audio_9706857d(book.chaptersAvailable, book.chaptersTotal)
                parts += Fmt.length(book.duration)
            }
        }
        return parts.dotJoined()
    }

    /** Dòng tình trạng dưới dòng trên (không hộp, không viên thuốc): sách chỉ có chữ, sách chưa đủ chương, sách nghe thẳng. null = không có gì để nói. */
    fun statusLine(book: ListenBook): String? = when {
        book.textOnly -> S.s_chi_co_chu_nghe_bang_giong_doc_edf36d64
        book.producing && book.pauseReason != null -> ProductionText.upcoming(book)
        book.producing -> S.s_dang_thu_chuong_moi_tu_hien_khi_xong_123d0db2
        !book.complete && book.remote != null -> S.s_chua_du_chuong_dang_dung_thu_3653bcf7
        !book.complete && book.imported -> S.s_chua_du_chuong_mo_file_sach_moi_hon_de_ngh_ca290cd2
        !book.complete -> S.s_sach_nay_co_0_1_chuong_da_thu_cac_chuong_s_b799aec1(book.chaptersAvailable, book.chaptersTotal)
        book.remote != null -> S.s_nghe_thang_tu_0_chuong_nghe_toi_duoc_giu_l_a6a23b61(book.remote.deviceName)
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
        if (heard <= 0 && listening) return if (failed) S.s_chua_phat_duoc_3ecb850e else S.s_dang_nghe_9310d8cf
        if (heard <= 0) return S.s_chua_nghe_0_dd595dec(Fmt.length(book.duration))
        return S.s_da_nghe_0_con_1_chua_nghe_478f5195(Fmt.length(heard), Fmt.length(maxOf(0.0, book.duration - heard)))
    }

    /** Dòng phụ của một chương: thời lượng (chương chữ chưa nghe thì không có) + đã nghe bao nhiêu phần trăm; chưa có audio thì nói thế. */
    fun chapterLine(chapter: ChapterLine, producing: Boolean = false): String {
        if (!chapter.playable) return if (producing) S.s_dang_thu_am_96160328 else S.s_chua_co_audio_4b0d19a4
        val parts = ArrayList<String>(2)
        if (chapter.duration > 0) parts += Fmt.length(chapter.duration)
        when {
            chapter.done -> parts += S.s_da_nghe_het_f413dcae
            chapter.heard > 0f -> parts += S.s_da_nghe_0_860c7b38(percent(chapter.heard))
        }
        return parts.dotJoined().replaceFirstChar { it.uppercase() }
    }

    /** "1%".."99%": chưa hết thì không làm tròn lên 100, đã nghe chút ít thì không về 0. */
    fun percent(fraction: Float): String = "${(fraction * 100).toInt().coerceIn(1, 99)}%"

    /** Chương "Nghe tiếp" chỉ vào: chương trình phát đang ở nếu đang nạp cuốn này, không thì chỗ nghe tiếp của cuốn. */
    fun currentChapter(book: ListenBook, player: PlayerState): Int? =
        if (player.bookId == book.id && player.chapterId != null) player.chapterId else book.resume?.chapterId
}
