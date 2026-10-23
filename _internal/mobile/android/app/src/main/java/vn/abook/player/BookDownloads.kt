package vn.abook.player

import android.content.Context
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.WorkQuery
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import java.util.concurrent.locks.ReentrantLock

/**
 * "Tải sách" về điện thoại (từ máy tính hay thiết bị ghép): việc nền của WorkManager ở dịch vụ nền loại dataSync như xuất MP3 - ra khỏi app, tắt màn hình,
 * hệ thống giết tiến trình vẫn tải tiếp (phần dở `.part` nối lại bằng Range, [PartResume]). Thông báo có tiến độ và nút "Huỷ". Giao diện nghe tiến độ qua sự kiện
 * "download" của EbookLibrary (app-level, downloads.ts), không giữ lời gọi nào chờ.
 */
/**
 * Cuốn -> mã việc tải đang giữ nó. Đăng ký và kết thúc nằm chung một khoá và mã việc đã kết thúc được nhớ: `start` / `restore` chụp danh sách việc
 * rồi mới ghi, nên việc kết thúc xen vào giữa không thể bị ghi lại thành "đang tải" (soát a111 R2).
 */
internal class ActiveRuns {
    val map: MutableMap<String, String> = ConcurrentHashMap()
    private val ended = LinkedHashSet<String>()

    @Synchronized
    fun add(id: String, run: String): Boolean {
        if (run in ended) return false
        map[id] = run
        return true
    }

    @Synchronized
    fun addIfAbsent(id: String, run: String): Boolean {
        if (run in ended) return false
        map.putIfAbsent(id, run)
        return true
    }

    /** Việc `run` đã kết thúc: gỡ khỏi cuốn `id` (true nếu nó đang là việc hiện tại của cuốn) và nhớ để không ai ghi lại. */
    @Synchronized
    fun end(id: String, run: String): Boolean {
        ended.add(run)
        if (ended.size > MAX_ENDED) ended.remove(ended.first())
        return map.remove(id, run)
    }

    companion object {
        private const val MAX_ENDED = 256

        /** Trạng thái WorkManager của việc: còn sống (xếp hàng, đang chạy, chờ) thì true; không còn bản ghi hay đã kết thúc thì false. */
        fun alive(state: WorkInfo.State?): Boolean = state != null && !state.isFinished
    }
}

object BookDownloads {
    private const val TAG = "book-download"
    private const val KEY_BOOK = "bookId"
    private const val KEY_SOURCE = "source"
    private const val KEY_REMOTE = "remoteId"

    /** Hệ thống dừng việc tải vì dịch vụ nền hết giờ (Android 15): không chạy lại vô hạn, người nghe bấm Tải để làm tiếp từ phần đã về. */
    const val TIMEOUT_NOTE = "Hệ thống Android đã dừng việc tải sau 6 giờ - bạn bấm Tải để làm tiếp"

    /** Giao diện đang mở thì nghe tin của việc nền ("download" của EbookLibrary): tiến độ, xong, huỷ, lỗi. */
    @Volatile var events: ((JSONObject) -> Unit)? = null

    /** Cuốn có lượt tải (đang xếp hàng hay đang chạy) -> mã việc: không xoá thư mục của nó, không sửa book.json của nó từ chỗ khác. */
    internal val runs = ActiveRuns()
    val active: MutableMap<String, String> get() = runs.map

    /**
     * Cuốn có lượt tải THẬT SỰ còn sống: mục `active` mà không phải việc đang chạy ở đây thì đối chiếu với WorkManager và bỏ nếu việc đã kết thúc
     * (mục sống lại sau khi tải xong sẽ chặn xoá cuốn và làm mới mô tả suốt phiên - soát a111 R2). Gọi từ luồng I/O.
     */
    fun isActive(context: Context, id: String): Boolean {
        val run = runs.map[id] ?: return false
        if (run in running) return true
        val state = runCatching { WorkManager.getInstance(context).getWorkInfoById(UUID.fromString(run)).get()?.state }.getOrNull()
        if (ActiveRuns.alive(state)) return true
        runs.end(id, run)
        return false
    }

