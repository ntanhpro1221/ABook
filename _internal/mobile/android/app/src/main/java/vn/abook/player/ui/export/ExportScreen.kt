package vn.abook.player.ui.export

import vn.abook.player.ui.components.ClockLabel
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.BatteryChargingIcon
import vn.abook.player.ui.components.BookAudioIcon
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.FolderDownIcon
import vn.abook.player.ui.components.HeadphonesIcon
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.components.ChoiceSetting
import vn.abook.player.ui.components.DisclosureRow
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.Option
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.StageProgress
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.devices.CreepProgress
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.components.fadeEdges
import androidx.compose.foundation.lazy.rememberLazyListState

/*
 * Xuất sách (MP3 hay M4B), một màn cho cả ba kiểu xuất. Màn có ba trang trượt ngang theo việc đang làm: CHỌN (dạng file, nơi lưu, nhạc) -> LÀM (tiến độ, Dừng)
 * -> KẾT QUẢ (mở, gửi, hay vì sao chưa được). Việc xuất chạy ở WorkManager nên rời màn không dừng nó; quay lại vẫn thấy đúng trang đang làm. Nút chính luôn nằm
 * ở chân màn, trong tầm ngón cái.
 */

@Composable
fun ExportScreen(book: ListenBook, exports: ExportState, onBack: () -> Unit, format: ExportFormat? = null) {
    val ui by exports.ui(book.id).collectAsState()
    val progress = exports.progress(book.id).collectAsState()
    LaunchedEffect(book.id) { exports.open(book, format) }
    // Xem kết quả rồi rời màn thì lần sau vào là tuỳ chọn mới; việc đang chạy thì sống tiếp.
    DisposableEffect(book.id) { onDispose { exports.leave(book.id) } }
    // Quay lại từ Cài đặt Android (bật chạy nền): đọc lại.
    LifecycleResumeEffect(book.id) {
        exports.refreshBackground(book.id)
        onPauseOrDispose { }
    }
    // Trang vừa rời vẫn vẽ nội dung cũ của nó trong lúc trượt đi (không trống trơn giữa chừng).
    val last = remember { arrayOfNulls<ExportPhase>(3) }
    when (val phase = ui.phase) {
        is ExportPhase.Running -> last[1] = phase
        is ExportPhase.Done, is ExportPhase.Stopped, is ExportPhase.Failed -> last[2] = phase
        else -> Unit
    }
    BookForm(
        "Xuất sách", onBack, "export_screen",
        footer = { Footer(book, ui, exports, last[1] as? ExportPhase.Running, last[2]) },
    ) {
        SheetPages(ui.phase.page, { it }, "export_pages") { page ->
            when (page) {
                0 -> OptionsPage(book, ui, exports)
                1 -> RunningPage(book, ui, progress, last[1] as? ExportPhase.Running, exports)
                else -> ResultPage(book, ui, last[2])
            }
        }
    }
}

// ---- trang chọn -----------------------------------------------------------------------------------------------------------

