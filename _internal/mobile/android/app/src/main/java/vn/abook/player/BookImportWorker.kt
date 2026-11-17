package vn.abook.player

import android.app.Activity
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
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
import vn.abook.player.ui.addbook.ImportLogic
import java.io.File

/**
 * Nhập file sách ở nền, dùng chung cho mọi lối vào: bộ chọn file và "Mở bằng" của "Thêm sách" ([vn.abook.player.ui.addbook.ImportRepo]), lệnh adb của
 * người phát triển ([ImportReceiver]), nút "Thử lại" / "Thay bằng file này" trên thông báo. Việc chạy bằng WorkManager (việc gấp - expedited, dịch vụ nền
 * loại dataSync khi được phép) nên sống qua lúc rời app, đóng màn, Activity dựng lại, và cả tiến trình chết (WorkManager chạy lại). Các lượt đi tuần tự
 * (một chuỗi việc duy nhất): hai file 1,4 GB không giành ổ và bộ nhớ đệm của nhau. Không bao giờ đưa Activity lên màn hình.
 */
object BookImports {
    val jobs = ImportJobs()

    /** Lệnh nhập ngầm (adb). Cùng tên cho bản phát hành và bản .dev. */
    const val ACTION_IMPORT = "com.ngdtuanh.abook.action.IMPORT"
    /** Thông báo "Đã thêm" mở trang của cuốn ([EXTRA_BOOK]); thông báo tiến độ mở "Thêm sách". */
    const val ACTION_OPEN_BOOK = "vn.abook.player.OPEN_IMPORTED_BOOK"
    const val ACTION_SHOW_IMPORTS = "vn.abook.player.SHOW_IMPORTS"
    const val EXTRA_BOOK = "bookId"
    internal const val ACTION_RETRY = "vn.abook.player.RETRY_IMPORT"

    private const val UNIQUE = "book-import"
    private const val TAG = "book-import"
    private const val KEY_SOURCE = "source"
    private const val KEY_NAME = "name"
    private const val KEY_OWNED = "owned"
    private const val KEY_OLDER = "allowOlder"
    private const val KEY_DISCARD = "discardImportedSource"

    /** Test JVM (Robolectric không chạy việc của WorkManager): lượt chạy ngay trên luồng gọi [start], cùng lõi [ImportJobs.run] như việc nền. */
    @androidx.annotation.VisibleForTesting
    @Volatile internal var inline = false

    /** Thư mục nhập của app; null khi bộ nhớ ngoài chưa sẵn (thẻ chưa gắn). */
    fun inbox(context: Context): File? = context.getExternalFilesDir(null)?.let { File(it, ImportInbox.FOLDER) }

    /** Xếp một lượt nhập; file đang có lượt chạy thì trả lượt ấy. Trả mã lượt. Luồng bất kỳ. */
    @Synchronized
    fun start(context: Context, source: String, name: String, owned: Boolean = false, allowOlder: Boolean = false): String {
        jobs.running(source)?.let { return it.id }
        val data = Data.Builder().putString(KEY_SOURCE, source).putString(KEY_NAME, name).putBoolean(KEY_OWNED, owned).putBoolean(KEY_OLDER, allowOlder).build()
        val request = OneTimeWorkRequestBuilder<BookImportWorker>()
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .setInputData(data)
            .addTag(TAG)
            .build()
        val id = request.id.toString()
        val job = ImportJob(id, source, name, owned, allowOlder)
        jobs.begin(job)
        if (inline) {
            jobs.run(job, { sink -> importOne(context, job, sink) }, { discardOwned(context, job) })
            return id
        }
        BookImportNotes.clearResult(context, source)
        // Nối vào chuỗi: lượt trước còn chạy thì lượt này chờ (BLOCKED) rồi tự chạy; chuỗi đã xong / hỏng thì bắt đầu chuỗi mới.
        val cleanup = OneTimeWorkRequestBuilder<BookImportCleanupWorker>().addTag(TAG).build()
        WorkManager.getInstance(context).beginUniqueWork(UNIQUE, ExistingWorkPolicy.APPEND_OR_REPLACE, request).then(cleanup).enqueue()
        return id
    }

    /**
     * "Thêm sách" nhập một file và chờ kết quả (luồng của màn, không chặn luồng chính). Coroutine bị huỷ (bỏ hàng) thì lượt nền vẫn chạy tới xong.
     * Lỗi thì ném [BookFileImport.Refused] mang lời của lượt.
     */
    suspend fun importNow(context: Context, source: String, name: String, allowOlder: Boolean = false, progress: WorkSink = {}): ImportJob {
        val id = start(context, source, name, allowOlder = allowOlder)
        val job = jobs.await(id, progress) ?: throw BookFileImport.Refused(S.s_chua_doc_duoc_file_6575d76b)
        if (job.state == ImportJobState.Failed) throw BookFileImport.Refused(job.problem)
        return job
    }

