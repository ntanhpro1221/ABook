package vn.abook.player.ui.music

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import vn.abook.player.ui.voice.MineImports
import vn.abook.player.ui.voice.MusicImportResult
import vn.abook.player.ui.voice.VoiceFailure
import vn.abook.player.ui.voice.VoiceText

/** Việc nhạc nền với lõi - tách khỏi màn để thử bằng nguồn giả. Nguồn thật: [MusicRepo]. Lỗi cho người nghe: [MusicFailure]. */
interface MusicSource {
    suspend fun menu(): MusicMenu
    suspend fun book(id: String): BookMusic
    /** `playlist`: mã danh sách, "mine", "off", hay null = để máy chọn. */
    suspend fun choose(id: String, playlist: String?): BookMusic
    suspend fun level(id: String, levelDb: Double): BookMusic
    suspend fun enable(id: String, enabled: Boolean): BookMusic
    /** Một đoạn nhạc gắn sẵn (`key` = MusicCue.key): im lặng / có nhạc lại. */
    suspend fun silence(id: String, key: String, silenced: Boolean): BookMusic
    /** Thay bài của một đoạn bằng một bài trong Nhạc của tôi (`link`), null = về bài gốc. */
    suspend fun pin(id: String, key: String, link: String?): BookMusic
    /** Các bài trong Nhạc của tôi đổi được cho đoạn `key` (trừ bài đang dùng). */
    suspend fun alternatives(id: String, key: String): List<MineTrack>
}

class MusicFailure(message: String) : Exception(message)

/**
 * Nhạc nền của cuốn đang mở trong bảng (trình phát hay trang sách): `book` null = chưa đọc xong. `busy`: đang lưu một lựa chọn. `problem`: lỗi của lần bấm vừa rồi,
 * `notice`: câu báo của lượt thêm nhạc. `importing`: có lượt thêm nhạc đang chạy - của cuốn nào hay của màn Nhạc
 * của tôi cũng vậy (một kho, một lượt mỗi lúc: [MineImports]).
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
    /** "Đổi bài" của đoạn `swapKey`: `mine` null = đang tìm, `swapFailed` = chưa tìm được. `choosing`: bài đang được ghim (chờ lõi). */
    val swapKey: String = "",
    val mine: List<MineTrack>? = null,
    val swapFailed: Boolean = false,
    val choosing: String = "",
)

/**
 * Trạng thái sống của nhạc nền một cuốn: một holder cho cả app (bảng của trình phát và của trang sách cùng đọc ở đây). Menu danh sách phát giữ [menuTtlMs]
 * (danh mục ít đổi, hỏi lại cần mạng); nhạc của cuốn đọc lại mỗi lần mở bảng. Thêm nhạc đi qua `imports`, chung với Cài đặt > Nhạc của tôi.
 */
