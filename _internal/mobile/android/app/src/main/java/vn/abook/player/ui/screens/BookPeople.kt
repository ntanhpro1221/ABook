package vn.abook.player.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import vn.abook.player.ui.components.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.GitMergeIcon
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.SearchIcon
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.TextCursorInputIcon
import vn.abook.player.ui.components.UserRoundIcon
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.BookNotes
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.Cast
import vn.abook.player.ui.data.CastMember
import vn.abook.player.ui.data.Gender
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/*
 * Việc làm với MỘT người ở tab Nhân vật: "Gộp vào người khác", "Đổi tên", "Đổi giới tính" - viết lại từ studio/CastEdits.tsx + studio/MergePeople.tsx,
 * cùng chữ. Điện thoại không có xưởng (docs/EDITING.md P2a): giới tính và gộp người chỉ ghi thành ý muốn chờ máy làm sách, đổi tên có hiệu lực ngay.
 */

private enum class PersonPage { Menu, Rename, Gender, Merge }

/** Bảng của một người ("⋯" cuối hàng): các việc, rồi từng việc là một trang trượt trong cùng bảng. */
@Composable
fun PersonSheet(
    bookId: String,
    person: CastMember,
    people: List<CastMember>,
    source: BookSource,
    notes: BookNotes,
    dismiss: () -> Unit,
) {
    var page by remember { mutableStateOf(PersonPage.Menu) }
    BackHandler(enabled = page != PersonPage.Menu) { page = PersonPage.Menu }
    val name = Cast.cleanName(person.displayName)
    SheetPages(page, { it.ordinal }, "person_sheet") { shown ->
        when (shown) {
            PersonPage.Menu -> Column(Modifier.fillMaxWidth()) {
                BasicText(name, style = Abook.type.sectionTitle)
                Spacer(Modifier.height(Dim.s8))
                if (person.lines > 0) MenuRow("Gộp vào người khác", tag = "person_merge", onClick = { page = PersonPage.Merge }) { ink -> GitMergeIcon(ink) }
                MenuRow("Đổi tên", tag = "person_rename", onClick = { page = PersonPage.Rename }) { ink -> TextCursorInputIcon(ink) }
                if (person.voice != null && person.lines > 0) {
                    MenuRow("Đổi giới tính", tag = "person_gender", onClick = { page = PersonPage.Gender }) { ink -> UserRoundIcon(ink) }
                }
            }
            PersonPage.Rename -> RenamePage(bookId, person, source, notes, dismiss, onBack = { page = PersonPage.Menu })
            PersonPage.Gender -> GenderPage(bookId, person, source, notes, dismiss, onBack = { page = PersonPage.Menu })
            PersonPage.Merge -> MergePage(bookId, person, people, source, notes, dismiss, onBack = { page = PersonPage.Menu })
        }
    }
}

/** "Chưa đổi được tên - <lý do của lõi>" (web: toast.error + description). */
private fun failure(title: String, reason: String): String = if (reason.isBlank()) title else "$title - $reason"

@Composable
private fun RenamePage(bookId: String, person: CastMember, source: BookSource, notes: BookNotes, dismiss: () -> Unit, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    val name = Cast.cleanName(person.displayName)
    var value by remember { mutableStateOf(name) }
    var busy by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    val save = { next: String ->
        if (!busy) {
            busy = true
            scope.launch {
                val done = source.renamePerson(bookId, person.name, next)
                busy = false
                val renamed = done.value
                if (renamed != null) {
                    dismiss()
                    notes.say(Cast.renamedNote(renamed.name, renamed.renamed))
                } else {
                    problem = failure("Chưa đổi được tên", done.problem.orEmpty())
                }
            }
        }
    }
    Column(Modifier.fillMaxWidth().imePadding().testTag("person_rename_page")) {
        BasicText("Đổi tên $name", style = Abook.type.sectionTitle)
        RowHint("Chỉ đổi tên hiển thị, giữ giọng và audio.")
        Spacer(Modifier.height(Dim.s12))
        SheetField(value, { value = it.take(80) }, "Tên mới của $name", "person_rename_field", onDone = { if (value.isNotBlank()) save(value) })
        person.originalName?.let { RowHint("Tên gốc: ${Cast.cleanName(it)}", Modifier.padding(top = Dim.s8)) }
        ProblemLine(problem, "person_rename_problem")
        Spacer(Modifier.height(Dim.s24))
        PrimaryButton(if (busy) "Đang lưu" else "Lưu", { if (value.isNotBlank()) save(value) }, Modifier.fillMaxWidth().testTag("person_rename_save"), enabled = value.isNotBlank() && !busy)
        if (person.originalName != null) QuietButton("Về tên gốc", { save("") }, "person_rename_original")
        QuietButton("Thôi", onBack, "person_rename_cancel")
    }
}

