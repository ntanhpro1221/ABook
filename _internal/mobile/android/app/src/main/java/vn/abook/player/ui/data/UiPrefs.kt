package vn.abook.player.ui.data

import android.content.Context

/** Lựa chọn nhỏ của giao diện native cần nhớ giữa các lần mở (hiện chỉ cách xếp Thư viện). Đọc/ghi ở luồng nền. */
class UiPrefs(context: Context) {
    private val app = context.applicationContext
    private val prefs by lazy { app.getSharedPreferences("native_ui", Context.MODE_PRIVATE) }

    fun sort(): LibrarySort = LibrarySort.entries.firstOrNull { it.name == prefs.getString(SORT, null) } ?: LibrarySort.Recent

    fun setSort(sort: LibrarySort) {
        prefs.edit().putString(SORT, sort.name).apply()
    }

    private companion object {
        const val SORT = "library_sort"
    }
}
