package vn.abook.player.ui.studio

import vn.abook.player.S

import vn.abook.player.ui.data.dotJoined
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject
import vn.abook.player.StudioErrors
import vn.abook.player.StudioPoller
import vn.abook.player.StudioPolling
import vn.abook.player.formatSize
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.export.ExportEvent
import vn.abook.player.ui.export.ExportFormat
import vn.abook.player.ui.export.ExportJson
import vn.abook.player.ui.export.ExportKind
import vn.abook.player.ui.export.ExportMusic
import vn.abook.player.ui.export.ExportProgress
import vn.abook.player.ui.export.ExportText

// "Xuất" của một dự án (NATIVE_REMOTE_STUDIO.md §6.11). Port từ ExportBook.tsx / bookFileExport.ts: việc xuất chạy TRÊN MÁY TÍNH (webui/export_jobs.py), file nằm trong thư mục
// "Đã xuất" của thư viện máy tính. Điện thoại chọn kiểu, bấm "Xuất", theo tiến độ (1 giây một lần khi chạy) và có thể huỷ; máy tính chỉ trả TÊN file, không đường dẫn.
// Phần tiến độ M4B / MP3 dùng lại ExportText của màn Xuất trên điện thoại (cùng pha, cùng chữ).

/** Ba kiểu xuất của máy tính; `job` là tên đường `POST/GET /api/books/<id>/<job>` ([vn.abook.player.StudioPaths.exportJob]). */
enum class StudioExportKind(val job: String, override val label: String) : Choice {
    BookFile("bookfile-job", S.s_file_sach_ccdcf961),
    M4b("m4b-job", S.s_m4b_c793d08a),
    Mp3("mp3-job", S.s_thu_muc_mp3_2eea06d7);

    override val key: String get() = job

    /** M4B và MP3 là âm thanh ghép (nhạc nền, bìa, ffmpeg); file sách chỉ đóng gói. */
    val audio: Boolean get() = this != BookFile
}

/** Kết quả một lượt xuất: chỉ TÊN file / thư mục (máy tính bỏ đường dẫn trước khi trả). */
@Immutable
data class StudioExportResult(
    val file: String,
    val folder: String,
    val size: Long,
    val parts: Int,
    val files: Int?,
    val chapters: Int?,
    val chaptersTotal: Int?,
    val missingSources: Int,
    val format: String,
    val coverBroken: Boolean,
    val musicMissing: Int,
    val skipped: List<Int>,
)

/** Lời đáp của `GET/POST .../<kiểu>-job`: máy tính nhớ lượt xuất gần nhất của mỗi cuốn. */
@Immutable
data class StudioExportJob(
    /** idle | running | done | error | cancelled. */
    val state: String,
    val id: String,
    val phase: String?,
    val done: Int?,
    val total: Int?,
    val chapter: Int?,
    val chapters: Int?,
    val percent: Int?,
    val secondsLeft: Long?,
    val waiting: String?,
    val peakRound: Int?,
    val peakOver: Int?,
    /** Giây đã làm (đang chạy). */
    val elapsed: Double,
    /** Giây kể từ lúc xong / hỏng; null khi đang chạy. */
    val finishedAgo: Double?,
    val result: StudioExportResult?,
    val error: String,
) {
    val running: Boolean get() = state == "running"
}

/** Một lần xuất trước đây (`GET export-history`): `changed` = số chương đã đổi từ lúc ấy. */
@Immutable
data class StudioPast(val kind: String, val target: String, val changed: Int)

/** Những điều hộp Xuất hỏi thêm: cỡ file sách, nhạc nền kèm được không, ffmpeg, lần xuất trước. Hỏi hụt từng phần thì để mặc định, không chặn hộp. */
@Immutable
data class StudioExportOptions(
    val bytes: Long = 0,
    val musicPending: Int = 0,
    val music: ExportMusic = ExportMusic(),
    /** null = máy không nói (hỏi hụt): không chặn nút "Xuất". */
    val ffmpegReady: Boolean? = null,
    val history: List<StudioPast> = emptyList(),
)

