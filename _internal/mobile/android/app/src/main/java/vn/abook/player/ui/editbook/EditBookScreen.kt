package vn.abook.player.ui.editbook

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.addbook.RevertName
import vn.abook.player.ui.components.ActionRow
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ConfirmPage
import vn.abook.player.ui.components.DangerButton
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.GlobeIcon
import vn.abook.player.ui.components.IconAction
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.ImageIcon
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.PencilIcon
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.TrashIcon
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.motion.rememberPresence
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs
import vn.abook.player.ui.components.fadeEdges
import androidx.compose.foundation.lazy.rememberLazyListState

/**
 * Bìa là chính nút đổi bìa: chạm bìa mở bảng "Chọn ảnh" / "Tìm bìa" / "Bỏ ảnh bìa". `sheets` là bảng trượt của cả app; `findCover` mở màn "Tìm ảnh bìa".
 */
@Composable
fun EditBookRoute(
    editor: BookEditor, covers: CoverLoader, sheets: SheetHost, onBack: () -> Unit, crop: (String) -> Unit, chapter: (Long) -> Unit,
    findCover: () -> Unit = {},
) {
    val state by editor.state.collectAsState()
    val readings by editor.readings.collectAsState()
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let { crop(it.toString()) } }
    EditBookScreen(
        state, covers, onBack, editor::change,
        openCover = {
            sheets.show { dismiss ->
                CoverSheet(
                    hasCover = editor.state.value.saved?.cover != null,
                    onPick = { dismiss(); picker.launch(arrayOf("image/*")) },
                    onRemove = { dismiss(); editor.setCover(null) },
                    onFind = { dismiss(); findCover() },
                )
            }
        },
        chapter = chapter, send = editor::send, retry = editor::retry,
        readings = readings, loadReadings = editor::loadReadings, setReading = editor::setReading,
        discard = { sheets.show { dismiss -> DiscardSheet(editor::discardAll, dismiss) } },
    )
}

/** Bảng của bìa: chọn ảnh trên máy, tìm bìa trên mạng (màn riêng), hay bỏ ảnh đang có (hàng "Bỏ ảnh bìa" chỉ khi đang có ảnh). */
@Composable
fun CoverSheet(hasCover: Boolean, onPick: () -> Unit, onRemove: () -> Unit, onFind: () -> Unit = {}) {
    Column(Modifier.fillMaxWidth().testTag("cover_sheet")) {
        BasicText("Ảnh bìa", style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s8))
        MenuRow("Chọn ảnh", tag = "cover_pick", onClick = onPick) { ink -> ImageIcon(ink) }
        MenuRow("Tìm bìa", tag = "cover_find", onClick = onFind) { ink -> GlobeIcon(ink) }
        if (hasCover) MenuRow("Bỏ ảnh bìa", tag = "cover_remove", danger = true, onClick = onRemove) { ink -> TrashIcon(ink) }
    }
}

/**
 * Bước hỏi trước "Bỏ mọi thay đổi" (cùng bước xác nhận với xoá khỏi máy): nói sách trở về thế nào, nút đỏ "Bỏ hết thay đổi", nút chữ "Thôi". Chưa bỏ được thì câu lỗi
 * ngay trong bảng, bảng ở nguyên. Việc chạy ở phạm vi của trình sửa: đóng bảng giữa chừng không cắt ngang một lần ghi.
 */
@Composable
fun DiscardSheet(discardAll: ((String?) -> Unit) -> Unit, dismiss: () -> Unit) {
    var working by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    ConfirmPage("Bỏ mọi thay đổi", "discard_confirm", listOf(ReadingText.DISCARD_HINT), problem) {
        DangerButton("Bỏ hết thay đổi", {
            if (working) return@DangerButton
            working = true
            problem = ""
            discardAll { error ->
                working = false
                problem = error.orEmpty()
                if (error == null) dismiss()
            }
        }, "discard_yes")
        Spacer(Modifier.height(Dim.s8))
        QuietButton("Thôi", dismiss, "discard_keep")
    }
}

/**
 * Sửa sách: cùng bố cục với đầu trang sách (bìa bên trái, chữ bên phải) nhưng chữ là ô nhập. Lưu im lặng (không có chữ "Đã lưu"); chỉ khi lưu hỏng mới hiện một dòng
 * lỗi tại chỗ kèm "Thử lại". Phần sửa chờ gửi là MỘT hàng, chỉ khi có gì để gửi - cùng chữ với dòng tình trạng "Gửi về máy tính" của web (SendEdits.tsx,
 * shared/editsSync.ts). Chương là danh sách hàng mở màn tên chương.
 */
