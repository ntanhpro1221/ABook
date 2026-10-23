package vn.abook.player

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.provider.DocumentsContract
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.Data
import androidx.work.ForegroundInfo
import androidx.work.ListenableWorker
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.WorkInfo
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONObject
import java.io.BufferedOutputStream
import java.io.File
import java.io.OutputStream

/**
 * "Xuất MP3" trên Android: chỗ lưu và việc nền quanh [Mp3Export].
 *
 * Chỗ lưu là một thư mục người dùng chọn bằng bộ chọn thư mục của hệ thống (ACTION_OPEN_DOCUMENT_TREE), nhớ lại cho lần sau - không
 * phải Music/ABook qua MediaStore. Cả hai đều không cần xin quyền trên Android 10-15, nhưng MediaStore chỉ nhận file âm thanh trong
 * Music/ (không có cover.jpg cạnh các chương như bản xuất của máy tính), không ghi đè được file của lần cài app trước (ra "(1)"), và
 * không có trên Android 7-9 (minSdk 24); thư mục tự chọn thì có cả bộ như máy tính, ghi được ra thẻ nhớ / USB, và chạy từ Android 7.
 *
 * Việc chạy bằng WorkManager ở dịch vụ nền (dataSync) - ra khỏi app, tắt màn hình vẫn chạy tiếp; tiến độ ở thông báo có nút "Dừng".
 */
object Mp3Exports {
    /**
     * Người dùng bấm "Dừng" (hay xuất lại cuốn này) khác hệ thống dừng việc (hết giờ chạy nền, máy thiếu bộ nhớ...): hệ thống dừng
     * thì việc trả `Result.retry()` và WorkManager tự chạy lại - file đích, quyền ghi và ảnh bìa vẽ sẵn phải còn. Dùng chung cho
     * ba kiểu xuất (MP3, M4B, sách nói). Không có dấu huỷ rõ ràng thì giữ tài nguyên, kể cả Android cũ không báo lý do. Hai lý do không
     * chạy lại: người dùng dừng ở trình quản lý tác vụ của hệ thống (STOP_REASON_USER, Android 14+) và dịch vụ nền hết giờ ([timedOut]).
     */
    fun stoppedBySystem(sdk: Int, reason: Int, explicitlyCancelled: Boolean = false): Boolean =
        !explicitlyCancelled && !(sdk >= 31 && (reason == WorkInfo.STOP_REASON_USER || reason == WorkInfo.STOP_REASON_FOREGROUND_SERVICE_TIMEOUT))

    /**
     * Android 15 giới hạn dịch vụ nền loại dataSync 6 giờ mỗi ngày rồi gọi onTimeout: WorkManager dừng việc với lý do này. Chạy lại ngay chỉ
     * thất bại tiếp (không còn được mở dịch vụ nền) nên việc kết thúc, báo người nghe bấm "Xuất lại" - phần đã làm vẫn còn như khi bấm "Dừng".
     */
    fun timedOut(sdk: Int, reason: Int): Boolean = sdk >= 31 && reason == WorkInfo.STOP_REASON_FOREGROUND_SERVICE_TIMEOUT

    internal fun stopReason(worker: ListenableWorker): Int =
        if (Build.VERSION.SDK_INT >= 31) worker.stopReason else WorkInfo.STOP_REASON_UNKNOWN

    internal fun stoppedBySystem(worker: ListenableWorker): Boolean = stoppedBySystem(
        Build.VERSION.SDK_INT, stopReason(worker), ExportCancellation.cancelled(worker.applicationContext, worker.id),
    )

    internal fun timedOut(worker: ListenableWorker): Boolean = timedOut(Build.VERSION.SDK_INT, stopReason(worker))

    /**
     * Việc vừa bị dừng vì dịch vụ nền hết 6 giờ và chưa có dấu kết thúc bền? WorkManager 2.12 coi kết quả trả sau khi việc đã bị dừng là vô nghĩa và đưa việc
     * về ENQUEUED (resetWorkerStatus), nên chỉ trả `Result.failure()` không ngăn được lượt chạy lại với tài nguyên đã dọn (soát a111 R1).
     */
    fun mustEnd(sdk: Int, reason: Int, stopped: Boolean, alreadyEnded: Boolean): Boolean = stopped && !alreadyEnded && timedOut(sdk, reason)

