package vn.abook.player.ui.studio

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import vn.abook.player.readaloud.WebSocket
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.editbook.BookEditor
import vn.abook.player.ui.export.DrawnCover

/** Danh sách dự án của máy `computer`: trạng thái sống theo màn (mở lại màn thì hỏi lại), phiên và quyền dùng chung theo máy ([StudioHub]). */
@Composable
fun StudioHomeRoute(hub: StudioHub, computer: String, onBack: () -> Unit, onOpen: (String) -> Unit, active: Boolean, onNew: (() -> Unit)? = null) {
    val state = remember(hub, computer) { StudioHomeState(hub.session(computer)) }
    StudioHomeScreen(state, onBack, { onOpen(it.id) }, active, onNew)
}

/** Một dự án ở tab `tab`. `listen`: sang phần Nghe (Thư viện) khi sách đã có chương nghe được. */
@Composable
fun StudioProjectRoute(
    hub: StudioHub, computer: String, book: String, tab: StudioTab, sheets: SheetHost, onBack: () -> Unit, listen: () -> Unit, active: Boolean,
    openSub: (StudioSubKind) -> Unit = {},
) {
    val state = remember(hub, computer, book) { StudioProjectState(hub.session(computer), book, tab) }
    StudioProjectScreen(state, sheets, onBack, listen, active, openSub)
}

/** Một màn con của dự án: "Duyệt trước khi thu" (dùng chính trạng thái dự án), "Kịch bản", "Cách đọc tên", "Xuất sách", "Ảnh bìa" hay "Nhật ký". `openSub`: sang màn con khác (duyệt -> cách đọc tên). */
@Composable
fun StudioSubRoute(
    hub: StudioHub, computer: String, book: String, kind: StudioSubKind, sheets: SheetHost, onBack: () -> Unit, openSub: (StudioSubKind) -> Unit, active: Boolean,
) {
    when (kind) {
        StudioSubKind.Precast -> {
            val state = remember(hub, computer, book) { StudioProjectState(hub.session(computer), book, StudioTab.Chapters) }
            PrecastScreen(state, sheets, onBack, { openSub(StudioSubKind.Readings) }, active)
        }
        StudioSubKind.Script -> {
            val state = remember(hub, computer, book) { StudioScriptState(hub.session(computer), book) }
            ScriptScreen(state, sheets, onBack, active)
        }
        StudioSubKind.Readings -> {
            val state = remember(hub, computer, book) { StudioReadingsState(hub.session(computer), book) }
            ReadingsScreen(state, onBack, active)
        }
        StudioSubKind.Export -> {
            val state = remember(hub, computer, book) {
                StudioProjectState(hub.session(computer), book, StudioTab.Chapters).also { it.export.drawCover = ::drawnCover }
            }
            StudioExportScreen(state, sheets, onBack, active)
        }
        StudioSubKind.Activity -> {
            val state = remember(hub, computer, book) { StudioProjectState(hub.session(computer), book, StudioTab.Chapters) }
            StudioActivityScreen(state, onBack, active)
        }
        StudioSubKind.Cover -> {
            val session = hub.session(computer)
            val editor = remember(hub, computer, book) { BookEditor(book, StudioCoverSource(session), session.scope) }
            val saved by editor.state.collectAsState()
            StudioCoverRoute(editor, saved.saved?.title.orEmpty(), onBack, active)
        }
    }
}

/** Bìa vẽ từ tên sách cho M4B / MP3 (data URL PNG); vẽ hỏng thì không gửi bìa, máy tính tự chọn. */
private fun drawnCover(title: String): String =
    runCatching { "data:image/png;base64," + WebSocket.base64(DrawnCover.png(title)) }.getOrDefault("")
