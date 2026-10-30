package vn.abook.player.ui.studio

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.Immutable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ClipState
import vn.abook.player.StudioPolling
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.studio.parts.AnswerButton
import vn.abook.player.ui.studio.parts.ClipButton
import vn.abook.player.ui.studio.parts.ClipProblem
import vn.abook.player.ui.studio.parts.SideBySide
import vn.abook.player.ui.studio.parts.collectClip
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Những gì tab "Cần nghe lại" đọc từ các luồng (lần hỏi gần nhất, tiếng đang phát) - gom lại để dựng các mục của danh sách mà không cần là hàm Composable. */
@Immutable
class ReviewData(val poll: StudioPolling.Poll<ReviewList>, val items: List<ReviewItem>, val clip: ClipState)

@Composable
internal fun rememberReviewData(review: StudioReviewState): ReviewData {
    val poll by review.poll.collectAsState()
    val clip = review.clip.collectClip()
    return ReviewData(poll, review.items(), clip)
}

/**
 * Tab "Cần nghe lại" (NATIVE_REMOTE_STUDIO.md §6.5): bộ lọc chưa xem / đã xem, "Nghe liền", rồi từng câu - nghe, rồi "Ổn" hay "Cần thu lại". Mỗi câu một mục
 * của danh sách lười, nên cả trăm câu không dựng một lượt.
 */
internal fun LazyListScope.reviewTab(review: StudioReviewState, data: ReviewData, book: StudioBook, slide: Modifier) {
    val list = review.list()
    item("review_head", "review_head") {
        Column(Modifier.fillMaxWidth().then(slide).padding(top = Dim.s8).testTag("studio_review")) {
            ChoiceRow(ReviewFilter.entries, review.filter, { filter, _ -> review.pick(filter) }, Modifier.fillMaxWidth(), "studio_review_filter")
            if (list != null) ReviewHeader(review, list, data)
            InlineProblem(review.problem, null, "studio_review_problem")
            ElsewhereNote(review)
            InlineProblem(data.poll.error?.let { StudioText.failure(it) }.orEmpty(), review::refreshSoon, "studio_review_poll_problem")
            ClipProblem(data.clip)
        }
    }
    when {
        list == null && data.poll.error == null -> item("review_loading", "status") {
            BasicText(WorkText.REVIEW_LOADING, style = Abook.type.body.copy(color = Abook.colors.text2), modifier = Modifier.then(slide).padding(top = Dim.s24).testTag("studio_review_loading"))
        }
        list == null -> Unit
        data.items.isEmpty() -> item("review_empty", "status") { ReviewEmpty(review, book, Modifier.then(slide)) }
        else -> {
            items(data.items, key = { "review_${it.stableId}" }, contentType = { "review" }) { entry ->
                Column(Modifier.fillMaxWidth().then(slide)) {
                    ReviewRow(entry, review, data.clip)
                    RowLine()
                }
            }
            if (list.nextCursor != null) {
                item("review_more", "more") {
                    TextAction(
                        if (review.loadingMore) WorkText.LOADING else "${WorkText.MORE_ITEMS} (còn ${list.remaining})", review::loadMore, "studio_review_more",
                        Modifier.fillMaxWidth().then(slide), Alignment.CenterStart,
                    )
                }
            }
        }
    }
}

/** Đầu danh sách: còn bao nhiêu câu chưa xem, chương sẽ thu lại, câu lệch nhẹ, "Nghe liền". */
@Composable
private fun ReviewHeader(review: StudioReviewState, list: ReviewList, data: ReviewData) {
    val minor = (list.counts[ReviewKind.Name] ?: 0) + (list.counts[ReviewKind.Text] ?: 0)
    Column(Modifier.fillMaxWidth().padding(top = Dim.s12)) {
        if (review.filter == ReviewFilter.Todo) Caption(WorkText.reviewPending(list.pending), Modifier.testTag("studio_review_pending"))
        if (list.redoChapters.isNotEmpty()) RowHint(WorkText.redoChapters(list.redoChapters), Modifier.padding(top = Dim.s4).testTag("studio_review_redo"))
        if (minor > 0 || review.showMinor) {
            TextAction(
                if (review.showMinor) WorkText.MINOR_HIDE else "${WorkText.MINOR_SHOW} ($minor)", review::toggleMinor, "studio_review_minor",
                Modifier.fillMaxWidth(), Alignment.CenterStart,
            )
        }
        val playable = data.items.count { review.clipOf(it) != null }
        if (review.continuous) {
            AnswerButton(WorkText.PLAY_ALL_STOP, review::stopContinuous, "studio_review_stop", Modifier.padding(top = Dim.s8))
        } else if (playable > 0) {
            AnswerButton(WorkText.playAll(playable), review::startContinuous, "studio_review_play_all", Modifier.padding(top = Dim.s8), primary = true)
        }
        if (review.finished && !review.continuous) Caption(WorkText.PLAY_FINISHED, Modifier.padding(top = Dim.s8).testTag("studio_review_finished"))
    }
}

