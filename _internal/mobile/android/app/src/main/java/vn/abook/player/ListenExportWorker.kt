package vn.abook.player

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONObject
import vn.abook.player.readaloud.ReadAloud
import java.io.File
import java.util.concurrent.ConcurrentHashMap

/**
 * "Xuất sách nói" của sách Nghe ngay trên Android: chỗ lưu và việc nền quanh [ListenExport].
 *
 * Chỗ lưu như xuất M4B: MỘT file `<tên sách>.m4b`, tên và nơi lưu do người dùng đặt bằng hộp thoại "tạo file" của hệ thống ([M4bExports.createIntent]). Việc chạy bằng
 * WorkManager ở dịch vụ nền như xuất M4B (tắt màn hình vẫn chạy); thông báo có tiến độ và nút "Dừng". Phần đã làm (file AAC từng chương) nằm trong `filesDir/export_work/<mã sách>/`
 * - KHÔNG phải cacheDir, Android dọn cache khi máy đầy mà đọc cả cuốn có thể mất hàng giờ: dừng, lỗi hay app bị giết rồi xuất lại thì làm tiếp từ chương đã xong; xuất xong cả cuốn thì
 * thư mục tạm bị xoá. App bị giết giữa chừng thì WorkManager tự chạy lại việc (quyền ghi file đã chọn được giữ cho tới khi xong).
 */
object ListenExports {
    private const val TAG = "audiobook-export"
    private const val KEY_BOOK = "bookId"
    private const val KEY_VOICE = "voice"
    private const val KEY_FILE = "file"
    private const val KEY_COVER = "cover"
    private const val WORK_FOLDER = "export_work"

    /** Giao diện đang mở thì nghe tin của việc nền ("audiobookExport" của EbookLibrary): tiến độ, xong, dừng, lỗi. */
    @Volatile var events: ((JSONObject) -> Unit)? = null

    /** Tin cuối của mỗi lượt đang chạy (theo cuốn): tải lại giao diện vẫn thấy tiến độ ([running]). */
    private val live = ConcurrentHashMap<String, JSONObject>()

    fun workRoot(context: Context) = File(context.filesDir, WORK_FOLDER)

    /** Các lượt đang chạy, tin cuối của từng lượt. */
    fun running(): List<JSONObject> = live.values.toList()

    internal fun emit(event: JSONObject) {
        val book = event.optString("bookId")
        if (event.optBoolean("finished") || event.optBoolean("stopped") || event.has("error")) {
            // Lượt cũ bị thay bằng lượt mới báo "dừng" muộn: không được xoá trạng thái của lượt mới.
            if (live[book]?.optString("run") == event.optString("run")) live.remove(book)
        } else {
            live[book] = event
        }
        runCatching { events?.invoke(event) }
    }

    /** Thư mục tạm của các cuốn không còn trên máy (xoá sách rồi mà chương tạm còn lại) dọn đi. */
    fun sweep(context: Context) {
        val root = workRoot(context)
        for (folder in root.listFiles().orEmpty()) {
            if (folder.isDirectory && Store.rawManifest(folder.name) == null) folder.deleteRecursively()
        }
    }

    /** Bắt đầu xuất cuốn `bookId` bằng giọng `voice` vào `file` (thay lượt đang chạy của cuốn ấy). Trả mã lượt - tin của lượt mang mã này. */
    fun start(context: Context, bookId: String, voice: String, file: Uri, drawnCover: File?): String {
        val data = Data.Builder().putString(KEY_BOOK, bookId).putString(KEY_VOICE, voice).putString(KEY_FILE, file.toString())
        drawnCover?.let { data.putString(KEY_COVER, it.absolutePath) }
        val request = OneTimeWorkRequestBuilder<ListenExportWorker>()
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .setInputData(data.build())
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("$TAG:$bookId", ExistingWorkPolicy.REPLACE, request)
        return request.id.toString()
    }

    fun cancel(context: Context, bookId: String) {
        WorkManager.getInstance(context).cancelUniqueWork("$TAG:$bookId")
    }

    internal fun foreground(context: Context, work: java.util.UUID, bookId: String, title: String, done: Int, total: Int, fraction: Double?): ForegroundInfo =
        Mp3Exports.foreground(context, work, bookId, title, done, total, TAG, fraction)

    internal fun finished(context: Context, bookId: String, title: String, text: String) = Mp3Exports.finished(context, bookId, title, text, TAG)

    internal class Inputs(val bookId: String?, val voice: String?, val file: Uri?, val cover: File?)