internal object StudioExportJson {
    private fun JSONObject.int(key: String): Int? = if (isNull(key) || !has(key)) null else optInt(key)
    private fun JSONObject.long(key: String): Long? = if (isNull(key) || !has(key)) null else optLong(key)

    fun result(json: JSONObject) = StudioExportResult(
        file = json.text("file"),
        folder = json.text("folder"),
        size = json.optLong("size"),
        parts = json.optJSONArray("parts")?.length() ?: 0,
        files = json.int("files"),
        chapters = json.int("chapters"),
        chaptersTotal = json.int("chaptersTotal"),
        missingSources = json.optJSONArray("missingSources")?.length() ?: 0,
        format = json.text("format"),
        coverBroken = json.optBoolean("coverBroken"),
        musicMissing = json.optInt("musicMissing"),
        skipped = json.optJSONArray("skipped").objects().map { it.optInt("part") },
    )

    fun job(json: JSONObject) = StudioExportJob(
        state = json.text("state").ifEmpty { "idle" },
        id = json.text("id"),
        phase = json.textOrNull("phase"),
        done = json.int("done"),
        total = json.int("total"),
        chapter = json.int("chapter"),
        chapters = json.int("chapters"),
        percent = json.int("percent"),
        secondsLeft = json.long("secondsLeft"),
        waiting = json.textOrNull("waiting"),
        peakRound = json.int("peakRound"),
        peakOver = json.int("peakOver"),
        elapsed = json.optDouble("elapsed", 0.0).let { if (it.isFinite()) it else 0.0 },
        finishedAgo = if (json.has("finishedAgo") && !json.isNull("finishedAgo")) json.optDouble("finishedAgo").takeIf { it.isFinite() } else null,
        result = json.optJSONObject("result")?.let(::result),
        error = json.text("error"),
    )

    fun past(json: JSONObject) = StudioPast(json.text("kind"), json.text("target"), json.optJSONArray("changed")?.length() ?: 0)

    fun options(size: JSONObject?, music: JSONObject?, ffmpeg: JSONObject?, history: List<JSONObject>?) = StudioExportOptions(
        bytes = size?.optLong("bytes") ?: 0,
        musicPending = size?.optInt("musicPending") ?: 0,
        music = ExportJson.music(music),
        ffmpegReady = ffmpeg?.takeIf { it.has("ready") }?.optBoolean("ready"),
        history = history.orEmpty().map(::past),
    )
}

/** Điều cần nói về một lượt xuất xong: tiêu đề, dòng tên file, các lưu ý (thiếu chương, nhạc, bìa...). */
@Immutable
data class StudioExportOutcome(val title: String, val lines: List<String>, val notes: List<String>)

object StudioExportLogic {
    /** Nhịp hỏi khi việc đang chạy (web `ExportJobHost`: 1 giây). */
    const val RUNNING_MS = 1_000L

    /** Xong cách đây không quá chừng này thì mở hộp là còn thấy kết quả; xa hơn chỉ còn dòng trong "Đã xuất" (web `RECENT_SECONDS`). */
    const val RECENT_SECONDS = 30 * 60

    /** Việc có đáng hiện kết quả không: đang chạy, hay vừa xong / hỏng / huỷ gần đây. Chưa từng xuất (idle) thì không. */
    fun shown(job: StudioExportJob?): Boolean = when {
        job == null || job.state == "idle" -> false
        job.running -> true
        else -> (job.finishedAgo ?: 0.0) <= RECENT_SECONDS
    }

    /** Phần của thanh tiến độ mỗi pha của file sách chiếm (web `BOOK_FILE_SPAN`): gom chương là gần hết, rồi ghi gói. */
    private val SPAN = mapOf(
        "prepare" to (0.0f to 0.02f), "listen" to (0.02f to 0.85f), "views" to (0.85f to 0.85f), "hash" to (0.85f to 0.85f), "write" to (0.85f to 1.0f),
    )

    private fun event(kind: StudioExportKind, job: StudioExportJob) = ExportEvent(
        kind = if (kind == StudioExportKind.Mp3) ExportKind.Mp3 else ExportKind.M4b, bookId = "", run = job.id, phase = job.phase,
        done = job.done, total = job.total, percent = job.percent, chapter = job.chapter, chapters = job.chapters, secondsLeft = job.secondsLeft,
        waiting = job.waiting, peakRound = job.peakRound, peakOver = job.peakOver,
    )