    /** Mã việc người nghe bấm Huỷ: việc dừng ở khối kế, giữ phần đã về (`.part`, file đã đủ) để lần bấm Tải sau tải tiếp. */
    private val cancelledRuns: MutableSet<String> = ConcurrentHashMap.newKeySet()

    /** Mỗi lần một cuốn (như hàng đợi một luồng trước đây): hai cuốn tải chung không tranh băng thông và chỗ trống của nhau; cuốn sau đứng chờ ở đây. */
    private val turn = ReentrantLock()

    /** Đợi tới lượt (kiểm [Gate] mỗi nửa giây - bấm Huỷ khi còn xếp hàng thì dừng ngay), chạy `block`, trả lượt. */
    internal fun <T> inTurn(gate: Gate, block: () -> T): T {
        while (!turn.tryLock(500, TimeUnit.MILLISECONDS)) gate.check()
        try {
            return block()
        } finally {
            turn.unlock()
        }
    }

    /** Mã việc đã vào doWork (khác việc còn xếp hàng chưa chạy). */
    private val running: MutableSet<String> = ConcurrentHashMap.newKeySet()

    class DownloadCancelled : Exception("Đã huỷ tải")

    /** Việc bị dừng từ ngoài (hệ thống dừng, hay nút Huỷ trên thông báo): [BookDownloadWorker] phân biệt hai trường hợp bằng dấu huỷ của [ExportCancellation]. */
    class Interrupted : Exception("Việc tải bị dừng")

    /** Cổng kiểm giữa các khối: ném khi người nghe bấm Huỷ ([DownloadCancelled]) hay khi việc nền bị dừng ([Interrupted]). */
    class Gate(private val run: String? = null, private val stopped: () -> Boolean = { false }) {
        fun check() {
            if (run != null && run in cancelledRuns) throw DownloadCancelled()
            if (stopped()) throw Interrupted()
        }
    }

    fun emit(event: JSONObject) {
        runCatching { events?.invoke(event) }
    }

    /** Lời cho người nghe + chữ gốc (chỉ khi là lỗi mạng đã dịch thành câu) - dùng chung cho lời gọi bị từ chối và sự kiện "download". */
    fun describe(error: Exception, fallback: String = error.javaClass.simpleName): Pair<String, String?> {
        if (error is Pin.ChangedException) return (error.message ?: Pin.CHANGED) to null
        if (NetErrors.unpaired(error)) return "Máy kia đã thôi ghép với điện thoại này - ghép lại để tải và nghe thẳng sách của nó" to null
        val kind = NetErrors.kind(error) ?: return (error.message ?: fallback) to null
        return NetErrors.message(kind) to NetErrors.technical(error)
    }

    private fun work(id: String) = "$TAG:$id"

    /**
     * Xếp việc tải cuốn `id` (nguồn: máy tính, hay thiết bị ghép `source` với mã sách `remoteId` bên ấy). Đã có việc tải cuốn này thì giữ việc ấy.
     * Gọi từ luồng I/O.
     */
    fun start(context: Context, id: String, source: String?, remoteId: String?) {
        Store.bookDir(id) // xác minh đích trước mọi yêu cầu mạng hay ghi dữ liệu
        Store.requireBookId(remoteId ?: id)
        if (source != null && remoteId == null) throw IllegalArgumentException("thiếu remoteId")
        val data = Data.Builder().putString(KEY_BOOK, id)
        source?.let { data.putString(KEY_SOURCE, it) }
        remoteId?.let { data.putString(KEY_REMOTE, it) }
        val request = OneTimeWorkRequestBuilder<BookDownloadWorker>()
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .setInputData(data.build())
            .addTag(TAG)
            .addTag("book:$id")
            .build()
        // Đã có việc tải cuốn này (xếp hàng hay đang chạy) thì giữ nó; việc đã huỷ / xong thì là việc mới.
        val queued = WorkManager.getInstance(context).enqueueUniqueWork(work(id), ExistingWorkPolicy.KEEP, request)
        runCatching { queued.result.get() }
        // Không còn việc chưa kết thúc (tải xong ngay, hay lỗi) thì không có gì để ghi; ghi một run đã chết là chặn cuốn ấy suốt phiên (soát a111 R2).
        val current = WorkManager.getInstance(context).getWorkInfosForUniqueWork(work(id)).get().firstOrNull { !it.state.isFinished }?.id ?: return
        runs.add(id, current.toString())
    }

