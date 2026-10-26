package vn.abook.player.ui.data

import android.content.Context
import androidx.compose.runtime.Immutable
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext
import vn.abook.player.AppLog
import vn.abook.player.Store
import vn.abook.player.SyncLink
import java.io.File

@Immutable
sealed interface LibraryState {
    @Immutable
    data object Loading : LibraryState

    /** `books` đã xếp "Nghe gần đây", chỉ gồm cuốn có chương nghe được (cuốn đang làm dở chưa có chương là việc của Studio). */
    @Immutable
    class Ready(val books: List<ListenBook>) : LibraryState
}

/**
 * Kho dữ liệu Thư viện cho giao diện native: đọc thẳng lõi ([Store]) - cùng nguồn với `LibraryPlugin.localBooks` (sách đã tải) và với gói sách
 * nghe thẳng đã cất (`stream.json`, cùng dữ liệu `streamableBooks` trả cho WebView) - không qua plugin. Cuốn nghe thẳng mang [RemoteRef]
 * (dấu "Trên máy tính"). Việc HỎI máy tính / thiết bị ghép xem có sách mới nằm trong `LibraryPlugin.streamableBooks` (thân phương thức plugin) và dời
 * vào lõi ở bước Thiết bị (P2); tới lúc đó danh sách nghe thẳng là những gì đã cất.
 */
class LibraryRepo(private val context: Context) {
    private val flow = MutableStateFlow<LibraryState>(LibraryState.Loading)
    val state: StateFlow<LibraryState> get() = flow

    /** Đọc lại danh sách (luồng nền). Lỗi đọc = danh sách rỗng, đã ghi nhật ký - không treo màn chờ. */
    suspend fun refresh() = withContext(Dispatchers.IO) {
        flow.value = LibraryState.Ready(
            try {
                readAll(context)
            } catch (error: Exception) {
                AppLog.w("Library", "Không đọc được thư viện: ${error.javaClass.simpleName}")
                emptyList()
            },
        )
    }

    /** Sách giả cho đo đạc (chỉ bản -PnativeUi, `abook.demo.books`): không chạm kho thật. */
    fun showDemo(count: Int) {
        flow.value = LibraryState.Ready(DemoLibrary.books(count))
    }

    companion object {
        fun readAll(context: Context): List<ListenBook> {
            Store.init(context)
            val holderNames = HashMap<String, String>()
            val books = ArrayList<ListenBook>()
            for (id in Store.bookIds()) {
                try {
                    val downloaded = Store.rawManifest(id) != null
                    val manifest = (if (downloaded) Store.manifest(id) else Store.streamManifest(id)?.let { Store.streamed(id, it) }) ?: continue
                    val remote = if (downloaded) null else {
                        val source = manifest.optString("source")
                        RemoteRef(holderNames.getOrPut(source) { SyncLink.holderName(context, id) })
                    }
                    val added = if (downloaded) File(Store.bookDir(id), "book.json").lastModified() / 1000.0 else null
                    val book = BookJson.book(manifest, Store.state(id), ::coverOf, remote, added)
                    if (book.chaptersAvailable > 0 || book.textOnly) books += book
                } catch (error: Exception) {
                    AppLog.w("Library", "Bỏ qua một cuốn không đọc được: ${error.javaClass.simpleName}")
                }
            }
            return Library.recentFirst(books)
        }

        /** Bìa người nghe thấy (bìa họ đặt, hay của sách); mất file thì không có bìa. */
        fun coverOf(id: String): CoverRef? =
            Store.coverFile(id)?.takeIf { it.isFile }?.let { CoverRef(it.path, it.lastModified()) }
    }
}
