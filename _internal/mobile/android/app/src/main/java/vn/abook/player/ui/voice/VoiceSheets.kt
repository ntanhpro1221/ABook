package vn.abook.player.ui.voice

import vn.abook.player.S

import vn.abook.player.formatSize

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import vn.abook.player.ui.components.BasicText
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
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
import vn.abook.player.ui.addbook.FieldGroup
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ConfirmPage
import vn.abook.player.ui.components.DangerButton
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.DownloadIcon
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RestartIcon
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.TrashIcon
import vn.abook.player.ui.components.WorkingProgress
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.components.fadeEdges

/*
 * Các bảng trượt của Giọng đọc làm thêm: việc của một giọng đã có trên máy (kèm bước xoá), tải bằng dữ liệu di động, đồng ý gửi chữ, một khoá giọng trực tuyến
 * (nhập, lưu, kiểm tra, xoá), xoá một bài nhạc. Mọi bước xác nhận dựng bằng [ConfirmPage] - cùng một chỗ với các bảng Thiết bị.
 */

private enum class ModulePage { Actions, Remove }

/** Bảng của một lựa chọn giọng trên máy: cập nhật, đo lại tốc độ, xoá khỏi máy (bước xác nhận ngay trong bảng). `initial`: hàng bạn vừa chạm; bảng theo trạng thái sống của lõi. */
@Composable
fun ModuleSheet(kind: ModuleKind, initial: ModuleChoice, voice: VoiceState, dismiss: () -> Unit) {
    var page by remember { mutableStateOf(ModulePage.Actions) }
    BackHandler(enabled = page != ModulePage.Actions) { page = ModulePage.Actions }
    val ui by voice.modules.collectAsState()
    val status = ui.getValue(kind).status
    // Lựa chọn vừa xoá rời danh sách (hay còn phần dở): giữ bản cuối trong lúc bảng trượt xuống.
    val last = remember { arrayOf(initial) }
    status?.choice(initial.id)?.let { last[0] = it }
    val choice = last[0]
    SheetPages(page, { it.ordinal }, "module_sheet") { shown ->
        when (shown) {
            ModulePage.Actions -> ModuleActions(kind, choice, status, voice, dismiss, onRemove = { page = ModulePage.Remove })
            ModulePage.Remove -> ModuleRemove(kind, choice, voice, dismiss, onKeep = { page = ModulePage.Actions })
        }
    }
}

@Composable
private fun ModuleActions(kind: ModuleKind, choice: ModuleChoice, status: ModuleStatus?, voice: VoiceState, dismiss: () -> Unit, onRemove: () -> Unit) {
    val colors = Abook.colors
    val bench = status?.benchmark?.get(choice.id)
    Column(Modifier.fillMaxWidth()) {
        BasicText(VoiceText.choiceTitle(choice), style = Abook.type.sectionTitle)
        if (bench != null && status != null) Caption(VoiceText.benchmark(choice.id, bench, status.slowRtf), Modifier.padding(top = Dim.s4).testTag("module_benchmark"))
        Spacer(Modifier.height(Dim.s8))
        if (choice.installed && status?.state == ModuleState.Outdated) {
            MenuRow(S.s_cap_nhat_0_618a3fa3(formatSize(status.outdatedBytes)), "module_update", onClick = { voice.download(kind, null); dismiss() }) { ink -> DownloadIcon(ink) }
        }
        Reveal(choice.installed) {
            MenuRow(
                if (status?.benchmarking == true) S.s_dang_do_toc_do_d0876866 else S.s_thu_lai_toc_do_a69ef56d, "module_measure", unavailable = status?.benchmarking == true,
                onClick = { voice.measure(kind); dismiss() },
            ) { ink -> RestartIcon(ink) }
        }
        Box(Modifier.fillMaxWidth().padding(vertical = Dim.s8).height(1.dp).background(colors.line))
        MenuRow(if (choice.installed) S.s_go_giong_2f8014a9 else S.s_xoa_phan_da_tai_9f9ae26f, "module_remove", danger = true, onClick = onRemove) { ink -> TrashIcon(ink) }
    }
}