    internal fun inputs(data: Data) = Inputs(
        data.getString(KEY_BOOK), data.getString(KEY_VOICE), data.getString(KEY_FILE)?.let(Uri::parse), data.getString(KEY_COVER)?.let(::File),
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

    override fun getForegroundInfo(): ForegroundInfo =
        ListenExports.foreground(applicationContext, id, ListenExports.inputs(inputData).bookId.orEmpty(), title, 0, 0, null)

    /** Người dùng bấm "Dừng" (hay xuất lại cuốn này) khác hệ thống dừng việc (hết giờ chạy nền...): hệ thống dừng thì WorkManager tự chạy lại, file đích phải còn. */
    private fun systemStop(): Boolean = Build.VERSION.SDK_INT >= 31 && stopReason != WorkInfo.STOP_REASON_CANCELLED_BY_APP && stopReason != WorkInfo.STOP_REASON_UNKNOWN

    override fun doWork(): Result {
        val context = applicationContext
        Playback.init(context)
        val input = ListenExports.inputs(inputData)
        val bookId = input.bookId
        val voice = input.voice
        val file = input.file
        if (bookId == null || voice == null || file == null) return Result.failure()
        val run = id.toString()
        fun event() = JSONObject().put("bookId", bookId).put("run", run)
        var done = 0
        var retrying = false
        try {
            val book = Store.manifest(bookId) ?: throw Mp3Export.Refused("Không tìm thấy sách này trên điện thoại")
            title = book.optString("title").ifEmpty { bookId }
            val chapters = ListenExport.chapters(bookId)
            if (chapters.isEmpty()) throw Mp3Export.Refused("Sách chưa có chương nào có chữ để đọc")
            val reading = ListenExport.Reading(voice, ReadAloud.originNow(bookId), ReadAloud.readingsOf(bookId))
            val work = ListenExport.workFolder(ListenExports.workRoot(context), bookId).apply { mkdirs() }
            // Không vào được dịch vụ nền (Android 12+ khi app đã ở nền lúc việc bắt đầu): vẫn chạy, chỉ không có thông báo đứng.
            runCatching { setForegroundAsync(ListenExports.foreground(context, id, bookId, title, 0, chapters.size, 0.0)).get() }
            val need = ListenExport.plan(chapters, reading, work, null).bytes
            if (work.usableSpace < need) {
                throw Mp3Export.Refused("Điện thoại không đủ chỗ trống để làm sách nói (cần khoảng ${need shr 20} MB) - dọn bớt rồi xuất lại")
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
            val runner = ListenExport.Run(
                chapters, reading, work,
                synth = { text -> ReadAloud.readExactly(voice, text, origin, readings).file },
                decoder = Clips, outputs = ListenAudio.outputs, progress = ::show, stopped = { isStopped },
                live = { ReadAloud.liveJobs() > 0 },
                timed = { chars, seconds -> runCatching { ReadAloud.speeds().record(voice, chars, seconds) } },
            )
            val stamps = runner.build()

            val (cover, coverName) = Mp3Export.coverOf(bookId, input.cover?.takeIf { it.isFile }?.readBytes())
            val exportPlan = ListenExport.exportPlan(book, bookId, chapters, stamps, work, cover, coverName)
            val joined = File(work, "all.m4a")
            val out = context.contentResolver.openOutputStream(file, "wt") ?: throw Mp3Export.Refused("Không ghi được vào chỗ đã chọn")
            val result = out.buffered(256 * 1024).use { stream ->
                M4bExport.run(exportPlan, joined, stream, ListenAudio, progress = { joinedChapters, total, _ -> show(ListenExport.encodeProgress(chapters, joinedChapters, total)) }, stopped = { isStopped })
            }
            work.deleteRecursively()
            ListenExports.finished(context, bookId, "Đã xuất sách nói", "$title · ${result.chapters} chương, ${megabytes(result.size)} MB.")
            ListenExports.emit(event().put("finished", true).put("name", result.name).put("size", result.size).put("chapters", result.chapters)
                .put("chaptersTotal", result.chaptersTotal).put("uri", file.toString()))
            return Result.success()
        } catch (stopped: Mp3Export.Stopped) {
            // Hệ thống dừng việc (không phải người dùng): WorkManager chạy lại, file đích, quyền ghi và phần đã làm đều còn.
            if (systemStop()) {
                retrying = true
                return Result.retry()
            }
            M4bExports.discard(context, file)
            ListenExports.finished(context, bookId, "Đã dừng xuất sách nói", "$title · phần đã đọc xong được giữ, xuất lại để làm tiếp")
            ListenExports.emit(event().put("stopped", true).put("files", done))
            return Result.failure()
        } catch (error: Throwable) {
            M4bExports.discard(context, file)
            val message = M4bExports.describe(error, lowSpace = context.filesDir.usableSpace < (32L shl 20))
            ListenExports.finished(context, bookId, "Không xuất được sách nói", "$title · $message")
            ListenExports.emit(event().put("error", message))
            return Result.failure()
        } finally {
            if (!retrying) {
                input.cover?.delete()
                M4bExports.release(context, file)
            }
        }
    }

    private fun megabytes(bytes: Long) = if (bytes < 10L shl 20) "%.1f".format(java.util.Locale.US, bytes / 1048576.0) else (bytes shr 20).toString()
}