    /**
     * Hết 6 giờ thì kết thúc HẲN việc, TRƯỚC khi worker dọn tài nguyên: ghi dấu bền theo mã việc rồi huỷ việc ở WorkManager (CANCELLED thật, không
     * về ENQUEUED); worker chạy lại vì lý do nào đó đọc dấu ấy ở đầu doWork và thoát không I/O. Trả true khi vừa kết thúc việc.
     */
    internal fun endIfTimedOut(worker: ListenableWorker): Boolean {
        val context = worker.applicationContext
        if (!mustEnd(Build.VERSION.SDK_INT, stopReason(worker), worker.isStopped, ExportCancellation.cancelled(context, worker.id))) return false
        runCatching { ExportCancellation.cancel(context, worker.id) }
        return true
    }

    /** Lời cho người nghe khi hệ thống dừng việc xuất vì dịch vụ nền hết 6 giờ. */
    const val TIMEOUT_NOTE = "Hệ thống Android đã dừng việc xuất sau 6 giờ - bạn bấm Xuất lại để làm tiếp"

    private const val CHANNEL = "export"

    /** Kênh thông báo của "Tải sách" ([BookDownloads]) - dùng chung thông báo tiến độ / kết quả với xuất sách, khác tên kênh trong cài đặt của máy. */
    internal const val DOWNLOAD_CHANNEL = "download"
    private const val KEY_BOOK = "bookId"
    private const val KEY_TREE = "tree"
    private const val KEY_COVER = "cover"
    private const val KEY_MUSIC = "music"
    private const val PREFS = "mp3_export"

    /** Giao diện đang mở thì nghe tin của việc nền ("mp3Export" của EbookLibrary): tiến độ, xong, dừng, lỗi. */
    @Volatile var events: ((JSONObject) -> Unit)? = null

    /** Tin cuối của các lượt đang chạy: giao diện mở lại giữa chừng hỏi [ExportJobs.running]. */
    val live = ExportLive("mp3")

