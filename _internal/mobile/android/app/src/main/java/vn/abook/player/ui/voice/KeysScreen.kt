package vn.abook.player.ui.voice

import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

import vn.abook.player.S

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.ui.platform.testTag
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
import vn.abook.player.ui.components.Reveal

/**
 * Khoá giọng trực tuyến: mỗi nhà cung cấp (Azure, Google Cloud, FPT.AI, Viettel AI) một hàng - tên, khoá che và kết quả lần kiểm tra; chạm mở bảng nhập / kiểm tra / xoá khoá.
 * Khoá lưu và đọc qua [vn.abook.player.readaloud.OnlineVoices]; màn không bao giờ thấy khoá thật. Chưa đọc xong thì các hàng đã có tên, chưa chạm được.
 */
@Composable
fun KeysScreen(voice: VoiceState, sheets: SheetHost, onBack: () -> Unit, modifier: Modifier = Modifier, embedded: Boolean = false) {
    val ui by voice.keys.collectAsState()
    LaunchedEffect(voice) {
        voice.loadKeys()
        voice.loadConsents()
    }
    val content: @Composable ColumnScope.() -> Unit = {
        ListSection(first = true) {
            MoreInfo(S.s_tim_hieu_them_032fe408, S.s_khoa_chi_luu_tren_may_dich_vu_co_the_tinh_a894acea, "keys_more")
            val rows = if (ui.loaded) ui.providers else VoiceText.KEYED.map { (id, name) -> KeyProvider(id, name, "", false, false, "", "", false, 0) }
            for ((index, provider) in rows.withIndex()) {
                Reveal(index > 0) { RowLine() }
                KeyRow(provider, if (ui.loaded) ({ sheets.show { dismiss -> KeySheet(provider, voice, dismiss) } }) else null)
            }
            InlineProblem(if (ui.failed && !ui.loaded) S.s_chua_doc_duoc_cac_khoa_87b08dca else "", voice::loadKeys, "keys_problem")
        }
    }
    SwapContent(embedded, contentKey = { embedded -> embedded }, layout = ContentLayout.Box) { embedded ->
        if (embedded) Column(modifier.fillMaxWidth().testTag("keys_screen"), content = content)
        else SettingsPage(S.s_khoa_truc_tuyen_b32d4988, onBack, "keys_screen", modifier, content)
    }
}