@Composable
private fun ModuleRemove(kind: ModuleKind, choice: ModuleChoice, voice: VoiceState, dismiss: () -> Unit, onKeep: () -> Unit) {
    val scope = rememberCoroutineScope()
    var working by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    val installed = choice.installed
    ConfirmPage(
        if (installed) S.s_go_0_khoi_may_nay_be8d523b(VoiceText.choiceTitle(choice)) else S.s_xoa_phan_da_tai_0e3fd01a, "module_remove_confirm",
        listOf(if (installed) VoiceText.REMOVE_ASK else S.s_phan_da_tai_do_se_bi_xoa_khoi_may_nay_4f5dc269), problem,
    ) {
        DangerButton(if (working) (if (installed) S.s_dang_go_eadfa314 else S.s_dang_xoa_71482e81) else if (installed) S.s_go_giong_2f8014a9 else S.s_xoa_phan_da_tai_9f9ae26f, {
            if (working) return@DangerButton
            working = true
            scope.launch {
                val error = voice.remove(kind, choice.id)
                working = false
                problem = error.orEmpty()
                if (error == null) dismiss()
            }
        }, "module_remove_yes")
        Spacer(Modifier.height(Dim.s8))
        QuietButton(S.s_giu_lai_3c3ba2db, onKeep, "module_remove_keep")
    }
}

/** Tải một giọng khi máy đang dùng dữ liệu di động: nói cỡ cần tải, để bạn quyết ngay lúc bấm. */
@Composable
fun MeteredSheet(text: String, onGo: () -> Unit, dismiss: () -> Unit) {
    ConfirmPage(S.s_du_lieu_di_dong_7ba9c799, "metered_confirm", listOf(text), "") {
        PrimaryButton(S.s_van_tai_b166c8ee, { onGo(); dismiss() }, Modifier.fillMaxWidth().testTag("metered_go"))
        Spacer(Modifier.height(Dim.s8))
        QuietButton(S.s_cho_wi_fi_60109e5c, dismiss, "metered_wait")
    }
}

/**
 * Bước đồng ý trước lần đầu đọc bằng giọng trực tuyến: nói chữ đi tới đâu và có thể bị tính tiền ở đâu - lời ở [VoiceText.consent]. `onAllow` chạy sau
 * khi bạn bấm "Đồng ý" (lõi nhớ, rồi việc đang chờ chạy tiếp).
 */
@Composable
fun ConsentPage(voiceName: String, provider: String, working: Boolean, onAllow: () -> Unit, onNo: () -> Unit) {
    ConfirmPage(S.s_giong_doc_truc_tuyen_44ae53c1, "consent_confirm", listOf(VoiceText.consent(voiceName, provider)), "") {
        PrimaryButton(if (working) S.s_dang_luu_e93f245d else S.s_dong_y_1246fb97, { if (!working) onAllow() }, Modifier.fillMaxWidth().testTag("consent_yes"), enabled = !working)
        Spacer(Modifier.height(Dim.s8))
        QuietButton(S.s_khong_5b3c9ba4, onNo, "consent_no")
    }
}

/** Bảng đồng ý khi chọn một giọng trực tuyến làm giọng mặc định: "Đồng ý" thì nhớ rồi chọn giọng; "Không" thì giữ giọng cũ. */
@Composable
fun ConsentSheet(voiceName: String, provider: String, allow: suspend () -> Unit, dismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var working by remember { mutableStateOf(false) }
    ConsentPage(voiceName, provider, working, onAllow = {
        working = true
        scope.launch {
            allow()
            dismiss()
        }
    }, onNo = dismiss)
}

private enum class KeyPage { Form, Consent, Remove }

private enum class KeyWork { None, Saving, Checking }

