package vn.abook.player

import android.content.Context
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Bắt văng (a114): bọc `UncaughtExceptionHandler` của hệ thống - ghi stack vào `filesDir/diag/crash-<giờ>.txt` (giữ [KEEP] file mới nhất) và một
 * dòng [AppLog], rồi GỌI LẠI handler cũ (app vẫn văng như trước, hệ thống vẫn ghi báo cáo của nó). Lần mở sau, [Diagnostics] đưa các file này
 * và lý do tiến trình chết (`ActivityManager.getHistoricalProcessExitReasons`, [ExitReasons]) vào bản chẩn đoán.
 */
object CrashLog {
    internal const val KEEP = 5
    internal const val PREFIX = "crash-"
    private const val MAX_CHARS = 12_000

    @Volatile private var installed = false

    fun install(context: Context) {
        if (installed) return
        installed = true
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            try {
                val folder = AppLog.folder() ?: File(context.applicationContext.filesDir, "diag")
                write(folder, System.currentTimeMillis(), thread.name, error)
                AppLog.e("Crash", "văng ở luồng ${thread.name}: ${error.javaClass.name}: ${error.message}", error)
            } catch (_: Throwable) {
            }
            previous?.uncaughtException(thread, error)
        }
    }

    /** Ghi file văng rồi dọn bớt (giữ [KEEP] file mới nhất). Trả file đã ghi, hay null nếu ghi hỏng. */
    internal fun write(folder: File, now: Long, thread: String, error: Throwable): File? = try {
        folder.mkdirs()
        val name = PREFIX + SimpleDateFormat("yyyyMMdd-HHmmss-SSS", Locale.US).format(Date(now)) + ".txt"
        val file = File(folder, name)
        file.writeBytes(text(now, thread, error).toByteArray(Charsets.UTF_8))
        prune(folder, KEEP)
        file
    } catch (_: Throwable) {
        null
    }

    internal fun text(now: Long, thread: String, error: Throwable): String {
        val time = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).format(Date(now))
        return AppLog.scrub("$time luồng $thread\n" + error.stackTraceToString()).take(MAX_CHARS)
    }

    /** Chỉ giữ `keep` file `crash-*.txt` mới nhất (tên có giờ nên xếp theo tên là xếp theo thời gian). */
    internal fun prune(folder: File, keep: Int) {
        val files = folder.listFiles { file -> file.isFile && file.name.startsWith(PREFIX) }?.sortedBy { it.name } ?: return
        files.dropLast(keep.coerceAtLeast(0)).forEach { it.delete() }
    }

    /** Các file văng, mới nhất trước: (tên, nội dung cắt ở `maxChars`). */
    fun read(folder: File?, maxChars: Int = 6000): List<Pair<String, String>> {
        val files = folder?.listFiles { file -> file.isFile && file.name.startsWith(PREFIX) }?.sortedByDescending { it.name } ?: return emptyList()
        return files.take(KEEP).map { it.name to runCatching { AppLog.scrub(it.readText(Charsets.UTF_8)).take(maxChars) }.getOrDefault("") }
    }
}
