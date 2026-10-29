package vn.abook.player.ui.data

import android.content.Context
import android.content.Intent
import androidx.compose.runtime.Immutable
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import vn.abook.player.AppLog
import org.json.JSONObject
import vn.abook.player.BookActions
import vn.abook.player.ListeningRecords
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
 * (dấu "Trên máy tính"). DevicesRepo chuyển danh sách có thẩm quyền từ RemoteBooks.streamable vào [acceptRemote]; gói đã cất chỉ dùng trước lượt hỏi đầu.
 */
class LibraryRepo(private val context: Context, private val scope: kotlinx.coroutines.CoroutineScope, removed: (String) -> Unit = {}) : BookSource {
    // null until the first authoritative network catalogue; downloaded books always stay local.
    @Volatile private var remoteIds: Set<String>? = null
    // "Xoá khỏi điện thoại" như bản WebView ([BookActions.delete] / [Store.undoBook]): cuốn dời vào chỗ chờ ngay, "Hoàn tác" đưa về.
    val deletions: UndoDelete = UndoDelete(
        scope,
        hold = { id -> withContext(Dispatchers.IO) { Store.init(context); BookActions.delete(context, id) { job -> scope.launch(Dispatchers.IO) { job.run() } } } },
        restore = { token -> withContext(Dispatchers.IO) { Store.init(context); Store.undoBook(token) } },
        changed = { refresh() },
        removed = removed,
    )

    init {
        // Cuốn còn nằm chờ Hoàn tác từ lần chạy trước: nút ấy đã mất cùng tiến trình, xoá hẳn (như LibraryPlugin lúc nạp).
        scope.launch(Dispatchers.IO) { runCatching { Store.init(context); Store.sweepTrash(everything = true) } }
    }

    suspend fun acceptRemote(rows: org.json.JSONArray) {
        remoteIds = (0 until rows.length()).map { rows.getJSONObject(it).getString("id") }.toSet()
        refresh()
    }

    fun isHidden(id: String) = deletions.contains(id)

    private val flow = MutableStateFlow<LibraryState>(LibraryState.Loading)
    val state: StateFlow<LibraryState> get() = flow

    /**
     * Đọc lại danh sách (luồng nền). Lỗi đọc, đã ghi nhật ký: lần đầu = danh sách rỗng (không treo màn chờ); đã có danh sách thì GIỮ nguyên -
     * một lần đọc đĩa hỏng không được làm cuốn đang nghe "biến mất" (PlayerRepo.reconcile sẽ đóng nó).
     */
    suspend fun refresh() = withContext(Dispatchers.IO) {
        val books = try {
            readAll(context).filter { !isHidden(it.id) && (it.remote == null || remoteIds?.contains(it.id) != false) }
        } catch (error: Exception) {
            AppLog.w("Library", "Không đọc được thư viện: ${error.javaClass.simpleName}")
            if (flow.value is LibraryState.Ready) return@withContext
            emptyList()
        }
        flow.value = LibraryState.Ready(books)
    }

    // ---- trang sách (BookSource): đọc / ghi qua lõi, ghi xong thì đọc lại Thư viện ----------------------------------------

    override suspend fun detail(id: String): BookDetail? = withContext(Dispatchers.IO) {
        try {
            Store.init(context)
            val downloaded = Store.rawManifest(id) != null
            val manifest = (if (downloaded) Store.manifest(id) else Store.streamManifest(id)?.let { Store.streamed(id, it) }) ?: return@withContext null
            val remote = if (downloaded) null else RemoteRef(SyncLink.holderName(context, id))
            BookDetail.of(manifest, Store.state(id), { coverOf(it) }, remote, BookActions.canShare(id), Store.records(id), Store.isImported(id))
        } catch (error: Exception) {
            AppLog.w("Library", "Không đọc được trang sách: ${error.javaClass.simpleName}")
            null
        }
    }

    override suspend fun passages(id: String, chapter: ChapterLine): List<Passage>? = withContext(Dispatchers.IO) {
        val path = if (chapter.textOnly) chapter.textPath else "scripts/${chapter.id}.json"
        if (path.isEmpty()) return@withContext null
        val raw = runCatching { BookActions.text(context, id, path) }.getOrNull() ?: return@withContext null
        if (chapter.textOnly) BookSearch.textPassages(raw) else BookSearch.scriptPassages(raw)
    }

    override suspend fun setFinished(id: String, finished: Boolean) = write { BookActions.setFinished(context, id, finished) }

    override suspend fun setChapterDone(id: String, chapterId: Int, done: Boolean) = write { BookActions.setChapterDone(context, id, chapterId, done) }

    override suspend fun delete(id: String): String? = removeFromPhone(id)

    /**
     * Xoá khỏi điện thoại (cuốn đang tải thì lõi từ chối, câu của lõi). `title` rỗng thì lấy tên ở Thư viện; `partial`: phần đã tải dở của sách ở máy khác.
     * Null = đã nhận (cuốn nằm chờ Hoàn tác), khác null = câu lỗi.
     */
    suspend fun removeFromPhone(id: String, title: String = "", partial: Boolean = false): String? {
        val name = title.ifEmpty { (flow.value as? LibraryState.Ready)?.books?.firstOrNull { it.id == id }?.title.orEmpty() }
        return deletions.remove(id, name, partial)
    }

