package vn.abook.player.ui.editbook

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicText
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
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.components.fadeEdges
import androidx.compose.foundation.lazy.rememberLazyListState

/** Bìa là chính nút đổi bìa: chạm bìa mở bảng "Chọn ảnh" / "Bỏ ảnh bìa". `sheets` là bảng trượt của cả app. */
@Composable
fun EditBookRoute(
    editor: BookEditor, covers: CoverLoader, sheets: SheetHost, onBack: () -> Unit, crop: (String) -> Unit, chapter: (Long) -> Unit,
) {
    val state by editor.state.collectAsState()
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let { crop(it.toString()) } }
    EditBookScreen(
        state, covers, onBack, editor::change,
        openCover = {
            sheets.show { dismiss ->
                CoverSheet(
                    hasCover = editor.state.value.saved?.cover != null,
                    onPick = { dismiss(); picker.launch(arrayOf("image/*")) },
                    onRemove = { dismiss(); editor.setCover(null) },
                )
            }
        },
        chapter = chapter, send = editor::send, retry = editor::retry,
    )
}

/** Bảng của bìa: chọn ảnh mới, hay bỏ ảnh đang có (hàng "Bỏ ảnh bìa" chỉ khi đang có ảnh). */
@Composable
fun CoverSheet(hasCover: Boolean, onPick: () -> Unit, onRemove: () -> Unit) {
    Column(Modifier.fillMaxWidth().testTag("cover_sheet")) {
        BasicText("Ảnh bìa", style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s8))
        MenuRow("Chọn ảnh", tag = "cover_pick", onClick = onPick) { ink -> ImageIcon(ink) }
        if (hasCover) MenuRow("Bỏ ảnh bìa", tag = "cover_remove", danger = true, onClick = onRemove) { ink -> TrashIcon(ink) }
    }
}

/**
 * Sửa sách: cùng bố cục với đầu trang sách (bìa bên trái, chữ bên phải) nhưng chữ là ô nhập. Lưu im lặng (không có chữ "Đã lưu"); chỉ khi lưu hỏng mới hiện một dòng
 * lỗi tại chỗ kèm "Thử lại". Phần sửa chờ gửi là MỘT hàng, chỉ khi có gì để gửi. Chương là danh sách hàng mở màn tên chương.
 */
@Composable
fun EditBookScreen(
    state: EditState, covers: CoverLoader, onBack: () -> Unit, change: ((EditDraft) -> EditDraft) -> Unit,
    openCover: () -> Unit, chapter: (Long) -> Unit, send: () -> Unit, retry: () -> Unit,
) {
    BookForm("Sửa sách", onBack, "edit_book_screen") {
        val book = state.saved
        val draft = state.draft
        val list = rememberLazyListState()
        LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("edit_book_list"), state = list, contentPadding = PaddingValues(bottom = Dim.s32)) {
            if (state.loading) item("loading", "state") { Caption("Đang đọc sách", Modifier.padding(top = Dim.s16)) }
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
                            BookField("Tác giả", draft.author, { value -> change { it.copy(author = value) } }, "edit_author", !state.sending)
                        }
                    }
                }
                item("problem", "problem") { InlineProblem(state.problem, retry, "edit_problem") }
                if (book.sendable && (book.pending > 0 || state.sending)) item("send", "send") {
                    Column(Modifier.padding(top = Dim.sectionGap)) {
                        ActionRow(
                            "Gửi phần sửa", if (state.sending) "Đang gửi" else "Gửi", { if (!state.sending && !state.saving) send() }, "send_edits",
                            hint = "${book.pending} thay đổi · về ${book.holder}",
                        )
                        if (book.syncNote.isNotEmpty()) Caption(book.syncNote, Modifier.testTag("sync_note"))
                        InlineProblem(state.sendProblem, send, "send_problem")
                    }
                }
                item("chapters_title", "section") { SectionTitle("Chương") }
                items(draft.chapters, key = { it.id }, contentType = { "chapter" }) { row ->
                    Column {
                        ListItem(
                            row.shown, onClick = { chapter(row.id) }, tag = "edit_chapter_${row.id}",
                            hint = if (row.renamed) "Gốc: ${row.original}" else null, hintColor = Abook.colors.text3, chevron = true,
                        )
                        RowLine()
                    }
                }
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
            .semantics { contentDescription = "Đổi ảnh bìa" }.testTag("edit_cover"),
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