/** Máy hay cửa sổ khác vừa phán quyết khác cho câu này: giữ của mình hay lấy của họ. */
@Composable
private fun ElsewhereNote(review: StudioReviewState) {
    val note = review.elsewhere ?: return
    Column(Modifier.fillMaxWidth().padding(top = Dim.s12).testTag("studio_review_elsewhere")) {
        RowHint(WorkText.elsewhere(note.theirs))
        Row(Modifier.fillMaxWidth()) {
            TextAction(WorkText.TAKE_THEIRS, review::takeTheirs, "studio_review_take", Modifier.weight(1f), Alignment.CenterStart)
            TextAction(WorkText.KEEP_MINE, review::dismissElsewhere, "studio_review_keep", Modifier.weight(1f), Alignment.CenterEnd)
        }
    }
}

@Composable
private fun ReviewEmpty(review: StudioReviewState, book: StudioBook, modifier: Modifier) {
    val notRecorded = review.filter == ReviewFilter.Todo && ReviewLogic.notRecordedYet(book)
    val title = when {
        review.filter == ReviewFilter.Done -> ""
        notRecorded -> WorkText.REVIEW_NOT_RECORDED_TITLE
        else -> WorkText.REVIEW_EMPTY_TITLE
    }
    val line = when {
        review.filter == ReviewFilter.Done -> WorkText.REVIEW_DONE_EMPTY
        notRecorded -> WorkText.REVIEW_NOT_RECORDED
        else -> WorkText.REVIEW_EMPTY
    }
    Column(modifier.fillMaxWidth().padding(top = Dim.s24).testTag("studio_review_empty")) {
        if (title.isNotEmpty()) BasicText(title, style = Abook.type.sectionTitle)
        RowHint(line, Modifier.padding(top = if (title.isEmpty()) 0.dp else Dim.s8))
    }
}

/** Một câu: vì sao cần nghe, chữ của sách, điều máy nghe ra; nút nghe; "Ổn" hay "Cần thu lại" (bấm lại lần nữa để bỏ phán quyết). */
@Composable
private fun ReviewRow(item: ReviewItem, review: StudioReviewState, clip: ClipState) {
    val spec = review.clipOf(item)
    Column(Modifier.fillMaxWidth().padding(vertical = Dim.s12).testTag("studio_review_${item.segmentId}")) {
        Row(verticalAlignment = Alignment.Top) {
            Column(Modifier.weight(1f)) {
                Caption("${WorkText.kind(item.kind)} · ${item.chapterTitle}")
                BasicText(item.text, style = Abook.type.body, modifier = Modifier.padding(top = Dim.s4).testTag("studio_review_text"))
            }
            if (spec != null) ClipButton(ReviewLogic.clipId(item), clip, { review.play(item) }, "studio_review_play")
        }
        if (item.reason.isNotEmpty()) RowHint(item.reason, Modifier.padding(top = Dim.s4))
        val heard = heardLine(item)
        if (heard.isNotEmpty()) RowHint(heard, Modifier.padding(top = Dim.s4).testTag("studio_review_heard"))
        item.pendingSpoken?.let { RowHint("Sẽ đọc là “$it”", Modifier.padding(top = Dim.s4)) }
        if (spec == null) Caption(WorkText.NO_AUDIO, Modifier.padding(top = Dim.s8))
        Spacer(Modifier.height(Dim.s8))
        SideBySide {
            AnswerButton(WorkText.OK, { review.judge(item, if (item.verdict == "ok") null else "ok") }, "studio_review_ok", Modifier.weight(1f), primary = item.verdict == "ok")
            AnswerButton(WorkText.REDO, { review.judge(item, if (item.verdict == "redo") null else "redo") }, "studio_review_redo_btn", Modifier.weight(1f), primary = item.verdict == "redo")
        }
    }
}

/** "Máy nghe ra: “...” (khớp 82%)" - nói điều máy nghe được khi nó khác chữ của sách. */
private fun heardLine(item: ReviewItem): String {
    val match = item.similarity?.let { " (${ReviewLogic.matchShort(StudioText.percent(it.toFloat()))})" }.orEmpty()
    return when {
        item.heard.isEmpty() -> if (item.kind == ReviewKind.Failed) WorkText.HEARD_NOTHING else ""
        ReviewLogic.sameText(item.heard, item.text) -> ""
        else -> "${WorkText.HEARD}: “${item.heard}”$match"
    }
}
