package vn.abook.player.ui.studio

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.StudioError
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.ui.components.ConfirmPage
import vn.abook.player.ui.components.DangerButton
import vn.abook.player.ui.components.ExportIcon
import vn.abook.player.ui.components.HeadphonesIcon
import vn.abook.player.ui.components.HistoryIcon
import vn.abook.player.ui.components.ImageIcon
import vn.abook.player.ui.components.IconAction
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.MoreIcon
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.ReadAlongIcon
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.StopIcon
import vn.abook.player.ui.components.TextCursorInputIcon
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.studio.parts.DecisionStrip
import vn.abook.player.ui.studio.parts.LinkBanner
import vn.abook.player.ui.studio.parts.PermissionCard
import vn.abook.player.ui.studio.parts.PollWhileVisible
import vn.abook.player.ui.studio.parts.ProgressBlock
import vn.abook.player.ui.studio.parts.ink
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/**
 * Một dự án của Studio từ xa (NATIVE_REMOTE_STUDIO.md §6.2): tên và trạng thái, MỘT nút chính theo trạng thái, tiến độ cả sách, rồi năm tab. S1 làm khung
 * và tab Chương; bốn tab còn lại là khung trống cho tới khi có nội dung (S2, S3). "Dừng" nằm sau "Thêm" và một bước xác nhận - xa nút "Tạm dừng" để
 * khỏi bấm nhầm. `listen`: mở phần Nghe (Thư viện) khi sách đã có chương nghe được.
 */
@Composable
fun StudioProjectScreen(state: StudioProjectState, sheets: SheetHost, onBack: () -> Unit, listen: () -> Unit, active: Boolean = true, openSub: (StudioSubKind) -> Unit = {}) {
    val session = state.session
    val poll by state.poll.collectAsState()
    PollWhileVisible(active, session.retries) { state.run() }
    val page = poll.data
    val book = page?.book
    val blocked = session.listenOnly || poll.error is StudioError.ListenOnly
    val kind = book?.let(StudioLogic::primaryKind)
    val canStop = book != null && book.running && !book.stopping
    val hasMore = book != null && (canStop || (book.chaptersCompleted > 0 && kind != PrimaryKind.Listen) || StudioLogic.subPages(book).isNotEmpty())
    BookForm(
        book?.title ?: StudioText.TITLE, onBack, "studio_project",
        trailing = if (hasMore && !blocked) ({
            IconAction(StudioText.MORE, { if (book != null) sheets.show { dismiss -> MoreSheet(book, kind, state, listen, openSub, dismiss) } }, "studio_more") { MoreIcon(Abook.colors.text) }
        }) else null,
    ) {
        when {
            blocked -> PermissionCard(session.name, session::retry)
            poll.error is StudioError.Gone -> GoneCard(onBack)
            page == null && poll.error == null -> BasicText(
                StudioText.LOADING, style = Abook.type.body.copy(color = Abook.colors.text2),
                modifier = Modifier.padding(top = Dim.s24).testTag("studio_loading"),
            )
            page == null -> InlineProblem(poll.error?.let { StudioText.failure(it) }.orEmpty(), state::refreshSoon, "studio_project_problem")
            else -> ProjectBody(page, kind, state, poll.error, sheets, listen, active)
        }
    }
}

/** 404: dự án đã bị chuyển hay xoá - hỏi tiếp cũng vô ích, nên chỉ còn đường về danh sách. */
@Composable
private fun GoneCard(onBack: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(top = Dim.s24).testTag("studio_gone")) {
        BasicText(StudioText.GONE_TITLE, style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s8))
        BasicText(StudioText.GONE, style = Abook.type.body.copy(color = Abook.colors.text2))
        Spacer(Modifier.height(Dim.s24))
        PrimaryButton(StudioText.BACK_TO_STUDIO, onBack, Modifier.fillMaxWidth().testTag("studio_gone_back"))
    }
}

