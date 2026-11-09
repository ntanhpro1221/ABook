package vn.abook.player.ui.music

import kotlin.math.roundToInt
import vn.abook.player.S

import vn.abook.player.ui.data.dotJoined
import androidx.compose.runtime.Immutable
import org.json.JSONObject
import vn.abook.player.ui.data.Fmt

/*
 * Nhạc nền của một cuốn, cho giao diện native. Cùng hình JSON với lõi (GET /music của LocalStudio, `/api/music/playlists`, `musicCredit` của Playback.state)
 * Chữ trên nút viết cho điện thoại (nhãn 1-4 chữ).
 */

/** Một danh sách phát của danh mục (menu "Nhạc nền" của sách chỉ có chữ). */
@Immutable
data class PlaylistSummary(val id: String, val name: String, val description: String, val minutes: Int)

/** Menu chọn nhạc: các danh sách của danh mục, số bài trong "Nhạc của tôi", lý do chưa tải được danh mục, máy dựng được nhạc theo cảnh không. */
@Immutable
data class MusicMenu(val playlists: List<PlaylistSummary> = emptyList(), val mine: Int = 0, val error: String = "", val scene: Boolean = false)

/** Cuốn này chỉnh nhạc nền kiểu nào: chọn danh sách (sách chỉ có chữ), bật/tắt nhạc người làm sách gắn, hay không có nhạc gì để chỉnh. */
enum class MusicKind { Playlist, Packaged, None }

/**
 * Màn "Nhạc nền" của một cuốn. `playlist`: mã người nghe đã chọn ("mine", "off", mã danh sách) hay - khi chưa chọn và "Tự chọn nhạc nền" còn bật - "scene" kèm
 * `playlistAuto`. `autoOff`: chưa chọn và đã tắt "Tự chọn nhạc nền". `error`: lời báo của lõi (mất mạng giữ bài lại).
 */
@Immutable
data class BookMusic(
    val kind: MusicKind,
    val enabled: Boolean = true,
    val levelDb: Double = MusicLevels.DEFAULT_DB,
    val playlist: String? = null,
    val playlistAuto: Boolean = false,
    val autoOff: Boolean = false,
    val error: String = "",
    /** Các đoạn nhạc người làm sách gắn (chỉ sách nói có nhạc gắn sẵn), theo thứ tự nghe. */
    val cues: List<MusicCue> = emptyList(),
)

/**
 * Một đoạn nhạc gắn sẵn: `key` = "chương:mili giây bắt đầu" (BookEdits.cueKey). `title` / `creator` là của bài đang ở đoạn ấy (bài của bạn nếu đã đổi).
 * `silenced`: người nghe cho đoạn này im. `pinned`: đã đổi sang một bài trong Nhạc của tôi.
 */
@Immutable
data class MusicCue(
    val key: String,
    val chapterId: Long,
    val chapter: String,
    val start: Double,
    val end: Double,
    val title: String = "",
    val creator: String = "",
    val silenced: Boolean = false,
    val pinned: Boolean = false,
) {
    /** Đoạn đang kêu ở chỗ nghe này (mốc cuối thuộc đoạn sau). */
    fun holds(chapterId: Long, seconds: Double): Boolean = this.chapterId == chapterId && seconds >= start && seconds < end
}

/** Một bài trong Nhạc của tôi có thể thay vào một đoạn ("Đổi bài"): `vocalsLikely` = máy nghe thấy có vẻ có lời, `fits` = hợp không khí đoạn này. */
@Immutable
data class MineTrack(
    val link: String,
    val title: String,
    val creator: String,
    val duration: Double,
    val analysed: Boolean,
    val vocalsLikely: Boolean = false,
    val fits: Boolean = false,
)

/** Ghi công bài nhạc đang kêu (CC BY đòi nêu tên ở nơi nhạc phát): chỉ khoá nào lõi có. */
@Immutable
data class MusicCredit(
    val title: String = "",
    val creator: String = "",
    val attribution: String = "",
    val landing: String = "",
    val license: String = "",
    val licenseUrl: String = "",
)

/** Phần nhạc của trạng thái trình phát: bài đang kêu, bài của chương này hỏng, lời báo mất mạng, nhạc đang theo cảnh. */
@Immutable
data class PlayerMusic(val credit: MusicCredit? = null, val broken: Boolean = false, val offline: String = "", val scene: Boolean = false) {
    companion object {
        val None = PlayerMusic()

        fun from(json: JSONObject): PlayerMusic = PlayerMusic(
            MusicJson.credit(json.optJSONObject("musicCredit")), json.optBoolean("musicBroken"), json.optString("musicOffline"), json.optBoolean("musicScene"),
        )
    }
}

