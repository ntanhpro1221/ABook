package vn.abook.player.ui.devices

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.components.CloseIcon
import vn.abook.player.ui.components.ConfirmPage
import vn.abook.player.ui.components.DangerButton
import vn.abook.player.ui.components.DeleteBookPage
import vn.abook.player.ui.components.LaptopIcon
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.PlusIcon
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RefreshIcon
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/*
 * Các bảng trượt của ba màn Thiết bị: việc của một thiết bị đã nối (kèm bước bỏ ghép), đổi tên máy này, thôi ghép một máy đang nghe, xoá một thứ khỏi máy.
 * Mọi bước xác nhận dựng bằng [ConfirmPage] / [DeleteBookPage] - cùng một chỗ với menu "Xoá khỏi máy" của trang sách.
 */

private enum class DevicePage { Actions, Forget }

/** Bảng của một thiết bị đã nối: Studio (máy tính), làm mới, ghép lại (khi nó đã thôi ghép), bỏ ghép (có bước xác nhận ngay trong bảng). */
@Composable
fun DeviceSheet(initial: Paired, state: DevicesState, dismiss: () -> Unit) {
    var page by remember { mutableStateOf(DevicePage.Actions) }
    BackHandler(enabled = page != DevicePage.Actions) { page = DevicePage.Actions }
    // Bảng sống theo trạng thái thật (Studio hỏi xong, thiết bị vừa bỏ ghép); thiết bị đã rời danh sách thì giữ bản cuối trong lúc bảng trượt xuống.
    val ui by state.pair.collectAsState()
    val last = remember { arrayOf(initial) }
    ui.devices.firstOrNull { it.key == initial.key }?.let { last[0] = it }
    val device = last[0]
    val studio = ui.studio[device.key]
    SheetPages(page, { it.ordinal }, "device_sheet") { shown ->
        when (shown) {
            DevicePage.Actions -> DeviceActions(device, studio, state, dismiss, onForget = { page = DevicePage.Forget })
            DevicePage.Forget -> ForgetPage(device, state, dismiss, onKeep = { page = DevicePage.Actions })
        }
    }
}

@Composable
private fun DeviceActions(device: Paired, studio: StudioComputer?, state: DevicesState, dismiss: () -> Unit, onForget: () -> Unit) {
    val colors = Abook.colors
    val scope = rememberCoroutineScope()
    var opening by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    Column(Modifier.fillMaxWidth()) {
        BasicText(device.name, style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s8))
        if (studio != null) {
            MenuRow(if (opening) "Đang mở Studio" else "Mở Studio", "device_studio", unavailable = studio.listenOnly,
                hint = if (studio.listenOnly) DeviceText.listenOnly(device.name) else null, onClick = {
                if (opening) return@MenuRow
                opening = true
                scope.launch {
                    val error = state.openStudio(device.key)
                    opening = false
                    problem = error.orEmpty()
                    if (error == null) dismiss()
                }
            }) { ink -> LaptopIcon(ink) }
        }
        MenuRow("Làm mới", "device_refresh", onClick = { state.refresh(); dismiss() }) { ink -> RefreshIcon(ink) }
        if (device.reach is Reach.Unpaired || device.reach is Reach.Changed) {
            MenuRow("Ghép lại", "device_repair", onClick = { state.repair(device); dismiss() }) { ink -> PlusIcon(ink) }
        }
        Box(Modifier.fillMaxWidth().padding(vertical = Dim.s8).height(1.dp).background(colors.line))
        MenuRow("Bỏ ghép", "device_forget", danger = true, onClick = onForget) { ink -> CloseIcon(ink) }
        if (problem.isNotEmpty()) {
            Spacer(Modifier.height(Dim.s4))
            BasicText(problem, style = Abook.type.bodySmall.copy(color = colors.danger), modifier = Modifier.testTag("device_problem"))
        }
    }
}

/**
 * Bước bỏ ghép: nói cái sẽ mất (sửa chưa gửi, sách nghe thẳng sẽ rời Thư viện) - cùng lời với bản WebView ([DeviceText.forgetCopy]). Máy tính chính và
 * thiết bị nào không còn gì để mất thì chỉ một câu nói sách đã tải ở lại.
 */
