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
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.WorkManager
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
    private const val CHANNEL = "export"
    private const val KEY_BOOK = "bookId"
    private const val KEY_TREE = "tree"
    private const val KEY_COVER = "cover"
    private const val PREFS = "mp3_export"

    /** Giao diện đang mở thì nghe tin của việc nền ("mp3Export" của EbookLibrary): tiến độ, xong, dừng, lỗi. */
    @Volatile var events: ((JSONObject) -> Unit)? = null

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
    fun start(context: Context, bookId: String, tree: Uri, drawnCover: File?): String {
        val data = Data.Builder().putString(KEY_BOOK, bookId).putString(KEY_TREE, tree.toString())
        drawnCover?.let { data.putString(KEY_COVER, it.absolutePath) }
        val request = OneTimeWorkRequestBuilder<Mp3ExportWorker>()
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .setInputData(data.build())
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("mp3-export:$bookId", ExistingWorkPolicy.REPLACE, request)
        return request.id.toString()
    }

    internal fun emit(event: JSONObject) {
        runCatching { events?.invoke(event) }
    }

    private fun channel(context: Context) {
        val manager = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(CHANNEL) == null) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL, "Xuất sách", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "Tiến độ khi xuất MP3 để nghe ở app khác"
                },
            )
        }
    }

    private fun openApp(context: Context): PendingIntent? =
        context.packageManager.getLaunchIntentForPackage(context.packageName)?.let {
            PendingIntent.getActivity(context, 0, it, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        }

    internal fun notificationId(bookId: String) = "mp3-export:$bookId".hashCode()

    /** Thông báo đang chạy: tên sách, "3/10 chương", thanh tiến độ, nút "Dừng". */
    internal fun foreground(context: Context, work: java.util.UUID, bookId: String, title: String, done: Int, total: Int): ForegroundInfo {
        channel(context)
        val stop = WorkManager.getInstance(context).createCancelPendingIntent(work)
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.mipmap.ic_launcher_monochrome)
            .setContentTitle("Đang xuất sách…")
            .setContentText(if (total > 0) "$title · $done/$total chương" else title)
            .setProgress(total, done, total == 0)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setContentIntent(openApp(context))
            .addAction(0, "Dừng", stop)
            .build()
        val id = notificationId(bookId)
        return if (Build.VERSION.SDK_INT >= 29) ForegroundInfo(id, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        else ForegroundInfo(id, notification)
    }

    /** Thông báo kết quả (xong / dừng / lỗi): nằm lại sau khi việc nền đã tắt, bấm vào mở app. */
    internal fun finished(context: Context, bookId: String, title: String, text: String) {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return
        channel(context)
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.mipmap.ic_launcher_monochrome)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(openApp(context))
            .setAutoCancel(true)
            .build()
        runCatching { NotificationManagerCompat.from(context).notify(notificationId(bookId) + 1, notification) }
    }

    internal fun inputs(data: Data): Triple<String?, Uri?, File?> = Triple(
        data.getString(KEY_BOOK),
        data.getString(KEY_TREE)?.let(Uri::parse),
        data.getString(KEY_COVER)?.let(::File),
    )
}

/** Thư mục đã chọn (SAF): mỗi bản xuất là một thư mục con mang tên sách. */
class SafDestination(private val resolver: ContentResolver, private val tree: Uri, private val treeName: String) : Mp3Export.Destination {
    override fun folder(name: String): Mp3Export.Folder {
        val root = DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree))
        val existing = children(resolver, tree, root)[name]?.takeIf { it.second == DocumentsContract.Document.MIME_TYPE_DIR }
        val dir = existing?.let { DocumentsContract.buildDocumentUriUsingTree(tree, it.first) }
            ?: DocumentsContract.createDocument(resolver, root, DocumentsContract.Document.MIME_TYPE_DIR, name)
            ?: throw Mp3Export.Refused("Không tạo được thư mục trong chỗ đã chọn")
        return SafFolder(resolver, tree, dir, "$treeName/$name")
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

    override fun doWork(): Result {
        val context = applicationContext
        Store.init(context)
        val (bookId, tree, cover) = Mp3Exports.inputs(inputData)
        if (bookId == null || tree == null) return Result.failure()
        val run = id.toString()
        fun event() = JSONObject().put("bookId", bookId).put("run", run)
        var done = 0
        try {
            val plan = Mp3Export.plan(bookId, cover?.takeIf { it.isFile }?.readBytes())
            title = plan.title
            // Không vào được dịch vụ nền (Android 12+ khi app đã ở nền lúc việc bắt đầu): vẫn chạy, chỉ không có thông báo đứng.
            runCatching { setForegroundAsync(Mp3Exports.foreground(context, id, bookId, title, 0, plan.chapters.size)).get() }
            val treeName = Mp3Exports.treeName(context, tree) ?: throw Mp3Export.Refused("Không mở được thư mục đã chọn - chọn lại nơi lưu")
            var shown = 0L
            val result = Mp3Export.run(plan, Mp3Exports.destination(context, tree, treeName), progress = { written, total ->
                done = written
                Mp3Exports.emit(event().put("done", written).put("total", total))
                val now = System.currentTimeMillis()
                if (now - shown > 700 || written == total) {
                    shown = now
                    runCatching { setForegroundAsync(Mp3Exports.foreground(context, id, bookId, title, written, total)) }
                }
            }, stopped = { isStopped })
            // Nói chỗ lưu trước (người nghe cần biết đi đâu tìm), rồi mới tới lưu ý chương thiếu.
            val partial = if (result.files < result.chaptersTotal) " Các chương chưa làm xong sẽ không có trong bản xuất." else ""
            Mp3Exports.finished(context, bookId, "Đã xuất ${result.files} chương", "$title · lưu ở ${result.folder}.$partial")
            Mp3Exports.emit(event().put("finished", true).put("files", result.files).put("chaptersTotal", result.chaptersTotal)
                .put("folder", result.folder).put("uri", result.uri))
            return Result.success()
        } catch (stopped: Mp3Export.Stopped) {
            Mp3Exports.finished(context, bookId, "Đã dừng xuất", "$title · đã xuất $done chương")
            Mp3Exports.emit(event().put("stopped", true).put("files", done))
            return Result.failure()
        } catch (error: Exception) {
            val message = if (error is Mp3Export.Refused) error.message.orEmpty() else "Lỗi khi ghi: ${error.message ?: error.javaClass.simpleName}"
            Mp3Exports.finished(context, bookId, "Không xuất được", "$title · $message")
            Mp3Exports.emit(event().put("error", message))
            return Result.failure()
        } finally {
            cover?.delete()
        }
    }
}
