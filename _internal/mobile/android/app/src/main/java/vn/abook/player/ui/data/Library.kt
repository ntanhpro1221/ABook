package vn.abook.player.ui.data

import android.content.Context
import androidx.compose.runtime.Immutable
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext
import vn.abook.player.AppLog
import vn.abook.player.Store

/** Một cuốn trong lưới Thư viện - đúng phần màn vẽ (id, tên, tác giả, bìa), bất biến. */
@Immutable
data class BookRow(val id: String, val title: String, val author: String, val coverPath: String?, val coverStamp: Long)

@Immutable
sealed interface LibraryState {
    @Immutable
    data object Loading : LibraryState

    @Immutable
    class Ready(val books: List<BookRow>) : LibraryState
}

/**
 * Kho dữ liệu Thư viện cho giao diện native: đọc thẳng lõi ([Store]) như `LibraryPlugin.localBooks` - cùng `Store.books()` -, không qua plugin.
 * Chỉ là phần P0 (danh sách + bìa); trạng thái nghe, sách nghe thẳng, tải về... vào ở P1.
 */
class LibraryRepo(private val context: Context) {
    private val flow = MutableStateFlow<LibraryState>(LibraryState.Loading)
    val state: StateFlow<LibraryState> get() = flow

    /** Đọc lại danh sách sách trên máy (luồng nền). Lỗi đọc = danh sách rỗng, đã ghi nhật ký - không treo màn chờ. */
    suspend fun refresh() = withContext(Dispatchers.IO) {
        flow.value = LibraryState.Ready(
            try {
                Store.init(context)
                Store.books().map { manifest ->
                    val id = manifest.getString("id")
                    val cover = Store.coverFile(id)?.takeIf { it.isFile }
                    BookRow(id, manifest.optString("title"), manifest.optString("creator"), cover?.path, cover?.lastModified() ?: 0L)
                }
            } catch (error: Exception) {
                AppLog.w("Library", "Không đọc được thư viện: ${error.javaClass.simpleName}")
                emptyList()
            },
        )
    }

    /** Sách giả cho đo đạc (chỉ bản -PnativeUi, `abook.demo.books`): không chạm kho thật. */
    fun showDemo(count: Int) {
        flow.value = LibraryState.Ready(List(count) { index ->
            BookRow("demo-$index", "Cuốn thử số ${index + 1}", "Tác giả ${index % 17 + 1}", null, 0L)
        })
    }
}
