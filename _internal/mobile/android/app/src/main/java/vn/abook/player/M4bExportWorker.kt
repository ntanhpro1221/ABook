package vn.abook.player

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.DocumentsContract
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONObject
import java.io.File
import java.io.IOException

/**
 * "Xuất M4B" trên Android: chỗ lưu và việc nền quanh [M4bExport].
 *
 * Chỗ lưu là MỘT file người dùng đặt tên và chọn nơi bằng hộp thoại "tạo file" của hệ thống (ACTION_CREATE_DOCUMENT, như "Lưu thành…"
 * của sách) - khác xuất MP3 (cả thư mục): M4B là một file duy nhất nên không cần nhớ thư mục. Việc chạy bằng WorkManager ở dịch vụ nền
 * như xuất MP3 (ra khỏi app, tắt màn hình vẫn chạy tiếp); thông báo có tiến độ và nút "Dừng". Hỏng hay dừng giữa chừng thì file đã tạo ở nơi
 * lưu bị xoá - không để lại file dở trong thư mục của người dùng.
 */
object M4bExports {
    private const val TAG = "m4b-export"
    private const val KEY_BOOK = "bookId"
    private const val KEY_FILE = "file"
    private const val KEY_COVER = "cover"

    /** Giao diện đang mở thì nghe tin của việc nền ("m4bExport" của EbookLibrary): tiến độ, xong, dừng, lỗi. */
    @Volatile var events: ((JSONObject) -> Unit)? = null

