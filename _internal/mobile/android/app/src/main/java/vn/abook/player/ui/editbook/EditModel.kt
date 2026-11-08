package vn.abook.player.ui.editbook

import vn.abook.player.S

import androidx.compose.runtime.Immutable
import vn.abook.player.ui.data.CoverRef

@Immutable
data class EditChapter(val id: Long, val title: String, val subtitle: String = "", val original: String = "") {
    val shown: String get() = listOf(title, subtitle).filter { it.isNotEmpty() }.joinToString(": ")

    /** Tên đang hiện khác tên trong file gốc (cuốn nghe thẳng chưa tải không có bản gốc: không bao giờ "đã đổi"). */
    val renamed: Boolean get() = original.isNotEmpty() && EditLogic.tidy(original) != EditLogic.tidy(shown)
}

@Immutable
data class EditSnapshot(
    val id: String, val title: String, val author: String = "", val chapters: List<EditChapter> = emptyList(),
    val cover: CoverRef? = null, val textOnly: Boolean = true, val sendable: Boolean = false,
    val holder: String = S.s_may_tinh_8eafc226, val pending: Int = 0, val syncNote: String = "",
    /** Số thay đổi của người nghe trên cuốn này (áp ngay + chờ Studio, `BookEdits.count`): "Bỏ mọi thay đổi (N)" chỉ hiện khi khác 0. */
    val edits: Int = 0,
)

@Immutable
data class EditDraft(val title: String, val author: String, val chapters: List<EditChapter>)

@Immutable
data class EditDiff(val title: String? = null, val author: String? = null, val chapters: List<EditChapter> = emptyList()) {
    val empty: Boolean get() = title == null && author == null && chapters.isEmpty()
}

@Immutable
data class EditState(
    val saved: EditSnapshot? = null, val draft: EditDraft? = null, val loading: Boolean = true,
    val saving: Boolean = false, val sending: Boolean = false, val problem: String = "", val sendProblem: String = "",
    val notice: String = "",
)

object EditLogic {
    private val spaces = Regex("\\s+")
    fun tidy(value: String) = value.trim().replace(spaces, " ")
    fun draft(snapshot: EditSnapshot) = EditDraft(snapshot.title, snapshot.author, snapshot.chapters)
    fun rebase(previous: EditSnapshot?, draft: EditDraft?, latest: EditSnapshot): EditDraft {
        if (previous == null || draft == null) return EditLogic.draft(latest)
        val pending = diff(previous, draft)
        return EditDraft(pending.title ?: latest.title, pending.author ?: latest.author,
            latest.chapters.map { row -> pending.chapters.firstOrNull { it.id == row.id } ?: row })
    }
    fun diff(saved: EditSnapshot, draft: EditDraft) = EditDiff(
        draft.title.takeIf { tidy(it) != tidy(saved.title) },
        draft.author.takeIf { tidy(it) != tidy(saved.author) },
        draft.chapters.filter { next -> saved.chapters.firstOrNull { it.id == next.id }?.let {
            tidy(next.title) != tidy(it.title) || tidy(next.subtitle) != tidy(it.subtitle)
        } == true },
    )

    fun validate(diff: EditDiff): String? {
        if (diff.title != null && tidy(diff.title).isEmpty()) return S.s_ban_hay_nhap_ten_sach_da2b7a84
        if (diff.chapters.any { tidy(it.title).isEmpty() }) return S.s_ban_hay_nhap_ten_chuong_e78e5b32
        val fields = listOfNotNull(diff.title, diff.author) + diff.chapters.flatMap { listOf(it.title, it.subtitle) }
        if (fields.any { it.codePointCount(0, it.length) > 160 }) return S.s_ten_qua_dai_ban_hay_dung_toi_da_160_ky_tu_51872335
        return null
    }

    /** Câu đầu của lời lỗi khi lưu hỏng, theo thứ đang lưu (cùng chữ với lời báo của web, listen/EditBook.tsx). */
    fun failure(diff: EditDiff): String = when {
        diff.title != null -> S.s_chua_doi_duoc_ten_sach_cbfa6bb5
        diff.author != null -> S.s_chua_doi_duoc_tac_gia_3e777e8e
        else -> S.s_chua_doi_duoc_ten_chuong_01cae915
    }
}

/** Một từ đã dạy giọng đọc ("Cách đọc tên", lớp sửa `readings`): chữ trong sách -> cách đọc. Chỉ giọng đọc đổi, chữ của sách giữ nguyên. */
@Immutable
data class WordReading(val surface: String, val spoken: String)

/**
 * "Cách đọc tên" của Sửa sách (web: BookReadingsSection). `problem`: chưa đọc được danh sách; `notice`: lời sau lần lưu vừa rồi (web: toast); `failed`: lần lưu / bỏ
 * vừa rồi hỏng.
 */
@Immutable
data class ReadingsUi(
    val loaded: Boolean = false, val list: List<WordReading> = emptyList(), val problem: String = "", val saving: Boolean = false,
    val notice: String = "", val failed: String = "",
)

