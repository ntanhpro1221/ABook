package vn.abook.player.ui.addbook

import vn.abook.player.S

import androidx.compose.runtime.Immutable

@Immutable
enum class ImportStage(val label: String) {
    Waiting(S.s_cho_8de7e9a5), Reading(S.s_dang_doc_1b09d2d9), Review(S.s_dang_xem_42cc3b08), Adding(S.s_dang_them_457edcc3),
    Added(S.s_da_them_e26b2fcb), Existing(S.s_da_co_trong_thu_vien_3bb6eeb4), Skipped(S.s_da_bo_qua_df41794e), Error(S.s_chua_doc_duoc_ad95887c),
}

@Immutable
data class ImportItem(
    val id: Long, val source: String, val name: String = S.s_file_da_chon_e29eb975, val folder: Boolean = false,
    val stage: ImportStage = ImportStage.Waiting, val problem: String = "", val bookId: String? = null,
)

@Immutable
data class ImportChapter(val index: Int, val title: String, val included: Boolean = true, val note: String = "")

@Immutable
data class Suggestion(val chapter: Int, val line: String, val skipped: Boolean = false)

@Immutable
data class SuggestionGroup(val line: String, val chapters: List<Int>, val skipped: Boolean)

@Immutable
data class ImportPreview(
    val title: String, val author: String = "", val chapters: List<ImportChapter>,
    val suggestions: List<Suggestion> = emptyList(), val notes: List<String> = emptyList(),
    val footnoteCount: Int = 0, val footnoteMarks: Int = 0, val footnoteExample: String = "",
    val splitOffer: Int = 0, val splitHeadings: Int = 0, val existingId: String? = null,
    /** Tên cuốn đã có trong thư viện (`existingId`), để nói cuốn nào. Trống khi không đọc được tên. */
    val existingTitle: String = "",
    val sameSource: Boolean = false,
    val existingChapters: Int = 0,
)

data class PackageReview(val bookId: String, val title: String, val incomingTitle: String, val how: String)

@Immutable
data class ImportChoices(
    val title: String = "", val picked: Set<Int> = emptySet(), val names: Map<Int, String> = emptyMap(),
    val skipped: Set<String> = emptySet(), val split: Boolean = false,
    val hideMarks: Boolean = false, val notes: String = "", val separate: Boolean = false,
)

@Immutable
data class ImportState(
    val items: List<ImportItem> = emptyList(), val currentId: Long? = null,
    val preview: ImportPreview? = null, val choices: ImportChoices = ImportChoices(),
    val busy: Boolean = false, val problem: String = "",
    val packageReview: PackageReview? = null,
    val notice: String = "",
    val addingRest: Boolean = false,
)

/** File order is preserved: native imports never navigate away automatically for a package. */
object ImportLogic {
    private val spaces = Regex("\\s+")

    /** Tên đang gõ khác tên gốc (khoảng trắng thừa không tính). */
    fun renamed(current: String, original: String) = current.trim().replace(spaces, " ") != original.trim().replace(spaces, " ")

    fun settle(items: List<ImportItem>, id: Long, stage: ImportStage, problem: String = "", bookId: String? = null) =
        items.map { if (it.id == id) it.copy(stage = stage, problem = problem, bookId = bookId) else it }

    fun next(items: List<ImportItem>) = items.firstOrNull { it.stage == ImportStage.Waiting }

    /** Chỗ của một gợi ý bỏ đọc dòng: "chương 3" hay "12 chương" (cùng chữ với `where` của web, listen/ReadingSuggestions.tsx). */
    fun where(chapters: List<Int>): String = if (chapters.size == 1) S.s_chuong_0_55d256d1(chapters[0]) else S.s_0_chuong_04093412(chapters.size)

    /** Dòng phụ của "Tách chương" (cùng chữ với `splitHint` của web, listen/textImport.ts): có phần Mở đầu thì nói thêm số chương. */
    fun splitHint(preview: ImportPreview): String {
        val extra = if (preview.splitOffer > preview.splitHeadings) S.s_them_phan_mo_dau_0_chuong_16e2c142(preview.splitOffer) else ""
        return S.s_theo_0_dong_chuong_n_trong_file_1_a36f5485(preview.splitHeadings, extra)
    }