@Composable
private fun ForgetPage(device: Paired, state: DevicesState, dismiss: () -> Unit, onKeep: () -> Unit) {
    val scope = rememberCoroutineScope()
    var unsent by remember { mutableStateOf<Unsent?>(null) }
    var ready by remember { mutableStateOf(device.main) }
    var working by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    LaunchedEffect(device.key) {
        if (!device.main) {
            unsent = state.unsent(device.key)
            ready = true
        }
    }
    val copy = if (device.main) null else DeviceText.forgetCopy(device.name, unsent, device.reach == Reach.Ok)
    fun run(choice: ForgetChoice) {
        if (working || !ready) return
        working = true
        scope.launch {
            val error = if (device.main) state.unpairMain() else state.forget(device.key, choice)
            working = false
            problem = error.orEmpty()
            if (error == null) dismiss()
        }
    }
    ConfirmPage(
        copy?.title ?: "Bỏ ghép ${device.name}?", "forget_confirm",
        copy?.lines ?: listOf("Sách đã tải vẫn ở lại máy này."), problem,
    ) {
        if (copy?.send != null) {
            PrimaryButton(copy.send, { run(ForgetChoice.Send) }, Modifier.fillMaxWidth().testTag("forget_send"), enabled = !working)
            Spacer(Modifier.height(Dim.s8))
        }
        DangerButton(if (working) "Đang bỏ ghép" else copy?.discard ?: "Bỏ ghép", { run(if (copy?.edited == true) ForgetChoice.Discard else ForgetChoice.Plain) }, "forget_yes")
        Spacer(Modifier.height(Dim.s8))
        QuietButton("Giữ lại", onKeep, "forget_keep")
    }
}

/** Bảng đổi tên máy này: một ô, "Lưu" ở dưới; lỗi hiện ngay dưới ô. */
@Composable
fun RenameSheet(current: String, state: DevicesState, dismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var name by remember { mutableStateOf(current) }
    var working by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    Column(Modifier.fillMaxWidth().testTag("rename_sheet")) {
        BasicText("Tên máy này", style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s16))
        BookField(null, name, { name = it; problem = "" }, "rename_field", !working, "Tên máy này")
        if (problem.isNotEmpty()) {
            Spacer(Modifier.height(Dim.s8))
            BasicText(problem, style = Abook.type.bodySmall.copy(color = Abook.colors.danger), modifier = Modifier.testTag("rename_problem"))
        }
        Spacer(Modifier.height(Dim.s24))
        PrimaryButton(if (working) "Đang lưu" else "Lưu", {
            if (working || name.isBlank()) return@PrimaryButton
            working = true
            scope.launch {
                val error = state.rename(name.trim())
                working = false
                problem = error.orEmpty()
                if (error == null) dismiss()
            }
        }, Modifier.fillMaxWidth().testTag("rename_save"), enabled = !working && name.isNotBlank())
    }
}

/** Thôi ghép một máy đang nghe thư viện này: máy ấy mất quyền nghe ngay. */
@Composable
fun RevokeSheet(sharer: Sharer, state: DevicesState, dismiss: () -> Unit) {
    ConfirmPage("Thôi ghép ${sharer.name}?", "revoke_confirm", listOf("${sharer.name} sẽ không nghe được thư viện này nữa."), "") {
        DangerButton("Thôi ghép", { state.revoke(sharer.id); dismiss() }, "revoke_yes")
        Spacer(Modifier.height(Dim.s8))
        QuietButton("Giữ lại", dismiss, "revoke_keep")
    }
}

/** Xoá một thứ khỏi máy từ danh sách Dung lượng: cùng bước xác nhận, cùng lõi với "Xoá khỏi máy" của trang sách. */
@Composable
fun StoredSheet(item: Stored, state: DevicesState, dismiss: () -> Unit) {
    Column(Modifier.fillMaxWidth().testTag("stored_sheet")) {
        DeleteBookPage(item.title, if (item.partial) item.holder.ifEmpty { "máy kia" } else null, { state.delete(item.id) }, dismiss, dismiss)
    }
}
