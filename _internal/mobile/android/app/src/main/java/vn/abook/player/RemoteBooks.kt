package vn.abook.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.readaloud.ReadAloud
import java.io.File
import java.util.concurrent.ExecutionException
import java.util.concurrent.FutureTask

/**
 * Sách ở máy khác (máy tính chính và thiết bị ghép) mà cả hai giao diện cùng dùng (WebView qua [LibraryPlugin], native qua `ui.data.DevicesRepo`):
 * danh sách để tải ([library]) và gói sách để nghe thẳng ([streamable] - ghi `stream.json` cạnh sách, Thư viện đọc lại từ đó). Hàm trả JSON giữ nguyên hình đã
 * gửi cho WebView. Mọi hàm hỏi mạng / ghi đĩa: gọi ở luồng nền.
 */
object RemoteBooks {
    private const val STREAM_PARALLEL = 4 // số gói sách nghe thẳng lấy cùng lúc ([streamable])
    private const val STREAM_BUDGET_MS = 12_000L // hết chừng này thì cuốn còn lại dùng gói đã cất, lượt hỏi sau lấy tiếp

    /**
     * Thư viện của máy tính chính để TẢI: mỗi cuốn kèm đã tải chưa và phiên bản của bản đã tải (so với máy tính để báo "Cập nhật"). Cuốn đã tải thì làm mới mô tả
     * của nó. Nơi gọi trả lời xong thì gọi [reached].
     */
    fun library(context: Context): JSONObject {
        val reply = JSONObject(SyncLink.request(context, "GET", "/sync/v1/library"))
        val books = reply.getJSONArray("books")
        BookDownloads.matchImported(context)
        for (index in 0 until books.length()) {
            val book = books.getJSONObject(index)
            runCatching { refreshMetadata(context, book.getString("id"), book) }
            val local = Store.rawManifest(book.getString("id"))
            book.put("downloaded", local != null)
            book.put("localChapters", local?.optInt("chaptersAvailable") ?: 0)
            book.put("localCoverVersion", local?.optJSONObject("cover")?.optLong("version") ?: 0L)
            book.put("localWordsVersion", local?.optString("wordsVersion") ?: "")
            book.put("localAudioVersion", local?.optString("audioVersion") ?: "")
            book.put("localMetaVersion", local?.optString("metaVersion") ?: "")
            // Cỡ khi tải về, hiện trước khi bấm Tải (soát a68 lỗi 7): máy tính gửi kèm (`bytes`); máy tính đời trước thì lấy từ gói sách đã cất
            // cho nghe thẳng nếu còn đúng - không hỏi máy tính từng cuốn (thư viện vài chục cuốn thành vài chục lượt mạng).
            if (local == null && !book.has("bytes")) {
                Store.streamManifest(book.getString("id"))?.takeIf { it.optInt("chaptersAvailable") == book.optInt("chaptersAvailable") }
                    ?.let { book.put("bytes", DownloadSpace.bookBytes(it)) }
            }
        }
        return JSONObject().put("name", reply.optString("name")).put("books", books)
    }

    /** Sau khi [library] trả lời xong: tới được máy tính thì gửi nốt phần sửa còn tồn và chỗ nghe ghi lúc mất kết nối (soát a68 lỗi 9). */
    fun reached(context: Context) {
        EditsSync.scheduleAllPending(context)
        StateSync.flushPending(context)
    }

