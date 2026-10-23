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
 * Nhạc nền THEO CẢNH của sách chỉ có chữ trên điện thoại (`music_nnscene.py` bên máy tính): học sinh NN-lite ([NnLite], 2 MB đóng sẵn trong app) chỉnh V / E / T của đoạn; model
 * không nạp được thì đường N0 (một dòng log). Phần máy thật giữa app và [SceneBook]: chữ chương ([Store], dòng `skip` của lớp sửa), danh mục bài ([DeviceMusic.catalog]:
 * các ô quanh đích của từng đoạn, tải khi cần như mảnh `tracks/`), thư mục đệm theo cuốn và luồng dựng nền.
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

    /** File model NN-lite trong assets của app (`abook/webui/assets/nnlite.bin`, cùng file với máy tính). */
    const val NNLITE_ASSET = "nnlite.bin"
    private var lite: Pair<NnLite, String>? = null // (model, mã băm file) - null: không nạp được
    private var liteTried = false

    /** Model NN-lite đã nạp một lần cho cả tiến trình; hỏng / thiếu thì null và đúng MỘT dòng log (nhạc đi đường N0). */
    @Synchronized
    private fun lite(context: Context): Pair<NnLite, String>? {
        if (!liteTried) {
            liteTried = true
            lite = try {
                val raw = context.applicationContext.assets.open(NNLITE_ASSET).use { it.readBytes() }
                NnLite.parse(raw) to SceneBook.sha1(raw).take(12)
            } catch (error: Exception) {
                AppLog.w("SceneMusic", "NN-lite không nạp được (${error.message}): nhạc theo cảnh chạy đường N0")
                null
            }
        }
        return lite
    }

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
        val model = lite(context)
        // Khoá mang học sinh nào dựng plan ("n0" hay mã model): model hỏng / đổi thì dựng lại (`student_tag` của máy tính).
        val key = SceneBook.sha1("$version|$revision|${SceneBook.ENGINE_VERSION}|${SceneBook.FORMAT_VERSION}|${model?.second ?: "n0"}".toByteArray(Charsets.UTF_8)).take(12)
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
        val student: SceneStudent? = model?.first?.let { it::chapterItems }
        val bounds: SceneBounds? = model?.first?.let { it::sceneBounds } // LB: ranh cảnh cùng model, chỉ ở đường NN-lite
        val book = SceneBook(File(root, key), order, { id -> body(bookId, id, entries[id]) }, choice, catalog::verifySizes, student, bounds) { valence, arousal -> near.tracks(valence, arousal) }
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

    /** Bài quanh một đích (valence, arousal) của danh mục: các ô kề đích (`MusicCatalog.near`, bán kính 1), mỗi ô đổi sang [SceneTrack] một lần rồi dùng lại trong bộ nhớ. */
    private class Near(private val catalog: MusicCatalog) {
        private val cells = HashMap<Pair<Int, Int>, List<SceneTrack>>()

        @Synchronized
        fun tracks(valence: Double, arousal: Double): List<SceneTrack> {
            val grid = catalog.manifest().optInt("grid", 5).takeIf { it != 0 } ?: 5
            val wanted = ArrayList<Pair<Int, Int>>()
            SceneMusic.near<SceneTrack>(grid, valence, arousal, 1) { v, a -> wanted.add(v to a); emptyList() }
            // Lần đầu nhiều ô chưa cất: để `catalog.near` tải song song (nhanh hơn nối nhau), rồi đọc từng ô như cũ - ô đã tải nằm trong bộ nhớ của danh mục.
            if (wanted.count { it !in cells } > 1) runCatching { catalog.near(valence, arousal, 1) }
            return SceneMusic.near(grid, valence, arousal, 1) { v, a -> cells.getOrPut(v to a) { catalog.cell(v, a).mapNotNull { json -> SceneTrack.of(json) } } }
        }
    }
}
