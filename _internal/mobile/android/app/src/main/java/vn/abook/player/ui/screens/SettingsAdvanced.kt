package vn.abook.player.ui.screens

import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

import vn.abook.player.S

import vn.abook.player.formatSize

import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.devices.StorageScreen
import vn.abook.player.ui.components.ListSection
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.ListRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.IconAction
import vn.abook.player.ui.components.RefreshIcon
import vn.abook.player.ui.components.ActionRow
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.Caption
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.LazyListState
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.ConfirmPage
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.keepUrlTogether
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.ThirdParty
import vn.abook.player.ui.data.ThirdPartySection
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.components.fadeEdges
import androidx.compose.foundation.lazy.rememberLazyListState
import vn.abook.player.ui.components.Reveal

/** Lời của Chẩn đoán và Bộ nhớ. */
private object AdvancedCopy {
    const val LOG = S.s_viec_app_lam_gan_day_de_tim_loi_xem_lai_tr_52f45596
    const val LOG_NOTE = S.s_gom_thong_tin_may_nhat_ky_gan_nhat_va_ten_0cc10d61
    const val SEND = S.s_xem_lai_truoc_khi_gui_ban_tu_gui_di_755dd05a
    const val CLEAR = S.s_gom_ca_cac_lan_vang_da_ghi_42922903
    const val CLEARED = S.s_da_xoa_nhat_ky_c5522117
    /** Lời hỏi lại trước khi xoá (web: CLEAR_QUESTION ở android/Diagnostics.tsx - cùng từng chữ). */
    val CLEAR_QUESTION = S.s_nhat_ky_cua_abook_se_bi_xoa_khoi_may_nay_0_b2e35856(CLEAR)
    val SOURCE = keepUrlTogether("github.com/ntanhpro1221/ABook")

    fun cache(bytes: Long?): String = when {
        bytes == null -> S.s_dang_do_6b5cb1b4
        bytes > 0 -> S.s_ban_doc_da_lam_chiem_0_tren_may_nay_903201f2(formatSize(bytes))
        else -> S.s_chua_co_ban_doc_da_luu_18fe660f
    }

    fun clearQuestion(bytes: Long): String =
        S.s_don_0_ban_doc_da_lam_cua_moi_cuon_may_se_d_224ee5c4(formatSize(bytes))
}

