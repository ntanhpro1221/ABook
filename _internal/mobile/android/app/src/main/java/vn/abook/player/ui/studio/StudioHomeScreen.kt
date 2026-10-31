package vn.abook.player.ui.studio

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.StudioError
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.ChevronIcon
import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.ui.components.GeneratedCover
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.StageProgress
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.studio.parts.LinkBanner
import vn.abook.player.ui.studio.parts.PermissionCard
import vn.abook.player.ui.studio.parts.PollWhileVisible
import vn.abook.player.ui.studio.parts.ink
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * Studio của một máy tính: các dự án xếp theo điều cần làm ngay - đang làm, cần bạn duyệt, còn lại (NATIVE_REMOTE_STUDIO.md §6.1). Mỗi dự án là một thẻ, chạm
 * để mở. Hỏi máy tính 5 giây một lần khi có sách chạy, 15 giây khi rảnh, và chỉ khi màn đang hiện (`active`).
 */
@Composable
fun StudioHomeScreen(state: StudioHomeState, onBack: () -> Unit, onOpen: (StudioBook) -> Unit, active: Boolean = true, onNew: (() -> Unit)? = null) {
    val session = state.session
    val poll by state.poll.collectAsState()
    PollWhileVisible(active, session.retries) { state.run() }
    val books = poll.data
    val blocked = session.listenOnly || poll.error is StudioError.ListenOnly
    val groups = remember(books) { books?.let(StudioLogic::groups).orEmpty() }
    BookForm(
        StudioText.TITLE, onBack, "studio_home",
        footer = if (onNew != null && !blocked && books != null) ({ PrimaryButton(StudioNewText.TITLE, onNew, Modifier.fillMaxWidth().testTag("studio_new")) }) else null,
    ) {
        val list = rememberLazyListState()
        when {
            blocked -> PermissionCard(session.name, session::retry)
            books == null && poll.error == null -> Column(Modifier.fillMaxWidth().padding(top = Dim.s24)) {
                BasicText(StudioText.LOADING, style = Abook.type.body.copy(color = Abook.colors.text2), modifier = Modifier.testTag("studio_loading"))
            }
            books == null -> InlineProblem(poll.error?.let { StudioText.failure(it) }.orEmpty(), state::refreshSoon, "studio_home_problem")
            else -> LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("studio_list"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
                item("notices", "notices") {
                    Column {
                        InlineProblem(if (state.mismatched) StudioText.MISMATCH else "", null, "studio_mismatch")
                        LinkBanner(poll.error, session.name, state::refreshSoon)
                    }
                }
                if (books.isEmpty()) item("empty", "status") {
                    ListItem(StudioText.NO_PROJECTS, Modifier.testTag("studio_empty"), hint = StudioText.NO_PROJECTS_HINT)
                }
                for ((index, entry) in groups.withIndex()) {
                    val (group, members) = entry
                    item("group_${group.name}", "group") { SectionTitle(StudioText.group(group), first = index == 0, modifier = Modifier.testTag("studio_group_${group.name}")) }
                    items(members, key = { "book_${it.id}" }, contentType = { "book" }) { book -> ProjectCard(book, onOpen) }
                }
            }
        }
    }
}

/** Một dự án: bìa nhỏ, tên, một dòng trạng thái (nhãn · chương xong/tổng, màu theo trạng thái), thanh tiến độ khi đang làm dở. */
@Composable
private fun ProjectCard(book: StudioBook, onOpen: (StudioBook) -> Unit) {
    val status = StudioLogic.status(book)
    Column(Modifier.fillMaxWidth().testTag("studio_book_${book.id}")) {
        Row(Modifier.fillMaxWidth().pressable { onOpen(book) }.padding(vertical = Dim.s12), verticalAlignment = Alignment.Top) {
            GeneratedCover(book.title, null, COVER_WIDTH, Modifier.width(COVER_WIDTH).aspectRatio(2f / 3f).clip(RoundedCornerShape(Dim.radiusControl)), small = true)
            Spacer(Modifier.width(Dim.s12))
            Column(Modifier.weight(1f)) {
                BasicText(book.title, style = Abook.type.bodyStrong, modifier = Modifier.testTag("studio_book_title"))
                ClockLabel(StudioText.statusLine(book), Modifier.padding(top = 2.dp).testTag("studio_book_status"), Abook.type.bodySmall.copy(color = status.tone.ink()))
                if (book.working && book.phase != "done" && book.phase != "idle") StageProgress { book.overall }
            }
            Spacer(Modifier.width(Dim.s12))
            ChevronIcon(Abook.colors.text3)
        }
        RowLine()
    }
}

private val COVER_WIDTH = 44.dp
