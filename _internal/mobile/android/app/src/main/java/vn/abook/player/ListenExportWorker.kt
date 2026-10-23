package vn.abook.player

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.work.Data
import androidx.work.ForegroundInfo
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONObject
import vn.abook.player.readaloud.ClipCancel
import vn.abook.player.readaloud.ClipRetry
import vn.abook.player.readaloud.IdleEngine
import vn.abook.player.readaloud.ReadAloud
import vn.abook.player.readaloud.VoiceSpeed
import java.io.File
import java.util.concurrent.ConcurrentHashMap

/**
 * "Xuất sách nói" của sách Nghe ngay trên Android: chỗ lưu và việc nền quanh [ListenExport].
 *
 * Chỗ lưu như xuất M4B: MỘT file `<tên sách>.m4b`, tên và nơi lưu do người dùng đặt bằng hộp thoại "tạo file" của hệ thống ([M4bExports.createIntent]). Việc chạy bằng
 * WorkManager ở dịch vụ nền như xuất M4B (tắt màn hình vẫn chạy); thông báo có tiến độ và nút "Dừng". Phần đã làm (file AAC từng chương) nằm trong `filesDir/export_work/<mã sách>/`
 * - KHÔNG phải cacheDir, Android dọn cache khi máy đầy mà đọc cả cuốn có thể mất hàng giờ: dừng, lỗi hay app bị giết rồi xuất lại thì làm tiếp từ chương đã xong; xuất xong cả cuốn thì
 * thư mục tạm bị xoá; lượt bỏ dở thì thư mục của nó được dọn khi sách bị xoá hay sau [ListenExport.STALE_DAYS] ngày không ai đụng tới ([sweep]). App bị giết giữa chừng thì
 * WorkManager tự chạy lại việc (quyền ghi file đã chọn được giữ cho tới khi xong).
 */
object ListenExports {
    private const val TAG = "audiobook-export"
    private const val KEY_BOOK = "bookId"
    private const val KEY_VOICE = "voice"
    private const val KEY_FILE = "file"
    private const val KEY_COVER = "cover"
    private const val KEY_MUSIC = "music"
    private const val WORK_FOLDER = "export_work"

    /** Giao diện đang mở thì nghe tin của việc nền ("audiobookExport" của EbookLibrary): tiến độ, xong, dừng, lỗi. */
    @Volatile var events: ((JSONObject) -> Unit)? = null

    /** Tin cuối của mỗi lượt đang chạy (theo cuốn): tải lại giao diện vẫn thấy tiến độ ([ExportJobs.running]). */
    val live = ExportLive("audiobook")

    /** Cuốn đang có lượt chạy (kể cả lượt WorkManager vừa chạy lại, chưa báo tin nào): thư mục làm việc của chúng không bị dọn. */
    internal val active: MutableSet<String> = ConcurrentHashMap.newKeySet()

    fun workRoot(context: Context) = File(context.filesDir, WORK_FOLDER)

    internal fun emit(event: JSONObject) {
        live.emit(event)
        runCatching { events?.invoke(event) }
    }

    /**
     * Thư mục tạm của các cuốn không còn trên máy (xoá sách rồi mà chương tạm còn lại) và của lượt bỏ dở quá [ListenExport.STALE_DAYS] ngày dọn đi (soát a62: máy tính chưa
     * bao giờ dọn). Lúc mở app và sau khi một cuốn bị xoá hẳn; cuốn đang xuất không bị đụng.
     */
    fun sweep(context: Context) {
        ListenExport.sweepFolders(workRoot(context), { Store.rawManifest(it) != null }, active.toSet() + live.books())
    }