@Composable
private fun ProjectBody(page: StudioPage, kind: PrimaryKind?, state: StudioProjectState, error: StudioError?, sheets: SheetHost, listen: () -> Unit, active: Boolean) {
    val book = page.book
    val status = StudioLogic.status(book)
    val list = rememberLazyListState()
    // Đổi tab: nội dung trượt vào từ phía tab mới (chỉ phép dịch, không mờ). Lần dựng đầu không trượt.
    val shift = remember { Animatable(0f) }
    var previous by remember { mutableStateOf(state.tab) }
    val distance = with(LocalDensity.current) { 48.dp.toPx() }
    LaunchedEffect(state.tab) {
        if (previous != state.tab) {
            shift.snapTo(if (state.tab.ordinal > previous.ordinal) distance else -distance)
            previous = state.tab
            shift.animateTo(0f, Motion.TabSlide)
        }
    }
    val slide = Modifier.graphicsLayer { translationX = shift.value }
    val retries = state.session.retries
    // Mỗi tab nội dung chỉ hỏi máy khi nó đang hiện (và màn đang ở trên cùng); đổi tab hay rời màn thì dừng tiếng, rời màn thì gửi nốt quyết định đang giữ.
    PollWhileVisible(active && state.tab == StudioTab.Work, retries) { state.work.run() }
    PollWhileVisible(active && state.tab == StudioTab.Review, retries) { state.review.run() }
    PollWhileVisible(active && state.tab == StudioTab.Cast, retries) { state.cast.run() }
    PollWhileVisible(active && state.tab == StudioTab.Music, retries) { state.music.run() }
    DisposableEffect(state.tab) { onDispose { state.stopAudio() } }
    DisposableEffect(state) { onDispose { state.leave() } }
    val reviewData = if (state.tab == StudioTab.Review) rememberReviewData(state.review) else null
    val castData = if (state.tab == StudioTab.Cast) rememberCastData(state.cast) else null
    val musicData = if (state.tab == StudioTab.Music) rememberMusicData(state.music) else null
    LaunchedEffect(musicData?.poll?.data) { musicData?.poll?.data?.let(state.music::seen) }
    LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("studio_project_list"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
        item("link", "notices") { LinkBanner(error, state.session.name, state::refreshSoon) }
        item("head", "head") {
            Column(Modifier.fillMaxWidth().testTag("studio_head")) {
                ClockLabel(status.label, Modifier.testTag("studio_status"), Abook.type.body.copy(color = status.tone.ink()))
            }
        }
        item("action", "action") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
                PrimaryAction(book, kind, state.busy, onPick = { picked -> pick(picked, book, state, sheets, listen) })
                val note = StudioText.actionNote(book, kind)
                if (note.isNotEmpty()) BasicText(note, style = Abook.type.bodySmall.copy(color = Abook.colors.text2), modifier = Modifier.padding(top = Dim.s8).testTag("studio_action_note"))
                InlineProblem(state.problem, state::retryLast, "studio_problem")
            }
        }
        item("progress", "progress") { ProgressBlock(book) }
        item("tabs", "tabs") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s24)) {
                ChoiceRow(StudioTab.entries, state.tab, { tab, _ -> state.tab = tab }, tag = "studio_tab")
                RowLine()
            }
        }
        item("undo", "undo") { DecisionStrip(state.decisions) }
        when (state.tab) {
            StudioTab.Chapters -> chapters(page.chapters, slide)
            StudioTab.Work -> item("work", "work") { WorkDeck(state, book, sheets, { state.tab = StudioTab.Review }, slide) }
            StudioTab.Review -> if (reviewData != null) reviewTab(state.review, reviewData, book, slide)
            StudioTab.Cast -> if (castData != null) castTab(state.cast, castData, state, sheets, slide)
            StudioTab.Music -> if (musicData != null) musicTab(state.music, musicData, page.chapters, sheets, slide)
        }
    }
}

/** Tab Chương: mỗi chương một hàng, thời lượng bên phải; chỉ chương LỆCH khỏi mặc định (mất file, lỗi, chờ thu lại) mới có dấu. */
private fun LazyListScope.chapters(chapters: List<StudioChapter>, slide: Modifier) {
    if (chapters.isEmpty()) {
        item("chapters_empty", "status") { ListItem(StudioText.NO_CHAPTERS, Modifier.then(slide).testTag("studio_chapters_empty")) }
        return
    }
    items(chapters, key = { "chapter_${it.id}" }, contentType = { "chapter" }) { chapter ->
        val mark = StudioLogic.chapterMark(chapter)
        Column(Modifier.fillMaxWidth().then(slide)) {
            ListItem(
                chapter.title, Modifier.testTag("studio_chapter_${chapter.id}"),
                hint = mark?.label, hintColor = mark?.tone?.ink() ?: Abook.colors.text2,
                trailing = { ClockLabel(StudioText.length(chapter.seconds), Modifier.testTag("studio_chapter_length"), Abook.type.bodySmall.copy(color = Abook.colors.text2)) },
            )
            RowLine()
        }
    }
}

/** Nút chính duy nhất; nhãn đổi theo trạng thái bằng trượt dọc (không mờ), khối mở / khép khi không còn việc để bấm. Nhạt đi khi một lệnh đang chạy hay khi chỉ là trạng thái ("Đang khởi động"). */
@Composable
private fun PrimaryAction(book: StudioBook, kind: PrimaryKind?, busy: Boolean, onPick: (PrimaryKind) -> Unit) {
    // Giữ nút cuối cùng trong lúc khối khép lại.
    var last by remember { mutableStateOf(kind) }
    if (kind != null) last = kind
    Reveal(kind != null) {
        val shown = last
        if (shown != null) AnimatedContent(
            targetState = shown,
            transitionSpec = {
                slideInVertically(tween(MotionMs.FAST, easing = Motion.Decelerate)) { it / 2 } togetherWith
                    slideOutVertically(tween(MotionMs.FAST_OUT, easing = Motion.Accelerate)) { -it / 2 }
            },
            label = "studio_primary",
        ) { target ->
            PrimaryButton(StudioText.label(target, book), { onPick(target) }, Modifier.fillMaxWidth().testTag("studio_primary"), enabled = !busy && !StudioText.inert(target))
        }
    }
}

