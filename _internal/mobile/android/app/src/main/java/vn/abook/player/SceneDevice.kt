package vn.abook.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.readaloud.Paragraphs
import java.io.File
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.Future
import java.util.concurrent.TimeUnit

/**
 * Nhạc nền THEO CẢNH của sách chỉ có chữ trên điện thoại, đường N0 (không model; `music_nnscene.py` bên máy tính): phần máy thật giữa app và [SceneBook] - chữ chương
 * ([Store], dòng `skip` của lớp sửa), danh mục bài ([DeviceMusic.catalog]: 9 ô quanh đích êm, tải khi cần như mảnh `tracks/`), thư mục đệm theo cuốn và luồng dựng nền.
 *
 * Dựng nền, MỘT luồng, chương người nghe đang ở trước rồi [AHEAD_CHAPTERS] chương kế: hỏi mốc của chương chưa dựng xong thì chờ tối đa [BUILD_WAIT_MS], quá thì trả
 * `pending` (giọng không chờ nhạc - giao diện hỏi lại sau). Danh mục chưa tải được (mất mạng lần đầu): không nhạc, `pending` false, `unavailable` = lý do bằng lời.
 */
object DeviceScenes {
    const val AHEAD_CHAPTERS = 3
    const val BUILD_WAIT_MS = 2000L

    private val builder = SceneQueue()
    private val waiters: ExecutorService = Executors.newCachedThreadPool { Thread(it, "scene-music-wait").apply { isDaemon = true } }
    private val books = HashMap<String, Pair<String, SceneBook>>() // mã sách -> (khoá, cuốn)

    /** Chạy [cues] ở luồng riêng (lời gọi plugin không được chiếm luồng `io` chung khi chờ dựng) và trả kết quả / lỗi qua `done`. */
    fun request(context: Context, bookId: String, chapterId: Int, done: (JSONObject?, Exception?) -> Unit) {
        waiters.execute {
            try {
                done(cues(context, bookId, chapterId), null)
            } catch (error: Exception) {
                done(null, error)
            }
        }
    }

    fun cues(context: Context, bookId: String, chapterId: Int): JSONObject {
        val empty = JSONObject().put("cues", JSONArray()).put("scene", true)
        val manifest = Store.manifest(bookId) ?: return empty
        val chapters = manifest.optJSONArray("chapters") ?: return empty
        val order = ArrayList<Int>()
        val entries = HashMap<Int, JSONObject>()
        for (index in 0 until chapters.length()) {
            val chapter = chapters.optJSONObject(index) ?: continue
            order.add(chapter.optInt("id"))
            entries[chapter.optInt("id")] = chapter
        }
        if (chapterId !in entries) return empty
        val catalog = DeviceMusic.catalog(context)
        val revision = try {
            catalog.manifest().optString("revision")
        } catch (error: Exception) {
            return empty.put("unavailable", error.message.orEmpty()) // chưa có danh mục (mất mạng lần đầu): chưa có nhạc, nói lý do, hỏi lại khi có mạng
        }
        val book = bookFor(context, bookId, manifest.optString("version"), revision, order, entries, catalog)
        // Chương đã dựng với bài mà máy này hoá ra không dùng được (tải báo quá cỡ): bỏ bản ghi, dựng lại chọn bài khác (`server._scene_cues`).
        fun ready(id: Int): JSONObject? {
            val record = book.read(id) ?: return null
            if (book.links(record).any { !catalog.usable(it, null) }) {
                book.discard(id)
                return null
            }
            return record
        }
        ready(chapterId)?.let { return book.response(it) }

        val wanted = order.subList(order.indexOf(chapterId), order.size).take(AHEAD_CHAPTERS + 1)
        // Đang nghe cuốn này: việc nền của cuốn khác không còn ai chờ, chương ngoài tầm nghe cũng thôi (`Builder.cancel_others` của máy tính).
        builder.cancelOthers(bookId)
        builder.cancelOutside(bookId, wanted)
        var waiting: Future<*>? = null
        // Ưu tiên theo khoảng cách tới chương đang nghe (0, 1, 2, ...): nhảy về chương trước thì nó được dựng TRƯỚC mấy chương kế đã xếp hàng.
        for ((distance, id) in wanted.withIndex()) {
            if (id != chapterId && ready(id) != null) continue
            val job = builder.submit(bookId, id, distance) { book.build(id) }
            if (id == chapterId) waiting = job
        }
        var failed = false
        var reason: String? = null
        try {
            waiting?.get(BUILD_WAIT_MS, TimeUnit.MILLISECONDS)
        } catch (_: java.util.concurrent.TimeoutException) {
            // chương nặng dựng chưa xong: trả `pending`
        } catch (error: java.util.concurrent.ExecutionException) {
            failed = true // danh mục không tải được, chữ không đọc được: hỏi lại sau
            reason = (error.cause as? MusicCatalog.CatalogError)?.message // mục lục đã cất mà mảnh ô / tracks/ không tải được (mất mạng sau lần đầu): nói lý do, như lúc chưa có mục lục
        } catch (_: java.util.concurrent.CancellationException) {
            failed = true
        }
        val record = ready(chapterId) ?: return empty.put("pending", !failed && waiting != null).also { answer -> reason?.let { answer.put("unavailable", it) } }
        return book.response(record)
    }