    /** Tiêu đề lúc đang làm. */
    fun busy(kind: StudioExportKind): String = when (kind) {
        StudioExportKind.BookFile -> StudioExportText.BUSY_BOOKFILE
        StudioExportKind.M4b -> ExportText.busy(ExportKind.M4b)
        StudioExportKind.Mp3 -> ExportText.busy(ExportKind.Mp3)
    }

    /** Dòng tiến độ + phần đã xong (null = chưa biết). File sách có pha + "đã/tổng chương"; M4B / MP3 dùng ExportText; chưa có pha nào thì chỉ nói thời gian đã trôi. */
    fun progress(kind: StudioExportKind, job: StudioExportJob): ExportProgress {
        if (kind == StudioExportKind.BookFile) {
            val phase = job.phase ?: return ExportProgress(StudioExportText.elapsed(job.elapsed), StudioExportText.BUSY_BOOKFILE, null)
            val (from, to) = SPAN[phase] ?: (0f to 0f)
            val total = job.total ?: 0
            val done = minOf(job.done ?: 0, total)
            val fraction = from + (to - from) * if (total > 0) done.toFloat() / total else 0f
            val text = when {
                phase == "listen" && total > 0 -> S.s_da_gom_0_1_chuong_ed4dbcd9(done, total)
                (phase == "hash" || phase == "write") && total > 0 -> "${formatSize(done.toLong())}/${formatSize(total.toLong())}"
                else -> StudioExportText.BUSY_BOOKFILE
            }
            return ExportProgress("$text · ${StudioExportText.elapsed(job.elapsed)}", ExportText.spokenProgress(StudioExportText.BUSY_BOOKFILE, fraction), if (phase == "prepare") null else fraction)
        }
        val hasPhase = job.phase != null || (job.total ?: 0) > 0
        if (!hasPhase) return ExportProgress(StudioExportText.elapsed(job.elapsed), busy(kind), null)
        return ExportText.progress(event(kind, job))
    }

    /** Máy đang chờ gì trước khi làm được (ffmpeg chưa có): `Busy` 409 của lúc bắt đầu đã mang lời của máy; còn lại là máy nói "chưa được". */
    fun needsFfmpeg(kind: StudioExportKind, withMusic: Boolean, options: StudioExportOptions): Boolean =
        options.ffmpegReady == false && (kind == StudioExportKind.M4b || (kind == StudioExportKind.Mp3 && withMusic))

    /** Ô "Kèm nhạc nền": chỉ MP3 / M4B, và chỉ khi cuốn có kế hoạch nhạc. */
    fun showMusic(kind: StudioExportKind, options: StudioExportOptions): Boolean = kind.audio && options.music.available

    /** "Kèm nhạc nền" đang bật: người dùng đã chọn thì theo đó, chưa thì theo công tắc Nhạc nền của cuốn. */
    fun musicOn(kind: StudioExportKind, options: StudioExportOptions, chosen: Boolean?): Boolean = showMusic(kind, options) && (chosen ?: options.music.enabled)

    /** Thân yêu cầu bắt đầu (web `startExport` / `packBookFile`): nơi lưu rỗng = thư mục "Đã xuất" của thư viện máy tính. `cover` là bìa vẽ từ tên (data URL) cho M4B / MP3. */
    fun body(kind: StudioExportKind, music: Boolean, cover: String): JSONObject = JSONObject().put("target", "").apply {
        when (kind) {
            StudioExportKind.BookFile -> put("series", false)
            else -> {
                if (cover.isNotEmpty()) put("cover", cover)
                if (music) put("music", true)
            }
        }
    }

    /** Có bắt đầu được: sách phải có chương. File sách mang cả chữ chương chưa có tiếng; M4B / MP3 cần chương đã thu. */
    fun canExport(kind: StudioExportKind, book: StudioBook): Boolean =
        if (kind == StudioExportKind.BookFile) book.chaptersTotal > 0 || book.chaptersCompleted > 0 else book.chaptersCompleted > 0