/** Nâng cao: bộ nhớ (bản đọc đã làm), chẩn đoán (xem / gửi / xoá nhật ký), giới thiệu (phiên bản, mã nguồn, thành phần bên thứ ba). */
@Composable
fun AdvancedSettings(env: SettingsEnv, sheets: SheetHost, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val repo = env.repo
    val cache by repo.cache.collectAsState()
    val notice by repo.notice.collectAsState()
    LaunchedEffect(repo) { repo.loadCache() }
    SettingsPage(SettingsGroup.Advanced.label, onBack, SettingsGroup.Advanced.screenTag, modifier) {
        MaintenanceSections(env, sheets)
        Fold(S.s_bo_nho_e3d4d2b2, "advanced_memory", Modifier.padding(top = Dim.s16)) {
            env.devices?.let { StorageScreen(it, sheets, embedded = true, onBack = {}) }
            val bytes = cache
            ListRow(S.s_ban_doc_da_lam_776edb87, hint = AdvancedCopy.cache(bytes)) {
                SwapContent(bytes, contentKey = { bytes -> bytes != null && bytes > 0 }, layout = ContentLayout.Box) { bytes ->
                    if (bytes != null && bytes > 0) {
                        TextAction(S.s_don_ban_doc_5ae4774e, { sheets.show { dismiss -> ClearSheet(bytes, onClear = { repo.clearCache(); dismiss() }, dismiss) } }, "cache_clear")
                    }
                }
            }
            vn.abook.player.ui.components.MoreInfo(S.s_tim_hieu_them_032fe408, S.s_nghe_lai_doan_da_doc_xong_thi_khong_phai_c_05c920a7, "cache_more")
        }
        ListSection(S.s_chan_doan_906791d5) {
            ActionRow(S.s_nhat_ky_1e6c3c10, S.s_xem_f6de0ffd, { sheets.show { LogSheet(repo) } }, "logs_view", AdvancedCopy.LOG)
            vn.abook.player.ui.components.MoreInfo(S.s_tim_hieu_them_032fe408, AdvancedCopy.LOG_NOTE, "logs_more")
            RowLine()
            ActionRow(S.s_gui_nhat_ky_2e35a4f8, S.s_gui_0564dcf3, env.links.shareLogs, "logs_send", AdvancedCopy.SEND)
            RowLine()
            // Việc phá huỷ là hàng thường tên màu nguy hiểm (cả hàng là chỗ chạm): mỗi phần chỉ có một chữ hổ phách.
            ListItem(
                S.s_xoa_nhat_ky_743fb17f, onClick = { sheets.show { dismiss -> ClearLogsSheet({ repo.clearLogs(); dismiss() }, dismiss) } }, tag = "logs_clear", titleStyle = Abook.type.bodyStrong, titleColor = Abook.colors.danger,
                hint = if (notice == S.s_da_xoa_nhat_ky_526f2ff7) AdvancedCopy.CLEARED else AdvancedCopy.CLEAR,
            )
        }
        ListSection(S.s_gioi_thieu_0c84d33f) {
            ListRow(S.s_phien_ban_e055ec35) { BasicText(repo.version, style = Abook.type.bodySmall, modifier = Modifier.testTag("app_version")) }
            RowLine()
            ActionRow(S.s_ma_nguon_mo_mit_d9c23b48, S.s_mo_741bd2c2, env.links.openSource, "source_open", AdvancedCopy.SOURCE)
            RowLine()
            NavRow(S.s_thanh_phan_su_dung_46f70f05, { sheets.show { ThirdPartySheet(repo) } }, "third_party")
        }
    }
}

/** Hàng mở một bảng hay trang ngoài: mũi tên cuối hàng, chữ cùng cỡ với các hàng khác của màn này (tên đậm, mô tả nhỏ). */
@Composable
private fun NavRow(title: String, onClick: () -> Unit, tag: String, hint: String? = null) {
    ListItem(title, onClick = onClick, tag = tag, hint = hint, titleStyle = Abook.type.bodyStrong, chevron = true)
}

/** Hỏi lại trước khi dọn: bước xác nhận chung [ConfirmPage] - nút đỏ "Dọn", "Giữ lại" là nút chữ. */
@Composable
private fun ClearSheet(bytes: Long, onClear: () -> Unit, dismiss: () -> Unit) {
    ConfirmPage(S.s_don_ban_doc_5ae4774e, "clear_sheet", listOf(AdvancedCopy.clearQuestion(bytes)), "") {
        // Dọn bản đọc làm lại được: chữ đỏ, không nút tô đỏ cả bề ngang - nút đặc chỉ cho xoá sách (DESIGN.md §6, soát 10-11 L13).
        QuietButton(S.s_don_6730827d, onClear, "clear_confirm", danger = true)
        Spacer(Modifier.height(Dim.s8))
        QuietButton(S.s_giu_lai_3c3ba2db, dismiss, "clear_cancel")
    }
}

/** Hỏi lại trước khi xoá nhật ký (không lấy lại được): cùng bước xác nhận với mọi việc phá huỷ khác. */
@Composable
private fun ClearLogsSheet(onClear: () -> Unit, dismiss: () -> Unit) {
    ConfirmPage(S.s_xoa_nhat_ky_c85df7e1, "logs_clear_sheet", listOf(AdvancedCopy.CLEAR_QUESTION), "") {
        QuietButton(S.s_xoa_777195ab, onClear, "logs_clear_confirm", danger = true)
        Spacer(Modifier.height(Dim.s8))
        QuietButton(S.s_giu_lai_3c3ba2db, dismiss, "logs_clear_cancel")
    }
}

