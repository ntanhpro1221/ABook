package vn.abook.player.ui.addbook

import androidx.compose.runtime.Immutable

@Immutable
enum class ImportStage(val label: String) {
    Waiting("Chờ"), Reading("Đang đọc"), Review("Đang xem"), Adding("Đang thêm"),
    Added("Đã thêm"), Existing("Đã có trong thư viện"), Skipped("Đã bỏ qua"), Error("Chưa đọc được"),
}

@Immutable
data class ImportItem(
    val id: Long, val source: String, val name: String = "File đã chọn", val folder: Boolean = false,
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
    fun where(chapters: List<Int>): String = if (chapters.size == 1) "chương ${chapters[0]}" else "${chapters.size} chương"

    /** Dòng phụ của "Tách chương" (cùng chữ với `splitHint` của web, listen/textImport.ts): có phần Mở đầu thì nói thêm số chương. */
    fun splitHint(preview: ImportPreview): String {
        val extra = if (preview.splitOffer > preview.splitHeadings) " (thêm phần Mở đầu - ${preview.splitOffer} chương)" else ""
        return "Theo ${preview.splitHeadings} dòng “Chương N” trong file$extra."
    }

    /** Số cuốn còn trong hàng mà chưa vào Thư viện (chờ, đang đọc, đang xem): đóng Thêm sách lúc còn hơn một cuốn như vậy thì hỏi trước (web AddBook `unfinished`). */
    fun unfinished(items: List<ImportItem>) = items.count { it.stage == ImportStage.Waiting || it.stage == ImportStage.Reading || it.stage == ImportStage.Review }

    /** Lời hỏi khi đóng Thêm sách giữa hàng (cùng câu với web). */
    fun leaveQuestion(count: Int) = "Còn $count cuốn chưa thêm vào thư viện. Đóng bây giờ thì các cuốn ấy sẽ không được thêm."
    fun rechooseQuestion(count: Int) = "Còn $count cuốn chưa thêm vào thư viện. Chọn lại thì các cuốn ấy sẽ không được thêm."
    fun openFailure(item: ImportItem, reason: String?): String {
        val book = item.name.endsWith(".abook", true) || item.name.endsWith(".abookproj", true)
        val title = if (book) "Chưa mở được file sách" else "Chưa mở được file"
        val details = reason?.takeIf { it.isNotBlank() } ?: if (book) "File không có sách nào." else "File này không có chữ để đọc."
        return "$title. $details"
    }

    /** "Chọn hết": mọi chương của bản xem trước. */
    fun all(preview: ImportPreview) = preview.chapters.map { it.index }.toSet()

    /** Không tích chương nào thì không thêm được sách - trừ khi việc là mở cuốn đã có ("Dùng sách có"), không cần chương nào. */
    fun canAdd(preview: ImportPreview, choice: ImportChoices) = choice.picked.isNotEmpty() || (preview.existingId != null && !choice.separate)

    const val NOTHING_PICKED = "Chưa chọn chương nào - tích ít nhất một chương để thêm vào thư viện."

    fun groups(items: List<Suggestion>): List<SuggestionGroup> = items.groupBy { it.line }.map { (line, rows) ->
        SuggestionGroup(line, rows.map { it.chapter }, rows.all { it.skipped })
    }

    fun defaults(preview: ImportPreview) = ImportChoices(
        title = preview.title, picked = preview.chapters.filter { it.included }.map { it.index }.toSet(),
    )

    fun summary(items: List<ImportItem>): String {
        if (items.isEmpty() || items.any { it.stage in setOf(ImportStage.Waiting, ImportStage.Reading, ImportStage.Review, ImportStage.Adding) }) return ""
        val count = items.count { it.stage == ImportStage.Added }
        return if (count == 0) "Không thêm cuốn nào" else "Đã thêm $count sách"
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