@Composable
private fun GenderPage(bookId: String, person: CastMember, source: BookSource, notes: BookNotes, dismiss: () -> Unit, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    val name = Cast.cleanName(person.displayName)
    val current = Cast.shownGender(person)
    var choice by remember { mutableStateOf(current) }
    var busy by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    val save = {
        val picked = choice
        if (picked != null && !busy) {
            busy = true
            scope.launch {
                val done = source.setGender(bookId, person.name, picked)
                busy = false
                val at = done.value
                if (at != null) {
                    dismiss()
                    notes.say(Cast.genderNote(name, picked), "Hoàn tác") {
                        scope.launch {
                            val problem = source.withdrawGender(bookId, person.name, at)
                            notes.say(if (problem == null) Cast.genderUndone(name) else failure("Chưa hoàn tác được", problem))
                        }
                    }
                } else {
                    problem = failure("Chưa đổi được giới tính", done.problem.orEmpty())
                }
            }
        }
    }
    Column(Modifier.fillMaxWidth().testTag("person_gender_page")) {
        BasicText("Giới tính của $name", style = Abook.type.sectionTitle)
        RowHint(Cast.genderCurrent(current))
        Spacer(Modifier.height(Dim.s8))
        for (gender in Gender.entries) {
            PickRow(gender.label, null, choice == gender, { choice = gender }, "person_gender_${gender.wire}")
        }
        Spacer(Modifier.height(Dim.s8))
        BasicText("Giọng đọc của $name chưa đổi ngay - Studio sẽ làm khi bạn mở file này ở máy có Studio.", style = Abook.type.bodySmall.copy(color = Abook.colors.text))
        ProblemLine(problem, "person_gender_problem")
        Spacer(Modifier.height(Dim.s24))
        PrimaryButton(if (busy) "Đang ghi" else "Ghi lại", { save() }, Modifier.fillMaxWidth().testTag("person_gender_save"), enabled = choice != null && choice != current && !busy)
        QuietButton("Thôi", onBack, "person_gender_cancel")
    }
}

@Composable
private fun MergePage(bookId: String, person: CastMember, people: List<CastMember>, source: BookSource, notes: BookNotes, dismiss: () -> Unit, onBack: () -> Unit) {
    val colors = Abook.colors
    val scope = rememberCoroutineScope()
    val name = Cast.cleanName(person.displayName)
    var query by remember { mutableStateOf("") }
    var into by remember { mutableStateOf<CastMember?>(null) }
    var busy by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    val others = remember(people, person, query) { Cast.mergeTargets(people, person, query) }
    val twins = remember(people) { Cast.twins(people) }
    val merge = {
        val target = into
        if (target != null && !busy) {
            busy = true
            scope.launch {
                val done = source.mergePeople(bookId, person.name, target.name)
                busy = false
                val lines = done.value
                if (lines != null) {
                    dismiss()
                    notes.say(Cast.mergedNote(lines, name, Cast.cleanName(target.displayName)))
                } else {
                    problem = failure("Chưa gộp được", done.problem.orEmpty())
                }
            }
        }
    }
    Column(Modifier.fillMaxWidth().imePadding().testTag("person_merge_page")) {
        BasicText("Gộp nhân vật", style = Abook.type.sectionTitle)
        RowHint("Mọi câu của $name và các phần sau dùng người bạn chọn.")
        Spacer(Modifier.height(Dim.s12))
        SheetField(query, { query = it }, "Tìm người trong truyện", "person_merge_search", leading = { SearchIcon(colors.text3) }, imeSearch = true)
        Spacer(Modifier.height(Dim.s8))
        if (others.isEmpty()) {
            BasicText("Không có ai khớp “$query”.", style = Abook.type.bodySmall, modifier = Modifier.padding(vertical = Dim.s12))
        } else {
            val list = rememberLazyListState()
            LazyColumn(Modifier.fillMaxWidth().heightIn(max = 256.dp).fadeEdges(list).testTag("person_merge_list"), state = list) {
                items(others, key = { it.name }, contentType = { "target" }) { other ->
                    PickRow(
                        Cast.cleanName(other.displayName), Cast.mergeTargetLine(other, Cast.nameKey(other.displayName) in twins),
                        into?.name == other.name, { into = other }, "person_merge_${other.name}",
                    )
                }
            }
        }
        val target = into
        if (target != null) {
            Spacer(Modifier.height(Dim.s8))
            BasicText(Cast.mergeSummary(person, target), style = Abook.type.bodySmall.copy(color = colors.text))
        }
        ProblemLine(problem, "person_merge_problem")
        Spacer(Modifier.height(Dim.s24))
        PrimaryButton(
            if (busy) "Đang gộp" else "Gộp", { merge() }, Modifier.fillMaxWidth().testTag("person_merge_go"), enabled = into != null && !busy,
            icon = { ink -> GitMergeIcon(ink) },
        )
        QuietButton("Thôi", onBack, "person_merge_cancel")
    }
}

