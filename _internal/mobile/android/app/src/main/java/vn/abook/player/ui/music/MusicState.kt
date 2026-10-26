package vn.abook.player.ui.music

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Việc nhạc nền với lõi - tách khỏi màn để thử bằng nguồn giả. Nguồn thật: [MusicRepo]. Lỗi cho người nghe: [MusicFailure]. */
interface MusicSource {
    suspend fun menu(): MusicMenu
    suspend fun book(id: String): BookMusic
    /** `playlist`: mã danh sách, "mine", "off", hay null = để máy chọn. */
    suspend fun choose(id: String, playlist: String?): BookMusic
    suspend fun level(id: String, levelDb: Double): BookMusic
    suspend fun enable(id: String, enabled: Boolean): BookMusic
    /** Thêm file vào Nhạc của tôi (hộp chọn file của hệ thống). */
    suspend fun importMine(uris: List<String>, progress: (done: Int, total: Int) -> Unit): MusicImported
}

/** Kết quả một lượt thêm nhạc: câu báo, file lỗi (một dòng mỗi file), và kho có bài để chọn cho cuốn này không. */
@Immutable
data class MusicImported(val summary: String, val problems: List<String>, val usable: Boolean)

class MusicFailure(message: String) : Exception(message)

/**
 * Nhạc nền của cuốn đang mở trong bảng (trình phát hay trang sách): `book` null = chưa đọc xong. `busy`: đang lưu một lựa chọn. `problem`: lỗi của lần bấm vừa rồi,
 * `notice`: câu báo của lượt thêm nhạc.
 */
@Immutable
data class BookMusicUi(
    val bookId: String = "",
    val book: BookMusic? = null,
    val failed: Boolean = false,
    val menu: MusicMenu? = null,
    val busy: Boolean = false,
    val problem: String = "",
    val importing: Boolean = false,
    val done: Int = 0,
    val total: Int = 0,
    val notice: String = "",
)

/**
 * Trạng thái sống của nhạc nền một cuốn: một holder cho cả app (bảng của trình phát và của trang sách cùng đọc ở đây). Menu danh sách phát giữ [menuTtlMs]
 * (danh mục ít đổi, hỏi lại cần mạng); nhạc của cuốn đọc lại mỗi lần mở bảng.
 */
@Stable
class MusicState(
    private val source: MusicSource,
    private val scope: CoroutineScope,
    private val menuTtlMs: Long = 10 * 60_000L,
    private val now: () -> Long = System::currentTimeMillis,
) {
    private val flow = MutableStateFlow(BookMusicUi())
    val ui: StateFlow<BookMusicUi> = flow
    private var menuAt = 0L

    /** Mở bảng của cuốn `bookId`: cuốn khác thì bắt đầu lại (giữ menu), cùng cuốn thì đọc lại mà vẫn vẽ cái đang có. */
    fun open(bookId: String) {
        if (bookId.isEmpty()) return
        if (flow.value.bookId != bookId) flow.value = BookMusicUi(bookId = bookId, menu = flow.value.menu)
        else flow.update { it.copy(problem = "", notice = if (it.importing) it.notice else "") }
        readBook(bookId)
        readMenu(force = false)
    }

    fun retry() {
        val id = flow.value.bookId
        if (id.isEmpty()) return
        flow.update { it.copy(failed = false) }
        readBook(id)
        readMenu(force = true)
    }

    fun choose(playlist: String?) = change { source.choose(it, playlist) }
    fun setLevel(levelDb: Double) = change { source.level(it, levelDb) }
    fun setEnabled(enabled: Boolean) = change { source.enable(it, enabled) }

    /** Thêm nhạc từ bảng: tiến độ ngay ở hàng "Thêm nhạc"; có bài trong kho thì chọn "Nhạc của tôi" cho cuốn này (sách mang theo đúng các bài đang có). */
    fun importMine(uris: List<String>) {
        val id = flow.value.bookId
        if (uris.isEmpty() || id.isEmpty() || flow.value.importing) return
        flow.update { it.copy(importing = true, done = 0, total = uris.size, notice = "", problem = "") }
        scope.launch {
            val result = attempt { source.importMine(uris) { done, total -> flow.update { it.copy(done = done, total = total) } } }
            result.onSuccess { done ->
                flow.update { it.copy(importing = false, notice = done.summary, problem = done.problems.joinToString("\n")) }
                readMenu(force = true)
                if (done.usable && flow.value.bookId == id) choose(MusicText.MINE)
            }
            result.onFailure { error -> flow.update { it.copy(importing = false, problem = message(error, "Chưa thêm được nhạc")) } }
        }
    }

    private fun readBook(id: String) {
        scope.launch {
            val result = attempt { source.book(id) }
            if (flow.value.bookId != id) return@launch
            result.onSuccess { book -> flow.update { it.copy(book = book, failed = false) } }
            result.onFailure { flow.update { it.copy(failed = true) } }
        }
    }

    private fun readMenu(force: Boolean) {
        if (!force && flow.value.menu != null && now() - menuAt < menuTtlMs) return
        scope.launch {
            // Danh mục chưa tải được (mất mạng lần đầu): lõi trả menu rỗng kèm lý do, không ném - lỗi khác thì giữ menu cũ.
            attempt { source.menu() }.onSuccess { menu ->
                menuAt = now()
                flow.update { it.copy(menu = menu) }
            }
        }
    }

    private fun change(apply: suspend (String) -> BookMusic) {
        val id = flow.value.bookId
        if (id.isEmpty() || flow.value.busy) return
        flow.update { it.copy(busy = true, problem = "") }
        scope.launch {
            val result = attempt { apply(id) }
            if (flow.value.bookId != id) return@launch
            result.onSuccess { book -> flow.update { it.copy(busy = false, book = book) } }
            result.onFailure { error -> flow.update { it.copy(busy = false, problem = message(error, "Chưa đổi được nhạc nền")) } }
        }
    }

    private suspend fun <T> attempt(block: suspend () -> T): Result<T> = try {
        Result.success(block())
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Exception) {
        Result.failure(error)
    }

    private fun message(error: Throwable, fallback: String): String = (error as? MusicFailure)?.message?.takeIf { it.isNotBlank() } ?: fallback
}