    /** Nút Huỷ khi đang tải một cuốn (soát a68 lỗi 7). Gọi từ luồng I/O. */
    fun cancel(context: Context, id: String) {
        val run = active[id] ?: return
        cancelledRuns.add(run)
        runCatching { ExportCancellation.cancel(context, UUID.fromString(run)) }
        // Việc còn xếp hàng chưa chạy: WorkManager bỏ nó, không có doWork nào báo lại.
        if (run !in running && runs.end(id, run)) {
            cancelledRuns.remove(run)
            emit(JSONObject().put("bookId", id).put("cancelled", true))
        }
    }

    /** Lúc mở app: việc tải WorkManager còn giữ từ lần trước thì tính là đang tải (không xoá cuốn dở dưới chân nó). Gọi từ luồng I/O. */
    fun restore(context: Context) {
        val query = WorkQuery.Builder.fromTags(listOf(TAG)).addStates(listOf(WorkInfo.State.ENQUEUED, WorkInfo.State.RUNNING, WorkInfo.State.BLOCKED)).build()
        val works = runCatching { WorkManager.getInstance(context).getWorkInfos(query).get() }.getOrDefault(emptyList())
        for (info in works) {
            val book = info.tags.firstOrNull { it.startsWith("book:") }?.removePrefix("book:") ?: continue
            runs.addIfAbsent(book, info.id.toString()) // việc đã kết thúc sau lúc chụp danh sách thì ActiveRuns từ chối
        }
    }

    internal fun inputs(data: Data) = Triple(data.getString(KEY_BOOK), data.getString(KEY_SOURCE), data.getString(KEY_REMOTE))

    internal fun enter(id: String, run: String) {
        runs.add(id, run)
        running += run
    }

    /** Việc `run` xong (hay dừng hẳn): true nếu nó vẫn là việc hiện tại của cuốn - chỉ khi ấy được báo kết quả lên giao diện. */
    internal fun leave(id: String, run: String, keep: Boolean = false): Boolean {
        running -= run
        if (keep) return false
        cancelledRuns -= run
        return runs.end(id, run)
    }

    internal fun foreground(context: Context, work: UUID, bookId: String, title: String, fraction: Double): ForegroundInfo =
        Mp3Exports.foreground(context, work, bookId, title, 0, 0, TAG, fraction, "Đang tải sách…", "Huỷ", Mp3Exports.DOWNLOAD_CHANNEL)

    internal fun finished(context: Context, bookId: String, title: String, text: String) =
        Mp3Exports.finished(context, bookId, title, text, TAG, Mp3Exports.DOWNLOAD_CHANNEL)

