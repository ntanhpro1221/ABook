package vn.abook.player.ui.voice

import vn.abook.player.S

import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import vn.abook.player.readaloud.MachineVoicePick
import vn.abook.player.readaloud.EnginePickStatus
import vn.abook.player.readaloud.EngineNumbers
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ListSection
import vn.abook.player.ui.components.ListRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.data.dotJoin
import vn.abook.player.ui.data.dotJoined
import java.util.Locale
import vn.abook.player.ui.components.Reveal

@Composable
fun VoicePickCard(voice: VoiceState) {
    val status by voice.pick.collectAsState()
    ListSection(S.s_giong_theo_may_bc8b9fff) {
        Caption(EnginePickText.headline(status))
        for (engine in status.installed) {
            val row = status.engines.firstOrNull { it.engine == engine }
            val chosen = engine == status.chosen
            val badge = when {
                chosen -> if (status.override.isEmpty()) S.s_may_chon_4329a3f3 else S.s_ban_chon_1c143e0b
                row == null -> S.s_chua_thu_d168d4a9
                row.verdict == "error" -> S.s_loi_e68991b7
                row.verdict == "slow" -> S.s_cham_6ddeaddc
                row.verdict == "unclear" -> S.s_chua_ro_be464a5a
                else -> ""
            }
            val numbers = EnginePickText.numbers(row)
            ListRow(dotJoin(MachineVoicePick.name(engine), badge), hint = numbers) {
                Reveal(!chosen && !status.measuring) { TextAction(S.s_dung_giong_nay_903b57aa, { voice.choosePick(engine) }, "voice_pick_$engine") }
            }
        }
        Reveal(status.engines.isNotEmpty()) { Caption(S.s_cung_vai_cau_cho_moi_giong_chua_co_bo_nghe_e6bb15d4) }
        Reveal(status.installed.isNotEmpty() && !status.measuring) {
            Column {
                TextAction(if (status.engines.isEmpty()) S.s_thu_77e1c0d9 else S.s_thu_lai_c58d068c, voice::measurePick, "voice_pick_measure")
                Reveal(status.override.isNotEmpty()) { TextAction(S.s_theo_so_do_f3663b51, { voice.choosePick("") }, "voice_pick_auto") }
            }
        }
    }
}

object EnginePickText {
    private fun number(value: Double) = vn.abook.player.UiNumber.decimal(value, 1, fixed = true)

    fun headline(status: EnginePickStatus): String {
        if (status.measuring) return S.s_dang_thu_cac_giong_872881f6
        if (status.error.isNotEmpty()) return status.error
        if (status.installed.isEmpty()) return S.s_chua_co_giong_nao_tren_may_tai_mot_bo_gion_7bdc8937
        if (status.engines.isEmpty()) return S.s_may_chua_thu_cac_giong_bam_thu_de_may_chon_f3ae77fe
        val chosen = status.chosen?.takeIf { it.isNotEmpty() }?.let(MachineVoicePick::name)
        val who = if (status.override.isNotEmpty()) S.s_ban_chon_bfffd506 else S.s_may_chon_theo_so_do_f4a15e17
        return if (chosen != null) S.s_sach_chua_chon_giong_doc_bang_0_1_e09ed89f(chosen, who)
            else S.s_chua_giong_nao_tren_may_vua_ro_vua_kip_doc_0bb2767a
    }

    fun numbers(row: EngineNumbers?): String {
        if (row == null) return S.s_chua_thu_tren_may_nay_db7eeae5
        if (row.verdict == "error") return if (row.error.isEmpty()) S.s_thu_khong_duoc_07616f5a else S.s_thu_khong_duoc_0_bf5f8af8(row.error)
        val clarity = row.cer?.let { S.s_ro_0_68776af2(kotlin.math.round((1 - it) * 100).toInt()) } ?: S.s_do_ro_chua_do_0986efe7
        val natural = row.natural?.let { S.s_tu_nhien_0_5_876223ac(number(it)) } ?: S.s_tu_nhien_chua_do_3eaed012
        val speed = row.rtf?.let {
            if (it >= MachineVoicePick.LIVE_RTF) S.s_cham_0_giay_cho_moi_giay_nghe_3439900c(number(it)) else S.s_nhanh_gap_0_lan_fd951c7d(number(1 / maxOf(it, 0.01)))
        }
        return listOfNotNull(clarity, natural, speed, row.ramMb?.let { S.s_ram_dinh_0_mb_077d5736(it) }).dotJoined()
    }
}
