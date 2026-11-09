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
        1 -> S.s_exit_self_app_tu_thoat_b7af1acb
        2 -> S.s_signaled_bi_tin_hieu_47279cbb
        3 -> S.s_low_memory_he_thong_thieu_bo_nho_5e59b552
        4 -> S.s_crash_vang_b602e3e6
        5 -> S.s_crash_native_vang_o_ma_native_7e8abd32
        6 -> S.s_anr_dung_khong_phan_hoi_78ddf6ba
        7 -> S.s_initialization_failure_khoi_dong_hong_29638038
        8 -> S.s_permission_change_doi_quyen_3a5c449d
        9 -> S.s_excessive_resource_usage_dung_qua_nhieu_ta_f542adfe
        10 -> S.s_user_requested_nguoi_dung_tat_a7348a73
        11 -> S.s_user_stopped_nguoi_dung_buoc_dung_fe50047b
        12 -> S.s_dependency_died_thanh_phan_phu_thuoc_chet_521cfd9e
        13 -> S.s_other_ly_do_khac_dbb224fb
        14 -> S.s_freezer_bi_dong_bang_b1c480d4
        15 -> S.s_package_state_change_doi_trang_thai_goi_bf76731d
        16 -> S.s_package_updated_cap_nhat_app_517c77ce
        else -> "UNKNOWN ($reason)"
    }

    /** Tên của `RunningAppProcessInfo.IMPORTANCE_*` lúc tiến trình chết. */
    fun importanceName(importance: Int): String = when (importance) {
        100 -> S.s_foreground_dang_o_truoc_mat_0fc3cc06
        125 -> S.s_foreground_service_dich_vu_nen_dang_chay_cb10ab7a
        200 -> S.s_visible_con_thay_duoc_987448fb
        230 -> S.s_perceptible_nguoi_dung_con_nghe_thay_12e5223a
        300 -> S.s_service_dich_vu_nen_73826efd
        325 -> "TOP_SLEEPING"
        350 -> "CANT_SAVE_STATE"
        400 -> S.s_cached_nam_trong_bo_nho_dem_4fbda3ce
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
