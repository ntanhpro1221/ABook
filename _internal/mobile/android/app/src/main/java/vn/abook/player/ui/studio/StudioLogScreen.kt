package vn.abook.player.ui.studio

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import vn.abook.player.StudioError
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.studio.parts.LinkBanner
import vn.abook.player.ui.studio.parts.PermissionCard
import vn.abook.player.ui.studio.parts.PollWhileVisible
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * "Nhật ký" của một dự án (NATIVE_REMOTE_STUDIO.md §6.14): vài dòng thông tin của sách (trạng thái, số chương, độ dài), rồi diễn biến theo thời gian, mới nhất ở trên.
 * "Chi tiết kỹ thuật" thêm các dòng kỹ thuật vào chính danh sách này. Hỏi 5 giây một lần khi máy đang làm sách.
 */
@Composable
fun StudioLogScreen(state: StudioProjectState, onBack: () -> Unit, active: Boolean = true) {
    val session = state.session
    val activity = state.activity
    val page by state.poll.collectAsState()
    val log by activity.poll.collectAsState()
    PollWhileVisible(active, session.retries) { state.run() }
    PollWhileVisible(active, session.retries) { activity.run() }
    DisposableEffect(state) { onDispose { state.leave() } }
    val blocked = session.listenOnly || page.error is StudioError.ListenOnly || log.error is StudioError.ListenOnly
    val items = remember(log.data) { log.data?.let(StudioLogLogic::ordered) }
    val facts = remember(page.data) { page.data?.let(StudioLogLogic::facts).orEmpty() }
    BookForm(StudioLogText.TITLE, onBack, "studio_activity") {
        val list = rememberLazyListState()
        when {
            blocked -> PermissionCard(session.name, session::retry)
            items == null && log.error == null -> BasicText(
                StudioLogText.LOADING, style = Abook.type.body.copy(color = Abook.colors.text2), modifier = Modifier.padding(top = Dim.s24).testTag("studio_activity_loading"),
            )
            items == null -> InlineProblem(log.error?.let { StudioText.failure(it) }.orEmpty(), activity::refreshSoon, "studio_activity_problem")
            else -> LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("studio_activity_list"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
                item("notices", "notices") { LinkBanner(log.error, session.name, activity::refreshSoon) }
                if (facts.isNotEmpty()) {
                    item("info_title", "title") { SectionTitle(StudioLogText.INFO, first = true) }
                    items(facts, key = { "fact_${it.first}" }, contentType = { "fact" }) { (label, value) -> FactRow(label, value) }
                }
                item("technical", "technical") {
                    Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
                        SwitchRow(StudioLogText.TECHNICAL, activity.technical, activity::showTechnical, "studio_activity_technical")
                        RowLine()
                    }
                }
                if (items.isEmpty()) {
                    item("empty", "status") { ListItem(StudioLogText.EMPTY, Modifier.testTag("studio_activity_empty"), hint = StudioLogText.EMPTY_HINT) }
                } else {
                    item("count", "count") { RowHint(StudioLogText.count(items.size), Modifier.padding(top = Dim.s8, bottom = Dim.s4).testTag("studio_activity_count")) }
                    items(items, key = { "log_${it.id}_${it.at}" }, contentType = { "log" }) { item -> LogRow(item, activity.technical) }
                }
            }
        }
    }
}

@Composable
private fun FactRow(label: String, value: String) {
    Column(Modifier.fillMaxWidth().testTag("studio_fact")) {
        Row(Modifier.fillMaxWidth().padding(vertical = Dim.s12)) {
            BasicText(label, style = Abook.type.body.copy(color = Abook.colors.text2), modifier = Modifier.weight(1f))
            BasicText(value, style = Abook.type.body, modifier = Modifier.testTag("studio_fact_value"))
        }
        RowLine()
    }
}

/** Mực của một dòng nhật ký theo mức: lỗi đỏ, cảnh báo hổ phách, còn lại mực thường. */
@Composable
private fun levelInk(level: String): Color = when (level) {
    "error" -> Abook.colors.danger
    "warning" -> Abook.colors.accentText
    else -> Abook.colors.text
}

@Composable
private fun LogRow(item: StudioLogItem, technical: Boolean) {
    val when_ = StudioLogLogic.at(item)
    ListItem(item.text, Modifier.testTag("studio_log_${item.level}"), titleColor = levelInk(item.level), hint = if (technical && item.code.isNotEmpty()) "$when_ · ${item.code}" else when_)
    RowLine()
}