    // ---- chỗ lưu ------------------------------------------------------------------------------------------------

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun rootDocument(tree: Uri): Uri = DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree))

    /** Tên thư mục đã chọn (vd "Music"); null khi không còn đọc được (thư mục bị xoá, thẻ nhớ rút ra, quyền bị thu). */
    fun treeName(context: Context, tree: Uri): String? = if (tree.scheme == "file") File(tree.path!!).takeIf { it.isDirectory }?.name else runCatching {
        context.contentResolver.query(rootDocument(tree), arrayOf(DocumentsContract.Document.COLUMN_DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
        }
    }.getOrNull()

    /** Thư mục đã chọn lần trước nếu vẫn ghi được; không thì null - hỏi lại. */
    fun remembered(context: Context): Uri? {
        val tree = prefs(context).getString(KEY_TREE, null)?.let(Uri::parse) ?: return null
        val granted = context.contentResolver.persistedUriPermissions.any { it.uri == tree && it.isWritePermission }
        return tree.takeIf { granted && treeName(context, it) != null }
    }

    /** Giữ quyền ghi thư mục vừa chọn qua các lần mở app; trả lại quyền của thư mục cũ. */
    fun remember(context: Context, tree: Uri) {
        val flags = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        context.contentResolver.takePersistableUriPermission(tree, flags)
        val old = prefs(context).getString(KEY_TREE, null)?.let(Uri::parse)
        if (old != null && old != tree) runCatching { context.contentResolver.releasePersistableUriPermission(old, flags) }
        prefs(context).edit().putString(KEY_TREE, tree.toString()).apply()
    }

    /** Bộ chọn thư mục của hệ thống, mở sẵn ở thư mục lần trước (hay Music). */
    fun pickIntent(context: Context): Intent {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        if (Build.VERSION.SDK_INT >= 26) {
            val start = prefs(context).getString(KEY_TREE, null)?.let { runCatching { rootDocument(Uri.parse(it)) }.getOrNull() }
                ?: DocumentsContract.buildDocumentUri("com.android.externalstorage.documents", "primary:Music")
            intent.putExtra(DocumentsContract.EXTRA_INITIAL_URI, start)
        }
        return intent
    }

    /**
     * Chỗ ghi của thư mục `tree`: thư mục SAF người dùng chọn; `file:` (một thư mục của chính app - chỉ bài thử trên máy dùng, giao diện
     * không bao giờ đưa) thì ghi thẳng.
     */
    internal fun destination(context: Context, tree: Uri, treeName: String): Mp3Export.Destination =
        if (tree.scheme == "file") Mp3Export.FileDestination(File(tree.path!!)) else SafDestination(context.contentResolver, tree, treeName)

    // ---- việc nền ------------------------------------------------------------------------------------------------

    /** Bắt đầu xuất cuốn `bookId` vào thư mục `tree` (thay lượt đang chạy của cuốn ấy nếu có). Trả mã lượt - tin của lượt mang mã này. */
    fun start(context: Context, bookId: String, tree: Uri, drawnCover: File?, chapterIds: List<Int>? = null, music: Boolean = false): String {
        val data = Data.Builder().putString(KEY_BOOK, bookId).putString(KEY_TREE, tree.toString()).putBoolean(KEY_MUSIC, music)
        chapterIds?.let { data.putIntArray("chapterIds", it.toIntArray()) }
        drawnCover?.let { data.putString(KEY_COVER, it.absolutePath) }
        val request = OneTimeWorkRequestBuilder<Mp3ExportWorker>()
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .setInputData(data.build())
            .apply { ExportJobs.tags("mp3", bookId).forEach { addTag(it) } }
            .build()
        ExportCancellation.enqueue(context, "mp3-export:$bookId", request)
        return request.id.toString()
    }

    internal fun emit(event: JSONObject) {
        live.emit(event)
        runCatching { events?.invoke(event) }
    }

    /**
     * Thư mục lượt này đã tạo, nhớ theo mã việc: WorkManager chạy lại đúng việc ấy (hệ thống dừng giữa chừng) thì ghi đè vào thư mục dở thay vì
     * tạo "Tên (2)" bên cạnh nó. Xoá khi việc kết thúc hẳn ([forget]).
     */
    internal fun folderMemory(context: Context, work: java.util.UUID): Mp3Export.FolderMemory = object : Mp3Export.FolderMemory {
        private val key = "folder:$work"
        override fun recall(): String? = prefs(context).getString(key, null)
        override fun remember(name: String) {
            prefs(context).edit().putString(key, name).commit()
        }
    }

    internal fun forget(context: Context, work: java.util.UUID) {
        prefs(context).edit().remove("folder:$work").apply()
    }

    private fun channel(context: Context, id: String = CHANNEL) {
        val manager = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(id) == null) {
            val (name, text) = if (id == DOWNLOAD_CHANNEL) "Tải sách" to "Tiến độ khi tải sách về điện thoại"
            else "Xuất sách" to "Tiến độ khi xuất MP3 / M4B để nghe ở app khác"
            manager.createNotificationChannel(NotificationChannel(id, name, NotificationManager.IMPORTANCE_LOW).apply { description = text })
        }
    }

    private fun openApp(context: Context): PendingIntent? =
        context.packageManager.getLaunchIntentForPackage(context.packageName)?.let {
            PendingIntent.getActivity(context, 0, it, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        }

    /** `tag` phân biệt hai kiểu xuất của cùng một cuốn ("mp3-export", "m4b-export") - mỗi kiểu một thông báo riêng. */
    internal fun notificationId(bookId: String, tag: String = "mp3-export") = "$tag:$bookId".hashCode()

    /**
     * Thông báo đang chạy: tên sách, "3/10 chương", thanh tiến độ, nút "Dừng". `fraction` (0..1): thanh chạy theo phần cả cuốn đã làm
     * (xuất M4B - một chương có thể mất vài phút), không thì theo số chương. `heading`, `stopLabel`, `channelId`: lời và kênh khác cho việc tải sách.
     */
    internal fun foreground(context: Context, work: java.util.UUID, bookId: String, title: String, done: Int, total: Int,
                            tag: String = "mp3-export", fraction: Double? = null, heading: String = "Đang xuất sách…",
                            stopLabel: String = "Dừng", channelId: String = CHANNEL): ForegroundInfo {
        channel(context, channelId)
        val stop = ExportCancellation.stopIntent(context, work)
        val notification = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(R.mipmap.ic_launcher_monochrome)
            .setContentTitle(heading)
            .setContentText(if (total > 0) "$title · $done/$total chương" else title)
            .apply { if (fraction != null) setProgress(1000, (fraction * 1000).toInt(), false) else setProgress(total, done, total == 0) }
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setContentIntent(openApp(context))
            .addAction(0, stopLabel, stop)
            .build()
        val id = notificationId(bookId, tag)
        return if (Build.VERSION.SDK_INT >= 29) ForegroundInfo(id, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        else ForegroundInfo(id, notification)
    }

    /** Thông báo kết quả (xong / dừng / lỗi): nằm lại sau khi việc nền đã tắt, bấm vào mở app. */
    internal fun finished(context: Context, bookId: String, title: String, text: String, tag: String = "mp3-export", channelId: String = CHANNEL) {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return
        channel(context, channelId)
        val notification = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(R.mipmap.ic_launcher_monochrome)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(openApp(context))
            .setAutoCancel(true)
            .build()
        runCatching { NotificationManagerCompat.from(context).notify(notificationId(bookId, tag) + 1, notification) }
    }

    internal fun inputs(data: Data): Triple<String?, Uri?, File?> = Triple(
        data.getString(KEY_BOOK),
        data.getString(KEY_TREE)?.let(Uri::parse),
        data.getString(KEY_COVER)?.let(::File),
    )

    /** Ô "Kèm nhạc nền" của lượt. */
    internal fun music(data: Data): Boolean = data.getBoolean(KEY_MUSIC, false)
}

/** Thư mục đã chọn (SAF): mỗi bản xuất là một thư mục con mang tên sách. */
class SafDestination(private val resolver: ContentResolver, private val tree: Uri, private val treeName: String) : Mp3Export.Destination {
    override fun folder(name: String): Mp3Export.Folder {
        val root = DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree))
        val existing = children(resolver, tree, root)
        val fresh = Mp3Export.freshFolderName(name) { existing.containsKey(it) }
        val dir = DocumentsContract.createDocument(resolver, root, DocumentsContract.Document.MIME_TYPE_DIR, fresh)
            ?: throw Mp3Export.Refused("Không tạo được thư mục trong chỗ đã chọn")
        return SafFolder(resolver, tree, dir, "$treeName/$fresh")
    }

    /** Thư mục con `name` còn ở đó (lần chạy trước của chính lượt này tạo); người dùng đã xoá nó hay có file trùng tên thì null. */
    override fun existing(name: String): Mp3Export.Folder? {
        val root = DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree))
        val (id, mime) = children(resolver, tree, root)[name] ?: return null
        if (mime != DocumentsContract.Document.MIME_TYPE_DIR) return null
        return SafFolder(resolver, tree, DocumentsContract.buildDocumentUriUsingTree(tree, id), "$treeName/$name")
    }

    companion object {
        /** Tên -> (mã tài liệu, kiểu) của các mục ngay trong thư mục `parent`. */
        fun children(resolver: ContentResolver, tree: Uri, parent: Uri): MutableMap<String, Pair<String, String>> {
            val out = HashMap<String, Pair<String, String>>()
            val uri = DocumentsContract.buildChildDocumentsUriUsingTree(tree, DocumentsContract.getDocumentId(parent))
            resolver.query(uri, arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE), null, null, null)?.use { cursor ->
                while (cursor.moveToNext()) out[cursor.getString(1)] = cursor.getString(0) to cursor.getString(2)
            }
            return out
        }
    }
}

