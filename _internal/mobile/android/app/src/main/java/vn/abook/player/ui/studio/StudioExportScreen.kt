package vn.abook.player.ui.studio

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import vn.abook.player.StudioError
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.ui.components.ConfirmPage
import vn.abook.player.ui.components.DangerButton
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.StageProgress
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.devices.CreepProgress
import vn.abook.player.ui.export.ExportText
import vn.abook.player.ui.studio.parts.PermissionCard
import vn.abook.player.ui.studio.parts.PollWhileVisible
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * Xuất một dự án (NATIVE_REMOTE_STUDIO.md §6.11): chọn kiểu (file sách, M4B, thư mục MP3), "Kèm nhạc nền", rồi MỘT nút "Xuất". Việc chạy trên máy tính và file nằm ở thư mục "Đã xuất"
 * của thư viện máy tính - màn nói thẳng điều đó. Tiến độ hỏi 1 giây một lần khi chạy; "Huỷ" có một bước xác nhận nhẹ.
 */
@Composable
fun StudioExportScreen(state: StudioProjectState, sheets: SheetHost, onBack: () -> Unit, active: Boolean = true) {
    val session = state.session
    val export = state.export
    val poll by state.poll.collectAsState()
    val jobs by export.poll.collectAsState()
    PollWhileVisible(active, session.retries) { state.run() }
    PollWhileVisible(active, session.retries) { export.run() }
    DisposableEffect(state) { onDispose { state.leave() } }
    val book = poll.data?.book
    val blocked = session.listenOnly || poll.error is StudioError.ListenOnly || jobs.error is StudioError.ListenOnly
    val job = export.job
    val ready = book != null && export.loaded
    BookForm(
        StudioExportText.TITLE, onBack, "studio_export",
        footer = if (ready && !blocked) ({ ExportFooter(state, sheets) }) else null,
    ) {
        when {
            blocked -> PermissionCard(session.name, session::retry)
            book == null && poll.error == null -> LoadingLine()
            book == null -> InlineProblem(poll.error?.let { StudioText.failure(it) }.orEmpty(), state::refreshSoon, "studio_export_problem")
            !export.loaded -> if (export.problem.isEmpty()) LoadingLine() else InlineProblem(export.problem, export::retry, "studio_export_problem")
            else -> ExportBody(state, book, job)
        }
    }
}

@Composable
private fun LoadingLine() {
    BasicText(StudioExportText.LOADING, style = Abook.type.body.copy(color = Abook.colors.text2), modifier = Modifier.padding(top = Dim.s24).testTag("studio_export_loading"))
}

@Composable
private fun ExportBody(state: StudioProjectState, book: StudioBook, job: StudioExportJob?) {
    val export = state.export
    val kind = export.kind
    val options = export.options
    val blocker = StudioExportLogic.blocker(kind, book)
    val list = rememberLazyListState()
    LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("studio_export_list"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
        item("head", "head") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
                BasicText(book.title, style = Abook.type.bodyStrong, modifier = Modifier.testTag("studio_export_book"))
                RowHint(StudioExportText.LEAD, Modifier.padding(top = Dim.s4).testTag("studio_export_lead"))
            }
        }
        item("kind", "kind") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
                ChoiceRow(StudioExportKind.entries, kind, { picked, _ -> export.choose(picked) }, Modifier.fillMaxWidth(), tag = "studio_export_kind")
                // Mô tả đổi theo kiểu: chữ cũ trượt đi, chữ mới trượt vào (cùng chiều với gạch chân).
                SheetPages(kind, { it.ordinal }, "studio_export_about") { shown ->
                    RowHint(StudioExportLogic.about(shown), Modifier.padding(top = Dim.s4, bottom = Dim.s8))
                }
                val size = if (kind == StudioExportKind.BookFile) StudioExportLogic.sizeNote(options) else ""
                if (size.isNotEmpty()) Caption(size, Modifier.testTag("studio_export_size"))
                if (blocker.isNotEmpty()) RowHint(blocker, Modifier.padding(top = Dim.s4).testTag("studio_export_blocker"), Abook.colors.accentText)
            }
        }
        item("music", "music") {
            Reveal(StudioExportLogic.showMusic(kind, options)) {
                Column(Modifier.fillMaxWidth()) {
                    RowLine()
                    SwitchRow(StudioExportText.MUSIC, export.musicOn, export::setMusic, "studio_export_music", hint = ExportText.MUSIC_MIX_HINT)
                }
            }
        }
        item("ffmpeg", "ffmpeg") {
            Reveal(StudioExportLogic.needsFfmpeg(kind, export.musicOn, options)) {
                Column(Modifier.fillMaxWidth().padding(top = Dim.s8).testTag("studio_export_ffmpeg")) {
                    BasicText(StudioExportText.FFMPEG_TITLE, style = Abook.type.bodyStrong)
                    RowHint(StudioExportText.FFMPEG_LINE, Modifier.padding(top = Dim.s4))
                }
            }
        }
        if (StudioExportLogic.shown(job) && job != null) item("job:${job.state}", "job") { JobBlock(state, kind, job) }
        if (options.history.isNotEmpty()) {
            item("history", "history") {
                Fold(StudioExportText.HISTORY, "studio_export_history", Modifier.padding(top = Dim.s16)) {
                    for (past in options.history) {
                        ListItem(StudioExportLogic.pastTitle(past), Modifier, null, "studio_export_past", hint = StudioExportLogic.pastLine(past))
                        RowLine()
                    }
                }
            }
        }
    }
}

