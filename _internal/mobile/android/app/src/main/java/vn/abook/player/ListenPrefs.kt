package vn.abook.player

import android.util.Log
import org.json.JSONObject
import java.io.File

/**
 * Tuỳ chọn nghe mà phần Kotlin cần NGAY khi tiến trình dậy, trước cả khi có WebView: nút tai nghe, tự lùi, lắc / úp máy, lịch đêm, số phút "nghe thêm", mờ dần, dừng an toàn.
 * Giao diện giữ bản của nó ở localStorage và đẩy xuống mỗi lần mở app ([PlayerPlugin.configure]); tiến trình khởi động lại từ tai nghe / widget / Android Auto (không có WebView)
 * trước đây quay về mặc định (soát a77 #6). Nay mỗi lần giao diện đẩy xuống, các trường ấy được ghi vào `listen-prefs.json` ở kho native và nạp lại ở [load].
 * Cùng file giữ hẹn giờ ngủ đang chạy (`timer`, [SleepTimer.persist]): mốc kết thúc tuyệt đối, khôi phục nếu chưa quá.
 */
object ListenPrefs {
    private const val FILE = "listen-prefs.json"
    private val KEYS = listOf(
        "sleepExtendMinutes", "sleepFadeSeconds", "shakeToExtend", "shakeAction", "shakeSensitivity", "flipToPause",
        "headsetSkips", "autoRewind", "safetyStopHours", "schedule",
    )
    private var loaded = false

    private fun file() = File(Store.root, FILE)

    /**
     * Áp các trường CÓ trong `json` (trường vắng giữ nguyên - lần `configure` chỉ đổi giọng không mang gì ở đây). `startup`: nạp lại ở lúc khởi động - không ghi lại, không đánh thức cảm biến
     * (Playback.onPlayingChanged tự làm khi bắt đầu phát).
     */
    fun apply(json: JSONObject, startup: Boolean = false) {
        if (json.has("sleepExtendMinutes")) SleepTimer.extendMinutes = json.optInt("sleepExtendMinutes", SleepTimer.extendMinutes)
        if (json.has("sleepFadeSeconds")) SleepTimer.fadeMs = json.optInt("sleepFadeSeconds", (SleepTimer.fadeMs / 1000).toInt()) * 1000L
        if (json.has("shakeToExtend")) SleepTimer.shakeEnabled = json.optBoolean("shakeToExtend", SleepTimer.shakeEnabled)
        if (json.has("shakeAction")) SleepTimer.shakeResets = json.optString("shakeAction") == "reset"
        if (json.has("headsetSkips")) Playback.headsetSkips = json.optBoolean("headsetSkips", Playback.headsetSkips)
        if (json.has("flipToPause")) {
            Motion.flipEnabled = json.optBoolean("flipToPause", Motion.flipEnabled)
            if (!startup) Motion.refresh()
        }
        if (json.has("shakeSensitivity")) {
            SleepTimer.shakeThresholdG = when (json.optString("shakeSensitivity")) { "gentle" -> 1.6; "firm" -> 2.8; else -> 2.2 }
        }
        if (json.has("safetyStopHours")) SleepTimer.safetyStopHours = json.optDouble("safetyStopHours", SleepTimer.safetyStopHours)
        if (json.has("schedule")) {
            val schedule = json.optJSONObject("schedule")
            fun minutesOf(clock: String?) = clock?.split(":")?.let { (it[0].toIntOrNull() ?: 0) * 60 + (it.getOrNull(1)?.toIntOrNull() ?: 0) }
            val from = minutesOf(schedule?.optString("from"))
            val to = minutesOf(schedule?.optString("to"))
            val planned = schedule?.optInt("minutes", -1)?.takeIf { it >= 0 }
            SleepTimer.schedule = if (from != null && to != null && planned != null) Triple(from, to, planned) else null
        }
        if (json.has("autoRewind")) Playback.configure(json.optBoolean("autoRewind", true))
        if (!startup) remember(json)
    }

    /** Nhớ các trường native có trong `json` (gộp vào bản đã lưu). Không ghi được thì chỉ ghi logcat: tuỳ chọn vẫn áp cho phiên này. */
    private fun remember(json: JSONObject) {
        if (KEYS.none(json::has)) return
        update { stored -> for (key in KEYS) if (json.has(key)) stored.put(key, json.get(key)) }
    }

    /** Hẹn giờ ngủ đang chạy (hay null = không còn): ghi vào cùng file. */
    fun saveTimer(timer: JSONObject?) = update { stored -> if (timer == null) stored.remove("timer") else stored.put("timer", timer) }

    private fun update(change: (JSONObject) -> Unit) {
        try {
            val stored = Store.readJson(file()) ?: JSONObject()
            change(stored)
            Store.writeAtomic(file(), stored.toString())
        } catch (error: Exception) {
            Log.w("ABookPrefs", "không ghi được tuỳ chọn nghe", error)
        }
    }

    /** Nạp lại lúc tiến trình dậy (một lần mỗi tiến trình, sau [Store.init]) rồi khôi phục hẹn giờ ngủ còn dở. */
    fun loadOnce() {
        if (loaded) return
        loaded = true
        load()
    }

    fun load(now: Long = System.currentTimeMillis()) {
        val stored = try { Store.readJson(file()) } catch (error: Exception) { null }
        if (stored != null) apply(stored, startup = true)
        SleepTimer.restore(stored?.optJSONObject("timer"), now)
    }
}
