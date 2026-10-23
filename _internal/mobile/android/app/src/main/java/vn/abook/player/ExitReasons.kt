package vn.abook.player

import android.app.ActivityManager
import android.content.Context
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject

/**
 * Vì sao tiến trình ABook chết những lần trước (Android 11+ `ActivityManager.getHistoricalProcessExitReasons`): hệ thống dọn vì thiếu bộ nhớ,
 * app tự văng, ANR, người dùng vuốt khỏi danh sách gần đây, bộ tối ưu pin của hãng đóng băng... - thứ nhật ký của chính app không ghi được vì app
 * đã chết. Mỗi mục: lý do (tên đọc được + mã), mô tả hệ thống ghi, giờ, mức quan trọng lúc chết, bộ nhớ PSS / RSS, và vết ANR / native nếu có (cắt ngắn).
 */
object ExitReasons {
    internal const val TRACE_CHARS = 3000

    /** Tên của `ApplicationExitInfo.REASON_*` (số cố định của Android, nên không cần API 30 để dịch). */
    fun reasonName(reason: Int): String = when (reason) {
        1 -> "EXIT_SELF (app tự thoát)"
        2 -> "SIGNALED (bị tín hiệu)"
        3 -> "LOW_MEMORY (hệ thống thiếu bộ nhớ)"
        4 -> "CRASH (văng)"
        5 -> "CRASH_NATIVE (văng ở mã native)"
        6 -> "ANR (đứng, không phản hồi)"
        7 -> "INITIALIZATION_FAILURE (khởi động hỏng)"
        8 -> "PERMISSION_CHANGE (đổi quyền)"
        9 -> "EXCESSIVE_RESOURCE_USAGE (dùng quá nhiều tài nguyên)"
        10 -> "USER_REQUESTED (người dùng tắt)"
        11 -> "USER_STOPPED (người dùng buộc dừng)"
        12 -> "DEPENDENCY_DIED (thành phần phụ thuộc chết)"
        13 -> "OTHER (lý do khác)"
        14 -> "FREEZER (bị đóng băng)"
        15 -> "PACKAGE_STATE_CHANGE (đổi trạng thái gói)"
        16 -> "PACKAGE_UPDATED (cập nhật app)"
        else -> "UNKNOWN ($reason)"
    }

    /** Tên của `RunningAppProcessInfo.IMPORTANCE_*` lúc tiến trình chết. */
    fun importanceName(importance: Int): String = when (importance) {
        100 -> "FOREGROUND (đang ở trước mặt)"
        125 -> "FOREGROUND_SERVICE (dịch vụ nền đang chạy)"
        200 -> "VISIBLE (còn thấy được)"
        230 -> "PERCEPTIBLE (người dùng còn nghe thấy)"
        300 -> "SERVICE (dịch vụ nền)"
        325 -> "TOP_SLEEPING"
        350 -> "CANT_SAVE_STATE"
        400 -> "CACHED (nằm trong bộ nhớ đệm)"
        1000 -> "GONE ($importance)"
        else -> "UNKNOWN ($importance)"
    }

    /** Một mục thuần (test JVM): các trường đã lấy ra khỏi `ApplicationExitInfo`. */
    internal fun entry(reason: Int, description: String?, timestamp: Long, importance: Int, pssKb: Long, rssKb: Long, trace: String?): JSONObject =
        JSONObject().put("reason", reasonName(reason)).put("code", reason).put("description", AppLog.scrub(description.orEmpty()).take(300))
            .put("timestamp", timestamp).put("importance", importanceName(importance)).put("importanceCode", importance)
            .put("pssKb", pssKb).put("rssKb", rssKb)
            .apply { if (!trace.isNullOrBlank()) put("trace", AppLog.scrub(trace).take(TRACE_CHARS)) }

    /** Tối đa `limit` lần chết gần nhất, mới nhất trước. Android dưới 11: mảng rỗng. */
    fun read(context: Context, limit: Int = 6): JSONArray {
        val out = JSONArray()
        if (Build.VERSION.SDK_INT < 30) return out
        val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        for (info in manager.getHistoricalProcessExitReasons(context.packageName, 0, limit)) {
            val trace = runCatching { info.traceInputStream?.bufferedReader()?.use { reader -> CharArray(TRACE_CHARS).let { buffer -> String(buffer, 0, maxOf(0, reader.read(buffer))) } } }.getOrNull()
            out.put(entry(info.reason, info.description, info.timestamp, info.importance, info.pss, info.rss, trace))
        }
        return out
    }
}
