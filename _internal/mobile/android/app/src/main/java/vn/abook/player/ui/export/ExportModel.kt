package vn.abook.player.ui.export

import vn.abook.player.S

import vn.abook.player.ui.data.dotJoined
import vn.abook.player.formatSize

import androidx.compose.runtime.Immutable
import org.json.JSONObject
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.voice.VoiceText

/*
 * Mô hình và chữ của màn Xuất sách (viết lại bằng Kotlin từ ui/src/android/ExportMp3|ExportM4b|ExportAudiobook.tsx, desktop/listenExport.ts và
 * desktop/bookFileExport.ts, mang theo ca test của chúng - ExportModelTest). Không Android, không Compose ngoài chú thích @Immutable: thử được trên JVM.
 */

/** Ba kiểu xuất của lõi; `wire` là `kind` trong tin của [vn.abook.player.ExportLive]. */
enum class ExportKind(val wire: String) {
    Mp3("mp3"), M4b("m4b"), Audiobook("audiobook");

    companion object {
        fun of(wire: String): ExportKind? = entries.firstOrNull { it.wire == wire }
    }
}

/** Hai dạng file người nghe chọn cho sách đã có tiếng. Sách chỉ có chữ chỉ có M4B (máy đọc cả cuốn rồi ghép), nên không có lựa chọn. */
enum class ExportFormat(override val key: String, override val label: String) : Choice {
    Mp3("mp3", S.s_mp3_theo_chuong_a08d3a89), M4b("m4b", S.s_m4b_ca_cuon_2cba5ce9);

    fun kind(textOnly: Boolean): ExportKind = if (textOnly) ExportKind.Audiobook else if (this == Mp3) ExportKind.Mp3 else ExportKind.M4b
}

/** Ô "Kèm nhạc nền" của cuốn: có kế hoạch nhạc không (không thì không hiện ô), mặc định của ô theo công tắc Nhạc nền của cuốn. */
@Immutable
data class ExportMusic(val available: Boolean = false, val enabled: Boolean = false)

/** Giọng đang chọn cho cuốn chỉ có chữ: `caption` là tên như người nghe gọi; `provider` / `online` cho lời báo chữ đi đâu. */
@Immutable
data class ExportVoice(val id: String, val caption: String, val provider: String, val online: Boolean)

/** Ước của lượt xuất sách nói ([vn.abook.player.ExportStart.audiobookPlan]). */
@Immutable
data class AudiobookPlan(
    val chapters: Int,
    val audioSeconds: Long,
    val secondsEstimate: Long?,
    val readyChapters: Int,
    val readySeconds: Long,
    val bytes: Long,
    val rereads: Int,
    val music: ExportMusic,
)

/** Một bản đã xuất trước đây của cuốn ([vn.abook.player.ExportHistory.view]): `changed` = các chương đã đổi từ lúc ấy. */
@Immutable
data class PastExport(val kind: ExportKind, val target: String, val changed: List<Int>) {
    val stale: Boolean get() = changed.isNotEmpty()
}

/** Máy cho ABook chạy nền chưa ([vn.abook.player.Devices.backgroundView]): hãng máy để chỉ đường trong Cài đặt. */
@Immutable
data class BackgroundView(val manufacturer: String, val allowed: Boolean)

/** Lượt vừa bắt đầu: mã lượt (tin của lượt mang mã này), nơi lưu và số chương lõi báo ngay. */
@Immutable
data class Started(val run: String, val folder: String? = null, val name: String? = null, val chapters: Int? = null)

