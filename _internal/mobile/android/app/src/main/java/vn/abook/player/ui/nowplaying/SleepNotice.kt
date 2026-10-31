package vn.abook.player.ui.nowplaying

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextAlign
import kotlinx.coroutines.flow.distinctUntilChanged
import vn.abook.player.ui.components.SleepIcon
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * Hai lời báo của hẹn giờ ngủ dưới hàng nút (web: FadingNotice và dòng "Sẽ dừng khi hết chương này."): đang nhỏ dần thì "Sắp tắt · …" kèm "+N phút" nghe thêm bằng một chạm;
 * hẹn theo chương thì một dòng nhắc sẽ dừng ở đâu - nhỏ dần đã nói thay thì dòng ấy lui đi (hai dòng cùng lúc ở chương rất ngắn đọc như mâu thuẫn).
 * Ngưỡng nhỏ dần chỉ đọc qua `snapshotFlow`: mỗi nhịp đồng hồ không dựng lại gì, chỉ lúc vượt ngưỡng.
 */
@Composable
fun SleepNotice(state: NowPlayingState, model: NowPlayingModel, modifier: Modifier = Modifier) {
    val options = model.sleepOptions
    var fading by remember { mutableStateOf(false) }
    LaunchedEffect(state.sleep, state.playing, options) {
        snapshotFlow { SleepText.fading(state.sleep, model.position.sleepRemainingMs.value, state.playing, options) }
            .distinctUntilChanged().collect { fading = it }
    }
    Column(modifier.fillMaxWidth()) {
        Reveal(fading) {
            Row(Modifier.fillMaxWidth().padding(top = Dim.s8).testTag("sleep_fading"), verticalAlignment = Alignment.CenterVertically) {
                SleepIcon(Abook.colors.accentText)
                Spacer(Modifier.width(Dim.s12))
                BasicText(SleepText.fadingLine(options), Modifier.weight(1f), style = Abook.type.bodySmall.copy(color = Abook.colors.accentText))
                TextAction(SleepText.extendLabel(options.extendMinutes), model::extendSleep, "sleep_extend_now")
            }
        }
        Reveal(state.sleep.kind == SleepKind.Chapter && !fading) {
            BasicText(SleepText.UNTIL_CHAPTER_END, Modifier.fillMaxWidth().padding(top = Dim.s8).testTag("sleep_chapter_note"),
                style = Abook.type.caption.copy(color = Abook.colors.text2, textAlign = TextAlign.Center))
        }
    }
}
