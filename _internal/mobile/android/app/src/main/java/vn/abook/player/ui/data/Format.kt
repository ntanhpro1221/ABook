package vn.abook.player.ui.data

import java.util.Calendar
import java.util.Locale

/** Định dạng kiểu Việt (viết lại từ ui/src/shared/format.ts, cùng ca test): "9 giờ 12 phút", "13:05", "hôm qua 09:15". Hàm thuần, không Android. */
object Fmt {
    /** Thời lượng cho con người: "45 phút", "9 giờ 12 phút", "2 giờ". */
    fun length(seconds: Double): String {
        if (!seconds.isFinite() || seconds <= 0) return "0 phút"
        val minutes = Math.round(seconds / 60.0).toInt()
        if (minutes < 1) return "dưới 1 phút"
        val hours = minutes / 60
        val rest = minutes % 60
        if (hours == 0) return "$minutes phút"
        return if (rest != 0) "$hours giờ $rest phút" else "$hours giờ"
    }

    /** Như [length] nhưng làm tròn LÊN tới phút (thời gian còn lại cạnh đồng hồ đếm ngược). */
    fun lengthUp(seconds: Double): String {
        if (!seconds.isFinite() || seconds <= 0) return "0 phút"
        return length(Math.ceil(seconds / 60.0) * 60.0)
    }

    /** Đồng hồ phát: 3:07, 13:05, 1:02:05. */
    fun clock(seconds: Double): String {
        val whole = (if (seconds.isFinite() && seconds >= 0) seconds else 0.0).toLong()
        val hours = whole / 3600
        val minutes = (whole % 3600) / 60
        val secs = whole % 60
        val mm = if (hours > 0) minutes.toString().padStart(2, '0') else minutes.toString()
        return (if (hours > 0) "$hours:" else "") + mm + ":" + secs.toString().padStart(2, '0')
    }

    /** Mốc thời gian nói kiểu người: "hôm nay 14:02", "tối qua 23:41", "hôm qua 09:15", "3 ngày trước", cũ hơn thì ngày/tháng/năm. */
    fun whenText(epochSeconds: Double, nowMs: Long = System.currentTimeMillis()): String {
        if (epochSeconds <= 0 || epochSeconds.isNaN()) return ""
        val then = Calendar.getInstance().apply { timeInMillis = (epochSeconds * 1000).toLong() }
        val today = Calendar.getInstance().apply { timeInMillis = nowMs }
        val days = Math.round((midnight(today) - midnight(then)) / 86_400_000.0).toInt()
        val time = String.format(Locale.ROOT, "%02d:%02d", then.get(Calendar.HOUR_OF_DAY), then.get(Calendar.MINUTE))
        return when {
            days <= 0 -> if (nowMs / 1000.0 - epochSeconds < 60) "vừa xong" else "hôm nay $time"
            days == 1 -> if (then.get(Calendar.HOUR_OF_DAY) >= 18) "tối qua $time" else "hôm qua $time"
            days < 7 -> "$days ngày trước"
            else -> "${then.get(Calendar.DAY_OF_MONTH)}/${then.get(Calendar.MONTH) + 1}/${then.get(Calendar.YEAR)}"
        }
    }

    private fun midnight(c: Calendar): Long = Calendar.getInstance().apply {
        set(c.get(Calendar.YEAR), c.get(Calendar.MONTH), c.get(Calendar.DAY_OF_MONTH), 0, 0, 0)
        set(Calendar.MILLISECOND, 0)
    }.timeInMillis

    /** Số đếm cho người đọc, tách nghìn bằng dấu chấm (vi-VN): 1.234 (shared/format.ts formatNumber). */
    fun number(value: Long): String = grouped(value)

    /** Số nguyên tách nghìn bằng dấu chấm (vi-VN): 1.234. */
    private fun grouped(value: Long): String = String.format(Locale.ROOT, "%,d", value).replace(',', '.')

    /** "Chương 3 · 12:04" - chỗ nghe tiếp, cùng dạng ở thẻ Đang nghe và nút chính trang sách. */
    fun resumeWhere(chapterTitle: String, seconds: Double): String =
        if (chapterTitle.isNotEmpty()) "$chapterTitle · ${clock(seconds)}" else clock(seconds)
}

/**
 * Các mẩu nối bằng " · " ở MỌI dòng phụ: mẩu trống (null, rỗng, chỉ khoảng trắng) biến mất, nên không bao giờ có "4 MB ·" treo cuối hay " · câu 3" mở đầu. Một chỗ duy nhất
 * (TextWrapRulesTest quét: không nơi nào khác tự nối " · "). Web: `DotJoin`.
 */
fun dotJoin(vararg parts: String?): String = parts.asList().dotJoined()

fun Iterable<String?>.dotJoined(): String = filter { !it.isNullOrBlank() }.joinToString(" · ")