/** Một dòng của danh sách chọn nhạc: `id` null = "Để máy chọn" (xoá lựa chọn). */
@Immutable
data class MusicOption(val id: String?, val label: String, val hint: String = "", val description: String = "", val disabled: Boolean = false)

object MusicJson {
    private fun text(json: JSONObject?, key: String): String = json?.optString(key).orEmpty().takeUnless { it == "null" }.orEmpty()

    fun menu(json: JSONObject): MusicMenu {
        val rows = json.optJSONArray("playlists")
        val playlists = (0 until (rows?.length() ?: 0)).mapNotNull { rows?.optJSONObject(it) }.map { row ->
            PlaylistSummary(text(row, "id"), text(row, "name"), text(row, "description"), row.optInt("minutes"))
        }.filter { it.id.isNotEmpty() }
        return MusicMenu(playlists, json.optInt("mine"), text(json, "error"), json.has("scene") && !json.isNull("scene"))
    }

    /** `textOnly`: sách chỉ có chữ (chọn danh sách phát); không thì nhạc người làm sách gắn (`hasMusic`) hay không có gì. */
    fun book(json: JSONObject, textOnly: Boolean): BookMusic = BookMusic(
        kind = when {
            textOnly -> MusicKind.Playlist
            json.optBoolean("hasMusic") -> MusicKind.Packaged
            else -> MusicKind.None
        },
        enabled = json.optBoolean("enabled", true),
        levelDb = json.optDouble("levelDb", MusicLevels.DEFAULT_DB).takeIf { it.isFinite() } ?: MusicLevels.DEFAULT_DB,
        playlist = text(json, "playlist").ifEmpty { null },
        playlistAuto = json.optBoolean("playlistAuto"),
        autoOff = json.optBoolean("autoOff"),
        error = text(json, "error"),
        cues = json.optJSONArray("cues")?.let { rows ->
            (0 until rows.length()).mapNotNull { rows.optJSONObject(it) }.map { row ->
                MusicCue(
                    text(row, "key"), row.optLong("chapterId"), text(row, "chapter"), row.optDouble("start", 0.0), row.optDouble("end", 0.0),
                    text(row, "title"), text(row, "creator"), row.optBoolean("silenced"), row.optBoolean("pinned"),
                )
            }.filter { it.key.isNotEmpty() }
        }.orEmpty(),
    )

    /** Lời đáp "Đổi bài" (`mine` của alternatives): bài đã phân tích trước, rồi theo tên. */
    fun mine(json: JSONObject): List<MineTrack> {
        val rows = json.optJSONArray("mine") ?: return emptyList()
        return (0 until rows.length()).mapNotNull { rows.optJSONObject(it) }.map { row ->
            MineTrack(
                text(row, "link"), text(row, "title"), text(row, "creator"), row.optDouble("duration", 0.0), row.optBoolean("analysed"),
                row.optBoolean("vocalsLikely"), row.optBoolean("fits"),
            )
        }.filter { it.link.isNotEmpty() }
    }

    fun credit(json: JSONObject?): MusicCredit? {
        json ?: return null
        val credit = MusicCredit(
            text(json, "title"), text(json, "creator"), text(json, "attribution"), text(json, "landing"), text(json, "license"), text(json, "licenseUrl"),
        )
        return credit.takeIf { it.title.isNotBlank() || it.creator.isNotBlank() }
    }
}