    @Synchronized
    private fun bookFor(
        context: Context, bookId: String, version: String, revision: String, order: List<Int>, entries: Map<Int, JSONObject>, catalog: MusicCatalog,
    ): SceneBook {
        val key = SceneBook.sha1("$version|$revision|${SceneBook.ENGINE_VERSION}|${SceneBook.FORMAT_VERSION}".toByteArray(Charsets.UTF_8)).take(12)
        books[bookId]?.takeIf { it.first == key }?.let { return it.second }
        val root = File(context.applicationContext.filesDir, "music/scene/${SceneBook.sha1(bookId.toByteArray(Charsets.UTF_8)).take(16)}")
        root.listFiles()?.forEach { old -> // khoá cũ (sách đổi chữ, danh mục mới): bỏ bản ghi cũ
            if (old.isDirectory && old.name != key) {
                old.listFiles()?.forEach { it.delete() }
                old.delete()
            }
        }
        val near = Near(catalog)
        // Bộ chọn chỉ hỏi thứ ĐÃ BIẾT (sổ bài quá cỡ): xếp hạng hàng trăm bài mà tra cỡ từng bài là hàng trăm mảnh danh mục. Cỡ của bài ĐÃ CHỌN tra một lượt sau mỗi lần chọn
        // (`catalog.verifySizes`) và chương chọn lại nếu có bài quá cỡ - `server.music_verify_sizes` của máy tính.
        // Hỏi cả chuyện MẠNG như máy tính (`music_track_available(sizes=False)`): nguồn bài vừa hỏng / máy mất mạng thì chọn trong số bài đã tải, không chọn bài sẽ im lặng.
        val choice = SceneChoice(bookId, available = catalog::available)
        val book = SceneBook(File(root, key), order, { id -> body(bookId, id, entries[id]) }, choice, catalog::verifySizes) { near.tracks() }
        books[bookId] = key to book
        return book
    }

    /** Chữ chương đã bỏ dòng `skip` (đúng cách ReadAloud đọc: cùng chữ với màn đọc); null khi chương không có chữ ở máy này. */
    private fun body(bookId: String, chapterId: Int, chapter: JSONObject?): String? {
        val entry = chapter?.let { LibraryTree.textEntry(it) }?.takeIf { it.isNotEmpty() } ?: return null
        val file = Store.file(bookId, entry)
        if (!file.isFile) return null
        val skip = chapter.optJSONArray("skip")?.let { list -> (0 until list.length()).map { list.getString(it) } } ?: emptyList()
        return Paragraphs.withoutLines(file.readText(Charsets.UTF_8), skip)
    }

    /** Bài quanh đích êm của danh mục: tải 9 ô lần đầu (cất theo `revision`), sau đó dùng lại trong bộ nhớ. */
    private class Near(private val catalog: MusicCatalog) {
        private var tracks: List<SceneTrack>? = null

        @Synchronized
        fun tracks(): List<SceneTrack> {
            tracks?.let { return it }
            val items = catalog.near(SceneChooser.TARGET[0], SceneChooser.TARGET[1], 1)
            val found = items.mapNotNull { json -> SceneTrack.of(json) }
            tracks = found
            return found
        }
    }
}
