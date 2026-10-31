package vn.abook.player

import org.json.JSONObject
import java.io.File

/**
 * Tuỳ chọn nghe mà phần Kotlin cần NGAY khi tiến trình dậy, trước cả khi có giao diện: nút tai nghe, tự lùi, lắc / úp máy, lịch đêm, số phút "nghe thêm", mờ dần, dừng an toàn.
 * Giao diện đẩy xuống mỗi lần mở app ([apply]); tiến trình khởi động lại từ tai nghe / widget / Android Auto (không có giao diện)
 * trước đây quay về mặc định (soát a77 #6). Nay mỗi lần giao diện đẩy xuống, các trường ấy được ghi vào `listen-prefs.json` ở kho native và nạp lại ở [load].
 * Cùng file giữ hẹn giờ ngủ đang chạy (`timer`, [SleepTimer.persist]): mốc kết thúc tuyệt đối, khôi phục nếu chưa quá.
 */
object ListenPrefs {
    private const val FILE = "listen-prefs.json"
    private val KEYS = listOf(
        "sleepExtendMinutes", "sleepFadeSeconds", "shakeToExtend", "shakeAction", "shakeSensitivity", "flipToPause",
        "headsetSkips", "autoRewind", "safetyStopHours", "schedule", "theme",
        // Tiếng chạm, rung, nền đọc: do giao diện áp; lõi chỉ nhớ để trả lại (như theme).
        "touchSounds", "haptics", "readingSurface",
        // Chỉ giao diện của điện thoại: tự vào cửa sổ nhỏ (PiP) khi rời app lúc có sách mở; bảng chung ranges.json không liệt kê.
        "autoPip",
        // Dấu giờ (ms) lần đổi cuối của giao diện: lúc mở app giao diện so với dấu này để biết bản nào mới hơn (soát a100 T3).
        "settingsStamp",
    )
    private var loaded = false

    private fun file() = File(Store.root, FILE)

    // Miền giá trị và mặc định: cùng bảng với giao diện (listen/sleep.ts, android/settings.ts) và Python (webui/library.py) - tests/fixtures/settings/ranges.json,
    // ListenPrefsRangesTest so khớp. Giá trị ngoài miền về mặc định RIÊNG trường ấy (soát a102 B3), không giữ giá trị cũ.
    private val FADE_SECONDS = listOf(10, 30, 60)
    private val EXTEND_MINUTES = listOf(5, 10, 15)
    private val SAFETY_HOURS = listOf(0, 1, 2, 3)
    private val SCHEDULE_MINUTES = listOf(15, 30, 45, 60)
    private val SHAKE_ACTIONS = listOf("extend", "reset")
    private val SHAKE_SENSITIVITIES = listOf("gentle", "normal", "firm")
    private val THEMES = listOf("system", "light", "dark")
    private val READING_SURFACES = listOf("auto", "paper", "ivory", "night")
    private val CLOCK = Regex("""([01]\d|2[0-3]):[0-5]\d""")
    private val SWITCHES = mapOf("shakeToExtend" to true, "flipToPause" to false, "headsetSkips" to true, "autoRewind" to true, "touchSounds" to true, "haptics" to true, "autoPip" to true)

    private fun choiceOr(json: JSONObject, key: String, allowed: List<Int>, default: Int): Int {
        val value = json.opt(key) as? Number ?: return default
        val number = value.toDouble()
        return allowed.firstOrNull { it.toDouble() == number } ?: default
    }

    private fun wordOr(json: JSONObject, key: String, allowed: List<String>, default: String): String = (json.opt(key) as? String)?.takeIf { it in allowed } ?: default

    /** "HH:mm" đúng 00:00-23:59 -> phút trong ngày, không thì null. */
    private fun clockMinutes(value: Any?): Int? {
        val text = value as? String ?: return null
        if (!CLOCK.matches(text)) return null
        return text.substring(0, 2).toInt() * 60 + text.substring(3).toInt()
    }

    /** Lịch đêm đúng cấu trúc, hay null (cùng `cleanSleepSchedule` bên giao diện): sai kiểu, thiếu trường, giờ lạ, số phút lạ. */
    private fun cleanSchedule(value: Any?): JSONObject? {
        val schedule = value as? JSONObject ?: return null
        if (clockMinutes(schedule.opt("from")) == null || clockMinutes(schedule.opt("to")) == null) return null
        val minutes = (schedule.opt("minutes") as? Number)?.toDouble() ?: return null
        val planned = SCHEDULE_MINUTES.firstOrNull { it.toDouble() == minutes } ?: return null
        return JSONObject().put("from", schedule.getString("from")).put("to", schedule.getString("to")).put("minutes", planned)
    }

