package vn.abook.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.readaloud.Paragraphs
import java.io.File
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.Future
import java.util.concurrent.TimeUnit

/**
 * Nhạc nền THEO CẢNH của sách chỉ có chữ trên điện thoại, đường N0 (không model; `music_nnscene.py` bên máy tính): phần máy thật giữa app và [SceneBook] - chữ chương
 * ([Store], dòng `skip` của lớp sửa), danh mục bài ([DeviceMusic.catalog]: 9 ô quanh đích êm, tải khi cần như mảnh `tracks/`), thư mục đệm theo cuốn và luồng dựng nền.
 *
 * Dựng nền, MỘT luồng, chương người nghe đang ở trước rồi [AHEAD_CHAPTERS] chương kế: hỏi mốc của chương chưa dựng xong thì chờ tối đa [BUILD_WAIT_MS], quá thì trả
 * `pending` (giọng không chờ nhạc - giao diện hỏi lại sau). Danh mục chưa tải được (mất mạng lần đầu): không nhạc, `pending` false.
 */
object DeviceScenes {
    const val AHEAD_CHAPTERS = 3
    const val BUILD_WAIT_MS = 2000L

    private val builder: ExecutorService = Executors.newSingleThreadExecutor { Thread(it, "scene-music").apply { isDaemon = true; priority = Thread.MIN_PRIORITY } }
    private val waiters: ExecutorService = Executors.newCachedThreadPool { Thread(it, "scene-music-wait").apply { isDaemon = true } }
    private val books = HashMap<String, Pair<String, SceneBook>>() // mã sách -> (khoá, cuốn)
    private val queued = ConcurrentHashMap<String, Future<*>>()    // "mã sách/chương" -> việc đang chờ / đang dựng

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
        } catch (_: Exception) {
            return empty // chưa có danh mục (mất mạng lần đầu): chưa có nhạc, hỏi lại khi có mạng
        }
        val book = bookFor(context, bookId, manifest.optString("version"), revision, order, entries, catalog)
        book.read(chapterId)?.let { return book.response(it) }

        val wanted = order.subList(order.indexOf(chapterId), order.size).take(AHEAD_CHAPTERS + 1)
        val prefix = "$bookId/"
        for ((key, job) in queued) if (key.startsWith(prefix) && key.substring(prefix.length).toIntOrNull() !in wanted) job.cancel(false) // đổi chỗ nghe: bỏ việc chưa chạy
        var waiting: Future<*>? = null
        for (id in wanted) {
            if (id != chapterId && book.read(id) != null) continue
            val key = "$bookId/$id"
            val job = queued.compute(key) { _, running ->
                if (running != null && !running.isDone) running else builder.submit(Runnable {
                    try {
                        book.build(id)
                    } finally {
                        queued.remove(key)
                    }
                })
            }
            if (id == chapterId) waiting = job
        }
        var failed = false
        try {
            waiting?.get(BUILD_WAIT_MS, TimeUnit.MILLISECONDS)
        } catch (_: java.util.concurrent.TimeoutException) {
            // chương nặng dựng chưa xong: trả `pending`
        } catch (error: java.util.concurrent.ExecutionException) {
            failed = true // danh mục không tải được, chữ không đọc được: hỏi lại sau
        } catch (_: java.util.concurrent.CancellationException) {
            failed = true
        }
        val record = book.read(chapterId) ?: return empty.put("pending", !failed && waiting != null)
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
        val choice = SceneChoice(bookId, available = { link -> catalog.usable(link, near.infoOf(link)) })
        val book = SceneBook(File(root, key), order, { id -> body(bookId, id, entries[id]) }, choice) { near.tracks() }
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
        private val infos = HashMap<String, JSONObject>()

        @Synchronized
        fun tracks(): List<SceneTrack> {
            tracks?.let { return it }
            val items = catalog.near(SceneChooser.TARGET[0], SceneChooser.TARGET[1], 1)
            val found = items.mapNotNull { json -> SceneTrack.of(json)?.also { infos.putIfAbsent(it.link, json) } }
            tracks = found
            return found
        }

        @Synchronized
        fun infoOf(link: String): JSONObject? = infos[link]
    }
}
