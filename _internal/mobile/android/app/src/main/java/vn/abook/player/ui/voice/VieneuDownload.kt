package vn.abook.player.ui.voice

import vn.abook.player.formatSize

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.devices.DownloadBar
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * Tải giọng VieNeu NGAY trong khối lỗi của trình phát, khi giọng đang chọn không đọc được mà máy chưa có giọng chạy trên máy (listen/VieneuDownload.tsx): cùng mô-đun với Cài đặt
 * ([VoiceState.download] / [VoiceState.cancel]) nên bạn không rời màn nghe. Chọn gì để tải: một giọng nhẹ nhất đủ đọc ([OfflineOffer]); gói đánh dấu sẵn của Cài đặt là nút phụ.
 * Tải xong thì danh sách giọng đọc lại ([VoiceState] báo `voicesChanged`) và khối lỗi đổi nút sang "Đọc bằng …".
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun VieneuDownload(voice: VoiceState, button: String, openSettings: () -> Unit, modifier: Modifier = Modifier) {
    val modules by voice.modules.collectAsState()
    val kind = ModuleKind.Vieneu
    androidx.lifecycle.compose.LifecycleResumeEffect(voice) { voice.openVoice(); onPauseOrDispose { voice.hideVoice() } }
    val status = modules[kind]?.shown
    Column(modifier.fillMaxWidth().testTag("vieneu_download")) {
        // Chưa biết trạng thái mô-đun: chỉ có đường tới Cài đặt.
        Reveal(status != null) {
            val shown = status ?: return@Reveal
            val offer = OfflineOffer.of(shown)
            val bytes = OfflineOffer.bytes(shown, offer.missing)
            val fullBytes = OfflineOffer.bytes(shown, offer.full)
            val downloading = shown.state == ModuleState.Downloading
            val failed = shown.state == ModuleState.Error
            val unsupported = shown.state == ModuleState.Unsupported
            val metered = if (!shown.working && offer.missing.isNotEmpty()) VoiceText.metered(shown, bytes) else null
            val note = when {
                downloading -> "Đang tải ${formatSize(shown.total)} · ${shown.percent}%"
                failed -> shown.error
                unsupported -> VoiceText.unsupported(shown)
                shown.cancelled -> VoiceText.CANCELLED
                else -> null
            }
            Column(Modifier.fillMaxWidth()) {
                if (downloading) {
                    Row(Modifier.fillMaxWidth().semantics { contentDescription = "Đang tải giọng VieNeu" }, verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) { DownloadBar(voice.progress(kind)) }
                        Spacer(Modifier.width(Dim.s12))
                        TextAction("Huỷ", { voice.cancel(kind) }, "vieneu_cancel")
                    }
                }
                if (failed) {
                    BasicText("Chưa tải được giọng VieNeu", style = Abook.type.bodySmall.copy(color = Abook.colors.danger), modifier = Modifier.padding(top = Dim.s4))
                }
                if (note != null) BasicText(note, style = Abook.type.bodySmall.copy(color = if (failed) Abook.colors.danger else Abook.colors.text2), modifier = Modifier.padding(top = Dim.s4).testTag("vieneu_note"))
                if (metered != null) BasicText(metered, style = Abook.type.bodySmall.copy(color = Abook.colors.text2), modifier = Modifier.padding(top = Dim.s4))
                Spacer(Modifier.height(Dim.s4))
                FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(Dim.s12)) {
                    if (!downloading && !unsupported && offer.missing.isNotEmpty()) {
                        TextAction(
                            OfflineOffer.label(button, failed, bytes),
                            { voice.download(kind, offer.missing) }, "vieneu_start", align = Alignment.CenterStart,
                        )
                    }
                    if (!downloading && !failed && !unsupported && offer.light.isNotEmpty() && fullBytes > bytes) {
                        TextAction(OfflineOffer.fullLabel(fullBytes), { voice.download(kind, offer.full) }, "vieneu_full", align = Alignment.CenterStart)
                    }
                }
            }
        }
        TextAction("Xem trong Cài đặt", openSettings, "vieneu_settings", align = Alignment.CenterStart)
    }
}