/** Một tin của lượt xuất (tiến độ, xong, dừng, lỗi) - các trường của ba kiểu gộp chung; trường không có là null. */
@Immutable
data class ExportEvent(
    val kind: ExportKind,
    val bookId: String,
    val run: String,
    val phase: String? = null,
    val done: Int? = null,
    val total: Int? = null,
    val percent: Int? = null,
    val chapter: Int? = null,
    val chapters: Int? = null,
    val secondsLeft: Long? = null,
    val waiting: String? = null,
    val peakRound: Int? = null,
    val peakOver: Int? = null,
    val finished: Boolean = false,
    val stopped: Boolean = false,
    val error: String? = null,
    val files: Int? = null,
    val chaptersTotal: Int? = null,
    val folder: String? = null,
    val uri: String? = null,
    val name: String? = null,
    val size: Long? = null,
    val selection: Boolean = false,
    val musicMissing: Int? = null,
    val music: Boolean = false,
) {
    /** Tin cuối của lượt (xong, dừng hay lỗi): không còn tiến độ nữa. */
    val ended: Boolean get() = finished || stopped || error != null
}

object ExportJson {
    private fun JSONObject.text(key: String): String? = if (isNull(key) || !has(key)) null else optString(key).takeIf { it.isNotEmpty() }
    private fun JSONObject.int(key: String): Int? = if (isNull(key) || !has(key)) null else optInt(key)
    private fun JSONObject.long(key: String): Long? = if (isNull(key) || !has(key)) null else optLong(key)

    /** Tin của lõi (JSON của [vn.abook.player.ExportLive]); `kind` rỗng hay lạ thì thôi - null. */
    fun event(json: JSONObject, kind: ExportKind? = null): ExportEvent? {
        val which = kind ?: ExportKind.of(json.optString("kind")) ?: return null
        val run = json.optString("run")
        if (run.isEmpty()) return null
        return ExportEvent(
            kind = which, bookId = json.optString("bookId"), run = run, phase = json.text("phase"),
            done = json.int("done"), total = json.int("total"), percent = json.int("percent"), chapter = json.int("chapter"), chapters = json.int("chapters"),
            secondsLeft = json.long("secondsLeft"), waiting = json.text("waiting"), peakRound = json.int("peakRound"), peakOver = json.int("peakOver"),
            finished = json.optBoolean("finished"), stopped = json.optBoolean("stopped"), error = json.text("error"),
            files = json.int("files"), chaptersTotal = json.int("chaptersTotal"), folder = json.text("folder"), uri = json.text("uri"),
            name = json.text("name"), size = json.long("size"), selection = json.optBoolean("selection"), musicMissing = json.int("musicMissing"),
            music = json.optBoolean("music"),
        )
    }

    fun music(json: JSONObject?): ExportMusic = ExportMusic(json?.optBoolean("available") ?: false, json?.optBoolean("enabled") ?: false)

    fun plan(json: JSONObject): AudiobookPlan = AudiobookPlan(
        chapters = json.optInt("chapters"), audioSeconds = json.optLong("audioSeconds"), secondsEstimate = json.long("secondsEstimate"),
        readyChapters = json.optInt("readyChapters"), readySeconds = json.optLong("readySeconds"), bytes = json.optLong("bytes"), rereads = json.optInt("rereads"),
        music = music(json.optJSONObject("music")),
    )

    fun past(json: JSONObject): PastExport? {
        val kind = ExportKind.of(json.optString("kind")) ?: return null
        val changed = json.optJSONArray("changed")?.let { array -> (0 until array.length()).map { array.optInt(it) } }.orEmpty()
        return PastExport(kind, json.optString("target"), changed)
    }
}

/** Tiến độ một lượt: dòng chữ, lời cho trình đọc màn hình (chỉ đổi khi đổi pha hay qua mốc 25 %), và phần đã xong 0..1 (null = chưa biết). */
@Immutable
data class ExportProgress(val text: String = "", val spoken: String = "", val fraction: Float? = null)

/** Kết quả một lượt xong: tiêu đề, các dòng nói gì đã ghi, các lưu ý (thiếu chương / nhạc), và nơi mở / gửi được. */
@Immutable
data class ExportResult(
    val kind: ExportKind,
    val title: String,
    val lines: List<String>,
    val notes: List<String>,
    /** File vừa xuất (M4B, sách nói) hay thư mục MP3: để Mở / Gửi. */
    val uri: String?,
    /** Thư mục MP3 (tên người nghe đọc được), để nói đường đi khi máy không mở được. */
    val folder: String? = null,
)