    /**
     * Cuốn mở từ file mà máy tính cũng có: hỏi máy tính (POST /sync/v1/match, gửi cỡ + mã băm audio từng chương - sách
     * không mang mã nào) rồi gộp làm một (Store.adopt). Cuốn đang nằm trong trình phát thì để lần sau - đổi thư mục dưới
     * tay trình phát là mất chương kế tiếp và chỗ đang nghe. Máy tính không trả lời thì thôi, lần sau hỏi lại.
     *
     * `listed`: mã các cuốn máy tính vừa liệt kê. Cuốn của máy tính trên máy này mà không có trong đó có thể mang mã kiểu
     * cũ (tải từ bản cũ, docs/BOOK_IDS.md): gửi luôn mã ấy - máy tính nhận ra mã cũ của chính nó và trả mã mới, điện
     * thoại đổi khoá (Store.rekey) thay vì hiện hai bản của một cuốn.
     */
    fun matchImported(context: Context, listed: Set<String>? = null) {
        val waiting = Store.importedBooks().filter { it != Playback.bookId }
        val renamed = if (listed == null) emptyList()
        else Store.computerBooks().filter { it !in listed && it != Playback.bookId }
        if (waiting.isEmpty() && renamed.isEmpty()) return
        val books = JSONArray()
        for (id in waiting) books.put(JSONObject().put("key", id).put("chapters", Store.chapterPrints(id)))
        for (id in renamed) books.put(JSONObject().put("key", id))
        val reply = runCatching { JSONObject(SyncLink.request(context, "POST", "/sync/v1/match", JSONObject().put("books", books))) }
            .getOrNull() ?: return
        val matches = reply.optJSONObject("matches") ?: return
        for (key in matches.keys()) {
            if (key in waiting) Store.adopt(key, matches.getString(key))
            else if (key in renamed) Store.rekey(key, matches.getString(key))
        }
    }

    /** Kết nối tới một file của sách bên máy kia (đã ghim chứng chỉ, mang mã thiết bị); `resumeFrom` > 0 thì xin tiếp từ byte ấy. */
    private fun fetchFile(context: Context, gate: Gate, id: String, relative: String, expectedSize: Long, link: Peers.Link, remote: String, digest: String): Long {
        val limit = PeerTransfer.budget(relative, expectedSize)
        val target = Store.file(id, relative)
        if (expectedSize > 0 && AudioRevision.matches(target, expectedSize, digest)) return 0
        target.parentFile?.mkdirs()
        val partial = File(target.path + ".part")
        // Phần dở chỉ được nối khi biết nó thuộc phiên bản nào (ETag cạnh nó) và máy kia xác nhận đúng phiên bản + đúng chỗ (PartResume).
        var (have, tag) = PartResume.point(partial, expectedSize)
        var connection = SyncLink.bookFile(context, link, remote, relative, have, tag)
        var code = Pin.guard { connection.responseCode }
        // 416: phần dở dài hơn file hiện có trên máy kia (file đã đổi) - bỏ phần dở như đuôi lạ bên dưới.
        if (code >= 400 && !(code == 416 && have > 0)) {
            connection.disconnect()
            throw IllegalStateException("Không tải được $relative (mã $code)")
        }
        var answer = if (code == 416) PartResume.Answer.STALE_TAIL
        else PartResume.answer(code, connection.getHeaderField("Content-Range"), connection.getHeaderField("ETag"), have, tag)
        if (have > 0 && answer == PartResume.Answer.STALE_TAIL) {
            // 206 mà ETag lệch (máy kia bỏ qua If-Range): đây là đuôi của file khác. Bỏ phần dở, hỏi lại cả file.
            connection.disconnect()
            PartResume.discard(partial)
            have = 0
            connection = SyncLink.bookFile(context, link, remote, relative)
            code = Pin.guard { connection.responseCode }
            if (code >= 400) {
                connection.disconnect()
                throw IllegalStateException("Không tải được $relative (mã $code)")
            }
            answer = PartResume.Answer.WHOLE
        }
        val append = answer == PartResume.Answer.RESUME
        try {
            val initial = if (append) have else 0L
            if (connection.getHeaderFieldLong("Content-Length", -1) > limit - initial) throw PeerTransfer.Limit()
            java.io.FileOutputStream(partial, append).use { output ->
                // Ghi phiên bản SAU khi cắt `.part` (mở không nối): phần cũ không bao giờ mang ETag mới.
                if (!append) PartResume.stamp(partial, connection.getHeaderField("ETag"))
                connection.inputStream.use { input ->
                    PeerTransfer.copy(input, output, limit, target.parentFile!!, initial) { gate.check() }
                }
                output.fd.sync()
            }
        } catch (error: Exception) {
            if (error is PeerTransfer.Limit || expectedSize <= 0) PartResume.discard(partial)
            throw error
        } finally {
            connection.disconnect()
        }
        // Cỡ cuối phải đúng cỡ sách ghi trước khi nhận file: thiếu thì giữ phần dở cho lần sau, khác thì bỏ - không bao giờ đổi tên file sai thành file thật.
        when (PartResume.finish(partial.length(), expectedSize)) {
            PartResume.Final.OK -> {}
            PartResume.Final.SHORT -> throw java.io.IOException("Tải $relative chưa đủ (${partial.length()}/$expectedSize byte)")
            PartResume.Final.WRONG -> {
                val got = partial.length()
                PartResume.discard(partial)
                throw java.io.IOException("File $relative tải về không đúng cỡ ($got/$expectedSize byte)")
            }
        }
        // Băm đúng byte vừa tải (không qua bộ nhớ: `.part` là file đang đổi), rồi ghi vào sổ khi đã đổi tên - lần kiểm sau không băm lại.
        val actual = if (digest.isEmpty()) "" else AudioRevision.sha256(partial)
        if (actual != digest) {
            PartResume.discard(partial)
            throw java.io.IOException("Bản thu đã đổi trong lúc tải; bạn hãy tải lại.")
        }
        if (!partial.renameTo(target)) {
            throw java.io.IOException("Không ghi được file; bạn hãy thử tải lại.")
        }
        if (actual.isNotEmpty()) Store.rememberDigest(id, relative, target, actual)
        PartResume.tagFile(partial).delete()
        return target.length()
    }