/** Mức nhạc dưới giọng đọc (shared/musicLevels.ts): dB nhỏ hơn giọng bấy nhiêu. */
object MusicLevels {
    const val DEFAULT_DB = vn.abook.player.BuildConfig.levelDefaultDb
    const val MIN_DB = vn.abook.player.BuildConfig.levelMinDb
    const val MAX_DB = vn.abook.player.BuildConfig.levelMaxDb
    const val STEP_DB = vn.abook.player.BuildConfig.levelStepDb
    const val TITLE = S.s_muc_nhac_nen_a45588ff
    const val RESET = S.s_ve_mac_dinh_4eb6b300
    fun clamp(value: Double): Double = value.coerceIn(MIN_DB, MAX_DB)
    fun label(value: Double): String = when {
        value >= -15.5 -> S.s_to_f4b06ef6
        value >= -18.5 -> S.s_hoi_to_953a7b53
        value >= -21.5 -> S.s_vua_8af1c03b
        value >= -25.5 -> S.s_nho_9c1511d3
        else -> S.s_rat_nho_ro_loi_0afefef2
    }
    private fun decibels(value: Double): String =
        if (value == Math.rint(value)) value.toLong().toString() else value.toString().replace('.', ',')
    fun number(value: Double): String = "${decibels(value)} dB" + if (value == DEFAULT_DB) S.s_mac_dinh_2a963068 else ""
    /** Cùng mức, nói bằng phần trăm của miền (0 % nhỏ nhất, 100 % to nhất) - thanh "Nhạc nền" của trang Âm thanh, cạnh thanh "Giọng đọc". */
    fun percent(value: Double): Int = ((clamp(value) - MIN_DB) / (MAX_DB - MIN_DB) * 100).roundToInt()
}

/** Chữ của nhạc nền trên điện thoại (cùng luật với playlistBed.ts, nhãn ngắn). */
object MusicText {
    const val MINE = "mine"
    const val OFF = "off"
    const val SCENE = "scene"

    const val AUTO_LABEL = S.s_de_may_chon_44450073
    const val OFF_LABEL = S.s_tat_3286064e
    const val SCENE_LABEL = S.s_theo_canh_6cc44c05
    const val MINE_LABEL = S.s_nhac_cua_toi_f65b7ac6
    /** playlistBed.ts ADD_MUSIC_LABEL. */
    const val ADD_LABEL = S.s_them_nhac_cua_ban_dbd7d8c4
    /** musicLocal.ts MY_MUSIC_INTRO: một câu cho mọi nơi nói về Nhạc của tôi. */
    const val MY_MUSIC_INTRO = S.s_them_nhac_lam_nen_bai_da_chon_di_cung_file_eefa0e8d
    /** musicLocal.ts MY_MUSIC_HELP: lời gập "Nhạc riêng" dưới [MY_MUSIC_INTRO] ở mọi nơi nói về Nhạc của tôi. */
    const val MY_MUSIC_HELP = S.s_nhac_duoc_chep_vao_kho_may_nay_dung_doi_ba_00b59983
    /** musicLocal.ts `UNANALYSED`: nhãn ngắn của bài chưa phân tích (điện thoại không tự chọn nên không nói bài đã phân tích). */
    const val UNANALYSED = S.s_chua_phan_tich_5c1c27fb
    const val PACKAGED_NOTE = S.s_chi_doi_tren_may_nay_93811b69
    const val AUTO_OFF_NOTE = S.s_tu_chon_nhac_nen_dang_tat_trong_cai_dat_89029817
    const val BROKEN_PACKAGED = S.s_bai_nhac_chuong_nay_khong_phat_duoc_e0bc4ba6
    const val BROKEN_PLAYLIST = S.s_co_bai_nhac_chua_phat_duoc_may_se_thu_lai_27ed64dd

    /** Lời "đã chỉnh sửa" đi kèm ghi công nhạc CC BY; cùng câu với bản web và bản xuất MP3 / M4B. */
    const val MODIFIED_NOTE = S.s_da_chinh_sua_cac_bai_nhac_duoc_cat_vong_tr_929d3f58

    /** Độ dài cả danh sách: "dài" để "8 giờ" không đọc như 8 giờ sáng. */
    fun length(minutes: Int): String = when {
        minutes <= 0 -> ""
        minutes < 90 -> S.s_dai_0_phut_52556926(minutes)
        else -> S.s_dai_0_gio_b717acba(Math.round(minutes / 60.0))
    }

    private fun nameOf(menu: MusicMenu?, code: String): String =
        if (code == SCENE) SCENE_LABEL else menu?.playlists?.firstOrNull { it.id == code }?.name.orEmpty()

    /** Mã dòng đang chọn: null = "Để máy chọn". */
    fun chosen(book: BookMusic?): String? = if (book == null || book.playlistAuto) null else book.playlist

    /** Nhạc đang chạy cho cuốn này (máy theo cảnh, người nghe chọn danh sách, hay nhạc gắn sẵn đang bật). */
    fun playing(book: BookMusic?): Boolean = when (book?.kind) {
        MusicKind.Playlist -> !book.playlist.isNullOrEmpty() && book.playlist != OFF
        MusicKind.Packaged -> book.enabled
        else -> false
    }

