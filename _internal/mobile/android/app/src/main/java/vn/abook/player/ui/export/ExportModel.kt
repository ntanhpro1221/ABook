package vn.abook.player.ui.export

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
    Mp3("mp3", "MP3"), M4b("m4b", "M4B");

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
        if (minutes < 1) return "dưới 1 phút"
        if (minutes < 60) return "khoảng $minutes phút"
        val hours = minutes / 60
        val rest = minutes % 60
        return "khoảng $hours giờ${if (rest != 0) " $rest phút" else ""}"
    }

    /** Dòng nói sách dài bao nhiêu và máy cần bao lâu: "12 chương · khoảng 8 giờ nghe · máy cần khoảng 2 giờ 10 phút." */
    fun planText(plan: AudiobookPlan): String {
        val machine = plan.secondsEstimate?.let { " · máy cần ${spokenDuration(it)}" }.orEmpty()
        return "${plan.chapters} chương · ${spokenDuration(plan.audioSeconds)} nghe$machine."
    }

    /** Nói phần nào đã có sẵn (đã nghe, đã làm trước, lần xuất trước); tính theo phần nghe đã có trên cả cuốn, không đếm chương đủ. */
    fun resumeText(plan: AudiobookPlan): String {
        if (plan.chapters > 0 && plan.readyChapters >= plan.chapters) return "Đã đọc sẵn cả cuốn - chỉ còn ghép thành file, không đọc lại."
        if (plan.readySeconds >= 60 && plan.audioSeconds > 0) {
            // Chưa đủ cả cuốn thì không nói 100% (quãng lặng giữa đoạn, làm tròn).
            val percent = Math.round(plan.readySeconds * 100.0 / plan.audioSeconds).toInt().coerceIn(1, 99)
            return "Đã đọc sẵn khoảng $percent% - phần này xuất ngay, không đọc lại."
        }
        return ""
    }

    /** Chỗ trống cần trong máy lúc làm (file tạm, xoá khi xong). */
    fun spaceText(plan: AudiobookPlan): String = "Lúc làm cần khoảng ${Fmt.size(plan.bytes)} trống trong điện thoại (file tạm, xoá khi xong)."

    /** Lượt kèm nhạc dài (trên 20 chương) tốn pin đáng kể: gợi ý cắm sạc, không chặn. Rỗng khi không cần. */
    fun chargerHint(music: Boolean, chapters: Int): String = if (music && chapters > 20) "Cuốn dài: nên cắm sạc trong lúc làm - trộn nhạc tốn pin." else ""

    /** "12 đoạn phải đọc lại" khi đổi nhạc nền buộc ghép lại chương đã làm mà bản đọc của đoạn ấy không còn trong máy; rỗng khi không có. */
    fun rereadText(plan: AudiobookPlan): String =
        if (plan.rereads > 0) "${plan.rereads} đoạn phải đọc lại vì đổi nhạc nền (bản đọc cũ đã được dọn khỏi máy)." else ""

    /** Chữ của giọng trực tuyến gửi CẢ CUỐN ra ngoài máy; rỗng khi giọng chạy trên máy. */
    fun wholeBookNotice(voice: ExportVoice): String {
        if (!voice.online) return ""
        VoiceText.KEYED[voice.provider]?.let { return "Chữ của cả cuốn được gửi tới $it để đọc, bằng khoá của bạn - dịch vụ có thể tính tiền vào tài khoản của bạn." }
        if (voice.provider == "edge") return "Chữ của cả cuốn được gửi tới máy chủ Microsoft để đọc."
        return "Chữ của cả cuốn được gửi tới dịch vụ ngoài để đọc."
    }

    /** Chỉ đường trong trang cài đặt mở ra, theo hãng máy (backgroundHelp.ts). */
    fun backgroundHelp(manufacturer: String): String {
        val maker = manufacturer.trim().lowercase()
        return when {
            maker in setOf("oppo", "realme", "oneplus") -> "Trong trang mở ra: Pin → bật “Cho phép hoạt động dưới nền” và “Cho phép tự động khởi chạy”."
            maker in setOf("xiaomi", "redmi", "poco") -> "Trong trang mở ra: Tiết kiệm pin → chọn “Không hạn chế”."
            maker == "samsung" -> "Trong trang mở ra: Pin → chọn “Không hạn chế”."
            else -> "Trong trang mở ra: Pin → chọn “Không hạn chế” hay “Cho phép chạy nền” (tên mục khác nhau tuỳ máy)."
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
        if ((event.peakOver ?: 0) > 0) "Mã hoá lại vì ${event.peakOver} chương vượt đỉnh (lượt ${event.peakRound ?: 1})" else ""

    /** Việc tự báo tiến độ theo pha (bookFileExport.ts `reportedProgress`): chữ + phần đã xong + lời đọc; không báo thì null. */
    private fun reported(event: ExportEvent): ExportProgress? {
        val total = event.total ?: 0
        if (event.phase == "music-fetch" && total > 0) {
            val done = event.done ?: 0
            val fraction = done.toFloat() / total
            return ExportProgress("Đang tải nhạc nền ${minOf(done + 1, total)}/$total bài", spokenProgress("Đang tải nhạc nền", fraction), fraction)
        }
        if (event.phase == "peaks") return ExportProgress("Đang kiểm đỉnh âm", "Đang kiểm đỉnh âm", 1f)
        val retry = again(event)
        if (event.phase == "reencode") return ExportProgress(retry, retry, 1f)
        val chapter = event.chapter ?: return null
        val chapters = event.chapters?.takeIf { it > 0 } ?: return null
        val where = "Chương $chapter/$chapters"
        when (event.phase) {
            "encode" -> return ExportProgress(if (retry.isNotEmpty()) "$retry · $where" else "Đang ghép file âm thanh · $where", retry.ifEmpty { "Đang ghép file âm thanh" }, 1f)
            "chapters" -> {
                val fraction = (chapter - 1f) / chapters
                return ExportProgress("Đang ghi chương $chapter/$chapters", spokenProgress("Đang xuất sách", fraction), fraction)
            }
            "music" -> {
                val text = "Đang trộn nhạc chương $chapter/$chapters"
                val fraction = event.percent?.let { it / 100f } ?: ((chapter - 1f) / chapters)
                return ExportProgress(if (retry.isNotEmpty()) "$retry · $text" else text, retry.ifEmpty { spokenProgress("Đang trộn nhạc nền", fraction) }, fraction)
            }
        }
        val parts = mutableListOf(where, "${event.percent ?: 0}%")
        when {
            event.waiting == "listening" -> parts += "nhường cho chương đang nghe"
            event.waiting == "network" -> parts += "Đang chờ mạng"
            event.secondsLeft != null -> parts += "còn ${spokenDuration(event.secondsLeft)}"
        }
        val fraction = (event.percent ?: 0) / 100f
        val spoken = when (event.waiting) {
            "listening" -> "Tạm nhường cho chương đang nghe"
            "network" -> "Mất mạng - đang chờ mạng về để làm tiếp"
            else -> spokenProgress("Đang xuất $chapters chương", fraction)
        }
        return ExportProgress(parts.joinToString(" · "), spoken, fraction)
    }

    /** Tiến độ của một tin: MP3 / M4B có "3/10 chương · 27%" lúc đang làm, trước tin đầu chỉ có số chương; sách nói thêm "nhường cho chương đang nghe", "còn 2 giờ"... */
    fun progress(event: ExportEvent, chapters: Int = 0): ExportProgress {
        reported(event)?.let { return it }
        val total = event.total ?: 0
        if (total <= 0) {
            val text = if (chapters > 0) "$chapters chương" else "Đang chuẩn bị"
            return ExportProgress(text, text, null)
        }
        val done = event.done ?: 0
        val percent = event.percent?.let { " · ${it.coerceIn(0, 99)}%" }.orEmpty()
        val fraction = event.percent?.let { it / 100f } ?: (done.toFloat() / total)
        return ExportProgress("$done/$total chương$percent", spokenProgress(busy(event.kind), fraction), fraction)
    }

    /** Dòng đầu của lượt vừa bắt đầu, trước tin tiến độ đầu tiên. */
    fun starting(kind: ExportKind, chapters: Int): ExportProgress =
        if (kind == ExportKind.Audiobook) ExportProgress("Chương 1/$chapters · 0%", "Đang làm sách nói", 0f)
        else progress(ExportEvent(kind, "", ""), chapters)

    /** Tên việc đang làm, một tiêu đề cho cả ba kiểu. */
    fun busy(kind: ExportKind): String = when (kind) {
        ExportKind.Mp3 -> "Đang xuất sách"
        ExportKind.M4b -> "Đang làm file M4B"
        ExportKind.Audiobook -> "Đang làm sách nói"
    }

    // ---- kết thúc -------------------------------------------------------------------------------------------------------

    private fun missingChapters(event: ExportEvent): String {
        val chapters = event.chapters ?: event.files
        val total = event.chaptersTotal
        return if (chapters != null && total != null && chapters < total) "$chapters/$total chương - chương chưa xong không có trong file" else ""
    }

    private fun musicMissing(event: ExportEvent): String =
        event.musicMissing?.takeIf { it > 0 }?.let { "$it đoạn thiếu nhạc vì chưa tải được bài" } ?: ""

    /** Kết quả "xong": MP3 nói số chương và thư mục; M4B / sách nói nói tên file và cỡ; lưu ý khi còn chương chưa làm xong hay thiếu nhạc. */
    fun finished(event: ExportEvent): ExportResult {
        if (event.kind == ExportKind.Mp3) {
            val files = event.files ?: 0
            val partial = if (!event.selection && files < (event.chaptersTotal ?: 0)) "Các chương chưa làm xong sẽ không có trong bản xuất." else ""
            val lost = event.musicMissing?.takeIf { it > 0 }?.let { "$it đoạn thiếu nhạc vì chưa tải được bài." }.orEmpty()
            return ExportResult(
                event.kind, "Đã xuất $files chương", listOfNotNull(event.folder?.let { "Vào $it" }),
                listOf(partial, lost).filter { it.isNotEmpty() }, event.uri, event.folder,
            )
        }
        val title = if (event.kind == ExportKind.Audiobook) "Đã xuất sách nói" else "Đã xuất M4B"
        val lines = listOfNotNull(event.name, event.size?.takeIf { it > 0 }?.let { Fmt.size(it) })
        val notes = listOf(missingChapters(event), musicMissing(event)).filter { it.isNotEmpty() }
        return ExportResult(event.kind, title, listOf(lines.joinToString(" · ")).filter { it.isNotEmpty() }, notes, event.uri)
    }

    /** Lượt dừng: điều còn lại sau khi dừng, theo kiểu xuất. */
    fun stoppedNote(event: ExportEvent): String = when (event.kind) {
        ExportKind.Mp3 -> "${event.files ?: 0} chương đã ghi"
        ExportKind.M4b -> "File dở đã xoá"
        ExportKind.Audiobook -> "Phần đã làm được giữ - xuất lại để làm tiếp từ đó."
    }

    /** Tiêu đề khi dừng, cùng chữ với thông báo của bản web (ExportMp3 / ExportM4b / listenExport.ts). */
    fun stoppedTitle(kind: ExportKind): String = when (kind) {
        ExportKind.Mp3 -> "Đã dừng xuất"
        ExportKind.M4b -> "Đã dừng xuất M4B"
        ExportKind.Audiobook -> "Đã dừng xuất sách nói"
    }

    /** Tiêu đề khi lỗi, cùng chữ với bản web. */
    fun failedTitle(kind: ExportKind): String = when (kind) {
        ExportKind.Mp3 -> "Không xuất được"
        ExportKind.M4b -> "Không xuất được M4B"
        ExportKind.Audiobook -> "Không xuất được sách nói"
    }

    // ---- lựa chọn -------------------------------------------------------------------------------------------------------

    /** Một câu nói dạng file là gì, cho người chưa biết MP3 / M4B khác nhau chỗ nào. */
    fun about(format: ExportFormat): String = when (format) {
        ExportFormat.Mp3 -> "Mỗi chương một file, kèm bìa và danh sách phát: app nghe nhạc nào cũng mở được."
        ExportFormat.M4b -> "Một file có mục lục chương: app nghe sách nói nào cũng mở được, nhớ chỗ nghe dở."
    }

    const val ABOUT_AUDIOBOOK = "Máy đọc cả cuốn rồi ghép thành MỘT file M4B có mục lục chương: app nghe sách nói nào cũng mở được, nhớ chỗ nghe dở."

    /** Lời dưới ô "Kèm nhạc nền" - đúng chữ của web (MUSIC_MIX_HINT). */
    const val MUSIC_MIX_HINT = "Nhạc được trộn thẳng vào file, không tắt riêng được khi nghe."

    /** Lời báo khi MP3 có nhạc ra file .m4a - đúng chữ của hộp Xuất MP3 trên web. */
    const val MP3_MUSIC_NOTE = "Có nhạc nền thì mỗi chương là file .m4a thay vì .mp3 (điện thoại không ghi được MP3 có trộn nhạc). Âm thanh y như bản M4B."

    /** Việc của sách nói và lời báo chạy nền - đúng chữ của hộp Xuất sách nói trên web. */
    const val AUDIOBOOK_PURPOSE = "Để nghe ở app sách nói khác, trên xe hơi hay máy khác."
    const val AUDIOBOOK_NOTE = "Xuất chạy nền, nhường lúc nghe; dừng rồi làm tiếp được."

    /** Máy không mở được thư mục: chỉ đường bằng tên thư mục nếu biết - đúng chữ của web. */
    fun noFolderOpener(folder: String?): String =
        if (folder != null) "Máy không mở được thư mục - mở app Tệp rồi vào $folder" else "Máy không mở được thư mục - mở app Tệp rồi vào thư mục đã chọn"

    /** Hỏi xuất riêng các chương đã đổi hay cả cuốn - đúng chữ của hộp "Có chương đã đổi" trên web. */
    fun changedAsk(count: Int): String = "Bản MP3 bạn xuất trước đây có $count chương đã đổi từ đó. Xuất riêng các chương ấy, hay cả cuốn?"

    /** Dòng phụ của một bản đã xuất: còn mới, hay đã đổi bao nhiêu chương từ lúc ấy. */
    fun pastLine(past: PastExport): String = when {
        !past.stale -> "Còn mới"
        past.kind == ExportKind.Mp3 -> "${past.changed.size} chương đã đổi từ lần xuất này"
        else -> "${past.changed.size} chương đã đổi - cần dựng lại cả file"
    }

    fun pastTitle(past: PastExport): String {
        val label = when (past.kind) {
            ExportKind.Mp3 -> "MP3"
            ExportKind.M4b -> "M4B"
            ExportKind.Audiobook -> "Sách nói"
        }
        // Đích là địa chỉ content: của nơi lưu ("…/document/primary%3AMusic%2FTên"): chỉ nói tên thư mục / file cuối.
        val name = runCatching { java.net.URLDecoder.decode(past.target.replace("+", "%2B"), "UTF-8") }.getOrDefault(past.target)
            .trimEnd('/', '\\').substringAfterLast('/').substringAfterLast('\\').substringAfterLast(':')
        return if (name.isEmpty()) label else "$label · $name"
    }

    /** Dòng nói của hàng "Đang xuất" trong menu của cuốn. */
    fun menuHint(phase: ExportPhase, fraction: Float?): String? = when (phase) {
        is ExportPhase.Running -> if (fraction == null) "Đang xuất" else "Đang xuất · ${(fraction * 100).toInt().coerceIn(0, 99)}%"
        is ExportPhase.Done -> "Đã xuất xong"
        is ExportPhase.Failed -> "Không xuất được"
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
