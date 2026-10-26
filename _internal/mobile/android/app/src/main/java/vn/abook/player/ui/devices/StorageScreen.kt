package vn.abook.player.ui.devices

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/*
 * Dung lượng. Đầu màn: tổng đã dùng và chỗ còn trống; rồi từng thứ chiếm chỗ, lớn nhất trước. Chạm một hàng để xoá khỏi máy - cùng bước xác nhận với "Xoá khỏi máy"
 * của trang sách (sách ở máy kia vẫn còn đó nếu đó chỉ là phần đã tải).
 */

@Composable
fun StorageScreen(devices: DevicesState, sheets: SheetHost, onBack: () -> Unit) {
    val ui by devices.storage.collectAsState()
    val pair by devices.pair.collectAsState()
    LaunchedEffect(devices) { devices.openStorage() }
    BookForm("Dung lượng", onBack, "storage_screen") {
        if (ui.loaded) LazyColumn(Modifier.fillMaxSize().testTag("storage_list"), contentPadding = PaddingValues(bottom = Dim.s16)) {
            item("total", "total") {
                Column(Modifier.fillMaxWidth().padding(top = Dim.s16, bottom = Dim.s8).testTag("storage_total")) {
                    BasicText(Fmt.size(ui.storage.bytes), style = Abook.type.screenTitle)
                    Caption("Còn trống ${Fmt.size(ui.storage.free)}")
                }
            }
            if (ui.storage.entries.isEmpty()) item("empty", "status") {
                ListItem("Chưa có gì trên máy", Modifier.testTag("storage_empty"))
            }
            items(ui.storage.entries, key = { "stored_${it.id}" }, contentType = { "stored" }) { item ->
                Column(Modifier.fillMaxWidth()) {
                    StoredRow(item, busy = item.id in pair.downloading, onDelete = { sheets.show { dismiss -> StoredSheet(item, devices, dismiss) } })
                    RowLine()
                }
            }
        }
    }
}
