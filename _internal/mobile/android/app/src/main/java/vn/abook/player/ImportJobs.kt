package vn.abook.player

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onEach
import java.io.File

enum class ImportJobState { Running, Done, Failed }

/**
 * Một lượt nhập file sách (.abook / .abookproj) chạy nền ([BookImportWorker]). `source`: địa chỉ file (content:// của bộ chọn file hay "Mở bằng",
 * file:// của thư mục nhập). `owned`: file nằm trong thư mục nhập của chính app ([ImportInbox]) - nhập xong thì xoá; file người dùng chọn không bao giờ bị xoá.
 * `how` như [BookFileImport.Imported.how]: "new", "updated", "existing", hay "older" / "conflict" (chưa thay gì, chờ người dùng chọn).
 */
data class ImportJob(
    val id: String, val source: String, val name: String,
    val owned: Boolean = false, val allowOlder: Boolean = false,
    val state: ImportJobState = ImportJobState.Running, val work: Work = Work(WorkStep.Read),
    val bookId: String? = null, val title: String = "", val how: String = "", val incomingTitle: String = "", val problem: String = "",
) {
    /** Sách trong máy khác / mới hơn bản trong file: lượt kết thúc mà chưa thay gì. */
    val needsChoice: Boolean get() = state == ImportJobState.Done && how in CHOICES

    companion object {
        val CHOICES = setOf("older", "conflict")
    }
}

/** Kết quả của bước nhập (lõi [BookFileImport]), tách khỏi Android để bài thử JVM giả được. */
data class ImportOutcome(val bookId: String, val title: String, val how: String, val incomingTitle: String = "")

/** A scheduler stop leaves the input available for WorkManager to replay the same request. */
internal class ImportStopped : RuntimeException()

/**
 * Trạng thái mọi lượt nhập nền của tiến trình: MỘT nguồn, mọi người xem (màn "Thêm sách", thông báo) đọc cùng nó. Việc nhập không gắn với Activity hay
 * ViewModel nào: rời app, đóng màn, Activity dựng lại đều không làm mất lượt. `now` (ms) cho test JVM đặt đồng hồ giả của bộ thưa lời báo.
 */
class ImportJobs(private val now: () -> Long = { System.nanoTime() / 1_000_000 }) {
    private val flow = MutableStateFlow<Map<String, ImportJob>>(emptyMap())
    val jobs: StateFlow<Map<String, ImportJob>> = flow

    operator fun get(id: String): ImportJob? = flow.value[id]

    /** Lượt đang chạy của cùng file: bấm / gửi lại một file đang nhập thì dùng lượt ấy, không nhập hai lần. */
    @Synchronized
    fun running(source: String): ImportJob? = flow.value.values.firstOrNull { it.source == source && it.state == ImportJobState.Running }

    /** Ghi một lượt mới (hay chạy lại) ở trạng thái đang chạy. Giữ tối đa [KEEP] lượt đã xong gần nhất. */
    @Synchronized
    fun begin(job: ImportJob) {
        val fresh = job.copy(state = ImportJobState.Running, work = Work(WorkStep.Read), problem = "")
        val ended = flow.value.values.filter { it.state != ImportJobState.Running && it.id != job.id }
        val drop = ended.take(maxOf(0, ended.size - KEEP)).map { it.id }.toSet()
        flow.value = flow.value.filterKeys { it != job.id && it !in drop } + (job.id to fresh)
    }

    @Synchronized
    private fun update(id: String, change: (ImportJob) -> ImportJob) {
        val job = flow.value[id] ?: return
        flow.value = flow.value + (id to change(job))
    }

    fun report(id: String, work: Work) = update(id) { if (it.state == ImportJobState.Running) it.copy(work = work) else it }

    fun finish(id: String, outcome: ImportOutcome) = update(id) {
        it.copy(state = ImportJobState.Done, work = Work(it.work.step, 1, 1), bookId = outcome.bookId, title = outcome.title, how = outcome.how,
            incomingTitle = outcome.incomingTitle)
    }

    fun fail(id: String, problem: String) = update(id) { it.copy(state = ImportJobState.Failed, problem = problem) }