    /**
     * Phần mô tả của cuốn ĐÃ TẢI đổi ở máy giữ sách (tên, tác giả, người đọc, liên kết bộ, tên chương - `metaVersion`): lấy gói mới và sửa book.json tại
     * chỗ, giữ nguyên audio và lớp sửa của máy này (StreamRefresh.withMetadata). Không mạng / máy kia lỗi thì thôi, lần sau thử lại. Cuốn đang tải
     * thì để lượt tải ghi book.json mới (soát a97 V1).
     */
    private fun refreshMetadata(context: Context, id: String, entry: JSONObject, source: String? = null, remoteId: String? = null) {
        if (BookDownloads.isActive(context, id)) return
        val local = Store.rawManifest(id) ?: return
        if (!StreamRefresh.metadataStale(local, entry)) return
        val remote = remoteId ?: id
        val fresh = JSONObject(
            if (source != null) Peers.request(context, source, "GET", "/sync/v1/books/$remote/manifest")
            else SyncLink.request(context, "GET", "/sync/v1/books/$id/manifest"),
        )
        PeerPaths.checkManifest(fresh)
        if (fresh.optString("id") != remote) return
        if (source != null) Peers.localizeSeries(fresh, source)
        Store.rewriteManifest(id) { StreamRefresh.withMetadata(it, fresh) }
    }

    /**
     * The readings, skipped lines and pending speakers the holder set ([BookEdits.HOLDER_FILE], webui/package_share.py `shared_edits`):
     * fetched again when the library entry's `listenerEdits` stamp changes, dropped when the holder has none (review a70: edits made on the
     * computer never reached the phone).
     */
    private fun syncHolderEdits(context: Context, id: String, entry: JSONObject) {
        val stamp = entry.optString("listenerEdits")
        val file = File(Store.bookDir(id), BookEdits.HOLDER_FILE)
        if (stamp.isEmpty()) {
            if (file.isFile && file.delete()) ReadAloud.readingsChanged(id)
            return
        }
        if (BookEdits.holderEdits(Store.bookDir(id))?.optString("stamp") != stamp) fetchHolderEdits(context, id)
    }

    /** Lấy lại phần sửa của máy giữ sách cho cuốn `id` (sau khi gửi phần sửa về, hay khi dấu `listenerEdits` đổi). */
    fun fetchHolderEdits(context: Context, id: String) {
        if (Streaming.fetchSmall(context, id, BookEdits.HOLDER_FILE) != null) ReadAloud.readingsChanged(id)
    }

    /**
     * Sách trên máy tính CHƯA tải mà nghe thẳng được (Streaming). Gói sách chỉ lấy lại khi máy tính có thêm chương, đổi
     * tên hay đổi bìa, còn lại dùng bản đã cất. Máy tính không trả lời thì không liệt kê sách của nó: những cuốn ấy không nằm trên
     * điện thoại, hiện ra mà bấm không nghe được thì chỉ làm người nghe bối rối - TRỪ cuốn đang nằm trong trình phát (`offline`): máy tắt hay
     * mất mạng không phải thôi ghép, trình phát không được tưởng cuốn đã rời Thư viện mà đóng giữa câu (soát a68 lỗi 3). Chỉ khi máy kia trả 401
     * (đã thôi ghép điện thoại này) cuốn mới thật sự rời đi.
     */
    fun streamable(context: Context): JSONArray {
        val books = JSONArray()
        var computerAnswered = true
        // Thiết bị ghép khác trả lời độc lập với máy tính: hỏi cùng lúc, không nối đuôi (mỗi bên đã có hạn chờ riêng).
        val peersAsk = FutureTask { Peers.libraries(context) }
        Thread(peersAsk, "abook-peer-libraries").apply { isDaemon = true }.start()
        val reply = if (SyncLink.paired(context)) {
            try {
                JSONObject(SyncLink.request(context, "GET", "/sync/v1/library", readTimeoutMs = 10_000, connectTimeoutMs = 1500))
            } catch (error: Exception) {
                computerAnswered = NetErrors.unpaired(error) // 401: máy tính trả lời - nó đã thôi ghép; không giữ cuốn nào của nó
                null
            }
        } else null
        val remote = reply?.optJSONArray("books") ?: JSONArray()
        if (reply != null) {
            BookDownloads.matchImported(context)
            StateSync.flushPending(context) // chỗ nghe ghi trong lúc mất kết nối về máy tính ngay khi nối lại (soát a68 lỗi 9)
        }
        val peers = try {
            peersAsk.get()
        } catch (error: ExecutionException) {
            throw error.cause as? Exception ?: error
        }
        // Mọi cuốn của máy tính rồi của từng thiết bị ghép xếp thành MỘT danh sách việc: gói sách lấy song song có giới hạn, chung một trần
        // thời gian (STREAM_BUDGET_MS). Hết trần thì cuốn còn lại dùng gói đã cất, lượt hỏi sau lấy tiếp.
        class Job(val entry: JSONObject, val source: String?, val sourceName: String?)
        val jobs = ArrayList<Job>()
        for (index in 0 until remote.length()) jobs.add(Job(remote.getJSONObject(index), null, null))
        val peerLists = (0 until peers.length()).map { peers.getJSONObject(it) }
        for (peer in peerLists) {
            val list = peer.optJSONArray("books") ?: continue
            for (item in 0 until list.length()) jobs.add(Job(list.getJSONObject(item), peer.getString("key"), peer.optString("name")))
        }
        val rows = Bounded.map(jobs, STREAM_PARALLEL, STREAM_BUDGET_MS) { job, expired ->
            streamedRow(context, job.entry, job.source, job.sourceName) { !expired() }
        }
        var next = 0
        if (reply == null && !computerAnswered) keepPlaying(books) { it.optString("source").isEmpty() }
        repeat(remote.length()) { rows[next++]?.let(books::put) }
        // Thiết bị ghép (điện thoại khác, máy tính khác): cùng cách, gói ghi nguồn - thiết bị không trả lời thì bỏ qua (trừ cuốn đang phát, như trên).
        for (peer in peerLists) {
            if (peer.has("error") && !peer.optBoolean("unpaired")) keepPlaying(books) { it.optString("source") == peer.optString("key") }
            repeat(peer.optJSONArray("books")?.length() ?: 0) { rows[next++]?.let(books::put) }
        }
        return books
    }