    /**
     * Tải (hoặc cập nhật) một cuốn: chỉ tải file mới/đổi; book.json ghi CUỐI để sách chỉ hiện khi đã đủ file. Chạy ở [BookDownloadWorker]; cũng dùng
     * được ngoài việc nền: gửi phần sửa về máy tính xong thì tải lại sách (EditsSync) mà không báo "Đã tải xong". `announce`: báo tiến độ cho giao diện
     * qua sự kiện "download". `title`: tên sách khi đã biết (thông báo); `progress(byte đã về, tổng byte)` cho thanh tiến độ của thông báo.
     */
    fun downloadBook(context: Context, id: String, source: String?, remoteId: String?, announce: Boolean, gate: Gate = Gate(), title: (String) -> Unit = {},
            progress: (Long, Long) -> Unit = { _, _ -> }) {
        Store.bookDir(id) // xác minh đích trước mọi yêu cầu mạng hay ghi dữ liệu
        Store.requireBookId(remoteId ?: id)
        val link = if (source != null) Peers.link(context, source) ?: throw IllegalStateException("Thiết bị này đã thôi ghép")
        else Peers.Link(SyncLink.base(context), SyncLink.prefs(context).getString("token", "") ?: "")
        val remote = if (source != null) remoteId ?: throw IllegalArgumentException("thiếu remoteId") else id
        if (source == null) matchImported(context) // đã mở cuốn này từ file: audio sẵn trên máy, chỉ tải phần còn thiếu
        val manifest = JSONObject(SyncLink.request(context, "GET", "/sync/v1/books/$remote/manifest", root = link.base, token = link.token))
        require(manifest.getString("id") == remote) { "Mã sách máy gửi trả về không khớp; bạn hãy thử tải lại." }
        PeerPaths.checkManifest(manifest)
        title(manifest.optString("title"))
        if (source != null) {
            manifest.put("id", id).put("source", source).put("remoteId", remote).put("sourceKind", Peers.kindOf(context, source))
            Peers.localizeSeries(manifest, source)
        }
        val chapters = manifest.getJSONArray("chapters")
        val files = mutableListOf<Pair<String, Long>>()
        for (index in 0 until chapters.length()) {
            val chapter = chapters.getJSONObject(index)
            // Văn bản của MỌI chương (vài KB) - chế độ đọc đọc được cả chương chưa thu âm; audio chỉ chương đã có.
            val script = chapter.optString("script")
            if (script.isNotBlank() && script != "null") files += script to 0L
            // Chữ của chương chỉ-có-chữ (`texts/<n>.txt`, sync.text_layer): sách chưa có audio nghe được bằng Nghe ngay khi đã tải, như bản máy tính
            // (remote_books.wanted) - trước đây bỏ sót, tải xong chỉ có book.json + cast.json (soát a68 lỗi 1).
            val text = chapter.optString("text")
            if (text.isNotBlank() && text != "null") files += text to 0L
            if (!chapter.optBoolean("available")) continue
            files += chapter.getString("file") to chapter.optLong("size")
        }
        files += "cast.json" to 0L
        val samples = manifest.optJSONArray("samples") ?: JSONArray()
        for (index in 0 until samples.length()) files += samples.getString(index) to 0L
        // Ảnh bìa thật (webui/covers.py): tải lại mỗi lần (vài trăm KB); máy tính đã bỏ bìa thì xoá bản cũ.
        val cover = manifest.optJSONObject("cover")
        if (cover != null) files += cover.optString("file", "cover.jpg") to 0L
        // Nhạc nền: đúng các bài mà một mốc đang dùng (BookMusic.tracks) - nghe được cả khi không có mạng, và chuyển tiếp được cho máy khác.
        val tracks = BookMusic.tracks(manifest.optJSONObject("music"))
        PeerTransfer.checkJob(files + tracks.map { it.name to it.size })
        val total = files.sumOf { it.second } + tracks.sumOf { it.size }
        // Đủ chỗ trước khi tải (soát a68 lỗi 10): thiếu thì báo ngay, không tải dở rồi hỏng giữa chừng.
        val missing = files.sumOf { (relative, size) ->
            DownloadSpace.stillNeeded(size, Store.file(id, relative), AudioRevision.expected(manifest, relative))
        } +
            tracks.sumOf { track -> DownloadSpace.stillNeeded(track.size, runCatching { Store.contained(Store.bookDir(id), track.name) }.getOrNull()) }
        DownloadSpace.shortage(missing, Store.root.usableSpace)?.let { throw IllegalStateException(it) }
        if (cover == null) Store.file(id, "cover.jpg").delete()
        val filesTotal = files.size + tracks.size
        var done = 0L
        files.forEachIndexed { index, (relative, size) ->
            gate.check()
            fetchFile(context, gate, id, relative, size, link, remote, AudioRevision.expected(manifest, relative))
            done += size
            progress(done, total)
            if (announce) {
                emit(JSONObject().put("bookId", id).put("done", done).put("total", total)
                    .put("files", index + 1).put("filesTotal", filesTotal))
            }
        }
        tracks.forEachIndexed { index, track ->
            gate.check()
            // Một bài không tải được (sai cỡ / mã băm, máy kia ngắt) thì bỏ bài ấy: sách vẫn lưu, chỗ đó nghe thẳng từ máy kia khi có mạng.
            BookMusic.fetch(Store.bookDir(id), track) { name -> SyncLink.musicSource(context, link, remote, name) }
            done += track.size
            progress(done, total)
            if (announce) {
                emit(JSONObject().put("bookId", id).put("done", done).put("total", total)
                    .put("files", files.size + index + 1).put("filesTotal", filesTotal))
            }
        }
        Store.writeAtomic(File(Store.bookDir(id), "book.json"), manifest.toString())
        File(Store.bookDir(id), "stream.json").delete() // từng nghe thẳng: nay đã tải hẳn
        StateSync.pushNow(context, id)
        if (announce) emit(JSONObject().put("bookId", id).put("finished", true))
    }
}