/** Lỗi tại chỗ của một bảng (màu nguy hiểm), chừa chỗ khi không có. */
@Composable
internal fun ProblemLine(problem: String, tag: String) {
    if (problem.isEmpty()) return
    Spacer(Modifier.height(Dim.s8))
    BasicText(problem, style = Abook.type.bodySmall.copy(color = Abook.colors.danger), modifier = Modifier.testTag(tag))
}

/** Ô gõ chữ trong bảng: nền chìm, cao ít nhất 48; `leading` là biểu tượng đầu ô (ô tìm). Tự lấy tiêu điểm khi mở. */
@Composable
internal fun SheetField(
    value: String,
    onChange: (String) -> Unit,
    placeholder: String,
    tag: String,
    modifier: Modifier = Modifier,
    leading: (@Composable () -> Unit)? = null,
    imeSearch: Boolean = false,
    onDone: () -> Unit = {},
) {
    val colors = Abook.colors
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) {
        try {
            focus.requestFocus()
        } catch (_: IllegalStateException) {
            // Ô chưa gắn vào cây: người dùng chạm vào ô là có tiêu điểm.
        }
    }
    Row(
        modifier.fillMaxWidth().heightIn(min = Dim.s48).clip(RoundedCornerShape(Dim.radiusControl)).background(colors.bgSunken).padding(horizontal = Dim.s12),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (leading != null) {
            leading()
            Spacer(Modifier.width(Dim.s8))
        }
        BasicTextField(
            value = value,
            onValueChange = onChange,
            modifier = Modifier.weight(1f).padding(vertical = Dim.s12).focusRequester(focus).testTag(tag),
            textStyle = Abook.type.body,
            singleLine = true,
            cursorBrush = SolidColor(colors.accent),
            keyboardOptions = KeyboardOptions(imeAction = if (imeSearch) ImeAction.Search else ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { onDone() }, onSearch = { onDone() }),
            decorationBox = { inner ->
                Box(contentAlignment = Alignment.CenterStart) {
                    if (value.isEmpty()) BasicText(placeholder, style = Abook.type.body.copy(color = colors.text3))
                    inner()
                }
            },
        )
    }
}

/** Một lựa chọn trong danh sách chọn-một của bảng (web: SelectionMark): dấu chọn đầu hàng, tên, dòng phụ; hàng đang chọn chữ hổ phách. */
@Composable
internal fun PickRow(title: String, hint: String?, selected: Boolean, onClick: () -> Unit, tag: String) {
    val colors = Abook.colors
    Row(
        Modifier.fillMaxWidth().heightIn(min = Dim.s48).pressable(Role.RadioButton, onClick = onClick).semantics { this.selected = selected }.padding(vertical = Dim.s12).testTag(tag),
        verticalAlignment = Alignment.Top,
    ) {
        Box(Modifier.size(Dim.s24, 24.dp), contentAlignment = Alignment.CenterStart) {
            if (selected) CheckIcon(colors.accentText)
        }
        Spacer(Modifier.width(Dim.s12))
        Column(Modifier.weight(1f)) {
            BasicText(
                title,
                style = Abook.type.body.copy(color = if (selected) colors.accentText else colors.text, fontWeight = if (selected) FontWeight.Medium else FontWeight.Normal),
            )
            if (hint != null) RowHint(hint, Modifier.padding(top = 2.dp), if (selected) colors.accentText else colors.text2)
        }
    }
}
