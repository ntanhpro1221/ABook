package vn.abook.player

import org.json.JSONObject
import vn.abook.player.ui.components.ValueSpec
import vn.abook.player.ui.components.ValueSpecs

/**
 * Lần hẹn giờ ngủ cuối người nghe tự đặt (chủ sách 17-11): `kind` là loại của lần cuối ("minutes" / "chapter"), [minutes] / [chapters] là số gần nhất của
 * từng loại. Tấm Hẹn giờ mở sẵn ở mốc này, nút "Bật lại" (tấm, widget) đặt lại đúng nó; chưa từng đặt thì 30 phút. Lõi nhớ ở `listen-prefs.json`
 * (khoá `lastSleep`, [ListenPrefs.saveLastSleep]) - qua tắt app và khởi động lại máy. Cùng hợp đồng với webui/library.py `clean_last_sleep`,
 * listen/sleep.ts `cleanLastSleep`, Qt playerlogic.h `cleanLastSleep`: tests/fixtures/settings/ranges.json `lastSleep` (LastSleepTest chạy bảng ca).
 */
data class LastSleep(val kind: String = MINUTES, val minutes: Int = 30, val chapters: Int = 1) {
    val isChapter: Boolean get() = kind == CHAPTER

    fun toJson(): JSONObject = JSONObject().put("kind", kind).put("minutes", minutes).put("chapters", chapters)

    /** Sau khi người nghe tự đặt N phút. */
    fun withMinutes(value: Int): LastSleep = copy(kind = MINUTES, minutes = value)

    /** Sau khi người nghe tự đặt "Hết N chương". */
    fun withChapters(value: Int): LastSleep = copy(kind = CHAPTER, chapters = value)

    companion object {
        const val MINUTES = "minutes"
        const val CHAPTER = "chapter"

        /** Số nguyên trong miền của `spec` (JSON đưa vào Int / Long / Double nguyên); chuỗi, bool, số lẻ thì null. */
        private fun whole(value: Any?, spec: ValueSpec): Int? {
            if (value !is Int && value !is Long && value !is Double && value !is Float) return null
            val number = (value as Number).toDouble()
            if (number.isNaN() || number != Math.floor(number) || number < spec.min || number > spec.max) return null
            return number.toInt()
        }

        /** Lần hẹn cuối đã làm sạch (khoá thừa bỏ đi), hay null: thiếu khoá, sai kiểu, ngoài miền ở bất kỳ khoá nào - coi như chưa từng đặt. */
        fun parse(value: Any?): LastSleep? {
            val json = value as? JSONObject ?: return null
            val kind = json.opt("kind") as? String ?: return null
            if (kind != MINUTES && kind != CHAPTER) return null
            val minutes = whole(json.opt("minutes"), ValueSpecs.sleepMinutes) ?: return null
            val chapters = whole(json.opt("chapters"), ValueSpecs.sleepChapters) ?: return null
            return LastSleep(kind, minutes, chapters)
        }
    }
}
