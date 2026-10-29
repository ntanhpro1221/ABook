package vn.abook.player.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.BasicText
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
        Caption("Trên ${book.remote?.deviceName ?: "máy tính"}")
        Spacer(Modifier.height(Dim.s16))
        PrimaryButton("Nghe", listen, Modifier.fillMaxWidth().testTag("remote_book_stream"))
        Reveal(!finished) {
        MovingTextAction(if (downloading) "Huỷ tải" else "Tải về máy", {
            if (downloading) devices.cancelDownload(book.id) else {
                started = true
                devices.download(RemoteBook(book.id, title = book.title, chaptersAvailable = book.chaptersAvailable, chaptersTotal = book.chaptersTotal))
            }
        }, "remote_book_download", Modifier.fillMaxWidth(), Alignment.CenterStart)
        }
        Reveal(downloading || started) {
            Caption(if (downloading) "Đang tải ${(progress * 100).toInt()}%" else pair.failed[book.id]?.let { "Chưa tải được. " + it } ?: if (finished) "Đã tải xong - nghe được cả khi không có mạng" else "Đã huỷ - lần tải sau làm tiếp từ chỗ dừng.")
        }
    }
}