/**
 * Bảng của một nhà cung cấp giọng dùng khoá của bạn. "Lưu": chỉ cất khoá trên máy này. "Kiểm tra": lưu rồi gọi dịch vụ đọc thử một câu ngắn - chữ đi ra ngoài, nên lần đầu có bước
 * đồng ý. Khoá gõ vào ô chỉ đi xuống [VoiceState.saveKey]; ô để chấm, "Hiện" cho xem khi gõ; khoá đã lưu chỉ thấy dạng che.
 */
@Composable
fun KeySheet(initial: KeyProvider, voice: VoiceState, dismiss: () -> Unit) {
    var page by remember { mutableStateOf(KeyPage.Form) }
    BackHandler(enabled = page != KeyPage.Form) { page = KeyPage.Form }
    val ui by voice.keys.collectAsState()
    val last = remember { arrayOf(initial) }
    ui.providers.firstOrNull { it.id == initial.id }?.let { last[0] = it }
    val provider = last[0]
    val scope = rememberCoroutineScope()
    var key by remember { mutableStateOf("") }
    var region by remember { mutableStateOf(initial.regionValue) }
    var revealed by remember { mutableStateOf(false) }
    var work by remember { mutableStateOf(KeyWork.None) }
    var problem by remember { mutableStateOf("") }
    var verdict by remember { mutableStateOf("") }
    var allowing by remember { mutableStateOf(false) }

    fun check() {
        work = KeyWork.Checking
        problem = ""
        verdict = ""
        scope.launch {
            val result = voice.checkKey(provider, key, region)
            work = KeyWork.None
            key = ""
            if (result.ok) verdict = result.text else problem = result.text
        }
    }

    fun save() {
        if (work != KeyWork.None) return
        work = KeyWork.Saving
        problem = ""
        verdict = ""
        scope.launch {
            val error = voice.saveKey(provider, key, region)
            work = KeyWork.None
            problem = error.orEmpty()
            if (error == null) { key = ""; verdict = S.s_da_luu_khoa_bam_kiem_tra_de_thu_a21b7359 }
        }
    }

    val form = rememberScrollState()
    Column(Modifier.fillMaxWidth().imePadding()) {
        SheetPages(page, { it.ordinal }, "key_sheet") { shown ->
            when (shown) {
                KeyPage.Form -> Column(Modifier.fillMaxWidth().fadeEdges(form).verticalScroll(form)) {
                    BasicText(provider.name, style = Abook.type.sectionTitle)
                    vn.abook.player.ui.components.MoreInfo(S.s_nhan_khoa_7ba3a705, VoiceText.keyHelp(provider.id), "key_help")
                    Caption(if (provider.timings == "exact") S.s_to_dung_tung_chu_dang_doc_b0692da6 else S.s_to_tung_chu_dang_doc_theo_uoc_luong_b0de406b)
                    Spacer(Modifier.height(Dim.s16))
                    FieldGroup {
                        BookField(
                            null, key, { key = it; problem = ""; verdict = "" }, "key_field", work == KeyWork.None, S.s_khoa_0_7f56ecc3(provider.name),
                            placeholder = if (provider.hasKey) S.s_da_luu_0_dan_khoa_moi_de_thay_1b8b024d(provider.masked) else S.s_dan_khoa_cua_ban_c390a2e9,
                            masked = !revealed,
                            trailing = { TextAction(if (revealed) S.s_an_9c7a6c2d else S.s_hien_79d3e7eb, { revealed = !revealed }, "key_reveal") },
                        )
                        Reveal(provider.region) {
                            Spacer(Modifier.height(Dim.s8))
                            BookField(null, region, { region = it; problem = ""; verdict = "" }, "key_region", work == KeyWork.None, S.s_vung_db826aa7, placeholder = S.s_vung_vi_du_southeastasia_959965a2)
                        }
                        Reveal(work == KeyWork.Checking) {
                            Column(Modifier.fillMaxWidth().padding(top = Dim.s12).testTag("key_checking")) {
                                Caption(S.s_dang_kiem_tra_424c43e3)
                                WorkingProgress()
                            }
                        }
                        InlineProblem(problem, null, "key_problem")
                        Reveal(verdict.isNotEmpty()) {
                            BasicText(verdict, style = Abook.type.bodySmall.copy(color = Abook.colors.success), modifier = Modifier.padding(top = Dim.s8).testTag("key_verdict"))
                        }
                        Spacer(Modifier.height(Dim.s24))
                        PrimaryButton(
                            if (work == KeyWork.Saving) S.s_dang_luu_e93f245d else S.s_luu_e91f26c0, ::save, Modifier.fillMaxWidth().testTag("key_save"),
                            enabled = work == KeyWork.None && (key.isNotBlank() || (provider.region && region.trim() != provider.regionValue)),
                        )
                        Spacer(Modifier.height(Dim.s8))
                        QuietButton(S.s_kiem_tra_ff6e2891, {
                            if (work != KeyWork.None) return@QuietButton
                            if (key.isBlank() && !provider.hasKey) {
                                problem = S.s_dan_khoa_truoc_da_d88da35d
                            } else if (voice.allowed(provider.id)) {
                                check()
                            } else {
                                page = KeyPage.Consent
                            }
                        }, "key_check")
                    }
                    Reveal(provider.hasKey) {
                        Box(Modifier.fillMaxWidth().padding(vertical = Dim.s8).height(1.dp).background(Abook.colors.line))
                        MenuRow(S.s_xoa_khoa_2ec6cb1a, "key_remove", danger = true, onClick = { page = KeyPage.Remove }) { ink -> TrashIcon(ink) }
                    }
                }
                KeyPage.Consent -> ConsentPage(S.s_nay_13127283, provider.id, allowing, onAllow = {
                    allowing = true
                    scope.launch {
                        voice.allow(provider.id)
                        allowing = false
                        page = KeyPage.Form
                        check()
                    }
                }, onNo = { page = KeyPage.Form })
                KeyPage.Remove -> RemoveKeyPage(provider, voice, dismiss, onKeep = { page = KeyPage.Form })
            }
        }
    }
}