@Composable
private fun OptionsPage(book: ListenBook, ui: ExportUi, exports: ExportState) {
    val mp3 = !book.textOnly && ui.format == ExportFormat.Mp3
    val kind = ui.format.kind(book.textOnly)
    val list = rememberLazyListState()
    LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("export_options"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
        item("head", "head") { BookHead(book) }
        if (book.textOnly) {
            item("about", "about") { Column(Modifier.fillMaxWidth().padding(bottom = Dim.s8)) {
                    BasicText(ExportText.AUDIOBOOK_PURPOSE, style = Abook.type.bodySmall.copy(color = Abook.colors.text2))
                    BasicText(ExportText.ABOUT_AUDIOBOOK, style = Abook.type.bodySmall.copy(color = Abook.colors.text2), modifier = Modifier.padding(top = Dim.s4))
                }
            }
        } else {
            item("format", "format") {
                Column(Modifier.fillMaxWidth()) {
                    ChoiceRow(ExportFormat.entries, ui.format, { format, _ -> exports.setFormat(book.id, format) }, Modifier.fillMaxWidth(), tag = "export_format")
                    // Mô tả đổi theo dạng file: chữ cũ trượt đi, chữ mới trượt vào (cùng chiều với gạch chân).
                    SheetPages(ui.format, { it.ordinal }, "export_about") { shown ->
                        BasicText(ExportText.about(shown), style = Abook.type.bodySmall.copy(color = Abook.colors.text2), modifier = Modifier.padding(top = Dim.s4, bottom = Dim.s8))
                    }
                }
            }
        }
        item("place_mp3", "row") {
            Reveal(mp3) {
                Column(Modifier.fillMaxWidth()) {
                    RowLine()
                    DisclosureRow("Nơi lưu", { exports.chooseFolder(book.id) }, "export_folder", summary = ui.folder ?: "Chưa chọn")
                }
            }
        }
        item("place_file", "row") {
            Reveal(!mp3) {
                Column(Modifier.fillMaxWidth()) {
                    RowLine()
                    ListItem("Nơi lưu", Modifier, null, "export_place", hint = "Bạn đặt tên và chọn nơi lưu ở bước kế", titleStyle = Abook.type.bodyStrong)
                }
            }
        }
        item("scope", "row") {
            Reveal(ui.askScope) {
                Column(Modifier.fillMaxWidth()) {
                    RowLine()
                    val count = ui.changedChapters.size
                    val options = listOf(Option(true, "Chỉ $count chương đổi"), Option(false, "Cả cuốn"))
                    ChoiceSetting(
                        "Có chương đã đổi", options, options.first { it.value == ui.onlyChanged }, { picked, _ -> exports.setOnlyChanged(book.id, picked.value) }, "export_scope",
                        hint = ExportText.changedAsk(count),
                    )
                }
            }
        }
        item("music", "row") {
            Reveal(ui.music.available) {
                Column(Modifier.fillMaxWidth()) {
                    RowLine()
                    SwitchRow("Kèm nhạc nền", ui.withMusic, { exports.setMusic(book, it) }, "export_music", hint = ExportText.MUSIC_MIX_HINT)
                    Note(if (ui.musicOn && kind == ExportKind.Mp3) ExportText.MP3_MUSIC_NOTE else "", "export_mp3_music")
                    val plan = ui.plan
                    Note(ExportText.chargerHint(ui.musicOn, plan?.chapters ?: book.chaptersAvailable), "export_charger")
                    Note(if (ui.musicOn && plan != null) ExportText.rereadText(plan) else "", "export_rereads", Abook.colors.danger)
                }
            }
        }
        if (book.textOnly) item("voice", "row") { VoiceBlock(ui) }
        if (book.textOnly) item("auto_note", "row") { Note(ExportText.AUDIOBOOK_NOTE, "export_audiobook_note") }
        item("background", "row") { BackgroundRow(ui, exports) }
        if (ui.history.isNotEmpty()) {
            item("past_title", "title") { SectionTitle("Đã xuất") }
            items(ui.history, key = { "${it.kind}:${it.target}" }, contentType = { "past" }) { past ->
                Column(Modifier.fillMaxWidth()) {
                    ListItem(ExportText.pastTitle(past), Modifier, null, "export_past", hint = ExportText.pastLine(past))
                    RowLine()
                }
            }
        }
    }
}

/** Đầu trang: tên sách và sách dài bao nhiêu. */
@Composable
private fun BookHead(book: ListenBook) {
    val facts = if (book.textOnly) "${book.chaptersTotal} chương" else "${book.chaptersAvailable} chương · ${Fmt.length(book.duration)}"
    Column(Modifier.fillMaxWidth().padding(top = Dim.s8, bottom = Dim.s12)) {
        BasicText(book.title, style = Abook.type.bodyStrong, modifier = Modifier.testTag("export_book"))
        RowHint(facts, Modifier.padding(top = 2.dp))
    }
}

/** Sách chỉ có chữ: giọng đang chọn cho cuốn, dài bao nhiêu và máy cần bao lâu, phần đã có sẵn, chỗ trống cần, lời báo chữ đi đâu khi giọng trực tuyến. */
@Composable
private fun VoiceBlock(ui: ExportUi) {
    val voice = ui.voice
    val plan = ui.plan
    Column(Modifier.fillMaxWidth()) {
        RowLine()
        if (voice != null) {
            ListItem("Giọng đọc", Modifier, null, "export_voice", hint = "${voice.caption} - giọng đang chọn cho cuốn này; đổi ở trình phát.", titleStyle = Abook.type.bodyStrong)
        } else if (ui.voiceChecked) {
            BasicText(
                "Máy chưa có giọng đọc nào - tải giọng ở Cài đặt → Giọng đọc rồi quay lại.",
                style = Abook.type.bodySmall.copy(color = Abook.colors.danger), modifier = Modifier.padding(vertical = Dim.s12).testTag("export_no_voice"),
            )
        }
        Note(ui.planError, "export_plan_error", Abook.colors.danger)
        Note(
            when {
                ui.planError.isNotEmpty() -> ""
                plan != null -> ExportText.planText(plan)
                voice != null -> "Đang tính độ dài"
                else -> ""
            },
            "export_plan",
        )
        Note(plan?.let(ExportText::resumeText).orEmpty(), "export_resume")
        Note(plan?.takeIf { it.chapters > 0 }?.let(ExportText::spaceText).orEmpty(), "export_space")
        Note(voice?.let(ExportText::wholeBookNotice).orEmpty(), "export_notice")
    }
}