/** Chữ của màn Xuất. Mọi hàm thuần. */
object ExportText {
    // ---- thời lượng, ước ------------------------------------------------------------------------------------------------

    /** "khoảng 1 giờ 20 phút", "khoảng 12 phút", "dưới 1 phút" (prepareAhead.ts `spokenDuration`). */
    fun spokenDuration(seconds: Long): String {
        val minutes = Math.round(seconds / 60.0).toInt()
        if (minutes < 1) return S.s_duoi_1_phut_a1dd4f60
        if (minutes < 60) return S.s_khoang_0_phut_db610fec(minutes)
        val hours = minutes / 60
        val rest = minutes % 60
        return S.s_khoang_0_gio_1_7ba17859(hours, if (rest != 0) S.s_0_phut_1bea6774(rest) else "")
    }

    /** Dòng nói sách dài bao nhiêu và máy cần bao lâu: "12 chương · khoảng 8 giờ nghe · máy cần khoảng 2 giờ 10 phút." */
    fun planText(plan: AudiobookPlan): String {
        val machine = plan.secondsEstimate?.let { S.s_may_can_0_6e7b3653(spokenDuration(it)) }.orEmpty()
        return S.s_0_chuong_1_nghe_2_7610a1f8(plan.chapters, spokenDuration(plan.audioSeconds), machine)
    }

    /** Nói phần nào đã có sẵn (đã nghe, đã làm trước, lần xuất trước); tính theo phần nghe đã có trên cả cuốn, không đếm chương đủ. */
    fun resumeText(plan: AudiobookPlan): String {
        if (plan.chapters > 0 && plan.readyChapters >= plan.chapters) return S.s_da_doc_san_ca_cuon_chi_con_ghep_thanh_file_d6e392df
        if (plan.readySeconds >= 60 && plan.audioSeconds > 0) {
            // Chưa đủ cả cuốn thì không nói 100% (quãng lặng giữa đoạn, làm tròn).
            val percent = Math.round(plan.readySeconds * 100.0 / plan.audioSeconds).toInt().coerceIn(1, 99)
            return S.s_da_doc_san_khoang_0_phan_nay_xuat_ngay_kho_6b951d4f(percent)
        }
        return ""
    }

    /** Chỗ trống cần trong máy lúc làm (file tạm, xoá khi xong). */
    fun spaceText(plan: AudiobookPlan): String = S.s_luc_lam_can_khoang_0_trong_trong_dien_thoa_95d36302(formatSize(plan.bytes))

    /** Lượt kèm nhạc dài (trên 20 chương) tốn pin đáng kể: gợi ý cắm sạc, không chặn. Rỗng khi không cần. */
    fun chargerHint(music: Boolean, chapters: Int): String = if (music && chapters > 20) S.s_cuon_dai_nen_cam_sac_trong_luc_lam_tron_nh_abda88ea else ""

    /** "12 đoạn phải đọc lại" khi đổi nhạc nền buộc ghép lại chương đã làm mà bản đọc của đoạn ấy không còn trong máy; rỗng khi không có. */
    fun rereadText(plan: AudiobookPlan): String =
        if (plan.rereads > 0) S.s_0_doan_phai_doc_lai_vi_doi_nhac_nen_ban_do_43436550(plan.rereads) else ""

    /** Chữ của giọng trực tuyến gửi CẢ CUỐN ra ngoài máy; rỗng khi giọng chạy trên máy. */
    fun wholeBookNotice(voice: ExportVoice): String {
        if (!voice.online) return ""
        VoiceText.KEYED[voice.provider]?.let { return S.s_chu_cua_ca_cuon_duoc_gui_toi_0_de_doc_bang_1e9d8dd0(it) }
        if (voice.provider == "edge") return S.s_chu_cua_ca_cuon_duoc_gui_toi_may_chu_micro_301f6ec7
        return S.s_chu_cua_ca_cuon_duoc_gui_toi_dich_vu_ngoai_a88c44d1
    }