    /** Các trường CÓ trong `json` đã đưa về miền giá trị (trường vắng vẫn vắng; trường lạ bỏ đi). */
    internal fun clean(json: JSONObject): JSONObject {
        val out = JSONObject()
        if (json.has("sleepExtendMinutes")) out.put("sleepExtendMinutes", choiceOr(json, "sleepExtendMinutes", EXTEND_MINUTES, 10))
        if (json.has("sleepFadeSeconds")) out.put("sleepFadeSeconds", choiceOr(json, "sleepFadeSeconds", FADE_SECONDS, 30))
        if (json.has("safetyStopHours")) out.put("safetyStopHours", choiceOr(json, "safetyStopHours", SAFETY_HOURS, 2))
        if (json.has("shakeAction")) out.put("shakeAction", wordOr(json, "shakeAction", SHAKE_ACTIONS, "extend"))
        if (json.has("shakeSensitivity")) out.put("shakeSensitivity", wordOr(json, "shakeSensitivity", SHAKE_SENSITIVITIES, "normal"))
        // Giao diện sáng/tối do giao diện áp; lõi chỉ nhớ để trả lại lúc mở app ([stored]).
        if (json.has("theme")) out.put("theme", wordOr(json, "theme", THEMES, "system"))
        if (json.has("readingSurface")) out.put("readingSurface", wordOr(json, "readingSurface", READING_SURFACES, "auto"))
        for ((key, default) in SWITCHES) if (json.has(key)) out.put(key, json.opt(key) as? Boolean ?: default)
        if (json.has("schedule")) out.put("schedule", cleanSchedule(json.opt("schedule")) ?: JSONObject.NULL)
        if (json.has("settingsStamp")) out.put("settingsStamp", (json.opt("settingsStamp") as? Number)?.toLong()?.takeIf { it > 0 } ?: 0L)
        return out
    }

    /**
     * Áp các trường CÓ trong `json` (trường vắng giữ nguyên - lần `configure` chỉ đổi giọng không mang gì ở đây), sau khi đưa về miền giá trị ([clean]).
     * `startup`: nạp lại ở lúc khởi động - không ghi lại, không đánh thức cảm biến (Playback.onPlayingChanged tự làm khi bắt đầu phát).
     */
    fun apply(raw: JSONObject, startup: Boolean = false) {
        val json = clean(raw)
        if (json.has("sleepExtendMinutes")) SleepTimer.extendMinutes = json.getInt("sleepExtendMinutes")
        if (json.has("sleepFadeSeconds")) SleepTimer.fadeMs = json.getInt("sleepFadeSeconds") * 1000L
        if (json.has("shakeToExtend")) SleepTimer.shakeEnabled = json.getBoolean("shakeToExtend")
        if (json.has("shakeAction")) SleepTimer.shakeResets = json.getString("shakeAction") == "reset"
        if (json.has("headsetSkips")) Playback.headsetSkips = json.getBoolean("headsetSkips")
        if (json.has("flipToPause")) {
            Motion.flipEnabled = json.getBoolean("flipToPause")
            if (!startup) Motion.refresh()
        }
        if (json.has("shakeSensitivity")) {
            SleepTimer.shakeThresholdG = when (json.getString("shakeSensitivity")) { "gentle" -> 1.6; "firm" -> 2.8; else -> 2.2 }
        }
        if (json.has("safetyStopHours")) SleepTimer.safetyStopHours = json.getInt("safetyStopHours").toDouble()
        if (json.has("schedule")) {
            val schedule = json.optJSONObject("schedule")
            SleepTimer.schedule = schedule?.let { Triple(clockMinutes(it.getString("from"))!!, clockMinutes(it.getString("to"))!!, it.getInt("minutes")) }
        }
        if (json.has("autoRewind")) Playback.configure(json.getBoolean("autoRewind"))
        if (!startup) remember(json)
    }

    /** Nhớ các trường native có trong `json` (gộp vào bản đã lưu). Không ghi được thì chỉ ghi logcat: tuỳ chọn vẫn áp cho phiên này. */
    private fun remember(json: JSONObject) {
        if (KEYS.none(json::has)) return
        update { stored -> for (key in KEYS) if (json.has(key)) stored.put(key, json.get(key)) }
    }

    /**
     * Các tuỳ chọn nghe đã nhớ (không kèm hẹn giờ đang chạy), cho giao diện lúc mở app
     * (so `settingsStamp`). Chưa có file: `{}`.
     */
    fun stored(): JSONObject {
        val saved = try { Store.readJson(file()) } catch (error: Exception) { null } ?: return JSONObject()
        return JSONObject().also { out -> for (key in KEYS) if (saved.has(key)) out.put(key, saved.get(key)) }
    }

    /** Hẹn giờ ngủ đang chạy (hay null = không còn): ghi vào cùng file. */
    fun saveTimer(timer: JSONObject?) = update { stored -> if (timer == null) stored.remove("timer") else stored.put("timer", timer) }

    private fun update(change: (JSONObject) -> Unit) {
        try {
            val stored = Store.readJson(file()) ?: JSONObject()
            change(stored)
            Store.writeAtomic(file(), stored.toString())
        } catch (error: Exception) {
            AppLog.w("ABookPrefs", "không ghi được tuỳ chọn nghe", error)
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
