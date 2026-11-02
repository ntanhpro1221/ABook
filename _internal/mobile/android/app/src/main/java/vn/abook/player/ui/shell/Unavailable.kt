package vn.abook.player.ui.shell

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.devices.DevicesPage
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.studio.PrecastText
import vn.abook.player.ui.studio.ReadingsText
import vn.abook.player.ui.studio.ScriptText
import vn.abook.player.ui.studio.StudioCoverText
import vn.abook.player.ui.studio.StudioExportText
import vn.abook.player.ui.studio.StudioLogText
import vn.abook.player.ui.studio.StudioNewText
import vn.abook.player.ui.studio.StudioSubKind
import vn.abook.player.ui.studio.StudioText
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.voice.VoicePage

/**
 * Màn con mà phần dựng nó (kho sách, máy tính đã ghép, Studio...) không có trong bản này - bản thử đo đạc (`abook.demo.books`) không nối máy tính, không xuất sách. Một màn con KHÔNG BAO GIỜ
 * được trống: chỗ nào thiếu kho thì dựng màn này (tên màn + một câu + nút ← và Back như mọi màn con), để người dùng không rơi vào khung đen không lối ra (soát điện thoại thật 02-11:
 * "Nối máy tính", "Xuất MP3", "Xuất M4B" ở bản thử). `ShellRoutesTest` đi qua mọi [Destination] khi không có kho nào và đòi đúng điều đó.
 */
@Composable
internal fun Unavailable(destination: Destination, onBack: () -> Unit) {
    BookForm(unavailableTitle(destination), onBack, "unavailable_screen") {
        BasicText("Bản thử chưa có màn này.", style = Abook.type.body.copy(color = Abook.colors.text2), modifier = Modifier.fillMaxWidth().padding(top = Dim.s8))
    }
}

/** Tên màn trên đầu trang [Unavailable]: cùng chữ với màn thật. */
internal fun unavailableTitle(destination: Destination): String = when (destination) {
    Destination.AddBook, is Destination.ImportReview -> "Thêm sách"
    is Destination.ImportChapter, is Destination.EditChapter -> "Tên chương"
    is Destination.EditBook -> "Sửa sách"
    is Destination.CropCover -> "Cắt ảnh bìa"
    is Destination.CoverSearch -> "Tìm ảnh bìa"
    is Destination.Book -> destination.book.title
    is Destination.Export -> if (destination.book.textOnly) "Xuất sách nói" else "Xuất sách"
    is Destination.Settings -> destination.group.label
    is Destination.Devices -> when (destination.page) {
        DevicesPage.Pair -> "Nối máy tính"
        DevicesPage.Share -> "Chia sẻ thư viện"
        DevicesPage.Storage -> "Dung lượng"
    }
    is Destination.Voice -> when (destination.page) {
        VoicePage.Keys -> "Khoá trực tuyến"
        VoicePage.Music -> "Nhạc của tôi"
    }
    is Destination.Studio, is Destination.StudioProject -> StudioText.TITLE
    is Destination.StudioNew -> StudioNewText.TITLE
    is Destination.StudioSub -> when (destination.kind) {
        StudioSubKind.Precast -> PrecastText.TITLE
        StudioSubKind.Script -> ScriptText.TITLE
        StudioSubKind.Readings -> ReadingsText.TITLE
        StudioSubKind.Export -> StudioExportText.TITLE
        StudioSubKind.Activity -> StudioLogText.TITLE
        StudioSubKind.Cover -> StudioCoverText.TITLE
    }
}