@Composable
fun EditBookScreen(
    state: EditState, covers: CoverLoader, onBack: () -> Unit, change: ((EditDraft) -> EditDraft) -> Unit,
    openCover: () -> Unit, chapter: (Long) -> Unit, send: () -> Unit, retry: () -> Unit,
    readings: ReadingsUi = ReadingsUi(), loadReadings: () -> Unit = {}, setReading: (String, String, () -> Unit) -> Unit = { _, _, _ -> },
    discard: () -> Unit = {},
) {
    BookForm("Sửa sách", onBack, "edit_book_screen") {
        val book = state.saved
        val draft = state.draft
        val list = rememberLazyListState()
        LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("edit_book_list"), state = list, contentPadding = PaddingValues(bottom = Dim.s32)) {
            if (state.loading) item("loading", "state") { Caption("Đang đọc", Modifier.padding(top = Dim.s16)) }
            if (book == null || draft == null) {
                if (!state.loading) item("failed", "state") { InlineProblem(state.problem, retry, "edit_problem", Modifier.padding(top = Dim.s16)) }
            } else {
                item("head", "head") {
                    Row(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
                        CoverButton(book, draft, covers, openCover, enabled = !state.saving && !state.sending)
                        Spacer(Modifier.width(Dim.s16))
                        Column(Modifier.weight(1f)) {
                            BookField("Tên sách", draft.title, { value -> change { it.copy(title = value) } }, "edit_title", !state.sending)
                            Spacer(Modifier.height(Dim.s16))
                            BookField("Tác giả", draft.author, { value -> change { it.copy(author = value) } }, "edit_author", !state.sending,
                                placeholder = "Không rõ tác giả")
                        }
                    }
                }
                item("problem", "problem") { InlineProblem(state.problem, retry, "edit_problem") }
                item("notice", "notice") { Reveal(state.notice.isNotBlank()) { Caption(state.notice) } }
                if (book.sendable && (book.pending > 0 || state.sending)) item("send", "send") {
                    Column(Modifier.padding(top = Dim.sectionGap)) {
                        ActionRow(
                            "${book.pending} thay đổi đang chờ gửi về ${book.holder}", if (state.sending) "Đang gửi" else "Gửi về ${book.holder}",
                            { if (!state.sending && !state.saving) send() }, "send_edits",
                            hint = "Tự gửi khi tới được ${book.holder}; bấm “Gửi về ${book.holder}” để gửi ngay.",
                        )
                        if (book.syncNote.isNotEmpty()) Caption(book.syncNote, Modifier.testTag("sync_note"))
                        InlineProblem(state.sendProblem, send, "send_problem")
                    }
                }
                if (book.sendable && book.pending == 0 && book.syncNote.isNotBlank()) item("sent", "sent") { Caption(book.syncNote) }
                item("chapters_title", "section") { SectionTitle("Chương") }
                items(draft.chapters, key = { it.id }, contentType = { "chapter" }) { row ->
                    Column {
                        ListItem(
                            row.shown, onClick = { chapter(row.id) }, tag = "edit_chapter_${row.id}",
                            hint = if (row.renamed) "Tên gốc: ${row.original}" else null, hintColor = Abook.colors.text3, chevron = true,
                        )
                        RowLine()
                    }
                }
                // Sách chỉ có chữ: các từ đã dạy giọng đọc (web: "Cách đọc tên" gập trong Sửa sách).
                if (book.textOnly) item("readings", "readings") {
                    Fold("Cách đọc tên", "edit_readings", Modifier.padding(top = Dim.sectionGap)) {
                        ReadingsSection(readings, loadReadings, setReading)
                    }
                }
                item("discard", "discard") { DiscardRow(book.edits, discard) }
            }
        }
    }
}

/**
 * Bìa 112 rộng làm nút: chạm là đổi bìa. Dấu bút nhỏ nói rằng nó chạm được; nó đậu ở góc dưới phải và nhô ra ngoài 8 để không đè lên tên sách in trên bìa
 * (bìa chưa có ảnh vẽ tên sách tới sát đáy), viền màu nền để nó đọc như một huy hiệu chứ không như nét vẽ của bìa.
 */