/**
 * Một thư mục bản xuất qua SAF. Ghi vào "<tên>.part" rồi mới đổi tên (như máy tính): dừng giữa chừng không để lại chương dở. Kiểu
 * "application/octet-stream" để bộ lưu trữ không tự thêm đuôi; đổi tên xong máy tự quét thành bài hát.
 */
private class SafFolder(private val resolver: ContentResolver, private val tree: Uri, private val dir: Uri, override val label: String) : Mp3Export.Folder {
    override val uri: String get() = dir.toString()

    private val known = SafDestination.children(resolver, tree, dir)

    private fun uri(documentId: String) = DocumentsContract.buildDocumentUriUsingTree(tree, documentId)

    private fun delete(name: String) {
        known.remove(name)?.let { runCatching { DocumentsContract.deleteDocument(resolver, uri(it.first)) } }
    }

    private fun create(name: String): Uri =
        DocumentsContract.createDocument(resolver, dir, "application/octet-stream", name)
            ?: throw Mp3Export.Refused("Không ghi được vào thư mục đã chọn")

    private fun stream(target: Uri): OutputStream =
        resolver.openOutputStream(target, "w") ?: throw Mp3Export.Refused("Không ghi được vào thư mục đã chọn")

    override fun write(name: String, body: (OutputStream) -> Unit) {
        val partName = "$name.part"
        delete(partName)
        val part = create(partName)
        try {
            BufferedOutputStream(stream(part), 256 * 1024).use(body)
        } catch (error: Throwable) {
            runCatching { DocumentsContract.deleteDocument(resolver, part) }
            throw error
        }
        delete(name)
        val renamed = try {
            DocumentsContract.renameDocument(resolver, part, name) ?: part
        } catch (error: Exception) {
            // Bộ lưu trữ không cho đổi tên: chép sang file tên thật rồi bỏ bản .part.
            val final = create(name)
            resolver.openInputStream(part)!!.use { input -> stream(final).use { input.copyTo(it) } }
            DocumentsContract.deleteDocument(resolver, part)
            final
        }
        known[name] = DocumentsContract.getDocumentId(renamed) to "application/octet-stream"
    }
}

