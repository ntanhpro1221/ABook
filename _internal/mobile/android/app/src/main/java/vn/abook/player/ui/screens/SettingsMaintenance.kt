package vn.abook.player.ui.screens

import vn.abook.player.S

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
    val trial by repo.trialBuild.collectAsState()
    val problem by repo.problem.collectAsState()
    val notice by repo.notice.collectAsState()
    LaunchedEffect(repo) { repo.loadMaintenance() }
    Reveal(old.isNotEmpty()) {
        ListSection(S.s_ban_luu_cu_0_5338309c(old.size), first = true) {
            Caption(S.s_ban_truoc_cua_mot_lan_luu_hong_luu_ra_de_k_f8881db4)
            for (file in old) {
                ListItem(file.title, tag = "old_save_${file.name}", hint = dotJoin(formatSize(file.size), Fmt.whenText(file.modified / 1000.0)))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextAction(S.s_luu_ra_09838147, { env.links.saveOld(file.name) { uri -> if (uri != null) repo.exportOldSave(file.name, uri) } }, "old_export_${file.name}")
                    TextAction(S.s_xoa_777195ab, { sheets.show { dismiss ->
                        val busy by repo.maintenanceBusy.collectAsState()
                        val failure by repo.problem.collectAsState()
                        ConfirmPage(S.s_xoa_ban_luu_cu_d8966e9e, "old_delete", listOf(S.s_0_1_se_bi_xoa_khoi_dien_thoai_va_khong_lay_a827e2f0(file.title, formatSize(file.size))), failure) {
                            DangerButton(S.s_xoa_777195ab, { if (!busy) repo.deleteOldSave(file.name) }, "old_delete_yes")
                            QuietButton(S.s_giu_lai_3c3ba2db, dismiss, "old_delete_keep")
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
            ListSection(S.s_cap_nhat_5293d03c) {
                ActionRow(S.s_co_ban_moi_0_f7b3885a(release.version), S.s_tai_73be7aad, { env.links.openRelease(release.apk ?: release.page) }, "update_download", S.s_cai_de_sach_va_cho_dang_nghe_giu_nguyen_12909d3c)
            }
        }
    }
    Reveal(trial) {
        ListSection(S.s_cap_nhat_5293d03c) {
            ListRow(S.s_ban_cai_thu_2e272283, Modifier.testTag("update_trial"), S.s_ban_cai_thu_khong_cap_nhat_duoc_bang_nut_n_51ab97fe)
        }
    }
    Reveal(problem.isNotBlank()) { Caption(problem, Modifier.testTag("maintenance_problem")) }
    Reveal(notice.isNotBlank()) { Caption(notice, Modifier.testTag("maintenance_notice")) }
}
