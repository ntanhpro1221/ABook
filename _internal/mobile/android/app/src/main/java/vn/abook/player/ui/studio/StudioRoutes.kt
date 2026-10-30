package vn.abook.player.ui.studio

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import vn.abook.player.ui.components.SheetHost

/** Danh sách dự án của máy `computer`: trạng thái sống theo màn (mở lại màn thì hỏi lại), phiên và quyền dùng chung theo máy ([StudioHub]). */
@Composable
fun StudioHomeRoute(hub: StudioHub, computer: String, onBack: () -> Unit, onOpen: (String) -> Unit, active: Boolean) {
    val state = remember(hub, computer) { StudioHomeState(hub.session(computer)) }
    StudioHomeScreen(state, onBack, { onOpen(it.id) }, active)
}

/** Một dự án ở tab `tab`. `listen`: sang phần Nghe (Thư viện) khi sách đã có chương nghe được. */
@Composable
fun StudioProjectRoute(
    hub: StudioHub, computer: String, book: String, tab: StudioTab, sheets: SheetHost, onBack: () -> Unit, listen: () -> Unit, active: Boolean,
) {
    val state = remember(hub, computer, book) { StudioProjectState(hub.session(computer), book, tab) }
    StudioProjectScreen(state, sheets, onBack, listen, active)
}