    /** Hộp thoại "tạo file" của hệ thống, mở sẵn tên "<tên sách>.m4b". */
    fun createIntent(title: String): Intent =
        Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
            .setType(MIME)
            .putExtra(Intent.EXTRA_TITLE, M4bExport.fileName(title))
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)

    // Kiểu file .m4b của hệ thống là audio/mp4 (đuôi .m4b thuộc kiểu ấy nên bộ lưu trữ giữ đúng tên người dùng đặt).
    const val MIME = "audio/mp4"

    /** Giữ quyền ghi file vừa tạo cho tới khi việc nền xong (tiến trình bị giết giữa chừng thì WorkManager chạy lại việc). */
    fun remember(context: Context, file: Uri) {
        if (file.scheme == "file") return
        runCatching {
            context.contentResolver.takePersistableUriPermission(file, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        }
    }

    internal fun release(context: Context, file: Uri) {
        if (file.scheme == "file") return
        runCatching {
            context.contentResolver.releasePersistableUriPermission(file, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        }
    }

    /** Xoá file đích đã tạo (hỏng / dừng / huỷ). Không xoá được thì thôi - cùng lắm còn một file rỗng. */
    internal fun discard(context: Context, file: Uri) {
        runCatching {
            if (file.scheme == "file") File(file.path!!).delete() else DocumentsContract.deleteDocument(context.contentResolver, file)
        }
    }

    /** Bắt đầu làm file M4B của cuốn `bookId` vào `file` (thay lượt đang chạy của cuốn ấy). Trả mã lượt - tin của lượt mang mã này. */
    fun start(context: Context, bookId: String, file: Uri, drawnCover: File?): String {
        val data = Data.Builder().putString(KEY_BOOK, bookId).putString(KEY_FILE, file.toString())
        drawnCover?.let { data.putString(KEY_COVER, it.absolutePath) }
        val request = OneTimeWorkRequestBuilder<M4bExportWorker>()
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .setInputData(data.build())
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("$TAG:$bookId", ExistingWorkPolicy.REPLACE, request)
        return request.id.toString()
    }

    fun cancel(context: Context, bookId: String) {
        WorkManager.getInstance(context).cancelUniqueWork("$TAG:$bookId")
    }

    internal fun emit(event: JSONObject) {
        runCatching { events?.invoke(event) }
    }

    internal fun foreground(context: Context, work: java.util.UUID, bookId: String, title: String, done: Int, total: Int, fraction: Double?): ForegroundInfo =
        Mp3Exports.foreground(context, work, bookId, title, done, total, TAG, fraction)

    internal fun finished(context: Context, bookId: String, title: String, text: String) = Mp3Exports.finished(context, bookId, title, text, TAG)

    internal fun inputs(data: Data): Triple<String?, Uri?, File?> = Triple(
        data.getString(KEY_BOOK),
        data.getString(KEY_FILE)?.let(Uri::parse),
        data.getString(KEY_COVER)?.let(::File),
    )

    private const val OUT_OF_SPACE = "Hết chỗ trống trên điện thoại hoặc ở nơi lưu - dọn bớt rồi xuất lại"

    /** Hết chỗ là lỗi người nghe tự xử được: nói thẳng chứ không đưa mã lỗi của hệ thống. */
    internal fun describe(error: Throwable, lowSpace: Boolean = false): String {
        var cause: Throwable? = error
        while (cause != null) {
            val text = cause.message.orEmpty()
            if (text.contains("ENOSPC") || text.contains("No space left", ignoreCase = true)) return OUT_OF_SPACE
            cause = cause.cause
        }
        // MediaMuxer báo hết chỗ bằng lời chung chung ("stop failed"...): máy đang gần đầy thì đó là lý do.
        if (lowSpace && error !is Mp3Export.Refused) return OUT_OF_SPACE
        return when (error) {
            is Mp3Export.Refused -> error.message.orEmpty()
            is IOException -> "Lỗi khi ghi: ${error.message ?: error.javaClass.simpleName}"
            else -> "Lỗi khi làm file M4B: ${error.message ?: error.javaClass.simpleName}"
        }
    }
}

/** Lượt làm file M4B một cuốn (M4bExports.start): mã hoá, ghi vào file người dùng chọn, báo tiến độ ở thông báo và lên giao diện. */
class M4bExportWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    @Volatile private var title = ""

    override fun getForegroundInfo(): ForegroundInfo =
        M4bExports.foreground(applicationContext, id, M4bExports.inputs(inputData).first.orEmpty(), title, 0, 0, null)

    override fun doWork(): Result {
        val context = applicationContext
        Store.init(context)
        val (bookId, file, cover) = M4bExports.inputs(inputData)
        if (bookId == null || file == null) return Result.failure()
        val run = id.toString()
        fun event() = JSONObject().put("bookId", bookId).put("run", run)
        var done = 0
        try {
            val plan = Mp3Export.plan(bookId, cover?.takeIf { it.isFile }?.readBytes())
            title = plan.title
            // Không vào được dịch vụ nền (Android 12+ khi app đã ở nền lúc việc bắt đầu): vẫn chạy, chỉ không có thông báo đứng.
            runCatching { setForegroundAsync(M4bExports.foreground(context, id, bookId, title, 0, plan.chapters.size, 0.0)).get() }
            val work = File(context.cacheDir, "m4b-export").apply { mkdirs() }.let { File(it, "$run.m4a") }
            val need = M4bExport.estimatedBytes(plan)
            if (work.parentFile!!.usableSpace < need) {
                throw Mp3Export.Refused("Điện thoại không đủ chỗ trống để làm file M4B (cần khoảng ${need shr 20} MB) - dọn bớt rồi xuất lại")
            }
            var shown = 0L
            val out = context.contentResolver.openOutputStream(file, "wt") ?: throw Mp3Export.Refused("Không ghi được vào chỗ đã chọn")
            val result = out.buffered(256 * 1024).use { stream ->
                M4bExport.run(plan, work, stream, M4bAudio, progress = { chapters, total, fraction ->
                    done = chapters
                    M4bExports.emit(event().put("done", chapters).put("total", total).put("percent", (fraction * 100).toInt()))
                    val now = System.currentTimeMillis()
                    if (now - shown > 700 || chapters == total) {
                        shown = now
                        runCatching { setForegroundAsync(M4bExports.foreground(context, id, bookId, title, chapters, total, fraction)) }
                    }
                }, stopped = { isStopped })
            }
            val partial = if (result.chapters < result.chaptersTotal) " Các chương chưa làm xong sẽ không có trong file." else ""
            M4bExports.finished(context, bookId, "Đã xuất M4B", "$title · ${result.chapters} chương, ${megabytes(result.size)} MB.$partial")
            M4bExports.emit(event().put("finished", true).put("name", result.name).put("size", result.size).put("chapters", result.chapters)
                .put("chaptersTotal", result.chaptersTotal))
            return Result.success()
        } catch (stopped: Mp3Export.Stopped) {
            M4bExports.discard(context, file)
            M4bExports.finished(context, bookId, "Đã dừng xuất M4B", "$title · file dở đã được xoá")
            M4bExports.emit(event().put("stopped", true).put("files", done))
            return Result.failure()
        } catch (error: Throwable) {
            M4bExports.discard(context, file)
            val message = M4bExports.describe(error, lowSpace = context.cacheDir.usableSpace < (32L shl 20))
            M4bExports.finished(context, bookId, "Không xuất được M4B", "$title · $message")
            M4bExports.emit(event().put("error", message))
            return Result.failure()
        } finally {
            cover?.delete()
            M4bExports.release(context, file)
        }
    }

    private fun megabytes(bytes: Long) = if (bytes < 10L shl 20) "%.1f".format(java.util.Locale.US, bytes / 1048576.0) else (bytes shr 20).toString()
}
