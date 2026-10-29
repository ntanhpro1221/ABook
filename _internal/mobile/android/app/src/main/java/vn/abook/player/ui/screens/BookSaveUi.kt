package vn.abook.player.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.components.ExportIcon
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.data.BookDetail
import vn.abook.player.ui.data.BookNotes
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.data.SaveStep
import vn.abook.player.ui.data.SaveText
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Loại file của "Lưu thành" (web: EditBook.tsx SaveAsDialog). */
enum class SaveKind(override val key: String, override val label: String, val project: Boolean) : Choice {
    Book("abook", "Sách nghe (.abook)", false),
    Project("abookproj", "Dự án (.abookproj)", true),
}

/**
 * Một lần lưu đang diễn ra của bảng "Thêm": đi qua [BookSource] (chỗ nhớ -> ghi; chưa có chỗ -> hộp "tạo file" của hệ thống -> ghi). `busy` đúng lúc đang ghi hay đang chờ
 * hộp chọn chỗ; `problem` là câu lỗi cuối (rỗng khi chưa có). Xong thì lời báo ở trang sách ([notes]) và bảng đóng ([done]).
 */
@Stable
class BookSaveRun(
    private val bookId: String,
    private val source: BookSource,
    private val scope: CoroutineScope,
    private val notes: BookNotes?,
    private val done: () -> Unit,
) {
    var busy by mutableStateOf(false)
        private set
    var problem by mutableStateOf("")
        private set
    internal var launch: (android.content.Intent) -> Unit = {}
    private var kind: SaveKind? = null

    /** "Lưu thay đổi": ghi thẳng vào chỗ đã nhớ, chưa có thì hỏi chỗ lưu. */
    fun saveKept() {
        if (busy) return
        busy = true
        problem = ""
        kind = null
        scope.launch { handle(source.saveKept(bookId)) }
    }

    /** "Lưu thành": luôn hỏi chỗ lưu, đúng loại file đã chọn. */
    fun saveAs(choice: SaveKind) {
        if (busy) return
        busy = true
        problem = ""
        kind = choice
        scope.launch {
            val intent = source.saveAsIntent(bookId, choice.project)
            if (intent == null) fail("") else launch(intent)
        }
    }

    /** Hộp chọn chỗ lưu trả về: `uri` null = đóng hộp mà không chọn (không lỗi). */
    internal fun picked(uri: android.net.Uri?) {
        if (uri == null) {
            busy = false
            return
        }
        scope.launch { handle(source.saveTo(bookId, kind?.project, uri)) }
    }

    private fun handle(step: SaveStep) {
        when (step) {
            is SaveStep.Done -> {
                busy = false
                notes?.say(SaveText.done(step.edits))
                done()
            }
            is SaveStep.Ask -> launch(step.intent)
            is SaveStep.Failed -> fail(step.message)
        }
    }

    private fun fail(message: String) {
        busy = false
        problem = SaveText.failed(message)
    }
}

@Composable
fun rememberBookSave(bookId: String, source: BookSource, notes: BookNotes?, done: () -> Unit): BookSaveRun {
    val scope = rememberCoroutineScope()
    val finished = rememberUpdatedState(done)
    val run = remember(bookId, source) { BookSaveRun(bookId, source, scope, notes) { finished.value() } }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { run.picked(it.data?.data) }
    run.launch = { picker.launch(it) }
    return run
}

/** Trang "Lưu thành" của bảng Thêm: chọn loại file, một dòng nói file mang theo gì, nút Lưu mở hộp chọn chỗ của hệ thống. */
@Composable
fun SaveAsPage(detail: BookDetail, run: BookSaveRun) {
    var kind by remember(detail.book.id) { mutableStateOf(if (detail.workshop != null) SaveKind.Project else SaveKind.Book) }
    Column(Modifier.fillMaxWidth().testTag("save_as_page")) {
        BasicText("Lưu thành", style = Abook.type.sectionTitle)
        RowHint("Lưu cuốn này kèm những thay đổi của bạn thành một file mới. File gốc không bị đụng tới.")
        Spacer(Modifier.height(Dim.s8))
        BasicText("Loại file", style = Abook.type.caption.copy(color = Abook.colors.text2))
        ChoiceRow(SaveKind.entries, kind, { picked, _ -> kind = picked }, tag = "save_kind")
        BasicText(
            SaveText.kindNote(kind.project, detail.workshop, detail.wishes),
            style = Abook.type.bodySmall.copy(color = Abook.colors.text2), modifier = Modifier.padding(vertical = Dim.s8).testTag("save_kind_note"),
        )
        PrimaryButton(if (run.busy) "Đang lưu" else "Lưu", { run.saveAs(kind) }, Modifier.fillMaxWidth().testTag("save_as_go"), enabled = !run.busy) { ink -> ExportIcon(ink) }
        if (run.problem.isNotEmpty()) {
            BasicText(run.problem, style = Abook.type.bodySmall.copy(color = Abook.colors.danger), modifier = Modifier.padding(top = Dim.s8).testTag("save_problem"))
        }
    }
}
