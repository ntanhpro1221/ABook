package vn.abook.player.ui.data

import android.content.Context
import vn.abook.player.ui.nowplaying.ReadLook

/** Lựa chọn nhỏ của giao diện native cần nhớ giữa các lần mở (hiện chỉ cách xếp Thư viện). Đọc/ghi ở luồng nền. */
class UiPrefs(context: Context) {
    private val app = context.applicationContext
    private val prefs by lazy { app.getSharedPreferences("native_ui", Context.MODE_PRIVATE) }

    fun sort(): LibrarySort = LibrarySort.entries.firstOrNull { it.name == prefs.getString(SORT, null) } ?: LibrarySort.Recent

    fun setSort(sort: LibrarySort) {
        prefs.edit().putString(SORT, sort.name).apply()
    }

    /** Dáng chữ của Đọc theo: cỡ chữ, giãn dòng, đã chạm chữ để nghe từ đó chưa ([vn.abook.player.ui.nowplaying.ReadLook]). */
    fun readLook(): ReadLook = ReadLook(
        prefs.getInt(READ_SIZE, 20).takeIf { it in ReadLook.SIZES } ?: 20,
        prefs.getFloat(READ_LEADING, 1.7f).toDouble().let { value -> ReadLook.LEADINGS.firstOrNull { Math.abs(it - value) < 0.01 } ?: 1.7 },
        prefs.getBoolean(READ_TAPPED, false),
    )

    fun setReadLook(look: ReadLook) {
        prefs.edit().putInt(READ_SIZE, look.size).putFloat(READ_LEADING, look.leading.toFloat()).putBoolean(READ_TAPPED, look.tapped).apply()
    }

    private companion object {
        const val SORT = "library_sort"
        const val READ_SIZE = "read_size"
        const val READ_LEADING = "read_leading"
        const val READ_TAPPED = "read_tapped"
    }
}