    /** Chờ lượt `id` kết thúc, chuyển từng lời báo tiến độ cho `progress`. Lượt không còn trong sổ thì trả null. */
    suspend fun await(id: String, progress: WorkSink = {}): ImportJob? =
        flow.map { it[id] }.onEach { job -> job?.let { progress(it.work) } }.first { it == null || it.state != ImportJobState.Running }

    /**
     * Thân của một lượt ([BookImportWorker] gọi ở luồng nền): ghi lượt nếu tiến trình mới chưa biết nó, nhập qua `importer` (lời báo thưa còn 10 lần/giây,
     * `shown` nhận cùng lời báo cho thông báo), rồi xong / lỗi. File của thư mục nhập (`owned`) chỉ bị xoá ([discard]) khi sách đã vào thư viện; lỗi hay
     * cần người dùng chọn thì giữ file để thử lại.
     */
    fun run(job: ImportJob, importer: (WorkSink) -> ImportOutcome, discard: () -> Unit, shown: WorkSink = {}): ImportJob {
        if (flow.value[job.id]?.state != ImportJobState.Running) begin(job)
        val sink = WorkThrottle({ work -> report(job.id, work); shown(work) }, now = now)
        try {
            val outcome = importer(sink)
            finish(job.id, outcome)
            if (job.owned && outcome.how !in ImportJob.CHOICES) runCatching(discard)
        } catch (stopped: ImportStopped) {
            throw stopped
        } catch (error: Exception) {
            fail(job.id, error.message?.takeIf { it.isNotBlank() } ?: error.javaClass.simpleName)
        }
        return flow.value.getValue(job.id)
    }

    companion object {
        const val KEEP = 20
    }
}

/**
 * Thư mục nhập của app (`<thư mục file ngoài của app>/import`, vd /sdcard/Android/data/com.ngdtuanh.abook/files/import): `adb push` file sách vào đây rồi
 * gửi lệnh nhập ngầm ([ImportReceiver]). Chỉ nhận file .abook / .abookproj nằm NGAY trong thư mục ấy: đường dẫn ngoài, `..`, liên kết mềm đều bị từ chối.
 * Lời từ chối bằng tiếng Anh vì chỉ người dùng adb đọc (kết quả của `am broadcast`).
 */
object ImportInbox {
    const val FOLDER = "import"

    fun isBookName(name: String): Boolean = name.endsWith(".abook", true) || name.endsWith(".abookproj", true)

    data class Pick(val files: List<File>, val refused: List<String>)

    /** `path` null / trống: mọi file sách trong thư mục nhập, theo tên. Có `path`: đúng file ấy nếu hợp lệ. */
    fun resolve(inbox: File, path: String?): Pick {
        val root = runCatching { inbox.canonicalFile }.getOrNull() ?: return Pick(emptyList(), listOf("import folder unavailable"))
        if (path.isNullOrBlank()) {
            val files = root.listFiles().orEmpty().filter { refusal(root, it) == null }.sortedBy { it.name }
            return Pick(files, emptyList())
        }
        val file = File(path)
        val problem = refusal(root, file)
        return if (problem == null) Pick(listOf(file.canonicalFile), emptyList()) else Pick(emptyList(), listOf("$path: $problem"))
    }

    /** null khi `file` là một file sách thật nằm ngay trong `root` (đã chuẩn hoá); không thì lý do từ chối. */
    fun refusal(root: File, file: File): String? {
        if (!file.isAbsolute) return "not an absolute path"
        if (file.path.split('/', '\\').any { it == ".." }) return "outside the import folder"
        val real = runCatching { file.canonicalFile }.getOrNull() ?: return "unreadable path"
        // Resolve the parent first: /sdcard is an Android alias, while a changed final component is a file symlink.
        val leaf = runCatching { File(file.parentFile.canonicalFile, file.name) }.getOrNull() ?: return "unreadable path"
        if (real != leaf) return "symbolic link"
        if (real.parentFile != root) return "outside the import folder"
        if (!isBookName(real.name)) return "not a .abook or .abookproj file"
        if (!real.isFile) return "not a regular file"
        return null
    }
}