/** Lượt xuất một cuốn (Mp3Exports.start): ghi bản xuất, báo tiến độ ở thông báo và lên giao diện. */
class Mp3ExportWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    @Volatile private var title = ""

    override fun getForegroundInfo(): ForegroundInfo =
        Mp3Exports.foreground(applicationContext, id, Mp3Exports.inputs(inputData).first.orEmpty(), title, 0, 0)

    override fun doWork(): Result = AppLog.worker("Mp3Export", this) { execute() }

    private fun execute(): Result {
        val context = applicationContext
        Store.init(context)
        if (ExportCancellation.cancelled(context, id)) return Result.failure() // việc đã kết thúc hẳn (huỷ / hết 6 giờ): không I/O nào
        val (bookId, tree, cover) = Mp3Exports.inputs(inputData)
        if (bookId == null || tree == null) return Result.failure()
        val run = id.toString()
        fun event() = JSONObject().put("bookId", bookId).put("run", run)
        var done = 0
        var retrying = false
        var music: ExportMusic? = null
        try {
            val base = Mp3Export.plan(bookId, cover?.takeIf { it.isFile }?.readBytes(), inputData.getIntArray("chapterIds")?.toList())
            val snapshot = ExportHistory.snapshot(base)
            title = base.title
            // Không vào được dịch vụ nền (Android 12+ khi app đã ở nền lúc việc bắt đầu): vẫn chạy, chỉ không có thông báo đứng.
            runCatching { setForegroundAsync(Mp3Exports.foreground(context, id, bookId, title, 0, base.chapters.size)).get() }
            val treeName = Mp3Exports.treeName(context, tree) ?: throw Mp3Export.Refused("Không mở được thư mục đã chọn - chọn lại nơi lưu")
            val ids = base.chapters.map { it.id }
            Mp3Exports.live.note(bookId, run, JSONObject().put("folder", "$treeName/${Mp3Export.folderName(title)}").put("music", Mp3Exports.music(inputData)))
            // "Kèm nhạc nền" (soát a99 V3): cùng bộ trộn, mức âm và ghi công với M4B; sách không có nhạc thì mỗi chương vẫn là MP3 như cũ.
            music = ExportMusic.open(context, bookId, run, ids, Mp3Exports.music(inputData), { isStopped }) { index, count ->
                Mp3Exports.emit(event().put("phase", "music-fetch").put("done", index).put("total", count))
            }
            val plan = base.with(music.mixer, music.guard)
            var shown = 0L
            fun report(written: Int, total: Int, fraction: Double) {
                val now = System.currentTimeMillis()
                if (now - shown > 700 || written == total) {
                    shown = now
                    runCatching { setForegroundAsync(Mp3Exports.foreground(context, id, bookId, title, written, total, fraction = if (plan.music != null) fraction else null)) }
                }
            }
            val destination = Mp3Exports.destination(context, tree, treeName)
            val folders = Mp3Exports.folderMemory(context, id)
            val result = if (plan.music == null) {
                Mp3Export.run(plan, destination, progress = { written, total ->
                    done = written
                    Mp3Exports.emit(event().put("done", written).put("total", total))
                    report(written, total, 0.0)
                }, stopped = { isStopped }, memory = folders)
            } else {
                val work = File(context.cacheDir, "mp3-export").apply { mkdirs() }.let { File(it, "$run.m4a") }
                // Chỗ trống cho chương dài nhất: các chương làm lần lượt, file trung gian dùng lại.
                val longest = plan.chapters.maxByOrNull { it.duration }!!
                val musicBytes = music.music?.let { json ->
                    val (rate, channels) = M4bAudio.layout(longest.file)
                    BookMusic.pcmBytes(Store.bookDir(bookId), json, rate, channels)
                } ?: 0L
                val need = M4bExport.estimatedBytes(Mp3Export.Plan(plan.title, plan.narrator, listOf(longest), 1, plan.chaptersTotal, plan.cover, plan.coverName, plan.music, plan.guard), musicBytes)
                if (work.parentFile!!.usableSpace < need) {
                    throw Mp3Export.Refused("Điện thoại không đủ chỗ trống để trộn nhạc nền (cần khoảng ${need shr 20} MB) - dọn bớt rồi xuất lại")
                }
                var offset = 0
                var phase: (JSONObject) -> JSONObject = { it }
                val encoder = M4bAudio.encoder({ name, chapter, round, over ->
                    phase = { event -> M4bExports.phase(event, name, offset + chapter, plan.chapters.size, round, over) }
                    if (name == "peaks" || name == "reencode") Mp3Exports.emit(phase(event()))
                }) { }
                try {
                    Mp3Export.runMixed(plan, destination, work, encoder, progress = { written, total ->
                        done = written
                        Mp3Exports.emit(phase(event().put("done", written).put("total", total)))
                        report(written, total, written.toDouble() / total)
                    }, stopped = { isStopped }, memory = folders, step = { finished, total, fraction ->
                        offset = finished
                        report(finished, total, (finished + fraction) / total)
                    })
                } finally {
                    work.delete()
                }
            }
            val missing = music.mixer?.missing(ids) ?: 0
            ExportHistory.remember(Store.bookDir(bookId), "mp3", result.uri ?: result.folder, snapshot)
            // Nói chỗ lưu trước (người nghe cần biết đi đâu tìm), rồi mới tới lưu ý chương thiếu.
            val selection = inputData.getIntArray("chapterIds") != null
            val partial = if (!selection && result.files < result.chaptersTotal) " Các chương chưa làm xong sẽ không có trong bản xuất." else ""
            val lost = if (missing > 0) " $missing đoạn thiếu nhạc vì chưa tải được bài." else ""
            Mp3Exports.finished(context, bookId, "Đã xuất ${result.files} chương", "$title · lưu ở ${result.folder}.$partial$lost")
            val finished = event().put("finished", true).put("files", result.files).put("chaptersTotal", result.chaptersTotal)
                .put("selection", selection)
                .put("folder", result.folder).put("uri", result.uri)
            if (plan.music != null) finished.put("mixed", true)
            if (missing > 0) finished.put("musicMissing", missing)
            Mp3Exports.emit(finished)
            Mp3Exports.endIfTimedOut(this)
            return Result.success()
        } catch (stopped: Mp3Export.Stopped) {
            Mp3Exports.endIfTimedOut(this) // hết 6 giờ: kết thúc HẲN việc (WorkManager không chạy lại) TRƯỚC khi dọn gì
            // Hệ thống dừng việc (không phải người dùng): WorkManager chạy lại, ghi đè các chương đã xuất.
            if (Mp3Exports.stoppedBySystem(this)) {
                retrying = true
                return Result.retry()
            }
            if (Mp3Exports.timedOut(this)) {
                // Dịch vụ nền hết 6 giờ (Android 15): các chương đã xuất còn nguyên; không chạy lại vô hạn.
                Mp3Exports.finished(context, bookId, "Hệ thống đã dừng việc xuất", "$title · đã xuất $done chương. ${Mp3Exports.TIMEOUT_NOTE}.")
                Mp3Exports.emit(event().put("error", Mp3Exports.TIMEOUT_NOTE))
                return Result.failure()
            }
            Mp3Exports.finished(context, bookId, "Đã dừng xuất", "$title · đã xuất $done chương")
            Mp3Exports.emit(event().put("stopped", true).put("files", done))
            return Result.failure()
        } catch (error: Exception) {
            Mp3Exports.endIfTimedOut(this) // hết 6 giờ: kết thúc HẲN việc (WorkManager không chạy lại) TRƯỚC khi dọn gì
            if (isStopped && Mp3Exports.stoppedBySystem(this)) {
                retrying = true
                return Result.retry()
            }
            val message = when {
                isStopped && Mp3Exports.timedOut(this) -> Mp3Exports.TIMEOUT_NOTE
                error is Mp3Export.Refused -> error.message.orEmpty()
                else -> "Lỗi khi ghi: ${error.message ?: error.javaClass.simpleName}"
            }
            Mp3Exports.finished(context, bookId, "Không xuất được", "$title · $message")
            Mp3Exports.emit(event().put("error", message))
            return Result.failure()
        } finally {
            music?.close()
            if (!retrying && (!isStopped || !Mp3Exports.stoppedBySystem(this))) {
                cover?.delete()
                Mp3Exports.forget(context, id)
            }
        }
    }
}
