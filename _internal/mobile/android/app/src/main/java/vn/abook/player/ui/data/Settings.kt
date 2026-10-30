package vn.abook.player.ui.data

import androidx.compose.runtime.Immutable
import org.json.JSONObject
import java.util.Locale

/*
 * Tuỳ chọn của Cài đặt điện thoại - cùng khoá, cùng giá trị, cùng mặc định với kho native
 * ([vn.abook.player.ListenPrefs]: `listen-prefs.json`). Hàm thuần, không Android: thử trên JVM.
 */

/**
 * Nhóm của trang gốc Cài đặt, theo thứ tự hay dùng (shared/SettingsNav.tsx `SETTINGS_GROUPS`, nhóm có mặt trên điện thoại). Mỗi nhóm một màn con - không cấp ba.
 */
enum class SettingsGroup(val label: String, val tag: String) {
    Voice("Giọng đọc", "settings_voice"),
    Listen("Nghe", "settings_listen"),
    Sleep("Hẹn giờ ngủ", "settings_sleep"),
    Look("Giao diện", "settings_look"),
    Devices("Thiết bị", "settings_devices"),
    Advanced("Nâng cao", "settings_advanced"),
}

/** Một lựa chọn trong nhóm chọn-một: `key` là giá trị lưu ở kho (giữ nguyên chữ đã lưu), `label` là chữ trên màn. */
interface Choice {
    val key: String
    val label: String
}

enum class ThemeMode(override val key: String, override val label: String) : Choice {
    System("system", "Tự động"),
    Light("light", "Sáng"),
    Dark("dark", "Tối");

    /** Giao diện tối thật sự hay không, khi máy đang ở `systemDark`. */
    fun dark(systemDark: Boolean): Boolean = this == Dark || (this == System && systemDark)
}

enum class ReadingSurface(override val key: String, override val label: String) : Choice {
    Auto("auto", "Tự động"),
    Paper("paper", "Giấy"),
    Ivory("ivory", "Ngà"),
    Night("night", "Đêm"),
}

enum class ShakeAction(override val key: String, override val label: String) : Choice {
    Extend("extend", "Cộng thêm"),
    Reset("reset", "Đặt lại"),
}

enum class ShakeSensitivity(override val key: String, override val label: String) : Choice {
    Gentle("gentle", "Nhẹ tay"),
    Normal("normal", "Vừa"),
    Firm("firm", "Mạnh tay"),
}

/** Lịch đêm tự hẹn giờ: nghe trong khung `from`-`to` ("HH:mm") thì tự hẹn `minutes` phút. */
@Immutable
data class SleepSchedule(val from: String, val to: String, val minutes: Int) {
    companion object {
        /** Bật lịch đêm lần đầu. */
        val Default = SleepSchedule("22:00", "06:00", 30)
        val MINUTES = listOf(15, 30, 45, 60)
    }
}

