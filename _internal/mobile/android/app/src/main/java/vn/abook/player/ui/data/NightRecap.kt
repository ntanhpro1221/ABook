package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable
import org.json.JSONObject
import java.util.Calendar
import java.util.TimeZone

/** Một mốc trong nhật ký đêm (Bedtime.kt): hẹn giờ, chạm máy, máy nằm yên, tự dừng. */
@Immutable
data class NightEvent(val type: String, val at: Double, val action: String, val chapterId: Int?, val chapterTitle: String, val seconds: Double)

/** Một đêm nghe (web: model.ts `NightSession`). `endedAt` null: đêm chưa kết thúc. */
@Immutable
data class NightSession(
    val bookId: String, val bookTitle: String, val startedAt: Double, val endedAt: Double?, val dismissed: Boolean, val events: List<NightEvent>,
) {
    companion object {
        fun parse(json: JSONObject): NightSession {
            val array = json.optJSONArray("events")
            val events = (0 until (array?.length() ?: 0)).mapNotNull { array?.optJSONObject(it) }.map { event ->
                val position = event.optJSONObject("position")
                NightEvent(
                    event.optString("type"), event.optDouble("at"), event.optString("action"),
                    position?.takeIf { !it.isNull("chapterId") }?.optInt("chapterId"), position?.optString("chapterTitle").orEmpty(), position?.optDouble("seconds", 0.0) ?: 0.0,
                )
            }
            return NightSession(
                json.optString("bookId"), json.optString("bookTitle"), json.optDouble("startedAt"),
                if (json.has("endedAt") && !json.isNull("endedAt")) json.optDouble("endedAt") else null, json.optBoolean("dismissed"), events,
            )
        }
    }
}

enum class MarkerKind { Timer, Touch, Still, Stopped }

/** Một mốc để người nghe nhận ra đoạn cuối mình còn nhớ: tên, lời giải thích, giờ, và chỗ nghe ở mốc ấy. */
@Immutable
data class NightMarker(
    val kind: MarkerKind, val label: String, val hint: String, val at: Double, val chapterId: Int, val chapterTitle: String, val seconds: Double,
    val suggested: Boolean = false,
)

/**
 * Thẻ "Tối qua" (web: MorningRecap.tsx + night.ts): không ai biết chính xác lúc người nghe thiếp đi, nhưng nhật ký đêm có những mốc chắc chắn - lúc hẹn giờ, lần cuối
 * còn chạm vào máy, lúc máy bắt đầu nằm yên, lúc tự dừng. Hàm thuần - thử trên JVM (NightRecapTest).
 */
object NightRecap {
    /** Thẻ chỉ hiện trong chừng này giờ sau lúc đêm kết thúc. */
    const val RECENT_HOURS = 18

    /** Máy nằm yên đo trong cửa sổ 2 phút: người nghe có lẽ đã ngủ từ trước mốc ấy chừng này. */
    const val BEFORE_SLEEP_SECONDS = 120.0

    /** Lần lưu chỗ nghe sát lúc tự dừng (hẹn "hết chương" lưu chương kế ở 0:00) vẫn thuộc đêm ấy, chưa phải nghe tiếp. */
    const val SAVED_AT_STOP_SECONDS = 60.0

    /** Sau lúc đêm kết thúc người nghe đã nghe tiếp cuốn ấy chưa (chỗ nghe lưu muộn hơn hẳn): rồi thì thẻ mời quay lại chỗ cũ là lùi họ về. */
    fun heardSince(endedAt: Double, lastAt: Double?): Boolean = lastAt != null && lastAt > endedAt + SAVED_AT_STOP_SECONDS

    /** Thẻ còn đúng để hiện: chưa ẩn, đã tự dừng, mới trong [RECENT_HOURS] giờ. */
    fun fresh(session: NightSession, nowSeconds: Double): Boolean =
        !session.dismissed && session.endedAt != null && session.events.any { it.type == "stopped" } && nowSeconds - session.endedAt < RECENT_HOURS * 3600

    /** "Tối qua" chỉ đúng khi lần hẹn giờ kết thúc hôm trước hay lúc rạng sáng; hẹn giờ ban ngày thì "Vừa hẹn giờ". */
    fun sessionLabel(endedAt: Double?, nowMs: Long, zone: TimeZone = TimeZone.getDefault()): String {
        if (endedAt == null || endedAt <= 0) return "Tối qua"
        val ended = Calendar.getInstance(zone).apply { timeInMillis = (endedAt * 1000).toLong() }
        val now = Calendar.getInstance(zone).apply { timeInMillis = nowMs }
        val today = ended.get(Calendar.YEAR) == now.get(Calendar.YEAR) && ended.get(Calendar.DAY_OF_YEAR) == now.get(Calendar.DAY_OF_YEAR)
        return if (today && ended.get(Calendar.HOUR_OF_DAY) >= 5) "Vừa hẹn giờ" else "Tối qua"
    }

    /** Giờ của một mốc, "HH:mm". */
    fun clock(at: Double, zone: TimeZone = TimeZone.getDefault()): String {
        val time = Calendar.getInstance(zone).apply { timeInMillis = (at * 1000).toLong() }
        return "%02d:%02d".format(time.get(Calendar.HOUR_OF_DAY), time.get(Calendar.MINUTE))
    }

    fun markers(session: NightSession): List<NightMarker> {
        val events = session.events.filter { it.chapterId != null }
        fun make(event: NightEvent?, kind: MarkerKind, label: String, hint: String, shift: Double = 0.0): NightMarker? =
            event?.let { NightMarker(kind, label, hint, it.at, it.chapterId!!, it.chapterTitle, maxOf(0.0, it.seconds - shift)) }
        val timer = events.firstOrNull { it.type == "timer" }
        val lastTouch = events.lastOrNull { it.type == "touch" || it.type == "shake" || it.type == "extend" }
        val still = events.lastOrNull { it.type == "still" }
        val stopped = events.lastOrNull { it.type == "stopped" }
        val safety = timer?.action == "safety"
        val list = listOfNotNull(
            if (safety) null else make(timer, MarkerKind.Timer, "Hẹn giờ ngủ", "chắc chắn còn thức"),
            if (lastTouch != null && lastTouch !== timer) make(lastTouch, MarkerKind.Touch, "Lần cuối chạm máy", "chắc chắn còn thức") else null,
            make(still, MarkerKind.Still, "Máy bắt đầu nằm yên", "có lẽ đã ngủ từ khoảng này", BEFORE_SLEEP_SECONDS),
            make(stopped, MarkerKind.Stopped, "Tự dừng", if (safety) "không ai chạm máy suốt một lúc lâu" else "lúc hết giờ hẹn"),
        )
        val pick = list.firstOrNull { it.kind == MarkerKind.Still } ?: list.firstOrNull { it.kind == MarkerKind.Touch } ?: list.firstOrNull()
        return list.map { it.copy(suggested = it === pick) }
    }
}