    /** Giá trị ngắn bên phải hàng "Nhạc nền" (playlistBed.ts `playlistLabel` + `shortPlaylistLabel`): tên thứ đang chạy, "Tắt", hay "Bật" với nhạc gắn sẵn. Rỗng khi chưa đọc xong (không nói "Tắt" rồi đổi). */
    fun value(book: BookMusic?, menu: MusicMenu?): String = when (book?.kind) {
        null, MusicKind.None -> ""
        MusicKind.Packaged -> if (book.enabled) S.s_bat_f26cbc4a else OFF_LABEL
        MusicKind.Playlist -> when {
            book.playlistAuto -> nameOf(menu, book.playlist.orEmpty()).ifEmpty { S.s_may_chon_4329a3f3 }
            book.playlist == null -> if (book.autoOff) S.s_chua_co_nhac_ed5dc66e else S.s_may_chon_4329a3f3
            book.playlist == OFF -> OFF_LABEL
            book.playlist == MINE -> MINE_LABEL
            else -> nameOf(menu, book.playlist).ifEmpty { S.s_danh_sach_da_chon_7b304e03 }
        }
    }

    /** Các dòng: Để máy chọn, Tắt, Theo cảnh (máy dựng được), các danh sách của danh mục, Nhạc của tôi (trống thì không chọn được). */
    fun options(menu: MusicMenu?, book: BookMusic?): List<MusicOption> = buildList {
        val auto = if (book?.playlistAuto == true) nameOf(menu, book.playlist.orEmpty()) else ""
        add(MusicOption(null, AUTO_LABEL, if (book?.autoOff == true) S.s_dang_tat_trong_cai_dat_729d6de0 else auto))
        add(MusicOption(OFF, OFF_LABEL))
        if (menu?.scene == true) add(MusicOption(SCENE, SCENE_LABEL, description = S.s_may_tu_dung_doi_theo_tung_canh_cua_truyen_9b723646))
        for (item in menu?.playlists.orEmpty()) add(MusicOption(item.id, item.name, length(item.minutes), item.description))
        val mine = menu?.mine ?: 0
        add(MusicOption(MINE, MINE_LABEL, if (mine > 0) S.s_0_bai_1e392237(mine) else S.s_chua_co_bai_nao_1911af5a, disabled = mine == 0))
    }

    /** Lời dưới danh sách: chỉ khi có điều cần biết (lỗi, bài hỏng, tự chọn đang tắt) - không nhắc suông. */
    fun note(book: BookMusic?, menu: MusicMenu?, player: PlayerMusic?): String = when (book?.kind) {
        MusicKind.Packaged -> listOf(if (book.enabled && player?.broken == true) BROKEN_PACKAGED else "", book.error, PACKAGED_NOTE)
            .filter { it.isNotEmpty() }.joinToString("\n")
        MusicKind.Playlist -> book.error.ifEmpty { player?.offline.orEmpty() }.ifEmpty { menu?.error.orEmpty() }
            .ifEmpty { if (playing(book) && player?.scene == true && player.broken) BROKEN_PLAYLIST else "" }
            .ifEmpty { if (book.playlist == null && book.autoOff) AUTO_OFF_NOTE else "" }
        else -> ""
    }

    /** Ghi công một dòng (shared/format.ts `musicCreditText`): lời ghi công của bài nếu có kèm tác giả, không thì "tên - tác giả". */
    fun creditText(credit: MusicCredit): String {
        if (credit.attribution.isNotBlank() && credit.creator.isNotBlank()) return credit.attribution.trim()
        return listOf(credit.title.trim(), credit.creator.trim()).filter { it.isNotEmpty() }.joinToString(" - ")
    }

    /** Tên ngắn trên hàng "Đang phát": tên bài · tác giả. */
    fun creditLine(credit: MusicCredit): String = listOf(credit.title.trim(), credit.creator.trim()).dotJoined()

    private val CC_URL = Regex("""creativecommons\.org/(licenses|publicdomain)/([a-z-]+)/(\d+(?:\.\d+)?)""", RegexOption.IGNORE_CASE)
    private val CC_CODE = Regex("""by(-(nc|nd|sa))*""")