    /** Lý do không xuất được, hay rỗng. */
    fun blocker(kind: StudioExportKind, book: StudioBook): String = when {
        canExport(kind, book) -> ""
        kind == StudioExportKind.BookFile -> StudioExportText.NO_CHAPTERS
        else -> StudioExportText.NO_AUDIO
    }

    /** Dòng cỡ ước của file sách; rỗng khi chưa biết. */
    fun sizeNote(options: StudioExportOptions): String {
        if (options.bytes <= 0) return ""
        val extra = if (options.musicPending > 0) S.s_cong_them_0_bai_nhac_khi_xuat_5661e4a4(options.musicPending) else ""
        return S.s_co_uoc_tinh_khoang_0_1_6d7f5901(formatSize(options.bytes), extra)
    }

    /** Lượt xuất xong nói gì: nằm ở máy nào, tên file / thư mục, cỡ, và phần thiếu. */
    fun outcome(kind: StudioExportKind, result: StudioExportResult, machine: String): StudioExportOutcome {
        val count = result.files ?: result.parts.takeIf { it > 0 }
        val name = result.file.ifEmpty { result.folder }
        val detail = listOfNotNull(
            if (result.file.isEmpty() && count != null) "$count file" else null,
            result.size.takeIf { it > 0 }?.let { formatSize(it) },
        )
        val notes = listOfNotNull(
            result.chapters?.let { c -> result.chaptersTotal?.takeIf { c < it }?.let { S.s_0_1_chuong_chuong_chua_xong_khong_co_trong_35795edf(c, it) } },
            result.missingSources.takeIf { it > 0 }?.let { S.s_0_file_nguon_chuong_da_bi_doi_hay_xoa_nen_a83aaefb(it) },
            result.musicMissing.takeIf { it > 0 }?.let { S.s_0_doan_thieu_nhac_vi_chua_tai_duoc_bai_66255efe(it) },
            if (result.coverBroken) S.s_anh_bia_cua_sach_bi_hong_nen_dung_bia_ve_t_782534c3 else null,
            result.skipped.takeIf { it.isNotEmpty() }?.let { S.s_chua_co_chuong_nao_nen_bo_qua_09add84f + it.joinToString(", ") { part -> S.s_phan_0_7c77642d(part) } },
        )
        return StudioExportOutcome(StudioExportText.doneTitle(machine), listOf((listOf(name) + detail).dotJoined()).filter { it.isNotEmpty() }, notes)
    }

    /** Điều còn lại sau khi huỷ, theo kiểu xuất (web `stoppedNote`). */
    fun stoppedNote(kind: StudioExportKind): String = when (kind) {
        StudioExportKind.BookFile -> S.s_chua_co_file_sach_nao_duoc_ghi_acffb6e0
        StudioExportKind.M4b -> S.s_chua_co_file_m4b_nao_duoc_ghi_341f690c
        StudioExportKind.Mp3 -> S.s_cac_chuong_da_ghi_do_duoc_xoa_55c0187f
    }

    /** Loại file của một lần xuất trước đây, nói bằng cái người dùng nhận ra. */
    fun pastLabel(past: StudioPast): String = when (past.kind) {
        "mp3" -> S.s_mp3_b84e4872
        "m4b" -> S.s_m4b_c793d08a
        "abookproj" -> S.s_du_an_4f139d43
        else -> S.s_file_sach_ccdcf961
    }

    /** Tên cuối của đích (chỉ TÊN, không đường dẫn) - đích do máy tính gửi, có thể là đường Windows. */
    fun pastName(past: StudioPast): String = past.target.trimEnd('/', '\\').substringAfterLast('/').substringAfterLast('\\')

    fun pastTitle(past: StudioPast): String = listOf(pastLabel(past), pastName(past)).dotJoined()

    fun pastLine(past: StudioPast): String = if (past.changed == 0) S.s_con_moi_47b72502 else S.s_0_chuong_da_doi_tu_lan_xuat_nay_e38aaaee(past.changed)

