package vn.abook.player.ui.shell

import vn.abook.player.S

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
        BasicText(UNAVAILABLE_LINE, style = Abook.type.body.copy(color = Abook.colors.text2), modifier = Modifier.fillMaxWidth().padding(top = Dim.s8))
    }
}

/** Tên màn trên đầu trang [Unavailable]: cùng chữ với màn thật. */
internal fun unavailableTitle(destination: Destination): String = when (destination) {
    Destination.AddBook, is Destination.ImportReview -> S.s_them_sach_2a9d3708
    is Destination.ImportChapter, is Destination.EditChapter -> S.s_ten_chuong_9edb6c28
    is Destination.EditBook -> S.s_sua_sach_79fb71d2
    is Destination.CropCover -> S.s_cat_anh_bia_d9d3257b
    is Destination.CoverSearch -> S.s_tim_anh_bia_9825b3d1
    is Destination.Book -> destination.book.title
    is Destination.Export -> if (destination.book.textOnly) S.s_xuat_sach_noi_219fb12a else S.s_xuat_sach_792effe5
    is Destination.Settings -> destination.group.label
    is Destination.Voice -> when (destination.page) {
        VoicePage.Music -> S.s_nhac_cua_toi_f65b7ac6
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
    is Destination.MusicPick -> S.s_chon_bai_cho_doan_840afc40
}

/** Câu duy nhất của màn trống, bằng lời người nghe ("ở đây" như web: "Ở đây chưa mở được file sách"), không nói về "bản thử" hay cách dựng app. */
internal const val UNAVAILABLE_LINE = S.s_man_nay_chua_mo_duoc_o_day_88fd4f22