    /** Chỉ đường trong trang cài đặt mở ra, theo hãng máy (backgroundHelp.ts). */
    fun backgroundHelp(manufacturer: String): String {
        val maker = manufacturer.trim().lowercase()
        return when {
            maker in setOf("oppo", "realme", "oneplus") -> S.s_trong_trang_mo_ra_pin_bat_cho_phep_hoat_do_32b8dd5a
            maker in setOf("xiaomi", "redmi", "poco") -> S.s_trong_trang_mo_ra_tiet_kiem_pin_chon_khong_cf948322
            maker == "samsung" -> S.s_trong_trang_mo_ra_pin_chon_khong_han_che_20bf23a6
            else -> S.s_trong_trang_mo_ra_pin_chon_khong_han_che_h_8ca81aa3
        }
    }

    // ---- tiến độ --------------------------------------------------------------------------------------------------------

    /** Mốc đã qua của phần đã xong (0-1): 0, 25, 50, 75, 100 (progressSpeech.ts). */
    fun milestone(fraction: Float?): Int? = fraction?.takeIf { it.isFinite() }?.let { (Math.floor(it.coerceIn(0f, 1f) * 4.0).toInt()) * 25 }

    /** "Đang tải nhạc nền · 50%": pha + mốc 25 %; chưa qua mốc đầu thì chỉ nói pha ("· 0%" cạnh số thật trên màn là hai số mâu thuẫn). */
    fun spokenProgress(phase: String, fraction: Float?): String {
        val at = milestone(fraction)
        return if (at == null || at == 0) phase else "$phase · $at%"
    }

    private fun again(event: ExportEvent): String =
        if ((event.peakOver ?: 0) > 0) S.s_ma_hoa_lai_vi_0_chuong_vuot_dinh_luot_1_04047057(event.peakOver, event.peakRound ?: 1) else ""

    /** Việc tự báo tiến độ theo pha (bookFileExport.ts `reportedProgress`): chữ + phần đã xong + lời đọc; không báo thì null. */
    private fun reported(event: ExportEvent): ExportProgress? {
        val total = event.total ?: 0
        if (event.phase == "music-fetch" && total > 0) {
            val done = event.done ?: 0
            val fraction = done.toFloat() / total
            return ExportProgress(S.s_dang_tai_nhac_nen_0_1_bai_2a186c13(minOf(done + 1, total), total), spokenProgress(S.s_dang_tai_nhac_nen_0b8c4795, fraction), fraction)
        }
        if (event.phase == "peaks") return ExportProgress(S.s_dang_kiem_dinh_am_fddf3cc5, S.s_dang_kiem_dinh_am_fddf3cc5, 1f)
        val retry = again(event)
        if (event.phase == "reencode") return ExportProgress(retry, retry, 1f)
        val chapter = event.chapter ?: return null
        val chapters = event.chapters?.takeIf { it > 0 } ?: return null
        val where = S.s_chuong_0_1_7e729467(chapter, chapters)
        when (event.phase) {
            "encode" -> return ExportProgress(if (retry.isNotEmpty()) "$retry · $where" else S.s_dang_ghep_file_am_thanh_0_a01e1ed9(where), retry.ifEmpty { S.s_dang_ghep_file_am_thanh_c3a409b3 }, 1f)
            "chapters" -> {
                val fraction = (chapter - 1f) / chapters
                return ExportProgress(S.s_dang_ghi_chuong_0_1_41650b16(chapter, chapters), spokenProgress(S.s_dang_xuat_mp3_99b61b74, fraction), fraction)
            }
            "music" -> {
                val text = S.s_dang_tron_nhac_chuong_0_1_1216281a(chapter, chapters)
                val fraction = event.percent?.let { it / 100f } ?: ((chapter - 1f) / chapters)
                return ExportProgress(if (retry.isNotEmpty()) "$retry · $text" else text, retry.ifEmpty { spokenProgress(S.s_dang_tron_nhac_nen_97fb2b7d, fraction) }, fraction)
            }
        }
        val parts = mutableListOf(where, "${event.percent ?: 0}%")
        when {
            event.waiting == "listening" -> parts += S.s_nhuong_cho_chuong_dang_nghe_93babd54
            event.waiting == "network" -> parts += S.s_dang_cho_mang_4e41560e
            event.secondsLeft != null -> parts += S.s_con_0_46699fed(spokenDuration(event.secondsLeft))
        }
        val fraction = (event.percent ?: 0) / 100f
        val spoken = when (event.waiting) {
            "listening" -> S.s_tam_nhuong_cho_chuong_dang_nghe_258d655c
            "network" -> S.s_mat_mang_dang_cho_mang_ve_de_lam_tiep_34393630
            else -> spokenProgress(S.s_dang_xuat_0_chuong_46b78449(chapters), fraction)
        }
        return ExportProgress(parts.dotJoined(), spoken, fraction)
    }