    /** Mô tả ngắn của từng kiểu, cho người chưa biết chúng khác nhau chỗ nào. */
    fun about(kind: StudioExportKind): String = when (kind) {
        StudioExportKind.BookFile -> StudioExportText.ABOUT_BOOKFILE
        StudioExportKind.M4b -> ExportText.about(ExportFormat.M4b)
        StudioExportKind.Mp3 -> ExportText.about(ExportFormat.Mp3)
    }
}

object StudioExportText {
    const val TITLE = S.s_xuat_sach_792effe5
    const val LEAD = S.s_may_tinh_dong_goi_file_nam_o_thu_muc_da_xu_40dbce64
    const val EXPORT = S.s_xuat_b2ebc56b
    const val CANCEL = S.s_huy_96732485
    const val STOPPING = S.s_dang_dung_9b35aeb5
    const val RETRY = S.s_xuat_lai_4ebb6635
    const val LOADING = S.s_dang_mo_hop_xuat_26410b21
    const val MUSIC = S.s_kem_nhac_nen_c616e8d2
    const val BUSY_BOOKFILE = S.s_dang_dong_goi_sach_ac7bab85
    const val ABOUT_BOOKFILE = S.s_mot_file_abook_mang_ca_chu_va_tieng_mo_duo_cc2f21c6
    const val NO_CHAPTERS = S.s_sach_chua_co_chuong_nao_de_xuat_cbf33efb
    const val NO_AUDIO = S.s_chua_co_chuong_nao_thu_xong_de_xuat_3b428245
    const val FFMPEG_TITLE = S.s_may_tinh_chua_co_ffmpeg_7d05b938
    const val FFMPEG_LINE = S.s_can_ffmpeg_de_ghep_am_thanh_ban_tai_no_tre_5e34a9d9
    const val HISTORY = S.s_da_xuat_d801674e
    const val CANCEL_TITLE = S.s_huy_xuat_fe04b8c2
    const val CANCEL_CONFIRM = S.s_huy_xuat_ca425e96
    const val CANCEL_KEEP = S.s_tiep_tuc_xuat_1c5b45b3
    const val STOPPING_NOTE = S.s_dung_o_cho_an_toan_ke_tiep_9103075b
    const val FAILED = S.s_chua_xuat_duoc_27b1025b
    const val STOPPED = S.s_da_dung_xuat_ab8ac9d1

    fun elapsed(seconds: Double) = S.s_da_0_0e900305(Fmt.clock(seconds))

    /** "Đã xuất vào máy tính MayCuaNam-Laptop": nói rõ file nằm ở máy nào. */
    fun doneTitle(machine: String): String = if (machine.isBlank()) S.s_da_xuat_vao_may_tinh_d121586e else S.s_da_xuat_vao_may_tinh_0_19bf0167(machine)

    fun failedTitle(kind: StudioExportKind): String = when (kind) {
        StudioExportKind.BookFile -> S.s_chua_xuat_duoc_file_sach_43236ec7
        StudioExportKind.M4b -> S.s_chua_xuat_duoc_m4b_5a39de4c
        StudioExportKind.Mp3 -> S.s_chua_xuat_duoc_mp3_1550e65a
    }
}

/**
 * Hộp Xuất của một dự án: kiểu đang chọn, "Kèm nhạc nền", việc đang chạy của kiểu ấy (hỏi 1 giây một lần khi chạy, không thì không hỏi theo nhịp), lần xuất trước.
 * Mỗi kiểu có việc riêng ở máy tính nên đổi kiểu thì hỏi lại việc của kiểu mới. Sách (số chương đã thu) lấy từ chính trang dự án.
 */
@Stable
class StudioExportState(private val project: StudioProjectState, pause: suspend (Long) -> Unit = { delay(it) }) {
    private val session get() = project.session
    private val bookId get() = project.bookId

    /** Việc đang hỏi, kèm kiểu của nó: lời đáp về muộn của kiểu cũ không hiện cho kiểu mới. */
    @Immutable
    data class Seen(val kind: StudioExportKind, val job: StudioExportJob)