/** Máy hãng cho app "ngủ" ở nền: xuất dài mà tắt màn hình có thể bị tạm dừng. Hiện khi biết chắc ABook CHƯA được chạy nền; chạm mở trang cài đặt của ABook. */
@Composable
private fun BackgroundRow(ui: ExportUi, exports: ExportState) {
    val view = ui.background
    // Giữ hãng máy cuối cùng trong lúc khối khép lại.
    var shown by remember { mutableStateOf(view) }
    if (view != null) shown = view
    Reveal(view != null && !view.allowed) {
        Column(Modifier.fillMaxWidth()) {
            RowLine()
            DisclosureRow(
                "Cho ABook chạy nền", exports::openBackgroundSettings, "export_background", icon = { BatteryChargingIcon(Abook.colors.text2) },
                summary = "Xuất sách dài khi tắt màn hình có thể bị máy tạm dừng. ${ExportText.backgroundHelp(shown?.manufacturer.orEmpty())}",
            )
        }
    }
}

/** Một dòng chú thích nhỏ; có chữ thì mở ra kèm trượt, hết chữ thì khép lại (giữ chữ cuối trong lúc khép). */
@Composable
private fun Note(text: String, tag: String, color: Color = Abook.colors.text2) {
    var shown by remember { mutableStateOf(text) }
    if (text.isNotEmpty()) shown = text
    Reveal(text.isNotEmpty()) {
        BasicText(shown, style = Abook.type.caption.copy(color = color), modifier = Modifier.fillMaxWidth().padding(bottom = Dim.s8).testTag(tag))
    }
}

// ---- trang làm ------------------------------------------------------------------------------------------------------------

@Composable
private fun RunningPage(book: ListenBook, ui: ExportUi, progress: State<ExportProgress>, running: ExportPhase.Running?, exports: ExportState) {
    val kind = running?.kind ?: ui.format.kind(book.textOnly)
    val stopping = running?.stopping == true
    Column(Modifier.fillMaxSize().testTag("export_running")) {
        Spacer(Modifier.height(Dim.s24))
        BasicText(ExportText.busy(kind), style = Abook.type.sectionTitle, modifier = Modifier.testTag("export_running_title"))
        RowHint(book.title, Modifier.padding(top = Dim.s4))
        Spacer(Modifier.height(Dim.s24))
        ProgressLine(progress, running?.folder)
        Spacer(Modifier.height(Dim.s16))
        BasicText(
            if (stopping) "Dừng ở chỗ an toàn kế, chưa ghi thêm gì." else "Việc chạy nền: bạn có thể rời màn này, xuất vẫn tiếp tục.",
            style = Abook.type.caption.copy(color = Abook.colors.text2), modifier = Modifier.testTag("export_background_note"),
        )
        BackgroundRow(ui, exports)
    }
}

/** Dòng tiến độ + thanh. Chữ đọc ở lá này; thanh chỉ đọc phần đã xong trong pha vẽ. Lời cho trình đọc màn hình chỉ đổi khi đổi pha hay qua mốc 25 %. */
@Composable
internal fun ProgressLine(progress: State<ExportProgress>, folder: String?) {
    val current = progress.value
    Column(Modifier.fillMaxWidth().testTag("export_progress")) {
        ClockLabel(
            current.text, style = Abook.type.body,
            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite; contentDescription = current.spoken }.testTag("export_progress_text"),
        )
        if (folder != null) BasicText("Vào $folder", style = Abook.type.caption.copy(color = Abook.colors.text2), modifier = Modifier.padding(top = 2.dp).testTag("export_progress_folder"))
        val known by remember { derivedStateOf { progress.value.fraction != null } }
        if (known) StageProgress { progress.value.fraction ?: 0f } else CreepProgress()
    }
}

// ---- trang kết quả --------------------------------------------------------------------------------------------------------