    internal fun inputs(id: String, data: Data): ImportJob? {
        val source = data.getString(KEY_SOURCE) ?: return null
        return ImportJob(id, source, data.getString(KEY_NAME).orEmpty(), data.getBoolean(KEY_OWNED, false), data.getBoolean(KEY_OLDER, false))
    }

    /**
     * Nhập một file. file:// (thư mục nhập, "Mở bằng" file trên máy) đọc thẳng tại chỗ - không chép 1,4 GB sang bộ nhớ đệm rồi mới kiểm; content:// đi đường
     * chép rồi kiểm của [BookFileImport.import]. File của thư mục nhập được kiểm lại ở đây (lúc chạy, không chỉ lúc nhận lệnh).
     */
    internal fun importOne(context: Context, job: ImportJob, progress: WorkSink, checkpoint: () -> Unit = {}): ImportOutcome {
        checkpoint()
        Store.init(context)
        val uri = Uri.parse(job.source)
        val result = if (uri.scheme == "file") {
            val file = File(requireNotNull(uri.path) { S.s_chua_doc_duoc_file_6575d76b })
            if (job.owned) ownedFile(context, file) ?: throw BookFileImport.Refused(S.s_chua_doc_duoc_file_6575d76b)
            if (!file.isFile) throw BookFileImport.Refused(S.s_chua_doc_duoc_file_6575d76b)
            BookFileImport.importFile(file, allowOlder = job.allowOlder, progress = progress, checkpoint = checkpoint)
        } else {
            BookFileImport.import(context, uri, job.allowOlder, progress, checkpoint)
        }
        checkpoint()
        return ImportOutcome(result.id, result.title, result.how, result.incomingTitle)
    }

    /** `file` nếu nó vẫn là file sách nằm ngay trong thư mục nhập của app; không thì null. */
    private fun ownedFile(context: Context, file: File): File? {
        val inbox = inbox(context) ?: return null
        val root = runCatching { inbox.canonicalFile }.getOrNull() ?: return null
        return file.takeIf { ImportInbox.refusal(root, it) == null }
    }

    /** Sách đã vào thư viện: bỏ file nguồn của thư mục nhập (không tốn chỗ gấp đôi). Chỉ file của thư mục nhập, kiểm lại trước khi xoá. */
    internal fun discardOwned(context: Context, job: ImportJob) {
        if (!job.owned) return
        val path = Uri.parse(job.source).takeIf { it.scheme == "file" }?.path ?: return
        val file = ownedFile(context, File(path)) ?: return
        if (file.delete()) AppLog.i("BookImport", "import folder file removed after import: ${file.name}")
    }

    internal fun completion(job: ImportJob): Data = Data.Builder()
        .putString(KEY_SOURCE, job.source).putString(KEY_NAME, job.name).putBoolean(KEY_OWNED, job.owned)
        .putBoolean(KEY_DISCARD, job.state == ImportJobState.Done && !job.needsChoice).build()

    internal fun cleanup(context: Context, data: Data) {
        if (data.getBoolean(KEY_DISCARD, false)) inputs("cleanup", data)?.let { discardOwned(context, it) }
    }
}

/** Runs only after WorkManager has durably accepted the import's success, so a replay never loses its source. */
class BookImportCleanupWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result = AppLog.worker("BookImportCleanup", this) {
        BookImports.cleanup(applicationContext, inputData)
        Result.success()
    }
}

/** Thông báo của việc nhập nền: tiến độ (bấm mở "Thêm sách"), xong (bấm mở sách), lỗi ("Thử lại"), cần chọn ("Thay bằng file này"). */
object BookImportNotes {
    private const val CHANNEL = "import"

