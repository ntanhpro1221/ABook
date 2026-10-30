package vn.abook.player.ui.studio

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
    BookFile("bookfile-job", "File sách"),
    M4b("m4b-job", "M4B"),
    Mp3("mp3-job", "Thư mục MP3");

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
                phase == "listen" && total > 0 -> "Đã gom $done/$total chương"
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
        val extra = if (options.musicPending > 0) "; cộng thêm ${options.musicPending} bài nhạc khi xuất" else ""
        return "Cỡ ước tính: khoảng ${formatSize(options.bytes)}$extra."
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
            result.chapters?.let { c -> result.chaptersTotal?.takeIf { c < it }?.let { "$c/$it chương - chương chưa xong không có trong file" } },
            result.missingSources.takeIf { it > 0 }?.let { "$it file nguồn chương đã bị dời hay xoá nên không có trong gói" },
            result.musicMissing.takeIf { it > 0 }?.let { "$it đoạn thiếu nhạc vì chưa tải được bài" },
            if (result.coverBroken) "ảnh bìa của sách bị hỏng nên dùng bìa vẽ từ tên" else null,
            result.skipped.takeIf { it.isNotEmpty() }?.let { "chưa có chương nào nên bỏ qua: " + it.joinToString(", ") { part -> "Phần $part" } },
        )
        return StudioExportOutcome(StudioExportText.doneTitle(machine), listOf((listOf(name) + detail).filter { it.isNotEmpty() }.joinToString(" · ")).filter { it.isNotEmpty() }, notes)
    }

    /** Điều còn lại sau khi huỷ, theo kiểu xuất (web `stoppedNote`). */
    fun stoppedNote(kind: StudioExportKind): String = when (kind) {
        StudioExportKind.BookFile -> "Chưa có file sách nào được ghi."
        StudioExportKind.M4b -> "Chưa có file M4B nào được ghi."
        StudioExportKind.Mp3 -> "Các chương đã ghi dở được xoá."
    }

    /** Loại file của một lần xuất trước đây, nói bằng cái người dùng nhận ra. */
    fun pastLabel(past: StudioPast): String = when (past.kind) {
        "mp3" -> "MP3"
        "m4b" -> "M4B"
        "abookproj" -> "Dự án"
        else -> "File sách"
    }

    /** Tên cuối của đích (chỉ TÊN, không đường dẫn) - đích do máy tính gửi, có thể là đường Windows. */
    fun pastName(past: StudioPast): String = past.target.trimEnd('/', '\\').substringAfterLast('/').substringAfterLast('\\')

    fun pastTitle(past: StudioPast): String = listOf(pastLabel(past), pastName(past)).filter { it.isNotEmpty() }.joinToString(" · ")

    fun pastLine(past: StudioPast): String = if (past.changed == 0) "Còn mới" else "${past.changed} chương đã đổi từ lần xuất này"

    /** Mô tả ngắn của từng kiểu, cho người chưa biết chúng khác nhau chỗ nào. */
    fun about(kind: StudioExportKind): String = when (kind) {
        StudioExportKind.BookFile -> StudioExportText.ABOUT_BOOKFILE
        StudioExportKind.M4b -> ExportText.about(ExportFormat.M4b)
        StudioExportKind.Mp3 -> ExportText.about(ExportFormat.Mp3)
    }
}

object StudioExportText {
    const val TITLE = "Xuất sách"
    const val LEAD = "Máy tính đóng gói; file nằm ở thư mục “Đã xuất” trong thư viện của máy tính."
    const val EXPORT = "Xuất"
    const val CANCEL = "Huỷ"
    const val STOPPING = "Đang dừng"
    const val RETRY = "Xuất lại"
    const val LOADING = "Đang mở hộp Xuất"
    const val MUSIC = "Kèm nhạc nền"
    const val BUSY_BOOKFILE = "Đang đóng gói sách"
    const val ABOUT_BOOKFILE = "Một file .abook mang cả chữ và tiếng: mở được ở ABook trên máy khác."
    const val NO_CHAPTERS = "Sách chưa có chương nào để xuất."
    const val NO_AUDIO = "Chưa có chương nào thu xong để xuất."
    const val FFMPEG_TITLE = "Máy tính chưa có ffmpeg"
    const val FFMPEG_LINE = "Cần ffmpeg để ghép âm thanh. Bạn tải nó trên máy tính, ở hộp Xuất của ABook."
    const val HISTORY = "Đã xuất"
    const val CANCEL_TITLE = "Huỷ xuất?"
    const val CANCEL_CONFIRM = "Huỷ xuất"
    const val CANCEL_KEEP = "Tiếp tục xuất"
    const val STOPPING_NOTE = "Dừng ở chỗ an toàn kế tiếp."
    const val FAILED = "Không xuất được"
    const val STOPPED = "Đã huỷ xuất"

    fun elapsed(seconds: Double) = "đã ${Fmt.clock(seconds)}"

    /** "Đã xuất vào máy tính NGDtuanh-Lecoo": nói rõ file nằm ở máy nào. */
    fun doneTitle(machine: String): String = if (machine.isBlank()) "Đã xuất vào máy tính" else "Đã xuất vào máy tính $machine"

    fun failedTitle(kind: StudioExportKind): String = when (kind) {
        StudioExportKind.BookFile -> "Không xuất được file sách"
        StudioExportKind.M4b -> "Không xuất được M4B"
        StudioExportKind.Mp3 -> "Không xuất được MP3"
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