@Composable
private fun ResultPage(book: ListenBook, ui: ExportUi, shown: ExportPhase?) {
    val colors = Abook.colors
    Column(Modifier.fillMaxSize().testTag("export_result"), verticalArrangement = Arrangement.Top) {
        Spacer(Modifier.height(Dim.s24))
        when (shown) {
            is ExportPhase.Done -> {
                Row(verticalAlignment = Alignment.Top) {
                    Column(Modifier.padding(top = 2.dp)) { CheckIcon(colors.success) }
                    Spacer(Modifier.width(Dim.s12))
                    BasicText(shown.result.title, style = Abook.type.sectionTitle, modifier = Modifier.testTag("export_result_title"))
                }
                for (line in shown.result.lines) {
                    BasicText(line, style = Abook.type.body.copy(color = colors.text2), modifier = Modifier.padding(top = Dim.s8).testTag("export_result_line"))
                }
                for (note in shown.result.notes) {
                    BasicText(note, style = Abook.type.bodySmall.copy(color = colors.text2), modifier = Modifier.padding(top = Dim.s8).testTag("export_result_note"))
                }
            }
            is ExportPhase.Stopped -> {
                BasicText(ExportText.stoppedTitle(shown.kind), style = Abook.type.sectionTitle, modifier = Modifier.testTag("export_result_title"))
                BasicText(shown.note, style = Abook.type.body.copy(color = colors.text2), modifier = Modifier.padding(top = Dim.s8).testTag("export_result_line"))
            }
            is ExportPhase.Failed -> {
                BasicText(ExportText.failedTitle(shown.kind), style = Abook.type.sectionTitle, modifier = Modifier.testTag("export_result_title"))
                BasicText(shown.message, style = Abook.type.body.copy(color = colors.danger), modifier = Modifier.padding(top = Dim.s8).testTag("export_error"))
            }
            else -> Unit
        }
    }
}

// ---- chân màn -------------------------------------------------------------------------------------------------------------

/** Nút ở chân màn đổi theo trang: Bắt đầu -> Dừng -> Mở / Gửi (hay Thử lại). Trượt cùng chiều với thân màn. */
@Composable
private fun Footer(book: ListenBook, ui: ExportUi, exports: ExportState, running: ExportPhase.Running?, shown: ExportPhase?) {
    SheetPages(ui.phase.page, { it }, "export_footer") { page ->
        Column(Modifier.fillMaxWidth()) {
            if (page != 1) InlineProblem(ui.problem, null, "export_problem")
            when (page) {
                0 -> {
                    val plan = ui.plan
                    val ready = ui.loaded && ui.phase is ExportPhase.Idle &&
                        (!book.textOnly || (ui.voice != null && plan != null && plan.chapters > 0 && ui.planError.isEmpty()))
                    PrimaryButton(
                        "Bắt đầu", { exports.start(book) }, Modifier.fillMaxWidth().testTag("export_start"), enabled = ready,
                        icon = { ink ->
                            when (ui.format.kind(book.textOnly)) {
                                ExportKind.Mp3 -> FolderDownIcon(ink)
                                ExportKind.M4b -> BookAudioIcon(ink)
                                ExportKind.Audiobook -> HeadphonesIcon(ink)
                            }
                        },
                    )
                }
                1 -> {
                    val stopping = running?.stopping == true
                    TextAction(if (stopping) "Đang dừng" else "Dừng", { exports.stop(book) }, "export_stop", Modifier.fillMaxWidth(), align = Alignment.Center)
                }
                else -> when (shown) {
                    is ExportPhase.Done -> DoneButtons(book, shown, exports)
                    is ExportPhase.Stopped -> PrimaryButton("Xuất lại", { exports.start(book) }, Modifier.fillMaxWidth().testTag("export_retry"))
                    is ExportPhase.Failed -> PrimaryButton("Thử lại", { exports.start(book) }, Modifier.fillMaxWidth().testTag("export_retry"))
                    else -> Unit
                }
            }
        }
    }
}

/** Sau khi xong: file M4B / sách nói mở được và gửi được; thư mục MP3 chỉ mở được (cả thư mục, không gửi một lần). */
@Composable
private fun DoneButtons(book: ListenBook, done: ExportPhase.Done, exports: ExportState) {
    val uri = done.result.uri ?: return
    if (done.result.kind == ExportKind.Mp3) {
        PrimaryButton("Mở thư mục", { exports.openFolder(book.id, uri, done.result.folder) }, Modifier.fillMaxWidth().testTag("export_open_folder"))
    } else {
        PrimaryButton("Mở", { exports.openFile(book.id, uri) }, Modifier.fillMaxWidth().testTag("export_open"))
        TextAction("Gửi", { exports.share(book.id, uri, book.title) }, "export_share", Modifier.fillMaxWidth(), align = Alignment.Center)
    }
}