/** Mọi tuỳ chọn Cài đặt đang dùng (bất biến; màn chỉ đọc). Mặc định = [AppSettings.Default]. */
@Immutable
data class AppSettings(
    val theme: ThemeMode = ThemeMode.System,
    val readingSurface: ReadingSurface = ReadingSurface.Auto,
    val touchSounds: Boolean = true,
    val haptics: Boolean = true,
    val autoRewind: Boolean = true,
    val headsetSkips: Boolean = true,
    val autoMusic: Boolean = true,
    /** "Tự mở cửa sổ mini": rời app lúc có sách mở thì nghe tiếp trong cửa sổ nhỏ (PiP). Chỉ điện thoại native. */
    val autoPip: Boolean = true,
    val safetyStopHours: Int = 2,
    val schedule: SleepSchedule? = null,
    val shakeToExtend: Boolean = true,
    val shakeAction: ShakeAction = ShakeAction.Extend,
    val shakeSensitivity: ShakeSensitivity = ShakeSensitivity.Normal,
    val flipToPause: Boolean = false,
    val sleepExtendMinutes: Int = 10,
    val sleepFadeSeconds: Int = 30,
    /** Dấu giờ lần đổi cuối (ms; 0 = chưa đổi): so dấu này để biết bản nào mới hơn. */
    val stamp: Long = 0L,
) {
    companion object {
        val Default = AppSettings()
        val SAFETY_HOURS = listOf(0, 1, 2, 3)
        val EXTEND_MINUTES = listOf(5, 10, 15)
        val FADE_SECONDS = listOf(10, 30, 60)
        private val CLOCK = Regex("""([01]\d|2[0-3]):[0-5]\d""")

        private inline fun <reified T> word(json: JSONObject, key: String, fallback: T): T where T : Enum<T>, T : Choice =
            enumValues<T>().firstOrNull { it.key == json.opt(key) } ?: fallback

        private fun flag(json: JSONObject, key: String, fallback: Boolean): Boolean = json.opt(key) as? Boolean ?: fallback

        private fun pick(json: JSONObject, key: String, allowed: List<Int>, fallback: Int): Int {
            val value = (json.opt(key) as? Number)?.toDouble() ?: return fallback
            return allowed.firstOrNull { it.toDouble() == value } ?: fallback
        }

        private fun schedule(value: Any?): SleepSchedule? {
            val json = value as? JSONObject ?: return null
            val from = json.opt("from") as? String ?: return null
            val to = json.opt("to") as? String ?: return null
            if (!CLOCK.matches(from) || !CLOCK.matches(to)) return null
            val minutes = (json.opt("minutes") as? Number)?.toDouble() ?: return null
            return SleepSchedule(from, to, SleepSchedule.MINUTES.firstOrNull { it.toDouble() == minutes } ?: return null)
        }

        /**
         * Từ kho native (`ListenPrefs.stored()` + `autoMusic`): khoá vắng hay giá trị lạ về mặc định RIÊNG khoá ấy (cùng luật `normalizeSettings`). Lịch đêm ở
         * kho native tên `schedule`.
         */
        fun from(json: JSONObject): AppSettings = AppSettings(
            theme = word(json, "theme", Default.theme),
            readingSurface = word(json, "readingSurface", Default.readingSurface),
            touchSounds = flag(json, "touchSounds", Default.touchSounds),
            haptics = flag(json, "haptics", Default.haptics),
            autoRewind = flag(json, "autoRewind", Default.autoRewind),
            headsetSkips = flag(json, "headsetSkips", Default.headsetSkips),
            autoMusic = flag(json, "autoMusic", Default.autoMusic),
            autoPip = flag(json, "autoPip", Default.autoPip),
            safetyStopHours = pick(json, "safetyStopHours", SAFETY_HOURS, Default.safetyStopHours),
            schedule = schedule(json.opt("schedule")),
            shakeToExtend = flag(json, "shakeToExtend", Default.shakeToExtend),
            shakeAction = word(json, "shakeAction", Default.shakeAction),
            shakeSensitivity = word(json, "shakeSensitivity", Default.shakeSensitivity),
            flipToPause = flag(json, "flipToPause", Default.flipToPause),
            sleepExtendMinutes = pick(json, "sleepExtendMinutes", EXTEND_MINUTES, Default.sleepExtendMinutes),
            sleepFadeSeconds = pick(json, "sleepFadeSeconds", FADE_SECONDS, Default.sleepFadeSeconds),
            stamp = (json.opt("settingsStamp") as? Number)?.toLong()?.takeIf { it > 0 } ?: 0L,
        )
    }

    /**
     * Các trường khác với `before`, ở đúng dạng [vn.abook.player.ListenPrefs.apply] nhận (để ghi qua cùng một cửa). Không có gì
     * khác thì rỗng. Dấu giờ không tính ở đây: nơi ghi gắn dấu mới.
     */
    fun changesFrom(before: AppSettings): JSONObject {
        val out = JSONObject()
        if (theme != before.theme) out.put("theme", theme.key)
        if (readingSurface != before.readingSurface) out.put("readingSurface", readingSurface.key)
        if (touchSounds != before.touchSounds) out.put("touchSounds", touchSounds)
        if (haptics != before.haptics) out.put("haptics", haptics)
        if (autoRewind != before.autoRewind) out.put("autoRewind", autoRewind)
        if (headsetSkips != before.headsetSkips) out.put("headsetSkips", headsetSkips)
        if (autoMusic != before.autoMusic) out.put("autoMusic", autoMusic)
        if (autoPip != before.autoPip) out.put("autoPip", autoPip)
        if (safetyStopHours != before.safetyStopHours) out.put("safetyStopHours", safetyStopHours)
        if (schedule != before.schedule) {
            out.put("schedule", schedule?.let { JSONObject().put("from", it.from).put("to", it.to).put("minutes", it.minutes) } ?: JSONObject.NULL)
        }
        if (shakeToExtend != before.shakeToExtend) out.put("shakeToExtend", shakeToExtend)
        if (shakeAction != before.shakeAction) out.put("shakeAction", shakeAction.key)
        if (shakeSensitivity != before.shakeSensitivity) out.put("shakeSensitivity", shakeSensitivity.key)
        if (flipToPause != before.flipToPause) out.put("flipToPause", flipToPause)
        if (sleepExtendMinutes != before.sleepExtendMinutes) out.put("sleepExtendMinutes", sleepExtendMinutes)
        if (sleepFadeSeconds != before.sleepFadeSeconds) out.put("sleepFadeSeconds", sleepFadeSeconds)
        return out
    }
}

/** Dòng tóm tắt dưới tên nhóm ở trang gốc Cài đặt. */
object SettingsSummary {
    fun listen(settings: AppSettings): String =
        (if (settings.autoRewind) "Tự lùi" else "Không tự lùi") + " · " + (if (settings.autoMusic) "nhạc tự chọn" else "không nhạc nền")

    fun sleep(settings: AppSettings): String {
        val schedule = settings.schedule
        return when {
            schedule != null -> "Lịch đêm ${schedule.from}–${schedule.to}"
            settings.safetyStopHours > 0 -> "Tự tắt sau ${settings.safetyStopHours} giờ"
            else -> "Tắt"
        }
    }

    fun look(settings: AppSettings): String = settings.theme.label
}

/** Mốc giờ của ô chọn giờ lịch đêm: mỗi 15 phút trong ngày; giờ đã lưu lệch mốc thì chen vào đúng chỗ. */
object Quarters {
    val ALL: List<String> = List(96) { index -> String.format(Locale.ROOT, "%02d:%02d", index / 4, index % 4 * 15) }

    fun around(value: String): List<String> = if (value in ALL) ALL else (ALL + value).sorted()
}
