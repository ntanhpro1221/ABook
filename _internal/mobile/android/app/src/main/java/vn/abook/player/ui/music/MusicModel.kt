package vn.abook.player.ui.music

import androidx.compose.runtime.Immutable
import org.json.JSONObject

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
    )

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

    /** Nhãn ô ngắn (lưới ba cột như tốc độ); "Vừa" là mặc định của máy. */
    val levels: List<Pair<Double, String>> = listOf(-14.0 to "To", -17.0 to "Hơi to", -20.0 to "Vừa", -24.0 to "Nhỏ", -28.0 to "Rất nhỏ")

    /** -28 là mức nhạc khó che lời đọc nhất (MIX_QA mục 7.1). */
    const val CLEAREST_NOTE = "Rất nhỏ: dễ nghe lời nhất."

    /** Các ô: mức có sẵn, thêm mức của sách (sách đóng gói ở -18 dB) nếu không trùng mức nào - xếp từ to tới nhỏ. */
    fun options(current: Double): List<Pair<Double, String>> =
        if (levels.any { it.first == current }) levels else (levels + (current to "Của sách")).sortedByDescending { it.first }
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
    const val ADD_LABEL = "Thêm nhạc"
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

    /** Giá trị ngắn bên phải hàng "Nhạc nền": tên thứ đang chạy, "Tắt", hay "Bật" với nhạc gắn sẵn. Rỗng khi chưa đọc xong (không nói "Tắt" rồi đổi). */
    fun value(book: BookMusic?, menu: MusicMenu?): String = when (book?.kind) {
        null, MusicKind.None -> ""
        MusicKind.Packaged -> if (book.enabled) "Bật" else OFF_LABEL
        MusicKind.Playlist -> when {
            book.playlistAuto -> nameOf(menu, book.playlist.orEmpty()).ifEmpty { "Máy chọn" }
            book.playlist == null -> if (book.autoOff) OFF_LABEL else "Máy chọn"
            book.playlist == OFF -> OFF_LABEL
            book.playlist == MINE -> MINE_LABEL
            else -> nameOf(menu, book.playlist).ifEmpty { "Đã chọn" }
        }
    }

    /** Các dòng: Để máy chọn, Tắt, Theo cảnh (máy dựng được), các danh sách của danh mục, Nhạc của tôi (trống thì không chọn được). */
    fun options(menu: MusicMenu?, book: BookMusic?): List<MusicOption> = buildList {
        val auto = if (book?.playlistAuto == true) nameOf(menu, book.playlist.orEmpty()) else ""
        add(MusicOption(null, AUTO_LABEL, if (book?.autoOff == true) "đang tắt" else auto))
        add(MusicOption(OFF, OFF_LABEL))
        if (menu?.scene == true) add(MusicOption(SCENE, SCENE_LABEL, description = "Máy tự dựng, đổi theo từng cảnh của truyện."))
        for (item in menu?.playlists.orEmpty()) add(MusicOption(item.id, item.name, length(item.minutes), item.description))
        val mine = menu?.mine ?: 0
        add(MusicOption(MINE, MINE_LABEL, if (mine > 0) "$mine bài" else "chưa có bài", disabled = mine == 0))
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

    /** Giấy phép đòi ghi công (khác cc0; nhạc bạn tự thêm không có giấy phép) thì kèm [MODIFIED_NOTE]. */
    fun needsModifiedNote(license: String): Boolean = license.trim().lowercase().let { it.isNotEmpty() && it != "cc0" }
}
