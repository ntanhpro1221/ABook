package vn.abook.player.ui.nowplaying

import vn.abook.player.ui.components.ClockLabel
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.data.PrepareState
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * "Làm trước" ở cuối tấm "Giọng đọc" (web: PlayerViews `PrepareAhead`): máy đọc sẵn các chương tới ở nền, để giọng chậm hơn tốc độ nghe (VieNeu trên máy yếu) vẫn nghe
 * liền mạch. Nói rõ còn bao lâu; bấm mới làm, "Dừng làm trước" là thôi. Chỉ lắng nghe lõi khi khối đang hiện. Chương cuối (không còn chương nào để làm) thì không hiện câu mời.
 */
@Composable
fun PrepareBlock(state: NowPlayingState, prepare: PrepareState, modifier: Modifier = Modifier) {
    DisposableEffect(prepare) { prepare.watch(true); onDispose { prepare.watch(false) } }
    val status by prepare.status.collectAsState()
    val plan by prepare.plan.collectAsState()
    val failure by prepare.failure.collectAsState()
    val busy by prepare.busy.collectAsState()
    val upcoming = remember(state.chapters, state.chapterId) { PrepareText.upcoming(state.chapters, state.chapterId) }
    val ids = upcoming.map { it.id }
    val mine = PrepareText.mine(status, state.voiceId, state.bookId)
    val working = mine && status.running
    // Việc đang chạy thì khỏi ước lại; chương/giọng đổi thì ước mới.
    LaunchedEffect(state.voiceId, state.bookId, ids, working) { if (!working) prepare.loadPlan(state.voiceId, state.bookId, ids) }
    val label = when {
        mine -> PrepareText.label(status)
        status.running -> PrepareText.OTHER_JOB
        else -> ""
    }
    if (label.isEmpty() && upcoming.isEmpty()) return
    Column(modifier.fillMaxWidth().padding(top = Dim.s8).testTag("prepare_block")) {
        Box(Modifier.fillMaxWidth().height(1.dp).background(Abook.colors.line))
        ClockLabel(label.ifEmpty { PrepareText.intro(state.voiceId) }, Modifier.padding(top = Dim.s8).testTag("prepare_label"), style = Abook.type.caption.copy(color = Abook.colors.text2))
        val estimate = plan?.takeIf { !working }?.let(PrepareText::planLabel).orEmpty()
        Reveal(estimate.isNotEmpty()) { BasicText(estimate, Modifier.padding(top = Dim.s4).testTag("prepare_plan"), style = Abook.type.caption.copy(color = Abook.colors.text2)) }
        if (working) {
            TextAction("Dừng làm trước", prepare::cancel, "prepare_cancel", align = Alignment.CenterStart)
        } else if (upcoming.isNotEmpty()) {
            TextAction(PrepareText.startLabel(upcoming.size), {
                if (!busy) prepare.start(state.voiceId, state.bookId, ids, PrepareText.jobLabel(upcoming))
            }, "prepare_start", align = Alignment.CenterStart)
        }
        failure?.let {
            BasicText("Chưa làm trước được. " + it, Modifier.padding(bottom = Dim.s4).testTag("prepare_failed"), style = Abook.type.caption.copy(color = Abook.colors.danger))
        }
        SwitchRow("Chỉ khi đang sạc", status.chargingOnly, prepare::setChargingOnly, "prepare_charging")
    }
}