    override suspend fun share(id: String): Intent? = withContext(Dispatchers.IO) {
        try {
            BookActions.share(context, id, project = false).chooser
        } catch (error: Exception) {
            AppLog.w("Library", "Không đóng được file sách để chia sẻ: ${error.javaClass.simpleName}")
            null
        }
    }

    override suspend fun cast(id: String): CastView? = withContext(Dispatchers.IO) {
        try {
            Store.init(context)
            Cast.parse(BookActions.text(context, id, "cast.json"))
        } catch (error: Exception) {
            AppLog.w("Library", "Không đọc được dàn nhân vật: ${error.javaClass.simpleName}")
            null
        }
    }

    override suspend fun samplePath(id: String, sampleId: Int): String? = withContext(Dispatchers.IO) {
        runCatching { Store.init(context); Store.file(id, "samples/$sampleId.wav").takeIf { it.isFile }?.path }.getOrNull()
    }

    // ---- hồ sơ nghe: lõi chung với bản WebView ([ListeningRecords]); xong thì đọc lại Thư viện, báo máy tính ở nền ----

    private suspend fun records(change: () -> ListeningRecords.Change): String? {
        val problem = withContext(Dispatchers.IO) {
            try {
                Store.init(context)
                val done = change()
                scope.launch(Dispatchers.IO) { done.push() }
                null
            } catch (error: Exception) {
                AppLog.w("Library", "Không đổi được hồ sơ nghe: ${error.javaClass.simpleName}")
                error.message?.takeIf { it.isNotBlank() } ?: "Bạn hãy thử lại."
            }
        }
        refresh()
        return problem
    }

    override suspend fun createRecord(id: String, name: String) = records { ListeningRecords.create(context, id, name) }

    override suspend fun activateRecord(id: String, record: String) = records { ListeningRecords.activate(context, id, record) }

    override suspend fun renameRecord(id: String, record: String, name: String) = records { ListeningRecords.rename(context, id, record, name) }

    override suspend fun moveRecord(id: String, record: String, toBook: String) = records { ListeningRecords.move(context, id, record, toBook) }

    override suspend fun deleteRecord(id: String, record: String) = records { ListeningRecords.delete(context, id, record) }

    // ---- sửa một người: đường của lõi như Studio ([BookActions.studio]) ----

    private suspend fun <T> person(id: String, block: () -> T): Edit<T> {
        val result = withContext(Dispatchers.IO) {
            try {
                Edit(block(), null)
            } catch (error: Exception) {
                AppLog.w("Library", "Không sửa được nhân vật: ${error.javaClass.simpleName}")
                Edit<T>(null, error.message?.takeIf { it.isNotBlank() } ?: "Bạn hãy thử lại.")
            }
        }
        if (result.problem == null) refresh()
        return result
    }

    override suspend fun renamePerson(id: String, character: String, name: String): Edit<Renamed> = person(id) {
        val answer = BookActions.studio(context, "POST", id, "/characters/rename", JSONObject().put("character", character).put("name", name))
        Renamed(answer.optString("name"), answer.optBoolean("renamed"))
    }

    override suspend fun setGender(id: String, character: String, gender: Gender): Edit<Double> = person(id) {
        BookActions.studio(context, "POST", id, "/voice", JSONObject().put("character", character).put("gender", gender.wire)).optDouble("requestedAt")
    }

    override suspend fun withdrawGender(id: String, character: String, requestedAt: Double): String? = person(id) {
        BookActions.studio(context, "POST", id, "/voice", JSONObject().put("character", character).put("withdraw", true).put("requestedAt", requestedAt))
        true
    }.problem

    override suspend fun mergePeople(id: String, from: String, into: String): Edit<Int> = person(id) {
        BookActions.studio(context, "POST", id, "/characters/merge", JSONObject().put("from", from).put("into", into)).optInt("lines")
    }

    private suspend fun write(block: () -> Unit) {
        withContext(Dispatchers.IO) {
            try {
                block()
            } catch (error: Exception) {
                AppLog.w("Library", "Không ghi được trạng thái nghe: ${error.javaClass.simpleName}")
            }
        }
        refresh()
    }

    /** Xoá hẳn một cuốn (hết hạn hoàn tác): câu lỗi của lõi cho người nghe, không có thì "Chưa xoá được" như web; xong thì đọc lại Thư viện. */
    private suspend fun edit(block: () -> String?): String? {
        val problem = withContext(Dispatchers.IO) {
            try {
                block()
            } catch (error: Exception) {
                AppLog.w("Library", "Không sửa được sách: ${error.javaClass.simpleName}")
                error.message?.takeIf { it.isNotBlank() } ?: "Chưa xoá được"
            }
        }
        if (problem == null) refresh()
        return problem
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
                    val book = BookJson.book(manifest, Store.state(id), ::coverOf, remote, added, Store.isImported(id))
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