/** Việc của nút chính: lệnh thẳng, hay một bước xác nhận khi việc đổi cả quyển sách / thu lại câu. */
private fun pick(kind: PrimaryKind, book: StudioBook, state: StudioProjectState, sheets: SheetHost, listen: () -> Unit) {
    when (kind) {
        PrimaryKind.Start, PrimaryKind.Record, PrimaryKind.Continue -> state.send(StudioCommand.Start)
        PrimaryKind.Pause -> state.send(StudioCommand.Pause(true))
        PrimaryKind.Unpause -> state.send(StudioCommand.Pause(false))
        PrimaryKind.Dequeue -> state.send(StudioCommand.Dequeue)
        PrimaryKind.Listen -> listen()
        PrimaryKind.Starting, PrimaryKind.Stopping -> Unit
        PrimaryKind.Resume -> sheets.show { dismiss ->
            ConfirmPage(StudioText.resumeTitle(), "studio_resume", StudioText.resumeLines(book), "") {
                DangerButton("Vẫn tiếp tục", { dismiss(); state.send(StudioCommand.Start) }, "studio_resume_confirm")
                QuietButton("Để sau", dismiss, "studio_resume_later")
            }
        }
        PrimaryKind.Apply -> sheets.show { dismiss ->
            ConfirmPage(StudioText.applyTitle(book), "studio_apply", listOf(StudioText.APPLY_LINE), "") {
                PrimaryButton("Áp dụng", { dismiss(); state.send(StudioCommand.Start) }, Modifier.fillMaxWidth().testTag("studio_apply_confirm"))
                QuietButton("Để sau", dismiss, "studio_apply_later")
            }
        }
    }
}

private enum class MorePage { Menu, Stop }

/** "Thêm": việc hiếm. "Dừng" mở bước xác nhận ngay trong bảng; lúc phân tích, "Tạm dừng" đứng trước nó vì tạm dừng không đổi quyển sách còn dừng thì có. */
@Composable
private fun MoreSheet(book: StudioBook, kind: PrimaryKind?, state: StudioProjectState, listen: () -> Unit, openSub: (StudioSubKind) -> Unit, dismiss: () -> Unit) {
    var page by remember { mutableStateOf(MorePage.Menu) }
    SheetPages(page, { it.ordinal }, "studio_more_sheet") { shown ->
        when (shown) {
            MorePage.Menu -> Column(Modifier.fillMaxWidth()) {
                if (book.chaptersCompleted > 0 && kind != PrimaryKind.Listen) {
                    MenuRow(StudioText.label(PrimaryKind.Listen, book), "studio_more_listen", onClick = { dismiss(); listen() }) { HeadphonesIcon(it) }
                }
                for (sub in StudioLogic.subPages(book)) {
                    MenuRow(StudioText.subLabel(sub), "studio_more_${sub.name.lowercase()}", onClick = { dismiss(); openSub(sub) }) {
                        when (sub) {
                            StudioSubKind.Precast -> CheckIcon(it)
                            StudioSubKind.Script -> ReadAlongIcon(it)
                            StudioSubKind.Readings -> TextCursorInputIcon(it)
                            StudioSubKind.Export -> ExportIcon(it)
                            StudioSubKind.Activity -> HistoryIcon(it)
                            StudioSubKind.Cover -> ImageIcon(it)
                        }
                    }
                }
                if (book.running && !book.stopping) MenuRow("Dừng", "studio_more_stop", onClick = { page = MorePage.Stop }) { StopIcon(it) }
            }
            MorePage.Stop -> ConfirmPage(StudioText.stopTitle(book), "studio_stop", StudioText.stopLines(book), "") {
                // Tạm dừng luôn là lựa chọn đầu khi đang phân tích (AGENTS.md: dừng giữa phân tích là đổi cả quyển sách).
                if (book.phase == "analysis" && book.paused == null && book.canPause) {
                    PrimaryButton("Tạm dừng", { dismiss(); state.send(StudioCommand.Pause(true)) }, Modifier.fillMaxWidth().testTag("studio_stop_pause"))
                    Spacer(Modifier.height(Dim.s8))
                }
                DangerButton(StudioText.stopConfirm(book), { dismiss(); state.send(StudioCommand.Stop) }, "studio_stop_confirm")
                QuietButton(StudioText.stopKeep(book), dismiss, "studio_stop_keep")
            }
        }
    }
}