    /** Tiến độ của một tin: MP3 / M4B có "3/10 chương · 27%" lúc đang làm, trước tin đầu chỉ có số chương; sách nói thêm "nhường cho chương đang nghe", "còn 2 giờ"... */
    fun progress(event: ExportEvent, chapters: Int = 0): ExportProgress {
        reported(event)?.let { return it }
        val total = event.total ?: 0
        if (total <= 0) {
            val text = if (chapters > 0) S.s_0_chuong_04093412(chapters) else S.s_dang_chuan_bi_597acedb
            return ExportProgress(text, text, null)
        }
        val done = event.done ?: 0
        val percent = event.percent?.let { " · ${it.coerceIn(0, 99)}%" }.orEmpty()
        val fraction = event.percent?.let { it / 100f } ?: (done.toFloat() / total)
        return ExportProgress(S.s_0_1_chuong_2_1cd18526(done, total, percent), spokenProgress(busy(event.kind), fraction), fraction)
    }

    /** Dòng đầu của lượt vừa bắt đầu, trước tin tiến độ đầu tiên. */
    fun starting(kind: ExportKind, chapters: Int): ExportProgress =
        if (kind == ExportKind.Audiobook) ExportProgress(S.s_chuong_1_0_0_2a765294(chapters), S.s_dang_lam_sach_noi_99820a05, 0f)
        else progress(ExportEvent(kind, "", ""), chapters)

    /** Tên việc đang làm, một tiêu đề cho cả ba kiểu. */
    fun busy(kind: ExportKind): String = when (kind) {
        ExportKind.Mp3 -> S.s_dang_xuat_mp3_99b61b74
        ExportKind.M4b -> S.s_dang_lam_file_m4b_4a95b4ac
        ExportKind.Audiobook -> S.s_dang_lam_sach_noi_99820a05
    }

    // ---- kết thúc -------------------------------------------------------------------------------------------------------

    private fun missingChapters(event: ExportEvent): String {
        val chapters = event.chapters ?: event.files
        val total = event.chaptersTotal
        return if (chapters != null && total != null && chapters < total) S.s_0_1_chuong_chuong_chua_xong_khong_co_trong_35795edf(chapters, total) else ""
    }

    private fun musicMissing(event: ExportEvent): String =
        event.musicMissing?.takeIf { it > 0 }?.let { S.s_0_doan_thieu_nhac_vi_chua_tai_duoc_bai_66255efe(it) } ?: ""

