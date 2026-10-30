package vn.abook.player.ui.studio.parts

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextAlign
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import vn.abook.player.StudioError
import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.StageProgress
import vn.abook.player.ui.studio.StudioBook
import vn.abook.player.ui.studio.StudioText
import vn.abook.player.ui.studio.StudioTone
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Màu chữ của một trạng thái. Bảng màu không có màu cảnh báo riêng: "cần để ý" và "đang chạy" cùng dùng mực hổ phách. */
@Composable
fun StudioTone.ink(): Color = when (this) {
    StudioTone.Accent, StudioTone.Warning -> Abook.colors.accentText
    StudioTone.Success -> Abook.colors.success
    StudioTone.Danger -> Abook.colors.danger
    StudioTone.Muted -> Abook.colors.text2
}

/**
 * Hỏi máy tính chỉ khi màn đang hiện VÀ app ở phía trước (NATIVE_REMOTE_STUDIO.md §3.5): `active` = màn ở trên cùng (không bị màn khác phủ, không đang
 * chuyển cảnh); rời khỏi trạng thái STARTED thì `run` bị huỷ, trở lại thì chạy lại và hỏi ngay một lần. `retries` đổi (bấm "Thử lại" ở thẻ quyền) cũng chạy lại.
 */
@Composable
fun PollWhileVisible(active: Boolean, retries: Int, run: suspend () -> Unit) {
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(active, retries, lifecycle) {
        if (active) lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) { run() }
    }
}

/**
 * Thẻ "Máy tính chưa cho bạn sửa" (§3.4): thay CẢ nội dung Studio khi máy tính chỉ cho điện thoại này nghe. Một nút duy nhất; không có nút nào bị tắt xám
 * rải rác - có quyền thì dùng, không thì cả Studio là một thẻ.
 */
@Composable
fun PermissionCard(machine: String, onRetry: () -> Unit, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(top = Dim.s24).testTag("studio_permission")) {
        BasicText(StudioText.PERMISSION_TITLE, style = Abook.type.sectionTitle, modifier = Modifier.testTag("studio_permission_title"))
        Spacer(Modifier.height(Dim.s8))
        BasicText(StudioText.permissionLine(machine), style = Abook.type.body.copy(color = Abook.colors.text2), modifier = Modifier.testTag("studio_permission_line"))
        Spacer(Modifier.height(Dim.s24))
        PrimaryButton(StudioText.RETRY, onRetry, Modifier.fillMaxWidth().testTag("studio_permission_retry"))
    }
}

/**
 * Dải báo khi lần hỏi gần nhất hỏng mà đã có bản cũ: giữ trang, nói vì sao và mời thử lại. Máy im lặng thì nói "{máy} không trả lời - đang chờ nối lại"
 * (cùng câu `StudioLink.silentLine` của trang Studio cũ); nhịp hỏi tự lùi dần rồi tự nối lại, nên không cần theo dõi riêng.
 */
@Composable
fun LinkBanner(error: StudioError?, machine: String, onRetry: () -> Unit, modifier: Modifier = Modifier) {
    val message = when {
        error == null || error is StudioError.ListenOnly -> ""
        error is StudioError.Offline -> StudioText.silent(machine)
        else -> StudioText.failure(error)
    }
    InlineProblem(message, onRetry, "studio_link", modifier)
}

/**
 * Tiến độ cả sách: thanh mảnh + phần trăm, kèm còn bao lâu (web `HeaderProgress`). Sách chưa chạy / đã xong không có gì để đo - khối khép lại. Cả hai số đi
 * qua [ClockLabel] (số rộng đều, không nhảy khi đổi); thanh đọc giá trị trong pha vẽ.
 */
@Composable
fun ProgressBlock(book: StudioBook, modifier: Modifier = Modifier) {
    Reveal(book.phase != "done" && book.phase != "idle") {
        Column(modifier.fillMaxWidth().padding(top = Dim.s16).testTag("studio_progress")) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Dim.s12)) {
                Column(Modifier.weight(1f)) { StageProgress { book.overall } }
                ClockLabel(StudioText.percent(book.overall), Modifier.width(Dim.s48).testTag("studio_percent"), Abook.type.bodyStrong.copy(textAlign = TextAlign.End))
            }
            val note = StudioText.progressNote(book)
            if (note.isNotEmpty()) ClockLabel(note, Modifier.padding(top = Dim.s8).testTag("studio_note"), Abook.type.bodySmall.copy(color = Abook.colors.text2))
        }
    }
}
