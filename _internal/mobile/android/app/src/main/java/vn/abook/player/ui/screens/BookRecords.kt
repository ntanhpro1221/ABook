package vn.abook.player.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import vn.abook.player.ui.components.ArrowRightLeftIcon
import vn.abook.player.ui.components.DangerButton
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.PlusIcon
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.TextCursorInputIcon
import vn.abook.player.ui.components.TrashIcon
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.data.BookNotes
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.ListenRecord
import vn.abook.player.ui.data.RecordAction
import vn.abook.player.ui.data.Records
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/*
 * Hồ sơ nghe của cuốn (listen/BookScreen.tsx RecordPicker): dữ liệu nghe độc lập với sách, app giữ liên kết - một cuốn nhiều hồ sơ (nghe lại từ đầu mà giữ lần
 * trước, mỗi người trong nhà một hồ sơ). Nhiều hồ sơ: chip "Hồ sơ nghe: <tên>" mở bảng chọn + các việc; MỘT hồ sơ: chip không hiện, các việc nằm trong bảng
 * "Thêm" và mở thẳng trang biểu mẫu của bảng này (`start`). Cuốn đang ở trình phát thì trình phát theo sang hồ sơ mới (lõi: ListeningRecords).
 */

private enum class RecordPage { Pick, Form }

/** Biểu mẫu đang mở: việc, tên đang gõ, cuốn nhận (chuyển hồ sơ). */
private class RecordForm(val action: RecordAction, val name: String, val target: ListenBook? = null)

/** Hộp "Nghe lại từ đầu" mở sẵn tên gợi ý ("Lần nghe 2"). */
private fun formFor(action: RecordAction, active: ListenRecord, count: Int): RecordForm = when (action) {
    RecordAction.Create -> RecordForm(action, Records.suggestedName(count))
    else -> RecordForm(action, active.name)
}

@Composable
fun RecordSheet(
    book: ListenBook,
    records: List<ListenRecord>,
    others: List<ListenBook>,
    source: BookSource,
    notes: BookNotes,
    start: RecordAction?,
    openBook: (String) -> Unit,
    dismiss: () -> Unit,
) {
    val active = records.firstOrNull { it.active } ?: return
    var form by remember { mutableStateOf(start?.let { formFor(it, active, records.size) }) }
    BackHandler(enabled = start == null && form != null) { form = null }
    // Lúc trang biểu mẫu trượt ra (Back), `form` đã null: giữ biểu mẫu cuối để trang đang trượt không trống.
    val last = remember { arrayOfNulls<RecordForm>(1) }
    form?.let { last[0] = it }
    SheetPages(if (form == null) RecordPage.Pick else RecordPage.Form, { it.ordinal }, "record_sheet") { page ->
        when (page) {
            RecordPage.Pick -> PickPage(book, records, active, source, notes, dismiss, onForm = { form = formFor(it, active, records.size) })
            RecordPage.Form -> (form ?: last[0])?.let { shown ->
                FormPage(
                    book, records, active, others, source, notes, shown, openBook, dismiss,
                    onChange = { form = it }, onCancel = { if (start == null) form = null else dismiss() },
                )
            }
        }
    }
}

@Composable
private fun PickPage(
    book: ListenBook, records: List<ListenRecord>, active: ListenRecord, source: BookSource, notes: BookNotes, dismiss: () -> Unit, onForm: (RecordAction) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var problem by remember { mutableStateOf("") }
    Column(Modifier.fillMaxWidth()) {
        BasicText("Hồ sơ nghe", style = Abook.type.sectionTitle)
        RowHint("Mỗi hồ sơ giữ chỗ nghe, lịch sử riêng.")
        Spacer(Modifier.height(Dim.s8))
        val list = rememberLazyListState()
        LazyColumn(Modifier.fillMaxWidth().heightIn(max = 240.dp).fadeEdges(list).testTag("record_list"), state = list) {
            items(records, key = { it.id }, contentType = { "record" }) { record ->
                PickRow(record.name, Records.lastHeard(record), record.active, {
                    if (!record.active) {
                        scope.launch {
                            val error = source.activateRecord(book.id, record.id)
                            if (error == null) {
                                dismiss()
                                notes.say(Records.switchedNote(record.name))
                            } else {
                                problem = error
                            }
                        }
                    }
                }, "record_${record.id}")
            }
        }
        ProblemLine(problem, "record_problem")
        Box(Modifier.fillMaxWidth().padding(vertical = Dim.s8).height(1.dp).background(Abook.colors.line))
        MenuRow("Hồ sơ mới", tag = "record_create", onClick = { onForm(RecordAction.Create) }) { ink -> PlusIcon(ink) }
        MenuRow("Đổi tên hồ sơ", tag = "record_rename", onClick = { onForm(RecordAction.Rename) }) { ink -> TextCursorInputIcon(ink) }
        MenuRow("Chuyển sang cuốn khác", tag = "record_move", onClick = { onForm(RecordAction.Move) }) { ink -> ArrowRightLeftIcon(ink) }
        MenuRow("Xoá hồ sơ này", tag = "record_delete", danger = true, onClick = { onForm(RecordAction.Delete) }) { ink -> TrashIcon(ink) }
    }
}

