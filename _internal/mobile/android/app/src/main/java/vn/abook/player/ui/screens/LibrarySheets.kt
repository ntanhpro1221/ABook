package vn.abook.player.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.ListenLogic
import vn.abook.player.ui.data.ShelfTile
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.components.fadeEdges

/** Bảng của một bộ nhiều tập: tên bộ + số tập, rồi từng tập (bìa nhỏ nhãn số tập, tên, trạng thái). Chạm một tập: đóng bảng và mở trang sách. */
@Composable
fun SeriesSheet(tile: ShelfTile.Series, covers: CoverLoader, onOpen: (ListenBook) -> Unit, dismiss: () -> Unit) {
    Column(Modifier.fillMaxWidth().testTag("series_sheet")) {
        BasicText(tile.label, style = Abook.type.sectionTitle)
        RowHint("${tile.books.size} ${tile.unit}")
        Spacer(Modifier.height(Dim.s12))
        val scroll = rememberScrollState()
        Column(Modifier.heightIn(max = 420.dp).fadeEdges(scroll).verticalScroll(scroll)) {
            for (book in tile.books) {
                Row(
                    Modifier.fillMaxWidth().pressable { dismiss(); onOpen(book) }.padding(vertical = Dim.s8).testTag("series_row"),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    BookCover(book.cover, book.title, book.part, covers, 44.dp, Modifier.width(44.dp), small = true)
                    Spacer(Modifier.width(Dim.s12))
                    Column(Modifier.weight(1f)) {
                        BasicText(book.title, style = Abook.type.body)
                        val status = ListenLogic.progressText(book)
                        RowHint(if (book.remote != null) "$status · ${ListenLogic.remotePlace(book)}" else status, ticking = true)
                    }
                }
            }
        }
    }
}
