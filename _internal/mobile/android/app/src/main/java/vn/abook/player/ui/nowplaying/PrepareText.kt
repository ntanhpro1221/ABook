package vn.abook.player.ui.nowplaying

import vn.abook.player.S

import vn.abook.player.ui.data.PlayerChapter
import vn.abook.player.ui.data.PreparePlan
import vn.abook.player.ui.data.PrepareStatus
import vn.abook.player.ui.data.dotJoin

/**
 * Chữ của "Làm trước" (web: listen/prepareAhead.ts): câu mời, ước trước khi bấm, tiến độ - nói theo cái người nghe cần biết (còn bao lâu, đang chờ gì).
 * Hàm thuần - thử trên JVM (PrepareTextTest). Giọng trực tuyến nói rõ chữ sẽ được gửi tới đâu trước khi bạn bắt đầu.
 */
object PrepareText {
    /** Tối đa bao nhiêu chương tới được làm trước một lần (như web). */
    const val LIMIT = 5

    /** Cái lợi khi làm trước bằng giọng chạy trên máy. */
    private const val GAIN = S.s_nghe_lien_mach_khong_can_cho_35e14b83

    const val INTRO = S.s_may_doc_cham_lam_truoc_de_nghe_lien_mach_42dca0d0
    const val OTHER_JOB = S.s_dang_lam_truoc_cho_mot_cuon_hay_giong_khac_31f0b03e

    /** Giọng nào có "Làm trước": giọng tải về đọc trên máy (VieNeu, Supertonic - chậm hơn tốc độ nghe trên máy yếu). Giọng của máy đã đọc nhanh. */
    fun canPrepare(voiceId: String): Boolean = voiceId.startsWith("vieneu:") || voiceId.startsWith("supertonic:") ||
        vn.abook.player.ui.voice.VoiceText.isOnline(voiceId.substringBefore(':'))

    fun intro(voiceId: String): String {
        val provider = voiceId.substringBefore(':')
        if (!vn.abook.player.ui.voice.VoiceText.isOnline(provider)) return INTRO
        val destination = S.s_chu_se_duoc_gui_toi_0_362780c4(vn.abook.player.ui.voice.VoiceText.destination(provider))
        return S.s_lam_truoc_de_nghe_khi_khong_co_mang_0_3cd15943(destination)
    }

    /** Các chương chỉ-có-chữ ngay sau chương đang nghe (tối đa [limit]). */
    fun upcoming(chapters: List<PlayerChapter>, currentId: Int?, limit: Int = LIMIT): List<PlayerChapter> {
        val at = chapters.indexOfFirst { it.id == currentId }
        return chapters.drop(at + 1).filter { it.textPath.isNotEmpty() }.take(limit)
    }

    /** Tên việc gửi cho lõi: một chương thì tên chương, nhiều thì "N chương tới". */
    fun jobLabel(upcoming: List<PlayerChapter>): String = if (upcoming.size == 1) upcoming[0].title else S.s_0_chuong_toi_8b81be6f(upcoming.size)

    /** Nút bắt đầu: "Làm trước chương sau" / "Làm trước N chương". */
    fun startLabel(count: Int): String = if (count == 1) S.s_lam_truoc_chuong_sau_38defcbd else S.s_lam_truoc_0_chuong_08803833(count)

    /** "khoảng 1 giờ 20 phút", "khoảng 12 phút", "dưới 1 phút". */
    fun spokenDuration(seconds: Long): String {
        val minutes = Math.round(seconds / 60.0)
        if (minutes < 1) return S.s_duoi_1_phut_a1dd4f60
        if (minutes < 60) return S.s_khoang_0_phut_db610fec(minutes)
        val hours = minutes / 60
        val rest = minutes % 60
        return S.s_khoang_0_gio_c8a2f008(hours) + if (rest > 0) S.s_0_phut_1bea6774(rest) else ""
    }

    /** Câu ước trước khi bấm: "Khoảng 2 giờ nghe · máy cần khoảng 1 giờ 50 phút." (rỗng khi không chương nào nhận). */
    fun planLabel(plan: PreparePlan): String {
        if (plan.chapters == 0) return ""
        val listen = spokenDuration(plan.audioSeconds).removePrefix(S.s_khoang_934859d7) + " nghe"
        val machine = plan.secondsEstimate?.let { S.s_may_can_768870db + spokenDuration(it) }.orEmpty()
        val fits = if (plan.chapters < plan.offered) S.s_vua_cho_trong_cho_0_chuong_6f9821bd(plan.chapters) else ""
        return (fits + listen + machine + ".").replaceFirstChar { it.uppercase() }
    }

    /** Vì sao việc chưa chạy lúc này. */
    fun waiting(reason: String): String = when (reason) {
        "charging" -> S.s_cho_cam_sac_2dc75384
        "wifi" -> S.s_cho_wi_fi_d0476dd8
        "battery" -> S.s_cho_pin_day_hon_d715a386
        "listening" -> S.s_nhuong_cho_chuong_dang_nghe_93babd54
        else -> ""
    }

    /** Câu nói tiến độ của việc đang có (rỗng khi chưa có việc nào). */
    fun label(status: PrepareStatus): String {
        val what = status.label.ifEmpty { S.s_cac_chuong_toi_536a96b8 }
        val listen = if (status.audioSeconds > 0) " (" + spokenDuration(status.audioSeconds).removePrefix(S.s_khoang_934859d7) + " nghe)" else ""
        val chapters = status.chapters
        val ready = chapters?.let { S.s_da_san_sang_0_1_chuong_06edeb48(it.count { chapter -> chapter.ready }, it.size) }.orEmpty()
        return when (status.state) {
            "running" -> {
                if (chapters != null) {
                    dotJoin(ready, status.waitingFor?.let { waiting(it) } ?: status.secondsLeft?.let { S.s_con_c697bae9 + spokenDuration(it) })
                } else {
                    val left = status.secondsLeft?.let { S.s_con_5f606d44 + spokenDuration(it) }.orEmpty()
                    S.s_dang_lam_truoc_0_1_2_3_doan_4_b696b41e(what, listen, status.done, status.total, left)
                }
            }
            "done" -> {
                val partial = if (status.offered > status.total) S.s_phan_con_lai_lam_tiep_khi_ban_nghe_toi_a3c9e257 else ""
                if (chapters != null && chapters.any { !it.ready }) S.s_0_phan_con_lai_lam_tiep_khi_ban_nghe_toi_d5f3d6f8(ready)
                else S.s_da_lam_truoc_0_1_2_3_fc3aa7ee(what, listen, if (status.online) S.s_nghe_duoc_ca_khi_khong_co_mang_9308f988 else GAIN, partial)
            }
            "error" -> status.error.ifEmpty { S.s_lam_truoc_bi_dung_9e573747 }
            "cancelled" -> if (chapters != null) S.s_da_dung_lam_truoc_0_1_786d6dfb(ready.take(1).lowercase(), ready.drop(1)) else S.s_da_dung_lam_truoc_3658da6b
            else -> ""
        }
    }

    /** Việc đang có là của cuốn + giọng này (web: `mine`). */
    fun mine(status: PrepareStatus, voiceId: String, bookId: String?): Boolean =
        status.state != "idle" && status.voice == voiceId && (status.bookId.isEmpty() || status.bookId == bookId)
}