@Composable
private fun RemoveKeyPage(provider: KeyProvider, voice: VoiceState, dismiss: () -> Unit, onKeep: () -> Unit) {
    val scope = rememberCoroutineScope()
    var working by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    ConfirmPage(
        S.s_xoa_khoa_4f5ee78b, "key_remove_confirm",
        listOf(S.s_khoa_0_se_bi_xoa_khoi_may_nay_va_cac_giong_735b6db2(provider.name)), problem,
    ) {
        DangerButton(if (working) S.s_dang_xoa_71482e81 else S.s_xoa_khoa_2ec6cb1a, {
            if (working) return@DangerButton
            working = true
            scope.launch {
                val error = voice.removeKey(provider)
                working = false
                problem = error.orEmpty()
                if (error == null) dismiss()
            }
        }, "key_remove_yes")
        Spacer(Modifier.height(Dim.s8))
        QuietButton(S.s_giu_lai_3c3ba2db, onKeep, "key_remove_keep")
    }
}

/** Xoá một bài khỏi Nhạc của tôi: nói bài nào, nút đỏ "Xoá bài", nút chữ "Giữ lại"; lỗi hiện tại chỗ. */
@Composable
fun TrackSheet(track: MusicTrack, voice: VoiceState, dismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var working by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    ConfirmPage(S.s_xoa_bai_nay_412d7001, "track_confirm", listOf(S.s_0_se_bi_xoa_khoi_nhac_cua_toi_a41656b0(track.title)), problem) {
        DangerButton(if (working) S.s_dang_xoa_71482e81 else S.s_xoa_bai_d554a496, {
            if (working) return@DangerButton
            working = true
            scope.launch {
                val error = voice.removeTrack(track.link)
                working = false
                problem = error.orEmpty()
                if (error == null) dismiss()
            }
        }, "track_yes")
        Spacer(Modifier.height(Dim.s8))
        QuietButton(S.s_giu_lai_3c3ba2db, dismiss, "track_keep")
    }
}