@Composable
private fun FormPage(
    book: ListenBook,
    records: List<ListenRecord>,
    active: ListenRecord,
    others: List<ListenBook>,
    source: BookSource,
    notes: BookNotes,
    form: RecordForm,
    openBook: (String) -> Unit,
    dismiss: () -> Unit,
    onChange: (RecordForm) -> Unit,
    onCancel: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var busy by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    val action = form.action
    val name = form.name.trim()
    val ready = !busy && when (action) {
        RecordAction.Rename -> name.isNotEmpty()
        RecordAction.Move -> form.target != null
        else -> true
    }
    val submit = {
        if (ready) {
            busy = true
            scope.launch {
                val target = form.target
                val error = when (action) {
                    RecordAction.Create -> source.createRecord(book.id, name)
                    RecordAction.Rename -> source.renameRecord(book.id, active.id, name)
                    RecordAction.Delete -> source.deleteRecord(book.id, active.id)
                    RecordAction.Move -> if (target != null) source.moveRecord(book.id, active.id, target.id) else null
                }
                busy = false
                if (error != null) {
                    problem = error
                } else {
                    dismiss()
                    when (action) {
                        RecordAction.Create -> notes.say(Records.createdNote(name))
                        RecordAction.Rename -> notes.say(Records.RENAMED_NOTE)
                        RecordAction.Delete -> notes.say(Records.deletedNote(active.name))
                        RecordAction.Move -> if (target != null) notes.say(Records.movedNote(active.name, target.title), "Mở cuốn ấy") { openBook(target.id) }
                    }
                }
            }
        }
    }
    Column(Modifier.fillMaxWidth().imePadding().testTag("record_form")) {
        BasicText(Records.title(action, active.name), style = Abook.type.sectionTitle)
        Records.description(action, records.size)?.let { RowHint(it) }
        Spacer(Modifier.height(Dim.s12))
        when (action) {
            RecordAction.Create, RecordAction.Rename ->
                SheetField(form.name, { onChange(RecordForm(action, it.take(Records.NAME_MAX), form.target)) }, "Tên hồ sơ", "record_name", onDone = { submit() })
            RecordAction.Move -> if (others.isEmpty()) {
                BasicText("Thư viện chưa có cuốn nào khác.", style = Abook.type.bodySmall)
            } else {
                RowHint("Chọn cuốn")
                val list = rememberLazyListState()
                LazyColumn(Modifier.fillMaxWidth().heightIn(max = 240.dp).fadeEdges(list).testTag("record_targets"), state = list) {
                    items(others, key = { it.id }, contentType = { "target" }) { other ->
                        PickRow(other.title, null, form.target?.id == other.id, { onChange(RecordForm(action, form.name, other)) }, "record_target_${other.id}")
                    }
                }
            }
            RecordAction.Delete -> Unit
        }
        ProblemLine(problem, "record_problem")
        Spacer(Modifier.height(Dim.s24))
        val label = Records.confirmLabel(action)
        if (action == RecordAction.Delete) {
            DangerButton(label, { submit() }, "record_confirm")
        } else {
            PrimaryButton(label, { submit() }, Modifier.fillMaxWidth().testTag("record_confirm"), enabled = ready)
        }
        QuietButton("Huỷ", onCancel, "record_cancel")
    }
}
