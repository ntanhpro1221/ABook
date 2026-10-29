package vn.abook.player.ui.nowplaying

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import vn.abook.player.ui.components.CloseIcon
import vn.abook.player.ui.components.IconAction
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.voice.ConsentVoice
import vn.abook.player.ui.voice.VieneuDownload
import vn.abook.player.ui.voice.VoiceStuck

/**
 * Lời báo không phát được của trình phát (listen/PlayerViews.tsx `PlayerAlert`). Giọng đang chọn không đọc được (mất mạng, hay giọng trực tuyến hỏng) mà máy không có giọng nào khác:
 * một câu ngắn nói tên giọng, và nút theo tình huống - đã có giọng chạy trên máy thì "Đọc bằng …", chưa thì tải giọng VieNeu ngay tại đây ([VieneuDownload]); "Chọn giọng khác" mở tấm
 * "Giọng đọc". `openVoiceSettings`: tới Cài đặt > Giọng đọc (null: không có đường ấy).
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun PlayerAlert(state: NowPlayingState, model: NowPlayingModel, window: NowPlayingWindowState, modifier: Modifier = Modifier, onDismiss: (() -> Unit)? = null) {
    val stuck = VoiceStuck.isStuck(state.error)
    // Danh sách giọng chỉ được đọc khi cần (mở tấm Giọng đọc, hay lúc này): lời báo cần tên giọng đang chọn và biết đã có giọng chạy trên máy chưa.
    LaunchedEffect(stuck, state.bookId) { if (stuck) model.loadVoices() }
    val local = remember(state.voices, state.voiceId) {
        VoiceStuck.localVoiceFor(state.voices.map { ConsentVoice(it.id, it.name, it.id.substringBefore(':'), it.online, it.gender) }, null)
    }
    val message = VoiceStuck.shown(state.error, state.voiceName.ifEmpty { null })
    Column(modifier.fillMaxWidth().padding(top = Dim.s8).testTag("player_alert")) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
            BasicText(message, style = Abook.type.caption, modifier = Modifier.weight(1f).padding(top = Dim.s12).testTag("player_error"))
            if (onDismiss != null) IconAction("Đóng lời báo", onDismiss, "alert_dismiss") { CloseIcon(Abook.colors.text2) }
        }
        FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(Dim.s12)) {
            if (stuck && local != null) {
                TextAction("Đọc bằng " + VoiceStuck.caption(local), {
                    model.setVoice(local.id)
                    model.toggle()
                }, "alert_use_local", align = Alignment.CenterStart)
            }
            TextAction("Thử lại", model::toggle, "alert_retry", align = Alignment.CenterStart)
            if (stuck && state.voices.isNotEmpty()) {
                TextAction("Chọn giọng khác", { window.openSheet(PlayerSheet.Voice) }, "alert_choose", align = Alignment.CenterStart)
            }
        }
        val voice = model.voice
        if (stuck && local == null && voice != null) {
            VieneuDownload(voice, "Tải giọng VieNeu", { window.voiceSettings?.invoke() })
        }
    }
}