/** Một ảnh bìa tìm được trên mạng (`GET /api/books/<mã>/cover/search`, cùng JSON với máy tính - shared/CoverSearch.tsx `FoundCover`). */
@Immutable
data class FoundCover(val provider: String, val title: String, val author: String, val thumb: String, val url: String)

/** Lời đáp của một lượt tìm bìa: `failed` = nguồn chưa hỏi được (mất mạng, nguồn chậm). */
@Immutable
data class CoverResults(val query: String, val results: List<FoundCover> = emptyList(), val failed: List<String> = emptyList())

/**
 * Màn "Tìm ảnh bìa" (web: CoverSearchPanel). `searched`: đã có lời đáp (hay lỗi) cho lượt tìm gần nhất; `choosing`: địa chỉ ảnh đang được đặt làm bìa; `unset`: ảnh
 * vừa chọn mà chưa đặt được (cho "Thử lại"); `broken`: ảnh nhỏ không tải được - bỏ khỏi lưới, không để ô trống mà vẫn bấm được.
 */
@Immutable
data class CoverSearchUi(
    val query: String = "", val searching: Boolean = false, val searched: Boolean = false, val results: List<FoundCover> = emptyList(),
    val failed: List<String> = emptyList(), val error: Boolean = false, val choosing: String? = null, val unset: FoundCover? = null,
    val broken: Set<String> = emptySet(),
) {
    val shown: List<FoundCover> get() = results.filter { it.thumb !in broken }

    /** Mọi nguồn đã trả lời mà không có ảnh nào: mời chọn ảnh trên máy. */
    val nothing: Boolean get() = searched && !searching && !error && shown.isEmpty() && failed.isEmpty()
}

object ReadingText {
    private val spaces = Regex("\\s+")

    /** Cách đọc người gõ, làm sạch như web `cleanSpoken`: NFC, bỏ khoảng trắng hai đầu, gộp khoảng trắng. */
    fun spoken(value: String): String = java.text.Normalizer.normalize(value, java.text.Normalizer.Form.NFC).trim().replace(spaces, " ")

    /** "Lưu cho cả cuốn" bấm được: đã gõ, khác cách đọc đang có, và không phải chính chữ trong sách. */
    fun canSave(surface: String, current: String, typed: String): Boolean {
        val said = spoken(typed)
        return said.isNotEmpty() && said != current && said != surface
    }

    /** Lời sau khi lưu: đoạn đang đọc nói nốt cách cũ, từ đoạn sau mới là cách mới (web: toast của ReadingForm). */
    fun saved(surface: String, spoken: String): String =
        if (spoken.isNotEmpty()) S.s_0_se_doc_la_1_tu_doan_sau_da097218(surface, spoken) else S.s_0_doc_lai_nhu_chu_trong_sach_tu_doan_sau_bb73a28d(surface)

    const val HINT = S.s_day_cach_doc_tu_thuong_la_ten_rieng_chu_gi_69023eb0
    const val DISCARD_HINT = S.s_sach_tro_ve_dung_nhu_nguoi_lam_sach_da_don_f3a48d43
}

@Immutable
data class CropChoice(val zoom: Float = 1f, val x: Float = 0f, val y: Float = 0f)

@Immutable
data class CropRect(val left: Int, val top: Int, val width: Int, val height: Int)

object CropLogic {
    /**
     * Một cử chỉ (kéo `panX`/`panY` tính bằng điểm ảnh của ảnh, chụm `zoomBy`) lên khung cắt: khung đổi cỡ quanh tâm của chính nó, rồi dời, và không bao giờ
     * rời ảnh. Trả lựa chọn mới ([rect] dựng lại đúng khung ấy).
     */
    fun transform(width: Int, height: Int, choice: CropChoice, panX: Float, panY: Float, zoomBy: Float): CropChoice {
        val before = rect(width, height, choice)
        val zoom = (choice.zoom * zoomBy).coerceIn(1f, 4f)
        val size = rect(width, height, choice.copy(zoom = zoom))
        fun fraction(center: Float, length: Int, whole: Int): Float {
            val slack = whole - length
            return if (slack <= 0) 0f else ((center - length / 2f) / slack).coerceIn(0f, 1f) * 2f - 1f
        }
        return CropChoice(
            zoom,
            fraction(before.left + before.width / 2f + panX, size.width, width),
            fraction(before.top + before.height / 2f + panY, size.height, height),
        )
    }

    fun rect(width: Int, height: Int, choice: CropChoice): CropRect {
        require(width > 0 && height > 0)
        val zoom = choice.zoom.coerceIn(1f, 4f)
        val cropWidth = minOf(width.toFloat(), height * 2f / 3f) / zoom
        val cropHeight = cropWidth * 3f / 2f
        val w = cropWidth.toInt().coerceIn(1, width)
        val h = cropHeight.toInt().coerceIn(1, height)
        val left = ((width - w) * (choice.x.coerceIn(-1f, 1f) + 1f) / 2f).toInt()
        val top = ((height - h) * (choice.y.coerceIn(-1f, 1f) + 1f) / 2f).toInt()
        return CropRect(left, top, w, h)
    }
}
