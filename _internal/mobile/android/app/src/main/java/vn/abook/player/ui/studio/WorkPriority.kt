package vn.abook.player.ui.studio

import androidx.compose.runtime.Immutable
import vn.abook.player.S

@Immutable
data class WorkPriority(
    val reason: String,
    val lines: Int,
    val recordedLines: Int?,
    val recordedChapters: Int?,
    val estimatedActions: Int,
    val overlapLines: Int,
)

internal object WorkPriorityText {
    fun describe(item: WorkItem, note: String): String {
        val p = item.priority
        val reason = when (p?.reason) {
            "upcoming" -> S.s_work_reason_upcoming
            "tentative" -> S.s_work_reason_tentative
            "redo" -> S.s_work_reason_redo
            "refused" -> S.s_work_reason_refused
            else -> S.s_work_reason_impact
        }
        return listOf(reason,
            if (p?.recordedLines != null && p.recordedChapters != null)
                S.s_work_recorded(p.lines, p.recordedLines, p.recordedChapters) else S.s_work_unknown(p?.lines ?: item.affected),
            S.s_work_effort(p?.estimatedActions ?: 1),
            if ((p?.overlapLines ?: 0) > 0) S.s_work_overlap(p!!.overlapLines) else "",
            if (item.redoOnly) S.s_work_reason_redo else S.s_work_apply(note),
        ).filter { it.isNotEmpty() }.joinToString(" ")
    }
}
