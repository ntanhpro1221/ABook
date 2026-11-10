package vn.abook.player.ui.devices

import vn.abook.player.S

import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.formatSize

import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.motion.rememberPresence
import vn.abook.player.ui.theme.MotionMs

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.key
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
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
fun StorageScreen(devices: DevicesState, sheets: SheetHost, embedded: Boolean = false, onBack: () -> Unit) {
    val ui by devices.storage.collectAsState()
    val pair by devices.pair.collectAsState()
    val entries = rememberPresence(ui.storage.entries) { it.id }
    LaunchedEffect(devices) { devices.openStorage() }
    DeviceSettingsContent(S.s_dung_luong_32009349, onBack, "storage_screen", embedded) {
        if (ui.loaded) Column(Modifier.fillMaxWidth().testTag("storage_list").padding(bottom = Dim.s16)) {
            key("total", "total") {
                Column(Modifier.fillMaxWidth().padding(top = Dim.s16, bottom = Dim.s8).testTag("storage_total")) {
                    ClockLabel(formatSize(ui.storage.bytes), style = Abook.type.screenTitle)
                    Caption(S.s_con_trong_0_78b8755a(formatSize(ui.storage.free)), ticking = true)
                }
            }
            if (entries.isEmpty()) key("empty", "status") {
                ListItem(S.s_chua_co_gi_tren_may_e57d2ed6, Modifier.testTag("storage_empty"))
            }
            for (entry in entries) key("stored_${entry.item.id}") {
                AnimatedVisibility(entry.visible,
                    enter = expandVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) + slideInVertically(tween(MotionMs.MEDIUM)) { it / 4 },
                    exit = shrinkVertically(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) + slideOutVertically(tween(MotionMs.MEDIUM_OUT)) { it / 4 }) {
                val item = entry.item
                Column(Modifier.fillMaxWidth()) {
                    StoredRow(item, busy = item.id in pair.downloading, onDelete = { sheets.show { dismiss -> StoredSheet(item, devices, dismiss) } })
                    RowLine()
                }
                }
            }
        }
    }
}
