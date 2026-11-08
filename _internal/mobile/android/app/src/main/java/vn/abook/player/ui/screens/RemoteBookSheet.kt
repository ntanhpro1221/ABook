package vn.abook.player.ui.screens

import vn.abook.player.S

import androidx.compose.foundation.layout.*
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.testTag
import vn.abook.player.ui.components.*
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.devices.DevicesState
import vn.abook.player.ui.devices.RemoteBook
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** L9: choose stream or download at the book you touched, without a detour through device settings. */
@Composable
fun RemoteBookSheet(book: ListenBook, devices: DevicesState, listen: () -> Unit) {
    val pair by devices.pair.collectAsState()
    val downloading = book.id in pair.downloading
    val progress by devices.progress(book.id).collectAsState()
    val finished = !downloading && progress >= 1f
    var started by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().testTag("remote_book_sheet")) {
        BasicText(book.title, style = Abook.type.sectionTitle)
        Caption(S.s_tren_0_a2a4a4cb(book.remote?.deviceName ?: S.s_may_tinh_8eafc226))
        Spacer(Modifier.height(Dim.s16))
        PrimaryButton(S.s_nghe_a43aafef, listen, Modifier.fillMaxWidth().testTag("remote_book_stream"))
        Reveal(!finished) {
        MovingTextAction(if (downloading) S.s_huy_tai_1a9ff73d else S.s_tai_ve_may_41e0b494, {
            if (downloading) devices.cancelDownload(book.id) else {
                started = true
                devices.download(RemoteBook(book.id, title = book.title, chaptersAvailable = book.chaptersAvailable, chaptersTotal = book.chaptersTotal))
            }
        }, "remote_book_download", Modifier.fillMaxWidth(), Alignment.CenterStart)
        }
        Reveal(downloading || started) {
            Caption(if (downloading) S.s_dang_tai_0_c19ce634((progress * 100).toInt()) else pair.failed[book.id]?.let { S.s_chua_tai_duoc_e018ab1a + it } ?: if (finished) S.s_da_tai_xong_nghe_duoc_ca_khi_khong_co_mang_4eb58e30 else S.s_da_huy_lan_tai_sau_lam_tiep_tu_cho_dung_a3bd5f77, ticking = true)
        }
    }
}
