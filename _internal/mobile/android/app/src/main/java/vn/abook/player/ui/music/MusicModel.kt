package vn.abook.player.ui.music

import androidx.compose.runtime.Immutable
import org.json.JSONObject
import vn.abook.player.ui.data.Fmt

/*
 * Nhạc nền của một cuốn, cho giao diện native. Cùng hình JSON với lõi (GET /music của LocalStudio, `/api/music/playlists`, `musicCredit` của Playback.state)
 * và cùng luật với bản WebView (listen/playlistBed.ts, shared/musicLevels.ts, shared/format.ts) - chỉ chữ trên nút được viết lại cho điện thoại (nhãn 1-4 chữ).
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
    const val DEFAULT_DB = -20.0

    /** Cùng chữ với web (shared/musicLevels.ts MUSIC_LEVELS, đã kèm lời levelText): -28 là mức nhạc khó che lời đọc nhất (MIX_QA mục 7.1). */
    val levels: List<Pair<Double, String>> = listOf(
        -14.0 to "To", -17.0 to "Hơi to", -20.0 to "Vừa (mặc định)", -24.0 to "Nhỏ", -28.0 to "Rất nhỏ (dễ nghe lời nhất)",
    )

    /** Tên ô chọn mức của web: "Mức nhạc dưới giọng đọc". */
    const val TITLE = "Mức nhạc dưới giọng đọc"

    /** Các mức: có sẵn, thêm mức của sách (sách đóng gói ở -18 dB, "-18 dB (của sách)" như levelOptions) nếu không trùng mức nào - xếp từ to tới nhỏ. */
    fun options(current: Double): List<Pair<Double, String>> =
        if (levels.any { it.first == current }) levels
        else (levels + (current to "${decibels(current)} dB (của sách)")).sortedByDescending { it.first }

    /** Như `String(current).replace(".", ",")` của web: -18 -> "-18", -18.5 -> "-18,5". */
    private fun decibels(value: Double): String =
        if (value == Math.rint(value)) value.toLong().toString() else value.toString().replace('.', ',')

    /** Chữ của mức đang chọn. */
    fun label(current: Double): String = options(current).firstOrNull { it.first == current }?.second.orEmpty()
}

/** Chữ của nhạc nền trên điện thoại (cùng luật với playlistBed.ts, nhãn ngắn). */
object MusicText {
    const val MINE = "mine"
    const val OFF = "off"
    const val SCENE = "scene"

    const val AUTO_LABEL = "Để máy chọn"
    const val OFF_LABEL = "Tắt"
    const val SCENE_LABEL = "Theo cảnh"
    const val MINE_LABEL = "Nhạc của tôi"
    /** playlistBed.ts ADD_MUSIC_LABEL. */
    const val ADD_LABEL = "Thêm nhạc của bạn"
    /** musicLocal.ts MY_MUSIC_INTRO: một câu cho mọi nơi nói về Nhạc của tôi. */
    const val MY_MUSIC_INTRO = "Thêm nhạc làm nền; bài đã chọn đi cùng file sách."
    /** musicLocal.ts `analysisLabel` của bài chưa phân tích (điện thoại không tự chọn nên không nói bài đã phân tích). */
    const val UNANALYSED = "Chưa phân tích - máy chưa tự chọn, bạn vẫn ghim được"
    const val PACKAGED_NOTE = "Nhạc do người làm sách chọn. Đổi ở đây chỉ trên máy này."
    const val AUTO_OFF_NOTE = "\"Tự chọn nhạc nền\" đang tắt trong Cài đặt."
    const val BROKEN_PACKAGED = "Bài nhạc chương này không phát được."
    const val BROKEN_PLAYLIST = "Có bài nhạc chưa phát được, máy sẽ thử lại sau."

    /** Lời "đã chỉnh sửa" đi kèm ghi công nhạc CC BY; cùng câu với bản web và bản xuất MP3 / M4B. */
    const val MODIFIED_NOTE = "Đã chỉnh sửa: các bài nhạc được cắt vòng, trộn nhỏ dưới giọng đọc và chỉnh âm lượng cho vừa sách."

    /** Độ dài cả danh sách: "dài" để "8 giờ" không đọc như 8 giờ sáng. */
    fun length(minutes: Int): String = when {
        minutes <= 0 -> ""
        minutes < 90 -> "dài $minutes phút"
        else -> "dài ${Math.round(minutes / 60.0)} giờ"
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
        MusicKind.Packaged -> if (book.enabled) "Bật" else OFF_LABEL
        MusicKind.Playlist -> when {
            book.playlistAuto -> nameOf(menu, book.playlist.orEmpty()).ifEmpty { "Máy chọn" }
            book.playlist == null -> if (book.autoOff) "Chưa có nhạc" else "Máy chọn"
            book.playlist == OFF -> OFF_LABEL
            book.playlist == MINE -> MINE_LABEL
            else -> nameOf(menu, book.playlist).ifEmpty { "Danh sách đã chọn" }
        }
    }