@Stable
class MusicState(
    private val source: MusicSource,
    private val imports: MineImports,
    private val scope: CoroutineScope,
    private val menuTtlMs: Long = 10 * 60_000L,
    private val now: () -> Long = System::currentTimeMillis,
) {
    private val flow = MutableStateFlow(BookMusicUi())
    val ui: StateFlow<BookMusicUi> = flow
    private var menuAt = 0L

    init {
        imports.listen(object : MineImports.Listener {
            override fun changed(turn: MineImports.Turn?) {
                flow.update { it.copy(importing = turn != null, done = turn?.done ?: 0, total = turn?.total ?: 0) }
            }

            override fun finished(owner: String, result: Result<MusicImportResult>) = imported(owner, result)
        })
    }

    /** Mở bảng của cuốn `bookId`: cuốn khác thì bắt đầu lại (giữ menu), cùng cuốn thì đọc lại mà vẫn vẽ cái đang có. */
    fun open(bookId: String) {
        if (bookId.isEmpty()) return
        if (flow.value.bookId != bookId) flow.value = BookMusicUi(bookId = bookId, menu = flow.value.menu, importing = flow.value.importing, done = flow.value.done, total = flow.value.total)
        else flow.update { it.copy(problem = "", notice = if (it.importing) it.notice else "", swapKey = "", mine = null, swapFailed = false) }
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
    fun silence(key: String, silenced: Boolean) = change { source.silence(it, key, silenced) }

    /** Ghim một bài cho đoạn `key` (null = về bài gốc). Xong thì khép "Đổi bài" như web. */
    fun pin(key: String, link: String?) {
        if (flow.value.busy) return
        flow.update { it.copy(choosing = link.orEmpty()) }
        change(after = { ok -> flow.update { it.copy(choosing = "", swapKey = if (ok && link != null) "" else it.swapKey) } }) {
            source.pin(it, key, link)
        }
    }

    /** Mở / khép "Đổi bài" của đoạn `key` ("" = khép). Mỗi lần mở tìm lại (Nhạc của tôi có thể vừa thêm bài). */
    fun swap(key: String) {
        flow.update { it.copy(swapKey = key, mine = null, swapFailed = false) }
        if (key.isNotEmpty()) readMine(key)
    }

    fun retrySwap() = flow.value.swapKey.takeIf { it.isNotEmpty() }?.let(::swap)

    private fun readMine(key: String) {
        val id = flow.value.bookId
        if (id.isEmpty()) return
        scope.launch {
            val result = attempt { source.alternatives(id, key) }
            if (flow.value.bookId != id || flow.value.swapKey != key) return@launch
            result.onSuccess { mine -> flow.update { it.copy(mine = mine, swapFailed = false) } }
            result.onFailure { flow.update { it.copy(swapFailed = true) } }
        }
    }

    /** Thêm nhạc từ bảng: tiến độ ngay ở hàng "Thêm nhạc của bạn"; có bài trong kho thì chọn "Nhạc của tôi" cho cuốn này (sách mang theo đúng các bài đang có). */
    fun importMine(uris: List<String>) {
        val id = flow.value.bookId
        if (uris.isEmpty() || id.isEmpty() || imports.turn != null) return
        flow.update { it.copy(notice = "", problem = "") }
        imports.start(id, uris)
    }

    /**
     * Một lượt thêm nhạc xong (bấm ở đâu cũng vậy): kho đổi nên menu và "Đổi bài" đang mở đọc lại. Câu báo và lựa chọn "Nhạc của tôi" chỉ cho cuốn đã bấm,
     * khi bảng còn mở cuốn ấy.
     */
    private fun imported(owner: String, result: Result<MusicImportResult>) {
        val here = owner == flow.value.bookId
        result.onSuccess { done ->
            if (here) flow.update { it.copy(notice = VoiceText.imported(done), problem = done.failed.joinToString("\n")) }
            readMenu(force = true)
            if (flow.value.swapKey.isNotEmpty()) readMine(flow.value.swapKey)
            else if (here && done.added + done.existing > 0 && flow.value.book?.kind == MusicKind.Playlist) choose(MusicText.MINE)
        }
        result.onFailure { error -> if (here) flow.update { it.copy(problem = message(error, "Chưa thêm được nhạc")) } }
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

    private fun change(after: (ok: Boolean) -> Unit = {}, apply: suspend (String) -> BookMusic) {
        val id = flow.value.bookId
        if (id.isEmpty() || flow.value.busy) return
        flow.update { it.copy(busy = true, problem = "") }
        scope.launch {
            val result = attempt { apply(id) }
            if (flow.value.bookId != id) return@launch
            result.onSuccess { book -> flow.update { it.copy(busy = false, book = book) } }
            result.onFailure { error -> flow.update { it.copy(busy = false, problem = message(error, "Chưa đổi được nhạc nền")) } }
            after(result.isSuccess)
        }
    }

    private suspend fun <T> attempt(block: suspend () -> T): Result<T> = try {
        Result.success(block())
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Exception) {
        Result.failure(error)
    }

    private fun message(error: Throwable, fallback: String): String =
        (error as? MusicFailure ?: error as? VoiceFailure)?.message?.takeIf { it.isNotBlank() } ?: fallback
}