/** Nhật ký của ABook (500 dòng cuối, đã che như bản gửi đi): mới nhất ở dưới, cuộn sẵn tới đó; "Làm mới" đọc lại. Dòng dài xuống dòng. */
@Composable
private fun LogSheet(repo: SettingsRepo) {
    var lines by remember { mutableStateOf<List<String>?>(null) }
    var round by remember { mutableIntStateOf(0) }
    var problem by remember { mutableStateOf("") }
    LaunchedEffect(round) {
        problem = ""
        try { lines = repo.logLines() }
        catch (e: Exception) { problem = S.s_chua_doc_duoc_nhat_ky_7425c82b; lines = emptyList() }
    }
    Column(Modifier.fillMaxWidth().testTag("log_sheet")) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            BasicText(S.s_nhat_ky_cua_abook_bc72fe96, style = Abook.type.sectionTitle, modifier = Modifier.weight(1f))
            IconAction(S.s_lam_moi_b4c61340, { round++ }, "logs_refresh") { RefreshIcon(Abook.colors.text2) }
        }
        Caption(AdvancedCopy.LOG_NOTE, Modifier.padding(bottom = Dim.s8))
        vn.abook.player.ui.components.Reveal(problem.isNotEmpty()) { Caption(problem) }
        val shown = lines
        // Mỗi lần đọc một danh sách mới, mở sẵn ở dòng cuối (mới nhất) - không cuộn sau khi đã vẽ.
        val list = remember(shown) { LazyListState(shown?.lastIndex?.coerceAtLeast(0) ?: 0) }
        when {
            shown == null -> BasicText(S.s_dang_doc_nhat_ky_c001b4f7, style = Abook.type.bodySmall, modifier = Modifier.padding(vertical = Dim.s16))
            shown.isEmpty() -> BasicText(S.s_chua_co_dong_nao_88732bb0, style = Abook.type.bodySmall, modifier = Modifier.padding(vertical = Dim.s16))
            else -> LazyColumn(Modifier.fillMaxWidth().heightIn(max = 440.dp).fadeEdges(list), state = list) {
                itemsIndexed(shown, key = { index, _ -> index }, contentType = { _, _ -> "line" }) { _, line ->
                    BasicText(line, style = Abook.type.caption.copy(color = Abook.colors.text2), modifier = Modifier.padding(vertical = 4.dp))
                }
            }
        }
    }
}

/** "Thành phần sử dụng": docs/THIRD_PARTY.md (gói lúc build), mỗi mục tiêu đề + các dòng. */
@Composable
private fun ThirdPartySheet(repo: SettingsRepo) {
    var sections by remember { mutableStateOf<List<ThirdPartySection>?>(null) }
    LaunchedEffect(repo) { sections = repo.thirdParty() }
    Column(Modifier.fillMaxWidth().testTag("third_party_sheet")) {
        BasicText(S.s_thanh_phan_su_dung_46f70f05, style = Abook.type.sectionTitle)
        val shown = sections
        val list = rememberLazyListState()
        when {
            shown == null -> BasicText(S.s_dang_mo_danh_sach_7f36f104, style = Abook.type.bodySmall, modifier = Modifier.padding(vertical = Dim.s16))
            shown.isEmpty() -> BasicText(S.s_chua_mo_duoc_danh_sach_92a6ce82, style = Abook.type.bodySmall, modifier = Modifier.padding(vertical = Dim.s16))
            else -> LazyColumn(Modifier.fillMaxWidth().heightIn(max = 460.dp).fadeEdges(list), state = list) {
                for ((index, section) in shown.withIndex()) {
                    if (section.title.isNotEmpty()) {
                        item(key = "title:$index", contentType = "title") {
                            BasicText(ThirdParty.plain(section.title), style = Abook.type.label, modifier = Modifier.padding(top = Dim.s16, bottom = Dim.s4))
                        }
                    }
                    itemsIndexed(section.items, key = { line, _ -> "item:$index:$line" }, contentType = { _, _ -> "item" }) { _, item ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                            Reveal(item.bullet) { BasicText("•  ", style = Abook.type.caption.copy(color = Abook.colors.text2)) }
                            BasicText(ThirdParty.plain(item.text), style = Abook.type.caption.copy(color = Abook.colors.text2), modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        }
    }
}