    /** Các dòng: Để máy chọn, Tắt, Theo cảnh (máy dựng được), các danh sách của danh mục, Nhạc của tôi (trống thì không chọn được). */
    fun options(menu: MusicMenu?, book: BookMusic?): List<MusicOption> = buildList {
        val auto = if (book?.playlistAuto == true) nameOf(menu, book.playlist.orEmpty()) else ""
        add(MusicOption(null, AUTO_LABEL, if (book?.autoOff == true) "đang tắt trong Cài đặt" else auto))
        add(MusicOption(OFF, OFF_LABEL))
        if (menu?.scene == true) add(MusicOption(SCENE, SCENE_LABEL, description = "Máy tự dựng, đổi theo từng cảnh của truyện."))
        for (item in menu?.playlists.orEmpty()) add(MusicOption(item.id, item.name, length(item.minutes), item.description))
        val mine = menu?.mine ?: 0
        add(MusicOption(MINE, MINE_LABEL, if (mine > 0) "$mine bài" else "chưa có bài nào", disabled = mine == 0))
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
    fun creditLine(credit: MusicCredit): String = listOf(credit.title.trim(), credit.creator.trim()).filter { it.isNotEmpty() }.joinToString(" · ")

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
    const val PACKAGED_SWITCH = "Nhạc nền"
    const val ON = "Bật"
    const val SILENCE_LABEL = "Im lặng"
    const val UNSILENCE_LABEL = "Có nhạc"
    const val SWAP_LABEL = "Đổi bài"
    const val ORIGINAL_LABEL = "Về bài gốc"
    const val CHOOSE_LABEL = "Chọn"
    const val NO_MINE = "Chưa có bài nào khác trong Nhạc của tôi."
    const val SWAP_FAILED = "Bạn hãy kiểm tra kết nối rồi tìm lại bài nhạc."
    const val LOAD_FAILED = "Bạn hãy thử tải lại nhạc nền của cuốn này."
    const val NONE = "Người làm sách không gắn nhạc nền cho cuốn này."

    /** "Nhạc nền: Bật" - nhãn công tắc nói trạng thái (web: chữ trên nút đổi theo trạng thái thì không biết là hiện tại hay việc sẽ làm). */
    fun switchLabel(enabled: Boolean): String = "$PACKAGED_SWITCH: ${if (enabled) ON else OFF_LABEL}"

    /** Tên bài của một đoạn (không tên thì "Nhạc nền"). */
    fun cueTitle(cue: MusicCue): String = cue.title.trim().ifEmpty { "Nhạc nền" }

    /** Dòng phụ của một đoạn, như web: chương · khoảng giờ · tác giả · "bài của bạn" khi đã đổi (im lặng thì tên bài gạch ngang). */
    fun cueLine(cue: MusicCue): String = listOf(
        cue.chapter.trim(), "${Fmt.clock(cue.start)} – ${Fmt.clock(cue.end)}", cue.creator.trim(), if (cue.pinned) "bài của bạn" else "",
    ).filter { it.isNotEmpty() }.joinToString(" · ")

    /** Dòng phụ của một bài để đổi (SwapTrack): nghệ sĩ · độ dài. */
    fun mineLine(track: MineTrack): String =
        listOf(track.creator.trim(), if (track.duration > 0) Fmt.clock(track.duration) else "").filter { it.isNotEmpty() }.joinToString(" · ")

    /**
     * Dòng chú thích dưới một bài (studio/musicLocal.ts `mineNote`; điện thoại không có công tắc tự chọn nên `auto` luôn là mặc định):
     * có vẻ có lời, hợp không khí đoạn này, hay chưa phân tích. Không có gì đáng nói thì "".
     */
    fun mineNote(track: MineTrack): String = listOf(
        if (track.analysed && track.vocalsLikely) "Có vẻ có lời - máy không tự chọn bài này" else "",
        if (track.analysed) (if (track.fits) "Hợp không khí đoạn này" else "") else UNANALYSED,
    ).filter { it.isNotEmpty() }.joinToString(" · ")

    /** Giấy phép đòi ghi công (khác cc0; nhạc bạn tự thêm không có giấy phép) thì kèm [MODIFIED_NOTE]. */
    fun needsModifiedNote(license: String): Boolean = license.trim().lowercase().let { it.isNotEmpty() && it != "cc0" }
}