@Composable
private fun CoverButton(book: EditSnapshot, draft: EditDraft, covers: CoverLoader, onClick: () -> Unit, enabled: Boolean) {
    val colors = Abook.colors
    Box(
        Modifier.width(112.dp + Dim.s8).then(if (enabled) Modifier.pressable(onClick = onClick) else Modifier)
            .semantics { contentDescription = if (book.cover == null) "Chọn ảnh bìa" else "Đổi ảnh bìa" }.testTag("edit_cover"),
    ) {
        BookCover(book.cover, draft.title, null, covers, 112.dp, Modifier.width(112.dp).padding(bottom = Dim.s8))
        Box(
            Modifier.align(Alignment.BottomEnd).size(36.dp).clip(CircleShape).background(colors.bg).padding(3.dp).clip(CircleShape).background(colors.panel),
            contentAlignment = Alignment.Center,
        ) { PencilIcon(colors.text, size = 18.dp) }
    }
}

@Composable
fun EditChapterRoute(editor: BookEditor, chapterId: Long, onBack: () -> Unit) {
    val state by editor.state.collectAsState()
    val row = state.draft?.chapters?.firstOrNull { it.id == chapterId }
    BookForm("Tên chương", onBack, "edit_chapter_screen") {
        if (row != null) Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
            val textOnly = state.saved?.textOnly == true
            // Sách chữ: một tên. Sách nói: nhãn ("Chương 3") và tên riêng.
            BookField(if (textOnly) null else "Nhãn", row.title, { value ->
                editor.change { it.copy(chapters = it.chapters.map { chapter -> if (chapter.id == chapterId) chapter.copy(title = value) else chapter }) }
            }, "chapter_title", description = if (textOnly) "Tên chương" else "Nhãn")
            if (!textOnly) {
                Spacer(Modifier.height(Dim.s16))
                BookField("Tên", row.subtitle, { value ->
                    editor.change { it.copy(chapters = it.chapters.map { chapter -> if (chapter.id == chapterId) chapter.copy(subtitle = value) else chapter }) }
                }, "chapter_subtitle")
            }
            InlineProblem(state.problem, editor::retry, "chapter_problem")
            if (row.renamed) {
                Spacer(Modifier.height(Dim.s16))
                RevertName(row.original, { editor.revertChapter(chapterId) })
            }
        }
    }
}

/** "Bỏ mọi thay đổi (N)": cả hàng mở bước hỏi; chỉ có khi người nghe đã đổi gì đó. Số giữ lại trong lúc hàng khép (sau khi bỏ). */
@Composable
private fun DiscardRow(edits: Int, discard: () -> Unit) {
    val last = remember { intArrayOf(0) }
    if (edits > 0) last[0] = edits
    Reveal(edits > 0) {
        Column(Modifier.fillMaxWidth().padding(top = Dim.sectionGap)) {
            ListItem(
                "Bỏ mọi thay đổi (${last[0]})", Modifier, discard, "discard_edits", hint = ReadingText.DISCARD_HINT,
                titleColor = Abook.colors.danger,
            )
        }
    }
}

/**
 * Bên trong phần "Cách đọc tên": mỗi từ một hàng (chữ trong sách, "đọc là …", nút sửa / bỏ); sửa mở ô ngay dưới hàng ấy. Mở phần là đọc lại danh sách. Chưa có từ nào thì
 * nói đúng thế - giao diện native chưa có chạm giữ một chữ ở màn đọc để dạy, nên không chỉ cách ấy.
 */
