package vn.abook.player.ui.editbook

import android.content.Context
import android.graphics.BitmapFactory
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import vn.abook.player.AndroidCoverCodec
import vn.abook.player.BookActions
import vn.abook.player.BookEdits
import vn.abook.player.CoverSearch
import vn.abook.player.LocalStudio
import vn.abook.player.BookDownloads
import vn.abook.player.EditsSync
import vn.abook.player.Store
import vn.abook.player.Streaming
import vn.abook.player.SyncLink
import vn.abook.player.Playlists
import vn.abook.player.ui.data.LibraryRepo
import vn.abook.player.readaloud.ReadAloud

interface EditSource {
    suspend fun load(id: String): EditSnapshot
    suspend fun save(id: String, diff: EditDiff): EditSnapshot
    suspend fun cover(id: String, image: ByteArray?): EditSnapshot
    suspend fun revertChapter(id: String, chapterId: Long): EditSnapshot
    suspend fun send(id: String): EditSnapshot

    /** "Bỏ mọi thay đổi": sách trở về đúng như người làm sách đã đóng gói (`DELETE /edits`). */
    suspend fun discardAll(id: String): EditSnapshot = load(id)

    /** "Cách đọc tên" của cuốn (`GET /readings`). */
    suspend fun readings(id: String): List<WordReading> = emptyList()

    /** Đặt (hay bỏ - `spoken` rỗng) cách đọc của một từ cho cả cuốn (`PUT /readings`); trả danh sách mới. */
    suspend fun setReading(id: String, surface: String, spoken: String): List<WordReading> = readings(id)

    /** "Tìm bìa trên mạng" theo tên (`GET /cover/search?q=`). */
    suspend fun findCovers(id: String, query: String): CoverResults = CoverResults(query)

    /** Đặt ảnh tìm được làm bìa (`PUT /cover {url}`): lõi tự tải, chỉ từ các nguồn đã cho phép. */
    suspend fun coverFromUrl(id: String, url: String): EditSnapshot = load(id)

    /** Ảnh nhỏ của một kết quả tìm bìa; null khi không tải được. */
    suspend fun thumbnail(url: String): ImageBitmap? = null
}

class EditBookRepo(private val context: Context, private val library: LibraryRepo) : EditSource {
    override suspend fun load(id: String): EditSnapshot = withContext(Dispatchers.IO) {
        Store.init(context)
        val book = Store.manifest(id) ?: Store.streamManifest(id)?.let { Store.streamed(id, it) }
            ?: error("Không tìm thấy sách. Bạn hãy quay lại Thư viện.")
        val array = book.optJSONArray("chapters")
        val dir = Store.bookDir(id)
        // Tên trong file gốc (trước lớp sửa) để hiện "Về tên gốc": cuốn nghe thẳng chưa tải có stream.json cạnh lớp sửa, không có thì để trống.
        val originals = BookEdits.rawBookOrNull(dir)?.optJSONArray("chapters")?.let { raw ->
            (0 until raw.length()).mapNotNull { raw.optJSONObject(it) }.associate { row ->
                row.optLong("id") to listOf(row.optString("title"), row.optString("subtitle")).filter { it.isNotEmpty() && it != "null" }.joinToString(": ")
            }
        }.orEmpty()
        val chapters = (0 until (array?.length() ?: 0)).mapNotNull { index ->
            val row = array?.optJSONObject(index) ?: return@mapNotNull null
            EditChapter(row.optLong("id"), row.optString("title"), row.optString("subtitle"), originals[row.optLong("id")].orEmpty())
        }
        val edits = BookEdits.load(dir)
        val pending = EditsSync.pending(dir, edits)
        val sync = EditsSync.view(dir, pending)
        val last = sync.optJSONObject("last")
        EditSnapshot(id, book.optString("title"), book.optString("author").takeUnless { it == "null" }.orEmpty(), chapters,
            LibraryRepo.coverOf(id), Playlists.isTextBook(book), Store.editDestination(id) != null,
            SyncLink.holderName(context, id).ifEmpty { "máy tính" }, pending,
            last?.optString("error").orEmpty().ifEmpty {
                val waiting = last?.optInt("waiting") ?: 0
                when {
                    last?.optString("state") == EditsSync.FAILED -> "Chưa gửi được - sẽ thử lại."
                    waiting > 0 -> "$waiting thay đổi chờ duyệt trên máy tính."
                    else -> ""
                }
            }, BookEdits.count(edits))
    }

    override suspend fun save(id: String, diff: EditDiff): EditSnapshot = withContext(Dispatchers.IO) {
        EditLogic.validate(diff)?.let { error(it) }
        val dir = Store.bookDir(id)
        diff.title?.let { BookEdits.setTitle(dir, it) }
        diff.author?.let { BookEdits.setAuthor(dir, it) }
        for (chapter in diff.chapters) BookEdits.setChapterTitle(dir, chapter.id, chapter.title, chapter.subtitle)
        changed(id)
    }