    /** Kết quả "xong": MP3 nói số chương và thư mục; M4B / sách nói nói tên file và cỡ; lưu ý khi còn chương chưa làm xong hay thiếu nhạc. */
    fun finished(event: ExportEvent): ExportResult {
        if (event.kind == ExportKind.Mp3) {
            val files = event.files ?: 0
            val partial = if (!event.selection && files < (event.chaptersTotal ?: 0)) S.s_cac_chuong_chua_lam_xong_se_khong_co_trong_5186bdb4 else ""
            val lost = event.musicMissing?.takeIf { it > 0 }?.let { S.s_0_doan_thieu_nhac_vi_chua_tai_duoc_bai_3011f095(it) }.orEmpty()
            return ExportResult(
                event.kind, S.s_da_xuat_0_chuong_8de90dcc(files), listOfNotNull(event.folder?.let { S.s_vao_0_55d7d040(it) }),
                listOf(partial, lost).filter { it.isNotEmpty() }, event.uri, event.folder,
            )
        }
        val title = if (event.kind == ExportKind.Audiobook) S.s_da_xuat_sach_noi_82ff590c else S.s_da_xuat_m4b_76947b3a
        val lines = listOfNotNull(event.name, event.size?.takeIf { it > 0 }?.let { formatSize(it) })
        val notes = listOf(missingChapters(event), musicMissing(event)).filter { it.isNotEmpty() }
        return ExportResult(event.kind, title, listOf(lines.dotJoined()).filter { it.isNotEmpty() }, notes, event.uri)
    }

    /** Lượt dừng: điều còn lại sau khi dừng, theo kiểu xuất. */
    fun stoppedNote(event: ExportEvent): String = when (event.kind) {
        ExportKind.Mp3 -> S.s_0_chuong_da_ghi_902bdff1(event.files ?: 0)
        ExportKind.M4b -> S.s_file_do_da_xoa_3d5d9f52
        ExportKind.Audiobook -> S.s_phan_da_lam_duoc_giu_xuat_lai_de_lam_tiep_5da9523a
    }

    /** Tiêu đề khi dừng, cùng chữ với thông báo của bản web (ExportMp3 / ExportM4b / listenExport.ts). */
    fun stoppedTitle(kind: ExportKind): String = when (kind) {
        ExportKind.Mp3, ExportKind.M4b, ExportKind.Audiobook -> S.s_da_dung_xuat_ab8ac9d1
    }

    /** Tiêu đề khi lỗi, cùng chữ với bản web. */
    fun failedTitle(kind: ExportKind): String = when (kind) {
        ExportKind.Mp3 -> S.s_chua_xuat_duoc_mp3_1550e65a
        ExportKind.M4b -> S.s_chua_xuat_duoc_m4b_5a39de4c
        ExportKind.Audiobook -> S.s_chua_xuat_duoc_sach_noi_5468423d
    }

    // ---- lựa chọn -------------------------------------------------------------------------------------------------------

    /** Một câu nói dạng file là gì, cho người chưa biết MP3 / M4B khác nhau chỗ nào. */
    fun about(format: ExportFormat): String = when (format) {
        ExportFormat.Mp3 -> S.s_mot_thu_muc_moi_chuong_mot_mp3_kem_danh_sa_d7562c0b
        ExportFormat.M4b -> S.s_mot_file_co_muc_luc_chuong_nho_cho_nghe_do_903bace3
    }

    const val ABOUT_AUDIOBOOK = S.s_may_doc_ca_cuon_roi_ghep_thanh_mot_file_m4_845bc226

    /** Lời dưới ô "Kèm nhạc nền" - đúng chữ của web (MUSIC_MIX_HINT). */
    const val MUSIC_MIX_HINT = S.s_nhac_duoc_tron_thang_vao_file_khong_tat_ri_e1608133

    /** Lời báo khi MP3 có nhạc ra file .m4a - đúng chữ của hộp Xuất MP3 trên web. */
    const val MP3_MUSIC_NOTE = S.s_co_nhac_nen_thi_moi_chuong_la_file_m4a_tha_e5064103

    /** Việc của sách nói và lời báo chạy nền - đúng chữ của hộp Xuất sách nói trên web. */
    const val AUDIOBOOK_PURPOSE = S.s_doc_ca_cuon_thanh_file_am_thanh_nghe_o_may_d043f850
    const val AUDIOBOOK_NOTE = S.s_chay_nen_dung_van_giu_phan_da_lam_b5b35b4d

