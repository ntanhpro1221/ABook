package vn.abook.player.ui.editbook

import androidx.compose.runtime.Immutable
import vn.abook.player.ui.data.CoverRef

@Immutable
data class EditChapter(val id: Long, val title: String, val subtitle: String = "") {
    val shown: String get() = listOf(title, subtitle).filter { it.isNotEmpty() }.joinToString(": ")
}

@Immutable
data class EditSnapshot(
    val id: String, val title: String, val author: String = "", val chapters: List<EditChapter> = emptyList(),
    val cover: CoverRef? = null, val textOnly: Boolean = true, val sendable: Boolean = false,
    val holder: String = "máy tính", val pending: Int = 0, val syncNote: String = "",
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
    val saving: Boolean = false, val sending: Boolean = false, val problem: String = "", val note: String = "",
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
        if (diff.title != null && tidy(diff.title).isEmpty()) return "Bạn hãy nhập tên sách."
        if (diff.chapters.any { tidy(it.title).isEmpty() }) return "Bạn hãy nhập tên chương."
        val fields = listOfNotNull(diff.title, diff.author) + diff.chapters.flatMap { listOf(it.title, it.subtitle) }
        if (fields.any { it.codePointCount(0, it.length) > 160 }) return "Tên quá dài. Bạn hãy dùng tối đa 160 ký tự."
        return null
    }
}

@Immutable
data class CropChoice(val zoom: Float = 1f, val x: Float = 0f, val y: Float = 0f)

@Immutable
data class CropRect(val left: Int, val top: Int, val width: Int, val height: Int)

object CropLogic {
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