    private fun channel(context: Context) {
        val manager = context.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(CHANNEL) == null) {
            manager.createNotificationChannel(NotificationChannel(CHANNEL, S.s_them_sach_2a9d3708, NotificationManager.IMPORTANCE_LOW).apply {
                description = S.s_import_channel_note
            })
        }
    }

    /** Mã thông báo theo file (không theo lượt): thử lại cùng file thì thay thông báo cũ, không chồng thêm. */
    private fun progressId(source: String) = "book-import:$source".hashCode()
    private fun resultId(source: String) = progressId(source) + 1

    private fun activity(context: Context, action: String, code: Int, book: String? = null): PendingIntent =
        PendingIntent.getActivity(context, code, Intent(action).setClassName(context, "vn.abook.player.ui.NativeActivity")
            .apply { book?.let { putExtra(BookImports.EXTRA_BOOK, it) } }
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    private fun again(context: Context, job: ImportJob, allowOlder: Boolean): PendingIntent = PendingIntent.getBroadcast(
        context, resultId(job.source), Intent(context, ImportActionReceiver::class.java).setAction(BookImports.ACTION_RETRY)
            .putExtra("source", job.source).putExtra("name", job.name).putExtra("owned", job.owned).putExtra("allowOlder", allowOlder),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    private fun progress(context: Context, job: ImportJob, work: Work) = NotificationCompat.Builder(context, CHANNEL)
        .setSmallIcon(R.drawable.ic_notification)
        .setContentTitle(S.s_import_running_title)
        .setContentText(listOf(job.name, ImportLogic.workLabel(work)).filter { it.isNotBlank() }.joinToString(" · "))
        .apply { val fraction = work.fraction; if (fraction != null) setProgress(1000, (fraction * 1000).toInt(), false) else setProgress(0, 0, true) }
        .setOngoing(true)
        .setOnlyAlertOnce(true)
        .setSilent(true)
        .setContentIntent(activity(context, BookImports.ACTION_SHOW_IMPORTS, progressId(job.source)))
        .build()

    fun foreground(context: Context, job: ImportJob, work: Work): ForegroundInfo {
        channel(context)
        val note = progress(context, job, work)
        return if (Build.VERSION.SDK_INT >= 29) ForegroundInfo(progressId(job.source), note, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        else ForegroundInfo(progressId(job.source), note)
    }

    /** Không vào được dịch vụ nền (Android 12+ khi app đang ở nền và việc chạy kiểu gấp): cùng thông báo tiến độ, đăng thường. */
    fun showProgress(context: Context, job: ImportJob, work: Work) {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return
        channel(context)
        runCatching { NotificationManagerCompat.from(context).notify(progressId(job.source), progress(context, job, work)) }
    }

    fun clearProgress(context: Context, job: ImportJob) = runCatching { NotificationManagerCompat.from(context).cancel(progressId(job.source)) }

    fun clearResult(context: Context, source: String) = runCatching { NotificationManagerCompat.from(context).cancel(resultId(source)) }

    /** Thông báo kết quả, nằm lại sau khi việc nền đã tắt. Không có quyền thông báo thì thôi - sách vẫn vào thư viện. */
    fun finished(context: Context, job: ImportJob) {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return
        channel(context)
        val builder = NotificationCompat.Builder(context, CHANNEL).setSmallIcon(R.drawable.ic_notification).setAutoCancel(true)
        val book = job.bookId
        when {
            job.state == ImportJobState.Failed -> {
                val text = listOf(job.name, job.problem).filter { it.isNotBlank() }.joinToString(" · ")
                builder.setContentTitle(S.s_chua_them_duoc_sach_b327e086).setContentText(text).setStyle(NotificationCompat.BigTextStyle().bigText(text))
                    .setContentIntent(activity(context, BookImports.ACTION_SHOW_IMPORTS, resultId(job.source)))
                    .addAction(0, S.s_thu_lai_c58d068c, again(context, job, job.allowOlder))
            }
            job.needsChoice -> {
                val text = listOf(job.title, S.s_chinh_sua_va_cho_nghe_cua_ban_van_duoc_giu_287783a6).filter { it.isNotBlank() }.joinToString(" · ")
                builder.setContentTitle(S.s_file_nay_co_ban_thu_khac_6036a451).setContentText(text).setStyle(NotificationCompat.BigTextStyle().bigText(text))
                    .apply { if (book != null) setContentIntent(activity(context, BookImports.ACTION_OPEN_BOOK, resultId(job.source), book)) }
                    .addAction(0, S.s_thay_bang_file_nay_3140e07e, again(context, job, allowOlder = true))
            }
            else -> {
                val title = when (job.how) {
                    "updated" -> S.s_da_cap_nhat_0_627a2681(job.title)
                    "existing" -> S.s_da_co_trong_thu_vien_3bb6eeb4
                    else -> S.s_da_them_0_ea40abe7(job.title)
                }
                builder.setContentTitle(title).setContentText(if (job.how == "existing") job.title else S.s_import_open_hint)
                if (book != null) builder.setContentIntent(activity(context, BookImports.ACTION_OPEN_BOOK, resultId(job.source), book))
            }
        }
        runCatching { NotificationManagerCompat.from(context).notify(resultId(job.source), builder.build()) }
    }
}

/** Một lượt nhập ([BookImports.start]): chạy lõi nhập, báo tiến độ lên [BookImports.jobs] và thông báo. */
class BookImportWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun getForegroundInfo(): ForegroundInfo = BookImportNotes.foreground(applicationContext,
        BookImports.inputs(id.toString(), inputData) ?: ImportJob(id.toString(), "", ""), Work(WorkStep.Read))

    override fun doWork(): Result = AppLog.worker("BookImport", this) { execute() }

    private fun execute(): Result {
        val context = applicationContext
        val job = BookImports.inputs(id.toString(), inputData) ?: return Result.failure()
        // Android 12+ không cho mở dịch vụ nền khi app đang ở nền: việc vẫn chạy (kiểu gấp), thông báo tiến độ đăng thường.
        val foreground = runCatching { setForegroundAsync(BookImportNotes.foreground(context, job, Work(WorkStep.Read))).get() }.isSuccess
        if (!foreground) BookImportNotes.showProgress(context, job, Work(WorkStep.Read))
        val note = WorkThrottle({ work ->
            if (foreground) runCatching { setForegroundAsync(BookImportNotes.foreground(context, job, work)) } else BookImportNotes.showProgress(context, job, work)
        }, minMs = 1000)
        val checkpoint = { if (isStopped) throw ImportStopped() }
        val end = try {
            // Check every copy/extract chunk, before progress throttling, and at the importer's commit boundaries.
            BookImports.jobs.run(job, { sink ->
                try {
                    BookImports.importOne(context, job, { work -> checkpoint(); sink(work) }, checkpoint)
                } catch (error: Exception) {
                    checkpoint()
                    throw error
                }
            }, {}, note)
        } catch (_: ImportStopped) {
            BookImports.jobs.begin(job)
            return Result.retry()
        } finally {
            if (!foreground) BookImportNotes.clearProgress(context, job)
        }
        if (end.state == ImportJobState.Failed && isStopped && Mp3Exports.stoppedBySystem(this)) {
            // Hệ thống dừng giữa chừng (không phải lỗi của file): WorkManager chạy lại; người xem tiếp tục thấy "đang chạy".
            BookImports.jobs.begin(job)
            return Result.retry()
        }
        AppLog.i("BookImport", "import ${end.state.name.lowercase()}: ${end.how.ifEmpty { "-" }} ${end.problem.take(200)}")
        BookImportNotes.finished(context, end)
        return Result.success(BookImports.completion(end))
    }
}

/**
 * Lệnh nhập ngầm cho người phát triển / máy khác qua adb - KHÔNG đưa app lên màn hình:
 * `adb shell am broadcast -a com.ngdtuanh.abook.action.IMPORT -n <gói>/vn.abook.player.ImportReceiver [--es path <file trong thư mục nhập>] [--ez replace true]`.
 * Không có `path` = mọi file sách trong thư mục nhập. Được bảo vệ bằng quyền DUMP (khai ở manifest): chỉ shell / hệ thống gửi được, app khác không.
 * Kết quả (dòng "Broadcast completed" của am): mã -1 = đã xếp, 1 = không có gì / bị từ chối, kèm lời tiếng Anh.
 */
class ImportReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != BookImports.ACTION_IMPORT) return
        val inbox = BookImports.inbox(context)
        val pick = if (inbox == null) ImportInbox.Pick(emptyList(), listOf("external storage unavailable"))
        else { inbox.mkdirs(); ImportInbox.resolve(inbox, intent.getStringExtra("path")) }
        val replace = intent.getBooleanExtra("replace", false)
        for (file in pick.files) BookImports.start(context, Uri.fromFile(file).toString(), file.name, owned = true, allowOlder = replace)
        val message = buildList {
            add(if (pick.files.isEmpty()) "nothing queued" else "queued ${pick.files.size}: ${pick.files.joinToString { it.name }}")
            addAll(pick.refused.map { "refused $it" })
            if (inbox != null) add("import folder ${inbox.absolutePath}")
        }.joinToString("; ")
        AppLog.i("BookImport", message)
        if (isOrderedBroadcast) setResult(if (pick.files.isNotEmpty() && pick.refused.isEmpty()) Activity.RESULT_OK else 1, message, null)
    }
}

/** Nút trên thông báo ("Thử lại", "Thay bằng file này"): receiver riêng của app, không xuất ra ngoài. */
class ImportActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != BookImports.ACTION_RETRY) return
        val source = intent.getStringExtra("source") ?: return
        BookImports.start(context, source, intent.getStringExtra("name").orEmpty(), intent.getBooleanExtra("owned", false), intent.getBooleanExtra("allowOlder", false))
    }
}
