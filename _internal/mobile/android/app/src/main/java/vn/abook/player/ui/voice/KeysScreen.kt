package vn.abook.player.ui.voice

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListSection
import vn.abook.player.ui.components.MoreInfo
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.screens.SettingsPage
import vn.abook.player.ui.theme.Dim

/**
 * Khoá giọng trực tuyến: mỗi nhà cung cấp (Azure, Google Cloud, FPT.AI, Viettel AI) một hàng - tên, khoá che và kết quả lần kiểm tra; chạm mở bảng nhập / kiểm tra / xoá khoá.
 * Khoá lưu và đọc qua [vn.abook.player.readaloud.OnlineVoices]; màn không bao giờ thấy khoá thật. Chưa đọc xong thì các hàng đã có tên, chưa chạm được.
 */
@Composable
fun KeysScreen(voice: VoiceState, sheets: SheetHost, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val ui by voice.keys.collectAsState()
    LaunchedEffect(voice) {
        voice.loadKeys()
        voice.loadConsents()
    }
    SettingsPage("Khoá trực tuyến", onBack, "keys_screen", modifier) {
        ListSection(first = true) {
            MoreInfo("Tìm hiểu thêm", "Khoá chỉ lưu trên máy. Dịch vụ có thể tính phí; lỗi khoá thì tạm dùng Edge hoặc giọng máy.", "keys_more")
            val rows = if (ui.loaded) ui.providers else VoiceText.KEYED.map { (id, name) -> KeyProvider(id, name, "", false, false, "", "", false, 0) }
            for ((index, provider) in rows.withIndex()) {
                if (index > 0) RowLine()
                KeyRow(provider, if (ui.loaded) ({ sheets.show { dismiss -> KeySheet(provider, voice, dismiss) } }) else null)
            }
            InlineProblem(if (ui.failed && !ui.loaded) "Chưa đọc được các khoá" else "", voice::loadKeys, "keys_problem")
        }
    }
}
