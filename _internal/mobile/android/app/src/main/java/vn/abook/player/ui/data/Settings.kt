package vn.abook.player.ui.data

import vn.abook.player.S

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
    Voice(S.s_giong_doc_11f2548d, "settings_voice"),
    Listen(S.s_nghe_a43aafef, "settings_listen"),
    Sleep(S.s_hen_gio_ngu_21073488, "settings_sleep"),
    Look(S.s_giao_dien_0813b59e, "settings_look"),
    Devices(S.s_thiet_bi_eb706979, "settings_devices"),
    Advanced(S.s_nang_cao_d16fca15, "settings_advanced"),
}

/** Một lựa chọn trong nhóm chọn-một: `key` là giá trị lưu ở kho (giữ nguyên chữ đã lưu), `label` là chữ trên màn. */
interface Choice {
    val key: String
    val label: String
}

enum class ThemeMode(override val key: String, override val label: String) : Choice {
    System("system", S.s_tu_dong_a25c8028),
    Light("light", S.s_sang_8f0c677d),
    Dark("dark", S.s_toi_4ac2d267);

    /** Giao diện tối thật sự hay không, khi máy đang ở `systemDark`. */
    fun dark(systemDark: Boolean): Boolean = this == Dark || (this == System && systemDark)
}

enum class ReadingSurface(override val key: String, override val label: String) : Choice {
    Auto("auto", S.s_tu_dong_a25c8028),
    Paper("paper", S.s_giay_702e14de),
    Ivory("ivory", S.s_nga_370ffbed),
    Night("night", S.s_dem_98ef3f93),
}

enum class ShakeSensitivity(override val key: String, override val label: String) : Choice {
    Gentle("gentle", S.s_nhe_tay_a3b81145),
    Normal("normal", S.s_vua_8af1c03b),
    Firm("firm", S.s_manh_tay_fe6b55ab),
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
    val autoPip: Boolean = false,
    val schedule: SleepSchedule? = null,
    val shakeToExtend: Boolean = true,
    val shakeSensitivity: ShakeSensitivity = ShakeSensitivity.Normal,
    val flipToPause: Boolean = false,
    val sleepExtendMinutes: Int = 10,
    val sleepFadeSeconds: Int = 30,
    /** Dấu giờ lần đổi cuối (ms; 0 = chưa đổi): so dấu này để biết bản nào mới hơn. */
    val stamp: Long = 0L,
) {
    companion object {
        val Default = AppSettings()
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
            schedule = schedule(json.opt("schedule")),
            shakeToExtend = flag(json, "shakeToExtend", Default.shakeToExtend),
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
        if (schedule != before.schedule) {
            out.put("schedule", schedule?.let { JSONObject().put("from", it.from).put("to", it.to).put("minutes", it.minutes) } ?: JSONObject.NULL)
        }
        if (shakeToExtend != before.shakeToExtend) out.put("shakeToExtend", shakeToExtend)
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
        dotJoin(if (settings.autoRewind) S.s_tu_lui_6fc7685a else S.s_khong_tu_lui_8aec206c, if (settings.autoMusic) S.s_nhac_tu_chon_31bdb97d else S.s_khong_nhac_nen_0e54f623)

    fun sleep(settings: AppSettings): String {
        val schedule = settings.schedule
        return when {
            schedule != null -> S.s_lich_dem_0_1_4578d519(schedule.from, schedule.to)
            else -> S.s_tat_3286064e
        }
    }

    fun look(settings: AppSettings): String = settings.theme.label
}

/** Mốc giờ của ô chọn giờ lịch đêm: mỗi 15 phút trong ngày; giờ đã lưu lệch mốc thì chen vào đúng chỗ. */
object Quarters {
    val ALL: List<String> = List(96) { index -> String.format(Locale.ROOT, "%02d:%02d", index / 4, index % 4 * 15) }

    fun around(value: String): List<String> = if (value in ALL) ALL else (ALL + value).sorted()
}
