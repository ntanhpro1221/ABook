package vn.abook.player.ui.editbook

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.addbook.BookAction
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.addbook.BookProblem
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

@Composable
fun EditBookRoute(editor: BookEditor, covers: CoverLoader, onBack: () -> Unit, crop: (String) -> Unit, chapter: (Long) -> Unit) {
    val state by editor.state.collectAsState()
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let { crop(it.toString()) } }
    EditBookScreen(state, covers, onBack, editor::change, { picker.launch(arrayOf("image/*")) },
        { editor.setCover(null) }, chapter, editor::send, editor::retry)
}

@Composable
fun EditBookScreen(
    state: EditState, covers: CoverLoader, onBack: () -> Unit, change: ((EditDraft) -> EditDraft) -> Unit,
    pickCover: () -> Unit, removeCover: () -> Unit, chapter: (Long) -> Unit, send: () -> Unit, retry: () -> Unit,
) {
    BookForm("Sửa sách", onBack, "edit_book_screen") {
        val book = state.saved
        val draft = state.draft
        LazyColumn(Modifier.fillMaxSize().testTag("edit_book_list"), verticalArrangement = Arrangement.spacedBy(Dim.s16)) {
            item("state", "state") {
                Column {
                    BasicText(when { state.loading -> "Đang đọc sách"; state.saving -> "Đang lưu"; else -> state.note }, style = Abook.type.bodySmall)
                    BookProblem(state.problem)
                    if (state.problem.isNotEmpty()) BookAction("Thử lại", retry, Modifier.testTag("retry_edit"))
                }
            }
            if (book != null && draft != null) {
                item("fields", "fields") {
                    Column {
                        BookField("Tên sách", draft.title, { value -> change { it.copy(title = value) } }, "edit_title", !state.sending)
                        BookField("Tác giả", draft.author, { value -> change { it.copy(author = value) } }, "edit_author", !state.sending)
                        BasicText("Bạn sửa là tự lưu trên máy này.", style = Abook.type.bodySmall)
                    }
                }
                item("cover", "cover") {
                    Column {
                        BasicText("Ảnh bìa", style = Abook.type.sectionTitle)
                        Spacer(Modifier.height(Dim.s12))
                        BookCover(book.cover, draft.title, null, covers, 104.dp, Modifier.width(104.dp))
                        BookAction("Chọn ảnh bìa", pickCover, Modifier.testTag("pick_cover"), !state.saving && !state.sending)
                        if (book.cover != null) BookAction("Bỏ ảnh bìa", removeCover, enabled = !state.saving && !state.sending)
                    }
                }
                item("send", "send") {
                    Column {
                        BasicText(if (book.sendable) "${book.pending} thay đổi chờ gửi" else "Phần sửa trên máy", style = Abook.type.sectionTitle)
                        BasicText(if (book.sendable) "Tự gửi về ${book.holder} khi kết nối." else "Cuốn này giữ phần sửa trên máy bạn.", style = Abook.type.bodySmall)
                        if (book.syncNote.isNotEmpty()) BasicText(book.syncNote, style = Abook.type.bodySmall)
                        if (book.sendable) BookAction(if (state.sending) "Đang gửi" else "Gửi phần sửa", send,
                            Modifier.testTag("send_edits"), book.pending > 0 && !state.sending && !state.saving)
                    }
                }
                item("chapters", "heading") { BasicText("Tên chương", style = Abook.type.sectionTitle) }
                items(draft.chapters, key = { it.id }, contentType = { "chapter" }) { row ->
                    BookAction(row.shown, { chapter(row.id) }, Modifier.fillMaxWidth().testTag("edit_chapter_${row.id}"), !state.sending)
                }
            }
            item("end", "space") { Spacer(Modifier.height(Dim.s24)) }
        }
    }
}

@Composable
fun EditChapterRoute(editor: BookEditor, chapterId: Long, onBack: () -> Unit) {
    val state by editor.state.collectAsState()
    val row = state.draft?.chapters?.firstOrNull { it.id == chapterId }
    BookForm("Tên chương", onBack, "edit_chapter_screen") {
        LazyColumn(Modifier.fillMaxSize()) {
            item("fields", "fields") {
                if (row != null) Column {
                    BookField(if (state.saved?.textOnly == true) "Tên chương" else "Nhãn chương", row.title, { value ->
                        editor.change { it.copy(chapters = it.chapters.map { chapter -> if (chapter.id == chapterId) chapter.copy(title = value) else chapter }) }
                    }, "chapter_title")
                    if (state.saved?.textOnly != true) BookField("Tên chương", row.subtitle, { value ->
                        editor.change { it.copy(chapters = it.chapters.map { chapter -> if (chapter.id == chapterId) chapter.copy(subtitle = value) else chapter }) }
                    }, "chapter_subtitle")
                    BasicText(state.note, style = Abook.type.bodySmall)
                    BookProblem(state.problem)
                    if (state.problem.isNotEmpty()) BookAction("Thử lại", editor::retry)
                    BookAction("Về tên gốc", { editor.revertChapter(chapterId) }, enabled = !state.saving)
                }
            }
        }
    }
}
