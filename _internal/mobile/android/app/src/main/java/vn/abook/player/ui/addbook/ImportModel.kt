package vn.abook.player.ui.addbook

import androidx.compose.runtime.Immutable

@Immutable
enum class ImportStage(val label: String) {
    Waiting("Chờ"), Reading("Đang đọc"), Review("Đang xem"), Adding("Đang thêm"),
    Added("Đã thêm"), Existing("Đã có trong thư viện"), Skipped("Đã bỏ qua"), Error("Chưa nhập được"),
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
)

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
)

/** File order is preserved: native imports never navigate away automatically for a package. */
object ImportLogic {
    private val spaces = Regex("\\s+")

    /** Tên đang gõ khác tên gốc (khoảng trắng thừa không tính). */
    fun renamed(current: String, original: String) = current.trim().replace(spaces, " ") != original.trim().replace(spaces, " ")

    fun settle(items: List<ImportItem>, id: Long, stage: ImportStage, problem: String = "", bookId: String? = null) =
        items.map { if (it.id == id) it.copy(stage = stage, problem = problem, bookId = bookId) else it }

    fun next(items: List<ImportItem>) = items.firstOrNull { it.stage == ImportStage.Waiting }

    fun groups(items: List<Suggestion>): List<SuggestionGroup> = items.groupBy { it.line }.map { (line, rows) ->
        SuggestionGroup(line, rows.map { it.chapter }, rows.all { it.skipped })
    }

    fun defaults(preview: ImportPreview) = ImportChoices(
        title = preview.title, picked = preview.chapters.filter { it.included }.map { it.index }.toSet(),
    )

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
