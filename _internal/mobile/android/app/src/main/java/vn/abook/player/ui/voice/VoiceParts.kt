package vn.abook.player.ui.voice

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import kotlinx.coroutines.flow.StateFlow
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.PlayPauseGlyph
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.devices.DownloadBar
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/*
 * Các loại hàng của Giọng đọc làm thêm. Mọi hàng là một [ListItem]: biểu tượng / nút đầu hàng và phần cuối hàng cùng thẳng dòng đầu của tên (luật của cả danh sách).
 */

fun moduleTag(kind: ModuleKind, id: String) = "module_${kind.key}_$id"

/**
 * Một lựa chọn của mô-đun giọng trên máy: việc ở cuối dòng đầu (Tải / Huỷ / Thử lại; đã có thì mũi tên mở bảng việc), dòng phụ nói cỡ, tốc độ máy đo được hay lỗi (đỏ),
 * thanh tiến độ ngay dưới tên khi đang tải. `onOpen` null = chạm hàng không mở gì.
 */
@Composable
fun ModuleChoiceRow(kind: ModuleKind, row: ModuleRow, progress: () -> StateFlow<Float>, onOpen: (() -> Unit)?, onAction: () -> Unit) {
    val colors = Abook.colors
    val tag = moduleTag(kind, row.id)
    val action = row.action
    val trailing: (@Composable () -> Unit)? = when (action) {
        is ModuleAction.Download -> ({ TextAction(action.label, onAction, "${tag}_action") })
        ModuleAction.Cancel -> ({ TextAction("Huỷ", onAction, "${tag}_cancel") })
        ModuleAction.Retry -> ({ TextAction("Thử lại", onAction, "${tag}_retry") })
        ModuleAction.Manage, ModuleAction.None -> null
    }
    ListItem(
        row.title, Modifier, onOpen, tag, hint = row.hint, hintColor = if (row.problem) colors.danger else colors.text2,
        trailing = trailing, chevron = action == ModuleAction.Manage,
        below = if (row.progress) ({ DownloadBar(progress()) }) else null,
    )
}

/** Nút nghe thử ở cuối hàng giọng: ô chạm 48, nút phát biến thành nút dừng khi đang lấy mẫu / đang phát. */
@Composable
fun SampleButton(active: Boolean, description: String, tag: String, onClick: () -> Unit) {
    val colors = Abook.colors
    Box(
        Modifier.size(Dim.s48).pressable(Role.Button, onClick = onClick).semantics { contentDescription = description }.testTag(tag),
        contentAlignment = Alignment.Center,
    ) {
        PlayPauseGlyph(active, if (active) colors.accentText else colors.text2, Dim.s24)
    }
}

/** Một nhà cung cấp giọng dùng khóa: tên, khóa che + kết quả lần kiểm tra (đỏ khi khóa chưa dùng được), chạm mở bảng của nó. */
@Composable
fun KeyRow(provider: KeyProvider, onOpen: (() -> Unit)?) {
    val colors = Abook.colors
    ListItem(
        provider.name, Modifier, onOpen, "key_${provider.id}", hint = VoiceText.keyHint(provider).ifEmpty { null },
        hintColor = if (provider.hasKey && !provider.valid) colors.danger else colors.text2, chevron = onOpen != null,
    )
}

/** Một bài trong Nhạc của tôi: nghệ sĩ · độ dài dưới tên, cỡ file ở cuối dòng đầu; chạm mở bảng có "Xoá bài". */
@Composable
fun TrackRow(track: MusicTrack, onOpen: () -> Unit) {
    ListItem(
        track.title, Modifier, onOpen, trackTag(track), hint = VoiceText.trackLine(track).ifEmpty { null },
        trailing = { BasicText(VoiceText.size(track.bytes), style = Abook.type.bodySmall.copy(color = Abook.colors.text2)) },
    )
}

fun trackTag(track: MusicTrack) = "track_${track.link}"