@Composable
private fun ReadingsSection(ui: ReadingsUi, load: () -> Unit, setReading: (String, String, () -> Unit) -> Unit) {
    LaunchedEffect(Unit) { load() }
    var editing by remember { mutableStateOf<String?>(null) }
    val rows = rememberPresence(ui.list) { it.surface }
    val stage = when {
        !ui.loaded && ui.problem.isNotEmpty() -> ReadingsStage.Failed
        !ui.loaded -> ReadingsStage.Loading
        ui.list.isEmpty() && rows.isEmpty() -> ReadingsStage.Empty
        else -> ReadingsStage.Words
    }
    Column(Modifier.fillMaxWidth().testTag("readings_section")) {
        RowHint(ReadingText.HINT)
        // Đang tải -> danh sách (hay lời "chưa có"): trượt ngắn, không thay cứng; trong danh sách, từ thêm / bỏ mở / khép tại chỗ.
        AnimatedContent(
            targetState = stage,
            transitionSpec = {
                (slideInVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it / 8 } + fadeIn(tween(MotionMs.MEDIUM)))
                    .togetherWith(slideOutVertically(tween(MotionMs.FAST_OUT, easing = Motion.Accelerate)) { -it / 8 } + fadeOut(tween(MotionMs.FAST_OUT)))
                    .using(SizeTransform(clip = false))
            },
            label = "readings",
        ) { shown ->
            when (shown) {
                ReadingsStage.Failed -> InlineProblem(ui.problem, load, "readings_problem")
                ReadingsStage.Loading -> Caption("Đang tải cách đọc", Modifier.padding(top = Dim.s12).testTag("readings_loading"))
                ReadingsStage.Empty -> Caption("Chưa có từ nào.", Modifier.padding(top = Dim.s12).testTag("readings_empty"))
                ReadingsStage.Words -> Column(Modifier.fillMaxWidth()) {
                    for (row in rows) key(row.item.surface) {
                        AnimatedVisibility(
                            row.visible,
                            enter = expandVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) + slideInVertically(tween(MotionMs.MEDIUM)) { -it / 4 },
                            exit = shrinkVertically(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) + slideOutVertically(tween(MotionMs.MEDIUM_OUT)) { -it / 4 },
                        ) {
                            val item = row.item
                            Column(Modifier.fillMaxWidth()) {
                                ReadingRow(item, editing == item.surface, ui.saving, onEdit = { editing = if (editing == item.surface) null else item.surface },
                                    onRemove = { setReading(item.surface, "") {} }, onSave = { spoken -> setReading(item.surface, spoken) { editing = null } })
                                RowLine()
                            }
                        }
                    }
                }
            }
        }
        InlineProblem(ui.failed, tag = "readings_failed")
        Reveal(ui.notice.isNotEmpty()) { Caption(ui.notice, Modifier.padding(top = Dim.s8).testTag("readings_notice")) }
    }
}

private enum class ReadingsStage { Failed, Loading, Empty, Words }

/** Một từ đã dạy: tên là chữ trong sách, dòng phụ là cách đọc; cuối hàng "Sửa" (bút) và "Bỏ" (thùng rác). Ô sửa mở / khép ngay dưới. */
@Composable
private fun ReadingRow(item: WordReading, editing: Boolean, saving: Boolean, onEdit: () -> Unit, onRemove: () -> Unit, onSave: (String) -> Unit) {
    val colors = Abook.colors
    Column(Modifier.fillMaxWidth().testTag("reading_${item.surface}")) {
        ListItem(
            item.surface, hint = "đọc là “${item.spoken}”", titleStyle = Abook.type.bodyStrong,
            trailing = {
                Row {
                    IconAction("Sửa cách đọc ${item.surface}", onEdit, "reading_edit_${item.surface}") { PencilIcon(colors.text2) }
                    IconAction("Bỏ cách đọc ${item.surface}", { if (!saving) onRemove() }, "reading_remove_${item.surface}") { TrashIcon(colors.text2) }
                }
            },
        )
        Reveal(editing) { ReadingForm(item.surface, item.spoken, saving, onSave) }
    }
}

/** Ô cách đọc của một từ (web: ReadingForm): "“X” đọc là", ô gõ, "Lưu cho cả cuốn", và "Đọc như trong sách" khi từ đã có cách đọc riêng. */
@Composable
private fun ReadingForm(surface: String, current: String, saving: Boolean, onSave: (String) -> Unit) {
    var value by remember(surface, current) { mutableStateOf(current) }
    Column(Modifier.fillMaxWidth().padding(bottom = Dim.s16).testTag("reading_form")) {
        RowHint("“$surface” đọc là", Modifier.padding(bottom = Dim.s8))
        BookField(null, value, { value = it }, "reading_field", !saving, description = "Cách đọc cho $surface", placeholder = "vd Ha-ru-tô")
        Spacer(Modifier.height(Dim.s12))
        PrimaryButton("Lưu cho cả cuốn", { onSave(value) }, Modifier.fillMaxWidth().testTag("reading_save"),
            enabled = !saving && ReadingText.canSave(surface, current, value))
        if (current.isNotEmpty()) TextAction("Đọc như trong sách", { if (!saving) onSave("") }, "reading_plain", Modifier.fillMaxWidth(), align = Alignment.Center)
    }
}