    /** Số cuốn còn trong hàng mà chưa vào Thư viện (chờ, đang đọc, đang xem): đóng Thêm sách lúc còn hơn một cuốn như vậy thì hỏi trước (web AddBook `unfinished`). */
    fun unfinished(items: List<ImportItem>) = items.count { it.stage == ImportStage.Waiting || it.stage == ImportStage.Reading || it.stage == ImportStage.Review }

    /** Lời hỏi khi đóng Thêm sách giữa hàng (cùng câu với web). */
    fun leaveQuestion(count: Int) = S.s_con_0_cuon_chua_them_vao_thu_vien_dong_bay_91cf24f8(count)
    fun rechooseQuestion(count: Int) = S.s_con_0_cuon_chua_them_vao_thu_vien_chon_lai_0dbdaa1f(count)
    fun openFailure(item: ImportItem, reason: String?): String {
        val book = item.name.endsWith(".abook", true) || item.name.endsWith(".abookproj", true)
        val title = if (book) S.s_chua_mo_duoc_file_sach_2cdc21ae else S.s_chua_mo_duoc_file_bcf064f0
        val details = reason?.takeIf { it.isNotBlank() } ?: if (book) S.s_file_khong_co_sach_nao_842f4147 else S.s_file_nay_khong_co_chu_de_doc_b928a901
        return "$title. $details"
    }

    /** "Chọn hết": mọi chương của bản xem trước. */
    fun all(preview: ImportPreview) = preview.chapters.map { it.index }.toSet()

    /** Không tích chương nào thì không thêm được sách - trừ khi việc là mở cuốn đã có ("Dùng sách có"), không cần chương nào. */
    fun canAdd(preview: ImportPreview, choice: ImportChoices) = choice.picked.isNotEmpty() || (preview.existingId != null && !choice.separate)

    const val NOTHING_PICKED = S.s_chua_chon_chuong_nao_tich_it_nhat_mot_chuo_416cb9ec

    fun groups(items: List<Suggestion>): List<SuggestionGroup> = items.groupBy { it.line }.map { (line, rows) ->
        SuggestionGroup(line, rows.map { it.chapter }, rows.all { it.skipped })
    }

    fun defaults(preview: ImportPreview) = ImportChoices(
        title = preview.title, picked = preview.chapters.filter { it.included }.map { it.index }.toSet(),
    )

    fun summary(items: List<ImportItem>): String {
        if (items.isEmpty() || items.any { it.stage in setOf(ImportStage.Waiting, ImportStage.Reading, ImportStage.Review, ImportStage.Adding) }) return ""
        val count = items.count { it.stage == ImportStage.Added }
        return if (count == 0) S.s_khong_them_cuon_nao_0fb1d747 else S.s_da_them_0_sach_87064233(count)
    }

    fun picks(preview: ImportPreview, choice: ImportChoices) = preview.chapters.filter { it.index in choice.picked }.map {
        it.index to choice.names[it.index]?.trim().orEmpty()
    }

    fun accepted(preview: ImportPreview, choice: ImportChoices): List<SuggestionGroup> {
        return groups(forPicked(preview, choice).filter { it.line in choice.skipped }.map { it.copy(skipped = true) })
    }

    fun forPicked(preview: ImportPreview, choice: ImportChoices): List<Suggestion> {
        val numbers = preview.chapters.filter { it.index in choice.picked }.mapIndexed { index, row -> row.index to index + 1 }.toMap()
        return preview.suggestions.mapNotNull { row -> numbers[row.chapter]?.let { row.copy(chapter = it) } }
    }

    fun retain(preview: ImportPreview, previous: ImportPreview, choice: ImportChoices): ImportChoices {
        val same = preview.chapters.map { it.title to it.included } == previous.chapters.map { it.title to it.included }
        return if (same) choice else choice.copy(picked = defaults(preview).picked, names = emptyMap(), skipped = emptySet())
    }
}