/** Một lượt tải cuốn (BookDownloads.start): tải file mới/đổi, báo tiến độ ở thông báo và lên giao diện; hệ thống dừng giữa chừng thì WorkManager chạy lại. */
class BookDownloadWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    @Volatile private var title = ""

    override fun getForegroundInfo(): ForegroundInfo =
        BookDownloads.foreground(applicationContext, id, BookDownloads.inputs(inputData).first.orEmpty(), title, 0.0)

    override fun doWork(): Result {
        val context = applicationContext
        Store.init(context)
        if (ExportCancellation.cancelled(context, id)) return Result.failure() // việc đã kết thúc hẳn (huỷ / hết 6 giờ): không I/O nào
        val (bookId, source, remote) = BookDownloads.inputs(inputData)
        if (bookId == null) return Result.failure()
        val run = id.toString()
        BookDownloads.enter(bookId, run)
        var retrying = false
        fun report(error: String, technical: String?): Result {
            if (BookDownloads.leave(bookId, run)) {
                BookDownloads.emit(JSONObject().put("bookId", bookId).put("error", error).apply { if (technical != null) put("technical", technical) })
                BookDownloads.finished(context, bookId, "Tải bị gián đoạn", "$title · $error")
            }
            return Result.failure()
        }
        fun cancelled(): Result {
            if (BookDownloads.leave(bookId, run)) BookDownloads.emit(JSONObject().put("bookId", bookId).put("cancelled", true))
            return Result.failure()
        }
        try {
            title = Store.manifest(bookId)?.optString("title").orEmpty()
            // Không vào được dịch vụ nền (Android 12+ khi app đã ở nền lúc việc bắt đầu): vẫn chạy, chỉ không có thông báo đứng.
            runCatching { setForegroundAsync(BookDownloads.foreground(context, id, bookId, title, 0.0)).get() }
            var shown = 0L
            val gate = BookDownloads.Gate(run) { isStopped }
            BookDownloads.inTurn(gate) {
                BookDownloads.downloadBook(context, bookId, source, remote, announce = true, gate = gate,
                    title = { name -> if (name.isNotEmpty()) title = name },
                    progress = { done, total ->
                        val now = System.currentTimeMillis()
                        if (total > 0 && now - shown > 700) {
                            shown = now
                            runCatching { setForegroundAsync(BookDownloads.foreground(context, id, bookId, title, done.toDouble() / total)) }
                        }
                    })
            }
            BookDownloads.leave(bookId, run)
            BookDownloads.finished(context, bookId, "Đã tải xong", "$title · nghe được cả khi không có mạng")
            return Result.success()
        } catch (stopped: BookDownloads.DownloadCancelled) {
            return cancelled()
        } catch (stopped: BookDownloads.Interrupted) {
            Mp3Exports.endIfTimedOut(this) // hết 6 giờ: kết thúc HẲN việc (WorkManager không chạy lại) TRƯỚC khi dọn gì
            // Hệ thống dừng việc (không phải người nghe): WorkManager chạy lại, phần đã về nối tiếp bằng Range.
            if (Mp3Exports.stoppedBySystem(this)) {
                retrying = true
                return Result.retry()
            }
            if (Mp3Exports.timedOut(this)) return report(BookDownloads.TIMEOUT_NOTE, null)
            return cancelled()
        } catch (error: Exception) {
            Mp3Exports.endIfTimedOut(this) // hết 6 giờ: kết thúc HẲN việc (WorkManager không chạy lại) TRƯỚC khi dọn gì
            if (isStopped && Mp3Exports.stoppedBySystem(this)) {
                retrying = true
                return Result.retry()
            }
            if (isStopped && Mp3Exports.timedOut(this)) return report(BookDownloads.TIMEOUT_NOTE, null)
            val (message, technical) = BookDownloads.describe(error, "lỗi tải")
            return report(message, technical)
        } finally {
            BookDownloads.leave(bookId, run, keep = retrying)
        }
    }
}