    /** Tên giấy phép cho người đọc (shared/format.ts `licenseLabel`): "CC BY 4.0", "CC0 1.0", hay mã như lõi gửi. */
    fun licenseLabel(code: String, url: String = ""): String {
        CC_URL.find(url)?.let { match ->
            val (kind, slug, version) = match.destructured
            if (kind.equals("licenses", ignoreCase = true)) return "CC ${slug.uppercase()} $version"
            if (slug.equals("zero", ignoreCase = true)) return "CC0 $version"
        }
        val raw = code.trim()
        val lower = raw.lowercase()
        if (lower == "cc0") return "CC0"
        if (CC_CODE.matches(lower)) return "CC ${lower.uppercase()}"
        return raw
    }

    // ---- từng đoạn nhạc gắn sẵn --------------------------------------------------------------------------------------------------

    // Cùng chữ với Sửa sách > Nhạc nền của web (listen/EditBook.tsx MusicSection, MyMusic.tsx SwapTrack).
    const val ON = S.s_bat_f26cbc4a
    const val SILENCE_LABEL = S.s_im_lang_1a012238
    const val UNSILENCE_LABEL = S.s_co_nhac_f514e0fa
    const val SWAP_LABEL = S.s_doi_bai_7b81488f
    const val ORIGINAL_LABEL = S.s_ve_bai_goc_dc6a21f6
    const val CHOOSE_LABEL = S.s_chon_1171ca97
    const val NO_MINE = S.s_chua_co_bai_nao_khac_trong_nhac_cua_toi_811d988a
    const val SWAP_FAILED = S.s_ban_hay_kiem_tra_ket_noi_roi_tim_lai_bai_n_acc346b4
    const val LOAD_FAILED = S.s_ban_hay_thu_tai_lai_nhac_nen_cua_cuon_nay_b4336281
    const val NONE = S.s_nguoi_lam_sach_khong_gan_nhac_nen_cho_cuon_80c1a983

    /** "Bật" / "Tắt" - nhãn công tắc nói trạng thái; tên "Nhạc nền" đã ở đầu bảng, không lặp lại (soát UI nhạc 01-11 mục 6). */
    fun switchLabel(enabled: Boolean): String = if (enabled) ON else OFF_LABEL

    /** Đoạn người nghe cho im: nói thẳng như tab Nhạc của dự án, không gạch ngang tên (gạch ngang đọc như lỗi). */
    const val SILENCED_TITLE = S.s_im_lang_ban_chon_356a628b

    /** Tên của một đoạn: im lặng thì [SILENCED_TITLE], không tên thì "Nhạc nền". */
    fun cueTitle(cue: MusicCue): String = if (cue.silenced) SILENCED_TITLE else cue.title.trim().ifEmpty { S.s_nhac_nen_271fb292 }

    /** Dòng phụ của một đoạn, như web: chương · khoảng giờ · tác giả · "bài của bạn" khi đã đổi. */
    fun cueLine(cue: MusicCue): String = listOf(
        cue.chapter.trim(), "${Fmt.clock(cue.start)} – ${Fmt.clock(cue.end)}", cue.creator.trim(), if (cue.pinned) S.s_bai_cua_ban_2cac90c1 else "",
    ).dotJoined()

    /** Dòng phụ của một bài để đổi (SwapTrack): nghệ sĩ · độ dài. */
    fun mineLine(track: MineTrack): String =
        listOf(track.creator.trim(), if (track.duration > 0) Fmt.clock(track.duration) else "").dotJoined()

    /**
     * Dòng chú thích dưới một bài (studio/musicLocal.ts `mineNote`; điện thoại không có công tắc tự chọn nên `auto` luôn là mặc định):
     * có lời, hợp không khí đoạn này, hay chưa phân tích - cùng chữ ngắn với web. Không có gì đáng nói thì "".
     */
    fun mineNote(track: MineTrack): String = listOf(
        if (track.analysed && track.vocalsLikely) S.s_co_loi_4b381f10 else "",
        if (track.analysed) (if (track.fits) S.s_hop_khong_khi_doan_nay_44c3025b else "") else UNANALYSED,
    ).dotJoined()

    /** Giấy phép đòi ghi công (khác cc0; nhạc bạn tự thêm không có giấy phép) thì kèm [MODIFIED_NOTE]. */
    fun needsModifiedNote(license: String): Boolean = license.trim().lowercase().let { it.isNotEmpty() && it != "cc0" }
}