    /**
     * Dòng của một cuốn nghe thẳng trong thư viện, hay null khi không có gì để hiện: cuốn đã tải về thì chỉ làm mới mô tả / phần sửa của nó; cuốn chưa
     * tải mà chưa có gói sách (cũng không lấy được) thì bỏ. `source` / `sourceName`: thiết bị ghép giữ cuốn (null = máy tính chính). `network` sai (hết
     * trần thời gian của lượt) thì không hỏi mạng: dùng gói đã cất.
     */
    private fun streamedRow(context: Context, entry: JSONObject, source: String?, sourceName: String?, network: () -> Boolean): JSONObject? {
        val id = entry.getString("id")
        val remoteId = if (source != null) entry.getString("remoteId") else null
        if (Store.rawManifest(id) != null) {
            if (network()) runCatching { refreshMetadata(context, id, entry, source, remoteId) }
            if (network()) runCatching { syncHolderEdits(context, id, entry) }
            return null
        }
        val cached = Store.streamManifest(id)
        val stale = StreamRefresh.stale(cached, entry)
        val manifest = (if (stale && network()) runCatching { Streaming.fetchManifest(context, id, source, remoteId) }.getOrNull() else null) ?: cached ?: return null
        if (manifest.optJSONObject("cover") != null && (stale || !Store.file(id, "cover.jpg").isFile) && network()) {
            runCatching { Streaming.fetchSmall(context, id, "cover.jpg") }
        }
        if (network()) runCatching { syncHolderEdits(context, id, entry) }
        val row = Store.streamed(id, manifest).put("state", Store.state(id)).put("streamed", true)
        if (sourceName != null) row.put("sourceName", sourceName)
        return row
    }

    /** Cuốn nghe thẳng đang nằm trong trình phát mà máy giữ nó không trả lời: vẫn ở danh sách (gói đã cất), đánh dấu `offline`. */
    private fun keepPlaying(books: JSONArray, ownedBy: (JSONObject) -> Boolean) {
        val id = Playback.bookId.takeIf { it.isNotEmpty() } ?: return
        if (Store.rawManifest(id) != null) return
        val manifest = Store.streamManifest(id)?.takeIf(ownedBy) ?: return
        books.put(Store.streamed(id, manifest).put("state", Store.state(id)).put("streamed", true).put("offline", true))
    }
}
