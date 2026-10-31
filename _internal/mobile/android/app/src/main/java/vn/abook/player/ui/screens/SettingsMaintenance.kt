package vn.abook.player.ui.screens

import vn.abook.player.ui.data.dotJoin
import androidx.compose.foundation.layout.*
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.testTag
import vn.abook.player.formatSize
import vn.abook.player.ui.components.*
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Recovery copies stay on this device until the user exports or explicitly deletes them. */
@Composable
fun MaintenanceSections(env: SettingsEnv, sheets: SheetHost) {
    val repo = env.repo
    val old by repo.oldSaves.collectAsState()
    val update by repo.update.collectAsState()
    val problem by repo.problem.collectAsState()
    val notice by repo.notice.collectAsState()
    LaunchedEffect(repo) { repo.loadMaintenance() }
    Reveal(old.isNotEmpty()) {
        ListSection("Bản lưu cũ (${old.size})", first = true) {
            Caption("Bản trước của một lần lưu hỏng. Lưu ra để không mất.")
            for (file in old) {
                ListItem(file.title, tag = "old_save_${file.name}", hint = dotJoin(formatSize(file.size), Fmt.whenText(file.modified / 1000.0)))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextAction("Lưu ra", { env.links.saveOld(file.name) { uri -> if (uri != null) repo.exportOldSave(file.name, uri) } }, "old_export_${file.name}")
                    TextAction("Xoá", { sheets.show { dismiss ->
                        val busy by repo.maintenanceBusy.collectAsState()
                        val failure by repo.problem.collectAsState()
                        ConfirmPage("Xoá bản lưu cũ?", "old_delete", listOf("“${file.title}” (${formatSize(file.size)}) sẽ bị xoá khỏi điện thoại và không lấy lại được."), failure) {
                            DangerButton("Xoá", { if (!busy) repo.deleteOldSave(file.name) }, "old_delete_yes")
                            QuietButton("Giữ lại", dismiss, "old_delete_keep")
                        }
                        LaunchedEffect(old) { if (old.none { it.name == file.name }) dismiss() }
                    } }, "old_delete_${file.name}")
                }
                RowLine()
            }
        }
    }
    Reveal(update != null) {
        update?.let { release ->
            ListSection("Cập nhật") {
                ActionRow("Có bản mới ${release.version}", "Tải", { env.links.openRelease(release.apk ?: release.page) }, "update_download", "Cài đè; sách và chỗ đang nghe giữ nguyên.")
            }
        }
    }
    Reveal(problem.isNotBlank()) { Caption(problem, Modifier.testTag("maintenance_problem")) }
    Reveal(notice.isNotBlank()) { Caption(notice, Modifier.testTag("maintenance_notice")) }
}