    /** Bìa vẽ từ tên sách (data URL) cho M4B / MP3: chỉ Android vẽ được nên màn đặt vào; rỗng = không gửi bìa. */
    var drawCover: (String) -> String = { "" }

    var kind by mutableStateOf(StudioExportKind.BookFile)
        private set

    /** null = chưa chọn: theo công tắc Nhạc nền của cuốn. */
    var music by mutableStateOf<Boolean?>(null)
        private set

    var options by mutableStateOf(StudioExportOptions())
        private set

    var loaded by mutableStateOf(false)
        private set

    var starting by mutableStateOf(false)
        private set

    /** Đã bấm Huỷ mà máy chưa dừng (dừng ở chỗ an toàn kế tiếp). */
    var stopping by mutableStateOf(false)
        private set

    var problem by mutableStateOf("")
        private set

    private var latest: Seen? = null

    private val poller = StudioPoller<Seen>(
        {
            val asked = kind
            val seen = Seen(asked, session.source.exportJob(session.computer, bookId, asked))
            val before = latest
            latest = seen
            if (before != null && before.kind == asked && before.job.running && !seen.job.running) {
                // Việc vừa xong / hỏng / huỷ: hết "đang dừng", và lần xuất này vào danh sách "Đã xuất".
                stopping = false
                reloadQuietly()
            }
            seen
        },
        { seen -> if (seen?.job?.running == true) StudioExportLogic.RUNNING_MS else null },
        pause,
    )
    val poll: StateFlow<StudioPolling.Poll<Seen>> get() = poller.state

    /** Việc của kiểu đang chọn (null khi chưa hỏi xong cho kiểu này). */
    val job: StudioExportJob? get() = poller.state.value.data?.takeIf { it.kind == kind }?.job

    val musicOn: Boolean get() = StudioExportLogic.musicOn(kind, options, music)

    val machine: String get() = session.name

    /** Hỏi những điều thêm một lần, rồi theo việc. Việc đang chạy sẵn (máy tính đang xuất từ trước) hiện ngay. */
    suspend fun run() {
        if (!loaded) reload()
        poller.run()
    }

    suspend fun refresh() = poller.refresh()

    private suspend fun reload() {
        try {
            options = session.source.exportOptions(session.computer, bookId)
            loaded = true
            problem = ""
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            val failure = StudioErrors.of(error)
            session.note(failure)
            problem = StudioText.failure(failure)
        }
    }

    private suspend fun reloadQuietly() {
        try {
            options = session.source.exportOptions(session.computer, bookId)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            // Danh sách lần xuất trước chỉ để xem: hỏng thì giữ bản cũ.
        }
    }

    /** "Thử lại" khi chưa mở được hộp. */
    fun retry() {
        session.scope.launch {
            reload()
            poller.refresh()
        }
    }

    fun choose(next: StudioExportKind) {
        if (next == kind) return
        kind = next
        problem = ""
        stopping = false
        session.scope.launch { poller.refresh() }
    }

    fun setMusic(value: Boolean) {
        music = value
    }

    /** "Xuất": bắt đầu lượt của kiểu đang chọn; máy tính từ chối (409: ffmpeg, đang bận) thì nói lời của máy. */
    fun start() {
        val book = project.poll.value.data?.book
        val asked = kind
        if (starting || job?.running == true || (book != null && !StudioExportLogic.canExport(asked, book))) return
        starting = true
        problem = ""
        stopping = false
        val body = StudioExportLogic.body(asked, musicOn, if (asked.audio) drawCover(book?.title.orEmpty()) else "")
        session.scope.launch {
            try {
                session.source.exportStart(session.computer, bookId, asked, body)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                problem = StudioText.failure(failure)
            } finally {
                starting = false
            }
            poller.refresh()
        }
    }

    /** "Huỷ" đã được xác nhận: máy dừng ở chỗ an toàn kế tiếp rồi trả `cancelled`. */
    fun cancel() {
        val asked = kind
        if (job?.running != true || stopping) return
        stopping = true
        session.scope.launch {
            try {
                session.source.exportCancel(session.computer, bookId, asked)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                problem = StudioText.failure(failure)
                stopping = false
            }
            poller.refresh()
        }
    }
}