/** Việc của kiểu đang chọn: đang làm (tiến độ), vừa xong (nằm ở máy nào), huỷ hay hỏng. */
@Composable
private fun JobBlock(state: StudioProjectState, kind: StudioExportKind, job: StudioExportJob) {
    val export = state.export
    Column(Modifier.fillMaxWidth().padding(top = Dim.s16).testTag("studio_export_job")) {
        when {
            job.running -> {
                val progress = StudioExportLogic.progress(kind, job)
                BasicText(StudioExportLogic.busy(kind), style = Abook.type.sectionTitle, modifier = Modifier.testTag("studio_export_busy"))
                ClockLabel(
                    progress.text, Modifier.padding(top = Dim.s8).semantics { liveRegion = LiveRegionMode.Polite; contentDescription = progress.spoken }.testTag("studio_export_progress"),
                    Abook.type.body,
                )
                val fraction = progress.fraction
                if (fraction != null) StageProgress { fraction } else CreepProgress()
                RowHint(if (export.stopping) StudioExportText.STOPPING_NOTE else StudioExportText.LEAD, Modifier.padding(top = Dim.s8).testTag("studio_export_note"))
            }
            job.state == "done" && job.result != null -> {
                val outcome = StudioExportLogic.outcome(kind, job.result, export.machine)
                BasicText(outcome.title, style = Abook.type.sectionTitle, modifier = Modifier.testTag("studio_export_done"))
                for (line in outcome.lines) RowHint(line, Modifier.padding(top = Dim.s8).testTag("studio_export_done_line"))
                for (note in outcome.notes) Caption(note, Modifier.padding(top = Dim.s4).testTag("studio_export_done_note"))
            }
            job.state == "cancelled" -> {
                BasicText(StudioExportText.STOPPED, style = Abook.type.sectionTitle, modifier = Modifier.testTag("studio_export_stopped"))
                RowHint(StudioExportLogic.stoppedNote(kind), Modifier.padding(top = Dim.s8))
            }
            job.state == "error" -> {
                BasicText(StudioExportText.failedTitle(kind), style = Abook.type.sectionTitle, modifier = Modifier.testTag("studio_export_failed"))
                if (job.error.isNotBlank()) BasicText(job.error, style = Abook.type.body.copy(color = Abook.colors.danger), modifier = Modifier.padding(top = Dim.s8).testTag("studio_export_error"))
            }
        }
    }
}

@Composable
private fun ExportFooter(state: StudioProjectState, sheets: SheetHost) {
    val export = state.export
    val job = export.job
    val book = state.poll.collectAsState().value.data?.book
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
        InlineProblem(export.problem, null, "studio_export_footer_problem")
        if (job?.running == true) {
            TextAction(
                if (export.stopping) StudioExportText.STOPPING else StudioExportText.CANCEL,
                { if (!export.stopping) sheets.show { dismiss -> CancelSheet(export, dismiss) } }, "studio_export_cancel", Modifier.fillMaxWidth(), align = Alignment.Center,
            )
        } else {
            val again = StudioExportLogic.shown(job) && job?.state != "idle"
            val ok = book != null && StudioExportLogic.canExport(export.kind, book) && !export.starting && !StudioExportLogic.needsFfmpeg(export.kind, export.musicOn, export.options)
            PrimaryButton(if (again) StudioExportText.RETRY else StudioExportText.EXPORT, export::start, Modifier.fillMaxWidth().testTag("studio_export_start"), enabled = ok)
        }
    }
}

/** Bước xác nhận nhẹ trước khi huỷ: nói điều còn lại sau khi huỷ. */
@Composable
private fun CancelSheet(export: StudioExportState, dismiss: () -> Unit) {
    ConfirmPage(StudioExportText.CANCEL_TITLE, "studio_export_cancel_sheet", listOf(StudioExportLogic.stoppedNote(export.kind)), "") {
        DangerButton(StudioExportText.CANCEL_CONFIRM, { dismiss(); export.cancel() }, "studio_export_cancel_yes")
        QuietButton(StudioExportText.CANCEL_KEEP, dismiss, "studio_export_cancel_keep")
    }
}