    override suspend fun cover(id: String, image: ByteArray?): EditSnapshot = withContext(Dispatchers.IO) {
        if (image == null) BookEdits.removeCover(Store.bookDir(id)) else BookEdits.setCover(Store.bookDir(id), image, AndroidCoverCodec)
        changed(id)
    }

    override suspend fun revertChapter(id: String, chapterId: Long): EditSnapshot = withContext(Dispatchers.IO) {
        BookEdits.setChapterTitle(Store.bookDir(id), chapterId, null, null)
        changed(id)
    }

    private suspend fun changed(id: String): EditSnapshot {
        ReadAloud.readingsChanged(id)
        EditsSync.schedule(context, id)
        library.refresh()
        return load(id)
    }

    /**
     * Một đường của [LocalStudio] - cùng đường và cùng lời đáp mà bản web gọi (`EbookLibrary.studio`), nên hai giao diện sửa sách như nhau. Khác 200: ném câu lỗi của
     * lõi. Sửa xong (khác GET): nhạc đang phát đọc lại lớp sửa, cuốn của máy tính gửi phần sửa về ([BookActions.edited], như LibraryPlugin.studio).
     */
    private fun studio(method: String, id: String, rest: String, body: JSONObject? = null): JSONObject {
        Store.init(context)
        val (status, reply) = LocalStudio.handle(method, "/api/books/$id$rest", body)
        val answer = reply as? JSONObject ?: JSONObject()
        if (status != 200) error(answer.optString("error").ifEmpty { "Bạn hãy thử lại." })
        if (method != "GET") BookActions.edited(context, id)
        return answer
    }

    private fun readingsOf(view: JSONObject): List<WordReading> {
        val list = view.optJSONArray("readings") ?: return emptyList()
        return (0 until list.length()).mapNotNull { list.optJSONObject(it) }.map { WordReading(it.optString("surface"), it.optString("spoken")) }
    }

    override suspend fun discardAll(id: String): EditSnapshot = withContext(Dispatchers.IO) {
        studio("DELETE", id, "/edits")
        changed(id)
    }

    override suspend fun readings(id: String): List<WordReading> = withContext(Dispatchers.IO) { readingsOf(studio("GET", id, "/readings")) }

    override suspend fun setReading(id: String, surface: String, spoken: String): List<WordReading> = withContext(Dispatchers.IO) {
        readingsOf(studio("PUT", id, "/readings", JSONObject().put("surface", surface).put("spoken", spoken)))
    }

    override suspend fun findCovers(id: String, query: String): CoverResults = withContext(Dispatchers.IO) {
        // Tham số của GET đi trong `body` như android/localStudio.ts; cần mạng: lõi chạy ngoài khoá sửa.
        val view = studio("GET", id, "/cover/search", JSONObject().put("q", query))
        val results = view.optJSONArray("results")?.let { array ->
            (0 until array.length()).mapNotNull { array.optJSONObject(it) }.map {
                FoundCover(it.optString("provider"), it.optString("title"), it.optString("author"), it.optString("thumb"), it.optString("url"))
            }
        }.orEmpty()
        val failed = view.optJSONArray("failed")?.let { array -> (0 until array.length()).map { array.optString(it) } }.orEmpty()
        CoverResults(view.optString("query", query), results, failed)
    }

    override suspend fun coverFromUrl(id: String, url: String): EditSnapshot = withContext(Dispatchers.IO) {
        studio("PUT", id, "/cover", JSONObject().put("url", url))
        changed(id)
    }

    override suspend fun thumbnail(url: String): ImageBitmap? = withContext(Dispatchers.IO) {
        try {
            // Cùng cửa tải với ảnh bìa đã chọn: chỉ máy chủ ảnh của các nguồn đã cho phép, có trần cỡ.
            val bytes = CoverSearch.downloadImage(url)
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
        } catch (error: Exception) {
            null
        }
    }

    override suspend fun send(id: String): EditSnapshot = withContext(Dispatchers.IO) {
        EditsSync.pushNow(context, id)
        library.refresh()
        load(id)
    }

    /** EditsSync calls this on its I/O executor before removing acknowledged overlay entries. */
    fun refreshFromHolder(id: String) {
        Store.editDestination(id)?.let { (peer, remote) ->
            if (Store.rawManifest(id) != null) BookDownloads.downloadBook(context, id, peer, remote, announce = false)
            else {
                val manifest = Streaming.fetchManifest(context, id, peer, remote)
                if (manifest.optJSONObject("cover") != null) Streaming.fetchSmall(context, id, "cover.jpg")
            }
        }
    }
}