    /**
     * Bắt đầu xuất cuốn `bookId` bằng giọng `voice` vào `file` (thay lượt đang chạy của cuốn ấy); `music` = ô "Kèm nhạc nền". Trả mã lượt - tin của lượt mang
     * mã này.
     */
    fun start(context: Context, bookId: String, voice: String, file: Uri, drawnCover: File?, music: Boolean = false): String {
        val data = Data.Builder().putString(KEY_BOOK, bookId).putString(KEY_VOICE, voice).putString(KEY_FILE, file.toString()).putBoolean(KEY_MUSIC, music)
        drawnCover?.let { data.putString(KEY_COVER, it.absolutePath) }
        val request = OneTimeWorkRequestBuilder<ListenExportWorker>()
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .setInputData(data.build())
            .apply { ExportJobs.tags("audiobook", bookId).forEach { addTag(it) } }
            .build()
        ExportCancellation.enqueue(context, "$TAG:$bookId", request)
        return request.id.toString()
    }

    fun cancel(context: Context, bookId: String) {
        ExportCancellation.cancel(context, "$TAG:$bookId")
    }

    internal fun foreground(context: Context, work: java.util.UUID, bookId: String, title: String, done: Int, total: Int, fraction: Double?): ForegroundInfo =
        Mp3Exports.foreground(context, work, bookId, title, done, total, TAG, fraction)

    internal fun finished(context: Context, bookId: String, title: String, text: String) = Mp3Exports.finished(context, bookId, title, text, TAG)

    internal class Inputs(val bookId: String?, val voice: String?, val file: Uri?, val cover: File?, val music: Boolean = false)

    internal fun inputs(data: Data) = Inputs(
        data.getString(KEY_BOOK), data.getString(KEY_VOICE), data.getString(KEY_FILE)?.let(Uri::parse), data.getString(KEY_COVER)?.let(::File),
        data.getBoolean(KEY_MUSIC, false),
    )

    /** Mở file vừa xuất bằng app nghe sách nói của máy; false khi không có app nào mở được (hay quyền đã hết). */
    fun open(context: Context, file: Uri): Boolean {
        val intent = Intent(Intent.ACTION_VIEW).setDataAndType(file, M4bExports.MIME)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
        return runCatching { context.startActivity(intent) }.isSuccess
    }
}