    /** Máy không mở được thư mục: chỉ đường bằng tên thư mục nếu biết - đúng chữ của web. */
    fun noFolderOpener(folder: String?): String =
        if (folder != null) S.s_may_khong_mo_duoc_thu_muc_mo_app_tep_roi_v_1c7714fc(folder) else S.s_may_khong_mo_duoc_thu_muc_mo_app_tep_roi_v_3490fb90

    /** Hỏi xuất riêng các chương đã đổi hay cả cuốn - đúng chữ của hộp "Có chương đã đổi" trên web. */
    fun changedAsk(count: Int): String = S.s_ban_mp3_ban_xuat_truoc_day_co_0_chuong_da_f85437e7(count)

    /** Dòng phụ của một bản đã xuất: còn mới, hay đã đổi bao nhiêu chương từ lúc ấy. */
    fun pastLine(past: PastExport): String = when {
        !past.stale -> S.s_con_moi_47b72502
        past.kind == ExportKind.Mp3 -> S.s_0_chuong_da_doi_tu_lan_xuat_nay_e38aaaee(past.changed.size)
        else -> S.s_0_chuong_da_doi_can_dung_lai_ca_file_a6e7de45(past.changed.size)
    }

    fun pastTitle(past: PastExport): String {
        val label = when (past.kind) {
            ExportKind.Mp3 -> S.s_mp3_b84e4872
            ExportKind.M4b -> S.s_m4b_c793d08a
            ExportKind.Audiobook -> S.s_sach_noi_65750c67
        }
        // Đích là địa chỉ content: của nơi lưu ("…/document/primary%3AMusic%2FTên"): chỉ nói tên thư mục / file cuối.
        val name = runCatching { java.net.URLDecoder.decode(past.target.replace("+", "%2B"), "UTF-8") }.getOrDefault(past.target)
            .trimEnd('/', '\\').substringAfterLast('/').substringAfterLast('\\').substringAfterLast(':')
        return if (name.isEmpty()) label else "$label · $name"
    }

    /** Dòng nói của hàng "Đang xuất" trong menu của cuốn. */
    fun menuHint(phase: ExportPhase, fraction: Float?): String? = when (phase) {
        is ExportPhase.Running -> if (fraction == null) S.s_dang_xuat_989a7c21 else S.s_dang_xuat_0_20b7b18c((fraction * 100).toInt().coerceIn(0, 99))
        is ExportPhase.Done -> S.s_da_xuat_xong_58c33c02
        is ExportPhase.Failed -> S.s_chua_xuat_duoc_27b1025b
        else -> null
    }
}

/** Việc của màn Xuất một cuốn. Đổi hiếm (đổi pha), tiến độ chạy theo nhịp ở luồng riêng ([ExportState.progress]). */
@Immutable
sealed interface ExportPhase {
    /** Chọn tuỳ chọn, chưa làm gì. */
    data object Idle : ExportPhase

    /** Đã bấm Bắt đầu, đang chờ hệ thống hỏi chỗ lưu / lõi nhận việc. */
    data object Starting : ExportPhase

    /** Việc nền đang chạy (sống tiếp khi rời màn). `stopping`: đã bấm Dừng, chờ lõi báo. `folder`: nơi lưu MP3 để nói "vào ...". */
    data class Running(val kind: ExportKind, val run: String, val stopping: Boolean = false, val folder: String? = null) : ExportPhase

    data class Done(val result: ExportResult) : ExportPhase

    data class Stopped(val kind: ExportKind, val note: String) : ExportPhase

    data class Failed(val kind: ExportKind, val message: String) : ExportPhase

    /** Thứ tự trang cho chuyển động trượt: chọn -> làm -> kết quả. */
    val page: Int
        get() = when (this) {
            Idle, Starting -> 0
            is Running -> 1
            is Done, is Stopped, is Failed -> 2
        }
}
