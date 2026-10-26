package vn.abook.player.ui.editbook

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import vn.abook.player.AndroidCoverCodec
import vn.abook.player.BookEdits
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
                if (waiting > 0) "$waiting thay đổi chờ duyệt trên máy tính." else ""
            })
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