/** Lượt xuất sách nói một cuốn (ListenExports.start): đọc từng đoạn, ghép chương, nối thành M4B, ghi vào file người dùng chọn, báo tiến độ ở thông báo và lên giao diện. */
class ListenExportWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    @Volatile private var title = ""

    /** Lượt đọc đang bay của việc này: "Dừng" cắt ổ cắm Edge ngay ([onStopped]) thay vì chờ hết đoạn (soát a62 trên máy tính: 7 giây). */
    private val reading = ClipCancel()

    override fun onStopped() {
        reading.cancel()
    }

    override fun getForegroundInfo(): ForegroundInfo =
        ListenExports.foreground(applicationContext, id, ListenExports.inputs(inputData).bookId.orEmpty(), title, 0, 0, null)

    override fun doWork(): Result = AppLog.worker("ListenExport", this) { execute() }

    private fun execute(): Result {
        val context = applicationContext
        Playback.init(context)
        if (ExportCancellation.cancelled(context, id)) return Result.failure() // việc đã kết thúc hẳn (huỷ / hết 6 giờ): không I/O nào
        val input = ListenExports.inputs(inputData)
        val bookId = input.bookId
        val voice = input.voice
        val file = input.file
        if (bookId == null || voice == null || file == null) return Result.failure()
        val run = id.toString()
        fun event() = JSONObject().put("bookId", bookId).put("run", run)
        var done = 0
        var retrying = false
        var music: ExportMusic? = null
        ListenExports.active += bookId
        try {
            val book = Store.manifest(bookId) ?: throw Mp3Export.Refused("Không tìm thấy sách này trên điện thoại")
            title = book.optString("title").ifEmpty { bookId }
            val chapters = ListenExport.chapters(bookId)
            if (chapters.isEmpty()) throw Mp3Export.Refused("Sách chưa có chương nào có chữ để đọc")
            val reading = ListenExport.Reading(voice, ReadAloud.originNow(bookId), ReadAloud.readingsOf(bookId))
            val work = ListenExport.workFolder(ListenExports.workRoot(context), bookId).apply { mkdirs() }
            // Không vào được dịch vụ nền (Android 12+ khi app đã ở nền lúc việc bắt đầu): vẫn chạy, chỉ không có thông báo đứng.
            runCatching { setForegroundAsync(ListenExports.foreground(context, id, bookId, title, 0, chapters.size, 0.0)).get() }
            music = ExportMusic.open(context, bookId, run, chapters.map { it.id }, input.music, { isStopped }) { index, count ->
                ListenExports.emit(event().put("phase", "music-fetch").put("done", index).put("total", count))
            }
            val mixer = music.mixer
            val guard = music.guard
            val runMusic = if (mixer != null && guard != null) ListenExport.Music(mixer, guard) { audio -> M4bAudio.truePeak(audio, guard) { isStopped } } else null
            val extra = music.music?.let { ExportMusic.listenBytes(Store.bookDir(bookId), it, chapters) } ?: 0L
            val need = ListenExport.plan(chapters, reading, work, null, music = { mixer?.chapter(it) }, extra = extra).bytes
            if (work.usableSpace < need) {
                throw Mp3Export.Refused("Thiếu chỗ làm sách nói (cần ${need shr 20} MB) — bạn dọn bớt rồi xuất lại.")
            }
            var shown = 0L
            fun show(progress: ListenExport.Progress) {
                done = progress.chapter - 1
                val fraction = progress.percent / 100.0
                ListenExports.emit(progress.toJson().put("bookId", bookId).put("run", run).put("done", done).put("total", progress.chapters))
                val now = System.currentTimeMillis()
                if (now - shown > 700) {
                    shown = now
                    runCatching { setForegroundAsync(ListenExports.foreground(context, id, bookId, title, done, progress.chapters, fraction)) }
                }
            }
            val origin = reading.origin
            val readings = reading.readings
            val cache = ReadAloud.cache()
            val runner = ListenExport.Run(
                chapters, reading, work,
                // Một lần đọc trong ClipRetry chỉ để mang [ClipCancel] tới giọng (Edge đăng ký ổ cắm vào đó); thử lại là việc của [ListenExport.Run].
                synth = { text ->
                    ClipRetry.run(online = false, delaysMs = LongArray(0), sleep = { false }, budgetMs = Long.MAX_VALUE / 4, cancel = this.reading) {
                        ReadAloud.readExactly(VoiceSpeed.quality(voice), text, origin, readings) // bản xuất luôn bậc chất lượng (giọng hai bậc, VoiceSpeed)
                    }.getOrThrow().file
                },
                decoder = Clips, outputs = ListenAudio.outputs, progress = ::show, stopped = { isStopped },
                live = { ReadAloud.liveJobs() > 0 },
                timed = { chars, seconds -> runCatching { ReadAloud.speeds().record(voice, chars, seconds) } },
                music = runMusic,
                cached = { text -> cache.contains(VoiceSpeed.quality(voice), text, origin, readings) },
            )
            val stamps = IdleEngine.holding { runner.build() } // giọng trên máy giữ model trong lúc xuất, kể cả lúc đứng chờ người nghe

            val (cover, coverName) = Mp3Export.coverOf(bookId, input.cover?.takeIf { it.isFile }?.readBytes())
            val exportPlan = ListenExport.exportPlan(book, bookId, chapters, stamps, work, cover, coverName)
            val joined = File(work, "all.m4a")
            val out = context.contentResolver.openOutputStream(file, "wt") ?: throw Mp3Export.Refused("Không ghi được vào chỗ đã chọn")
            val result = out.buffered(256 * 1024).use { stream ->
                M4bExport.run(exportPlan, joined, stream, ListenAudio, progress = { joinedChapters, total, _ -> show(ListenExport.encodeProgress(chapters, joinedChapters, total)) }, stopped = { isStopped })
            }
            work.deleteRecursively()
            val missing = mixer?.missing(chapters.map { it.id }) ?: 0
            val lost = if (missing > 0) " $missing đoạn chưa tải được nhạc — bạn tải lại nếu muốn xuất đủ nhạc." else ""
            ListenExports.finished(context, bookId, "Đã xuất sách nói", "$title · ${result.chapters} chương, ${megabytes(result.size)} MB.$lost")
            val finished = event().put("finished", true).put("name", result.name).put("size", result.size).put("chapters", result.chapters)
                .put("chaptersTotal", result.chaptersTotal).put("uri", file.toString())
            if (missing > 0) finished.put("musicMissing", missing)
            // Còn vượt trần sau mọi lượt hạ: vẫn xong, ghi số (như máy tính ghi nhật ký).
            val over = chapters.indices.mapNotNull { index ->
                stamps[index].peakDbtp?.takeIf { guard != null && it > guard.ceilingDbtp }?.let { index + 1 to it }
            }
            if (over.isNotEmpty()) {
                AppLog.w("ListenExport", "sau ${ListenExport.Run.PEAK_RETRIES} lượt mã hoá lại vẫn vượt trần: $over")
                finished.put("overCeiling", org.json.JSONArray(over.map { (chapter, dbtp) -> JSONObject().put("chapter", chapter).put("dbtp", dbtp) }))
            }
            ListenExports.emit(finished)
            Mp3Exports.endIfTimedOut(this)
            return Result.success()
        } catch (stopped: Mp3Export.Stopped) {
            Mp3Exports.endIfTimedOut(this) // hết 6 giờ: kết thúc HẲN việc (WorkManager không chạy lại) TRƯỚC khi dọn gì
            // Hệ thống dừng việc (không phải người dùng): WorkManager chạy lại, file đích, quyền ghi và phần đã làm đều còn.
            if (Mp3Exports.stoppedBySystem(this)) {
                retrying = true
                return Result.retry()
            }
            M4bExports.discard(context, file)
            if (Mp3Exports.timedOut(this)) {
                // Dịch vụ nền hết 6 giờ (Android 15): phần đã đọc xong được giữ, xuất lại là làm tiếp từ đó.
                ListenExports.finished(context, bookId, "Xuất đã dừng: $title", "Hết 6 giờ; giữ phần đã đọc — bạn bấm Xuất lại.")
                ListenExports.emit(event().put("error", Mp3Exports.TIMEOUT_NOTE))
                return Result.failure()
            }
            ListenExports.finished(context, bookId, "Đã dừng xuất", "$title · giữ phần đã đọc — bạn xuất lại để làm tiếp")
            ListenExports.emit(event().put("stopped", true).put("files", done))
            return Result.failure()
        } catch (error: Throwable) {
            Mp3Exports.endIfTimedOut(this) // hết 6 giờ: kết thúc HẲN việc (WorkManager không chạy lại) TRƯỚC khi dọn gì
            if (isStopped && Mp3Exports.stoppedBySystem(this)) {
                retrying = true
                return Result.retry()
            }
            M4bExports.discard(context, file)
            val message = if (isStopped && Mp3Exports.timedOut(this)) Mp3Exports.TIMEOUT_NOTE
                else M4bExports.describe(error, lowSpace = context.filesDir.usableSpace < (32L shl 20))
            ListenExports.finished(context, bookId, "Chưa xuất được", "$title · $message")
            ListenExports.emit(event().put("error", message))
            return Result.failure()
        } finally {
            ListenExports.active -= bookId
            music?.close()
            if (!retrying && (!isStopped || !Mp3Exports.stoppedBySystem(this))) {
                input.cover?.delete()
                M4bExports.release(context, file)
            }
        }
    }

    private fun megabytes(bytes: Long) = if (bytes < 10L shl 20) "%.1f".format(java.util.Locale.US, bytes / 1048576.0) else (bytes shr 20).toString()
}
