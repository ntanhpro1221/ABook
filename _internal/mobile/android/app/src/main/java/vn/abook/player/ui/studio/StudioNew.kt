package vn.abook.player.ui.studio

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.StudioError
import vn.abook.player.StudioErrors
import vn.abook.player.formatSize
import vn.abook.player.readaloud.WebSocket
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.data.Fmt
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.util.Calendar
import java.util.Locale

// "Sách mới" trên máy tính (NATIVE_REMOTE_STUDIO.md §6.12). Port từ NewProjectScreen.tsx / upload.ts: điện thoại không đưa được đường dẫn nào trên máy tính, nên gửi từng file nguồn
// lên (POST /api/sources/upload, thân JSON base64 ghi thẳng ra kết nối), máy tính quét ra chương (POST /api/scan), rồi POST /api/books. Ba bước: Nguồn, Chương, Bắt đầu.
// Không bao giờ sửa chữ của truyện: dòng ghi công chỉ được máy gợi ý ở web, ở đây không áp dòng nào.

/** Một file người dùng đã chọn: tên, cỡ và cách mở luồng đọc (mở khi gửi, không giữ file trong bộ nhớ). */
class PickedFile(val name: String, val size: Long, val open: () -> InputStream)

enum class UploadStatus { Waiting, Sending, Sent, Failed, TooBig, NotStory }

/** Một hàng ở bước Nguồn. `path` là tham chiếu máy tính trả về sau khi gửi xong; phần đã gửi của file đang gửi nằm ở [StudioNewState.progressOf]. */
@Immutable
data class SourceRow(
    val id: Int,
    val name: String,
    val size: Long,
    val status: UploadStatus,
    val path: String = "",
    val problem: String = "",
)

enum class NewStep(val label: String) {
    Source("Nguồn"),
    Chapters("Chương"),
    Start("Bắt đầu"),
}

/** Phản hồi `POST /api/sources/upload`: thư mục và tham chiếu của file vừa tới máy tính. */
@Immutable
data class UploadedSource(val folder: String, val path: String)

@Immutable
data class ScannedChapter(
    val path: String,
    val name: String,
    val title: String,
    val firstLine: String,
    val words: Int,
    val audioSeconds: Double,
    /** Trang phụ của file sách (bìa, bản quyền, mục lục): lý do; rỗng = chương thường. Mặc định chưa vào sách. */
    val matter: String,
    /** File chứa nhiều tiêu đề "Chương N" (cả truyện trong một file): số chương máy thấy; 0 = không. Máy đề xuất tách, không tự tách. */
    val splitChapters: Int,
    val estimated: Boolean,
)

@Immutable
data class ExistingBook(val id: String, val title: String, val statusLabel: String)

@Immutable
data class ScanView(
    val files: List<ScannedChapter>,
    val errors: List<String>,
    val notes: List<String>,
    val missing: List<String>,
    val suggestedTitle: String,
    val existing: List<ExistingBook>,
)

/** `POST /api/first-person`: truyện kể ngôi thứ nhất không, và vài tên gợi ý (không phải đáp án). */
@Immutable
data class FirstPersonView(val firstPerson: Boolean, val rate: Double, val suggestions: List<String>, val chaptersSampled: Int = 0, val chaptersWithI: Int = 0)

@Immutable
data class AnalysisModel(val name: String, val size: Long, val parameters: String)

@Immutable
data class AnalysisModels(val default: String, val models: List<AnalysisModel>, val reachable: Boolean) {
    /** Các bản khác mặc định - chỉ khi có bản khác mới có gì để chọn. */
    val others: List<AnalysisModel> get() = if (reachable) models.filter { it.name != default } else emptyList()
}

/** `POST /api/books`: mã sách mới và chỗ trong hàng chờ khi bắt đầu ngay mà máy đang bận. */
@Immutable
data class CreatedBook(val id: String, val queued: Int?)

/** Ba mức chất lượng (web `PROFILES`): `key` là giá trị `profile` gửi máy tính. */
enum class NewProfile(override val key: String, override val label: String, val summary: String) : Choice {
    Fast("fast", "Nhanh", "Nghe thử một truyện mới, hoặc cần gấp."),
    Balanced("balanced", "Cân bằng", "Nghe hằng ngày, chấp nhận vài câu chưa hoàn hảo."),
    High("high_quality", "Chất lượng cao", "Sách nghe lại nhiều lần hoặc để chia sẻ."),
}

internal object StudioNewJson {
    fun uploaded(json: JSONObject) = UploadedSource(json.text("folder"), json.text("path"))

    fun scan(json: JSONObject): ScanView = ScanView(
        files = json.optJSONArray("files").objects().map { file ->
            ScannedChapter(
                path = file.getString("path"),
                name = file.text("name"),
                title = file.text("title"),
                firstLine = file.text("firstLine"),
                words = file.optInt("words"),
                audioSeconds = file.optDouble("audioSeconds", 0.0).let { if (it.isFinite()) it else 0.0 },
                matter = file.text("matter"),
                splitChapters = file.optJSONObject("split")?.optInt("chapters") ?: 0,
                estimated = file.optBoolean("estimated"),
            )
        },
        errors = json.optJSONArray("errors").strings(),
        notes = json.optJSONArray("notes").strings(),
        missing = json.optJSONArray("missing").strings(),
        suggestedTitle = json.text("suggestedTitle"),
        existing = json.optJSONArray("existing").objects().map { ExistingBook(it.text("id"), it.text("title"), it.text("statusLabel")) },
    )

    fun firstPerson(json: JSONObject) = FirstPersonView(json.optBoolean("firstPerson"), json.optDouble("rate", 0.0), json.optJSONArray("suggestions").strings(), json.optInt("chaptersSampled"), json.optInt("chaptersWithI"))

    fun models(json: JSONObject) = AnalysisModels(
        default = json.text("default"),
        models = json.optJSONArray("models").objects().map { AnalysisModel(it.text("name"), it.optLong("size"), it.text("parameters")) },
        reachable = json.optBoolean("reachable"),
    )

    fun created(json: JSONObject) = CreatedBook(json.getString("id"), json.optInt("queued", 0).takeIf { !json.isNull("queued") && it > 0 })

    /** `/api/sources/split` → thư mục chương vừa tách. */
    fun folder(json: JSONObject): String = json.getString("folder")
}

/**
 * Thân JSON của `POST /api/sources/upload` ghi từng khúc: `{"folder":...,"name":...,"data":"<base64>"}`. Không dựng cả chuỗi trong bộ nhớ (file tới ~17 MiB, base64 hơn 23 MiB);
 * khúc đọc là bội của 3 byte nên các khúc base64 nối lại đúng, chỉ khúc cuối có đệm `=`.
 */
object StudioUpload {
    private const val CHUNK = 48 * 1024

    fun writer(folder: String, name: String, input: InputStream): (OutputStream) -> Unit = { out ->
        out.write("""{"folder":${JSONObject.quote(folder)},"name":${JSONObject.quote(name)},"data":"""".toByteArray(Charsets.UTF_8))
        input.use { source ->
            val buffer = ByteArray(CHUNK)
            while (true) {
                var filled = 0
                while (filled < CHUNK) {
                    val read = source.read(buffer, filled, CHUNK - filled)
                    if (read < 0) break
                    filled += read
                }
                if (filled == 0) break
                out.write(WebSocket.base64(if (filled == CHUNK) buffer else buffer.copyOf(filled)).toByteArray(Charsets.US_ASCII))
                if (filled < CHUNK) break
            }
        }
        out.write("\"}".toByteArray(Charsets.US_ASCII))
    }
}

object StudioNewLogic {
    /**
     * Cỡ lớn nhất của MỘT file gửi qua mạng: cổng của máy tính nhận thân JSON tới 24 MiB, base64 nở ra 4/3, trừ tên và khung - còn ~17 MiB file gốc. Trang web nói 40 MB nhưng
     * file lớn hơn mốc này không tới nơi (NATIVE_REMOTE_STUDIO.md 1.5, 13.1). Nói trước, không để hỏng giữa chừng.
     */
    const val UPLOAD_LIMIT = 17L * 1024 * 1024

    private val ACCEPTED = Regex(".+\\.(txt|epub|docx|pdf)", RegexOption.IGNORE_CASE)

    /** Có phải file truyện (.txt, .epub, .docx, .pdf) - hộp chọn file của Android không lọc theo đuôi được. */
    fun accepted(name: String): Boolean = ACCEPTED.matches(name)

    /** "Tải lên 05-10-2026 18h22 ab12": mỗi lần gửi một thư mục riêng (web `batchName`). */
    fun batchName(now: Calendar, tag: String): String = String.format(
        Locale.ROOT, "Tải lên %02d-%02d-%d %02dh%02d %s",
        now.get(Calendar.DAY_OF_MONTH), now.get(Calendar.MONTH) + 1, now.get(Calendar.YEAR), now.get(Calendar.HOUR_OF_DAY), now.get(Calendar.MINUTE), tag,
    )

    /** Hai file cùng tên trong một lần gửi sẽ đè nhau: file sau thêm " (2)" trước đuôi. */
    fun uniqueName(name: String, taken: Collection<String>): String {
        if (name !in taken) return name
        val dot = name.lastIndexOf('.').takeIf { it > 0 } ?: name.length
        var number = 2
        while ("${name.substring(0, dot)} ($number)${name.substring(dot)}" in taken) number++
        return "${name.substring(0, dot)} ($number)${name.substring(dot)}"
    }

    /** Trạng thái ban đầu của một file vừa chọn: lớn quá hoặc không phải file truyện thì không bao giờ gửi. */
    fun initial(name: String, size: Long): UploadStatus = when {
        !accepted(name) -> UploadStatus.NotStory
        size > UPLOAD_LIMIT -> UploadStatus.TooBig
        else -> UploadStatus.Waiting
    }

    /** "Tên được chọn, nhưng lớn hơn 17 MB..." - lời nói với người nghe, theo trạng thái. */
    fun problem(status: UploadStatus, name: String, size: Long): String = when (status) {
        UploadStatus.TooBig -> StudioNewText.tooBig(name, size)
        UploadStatus.NotStory -> StudioNewText.notStory(name)
        else -> ""
    }

    /** Có đi tiếp từ bước Nguồn được: đã có file nào tới nơi và không file nào đang gửi hay chờ gửi. */
    fun canScan(rows: List<SourceRow>): Boolean =
        rows.any { it.status == UploadStatus.Sent } && rows.none { it.status == UploadStatus.Sending || it.status == UploadStatus.Waiting }

    /** Đường nguồn đi vào lần quét: file đã tới nơi, theo thứ tự chọn. */
    fun paths(rows: List<SourceRow>): List<String> = rows.filter { it.status == UploadStatus.Sent && it.path.isNotEmpty() }.map { it.path }

    /** Chương vào sách: bỏ chương người dùng bỏ tay và trang phụ chưa tích lại. */
    fun kept(files: List<ScannedChapter>, excluded: Set<String>, keepMatter: Set<String>): List<ScannedChapter> =
        files.filter { it.path !in excluded && (it.matter.isEmpty() || it.path in keepMatter) }

    /** Số liệu của phần được giữ: chương, chữ, giờ nghe ước; "~" khi file dài chỉ đếm một phần. */
    fun totals(kept: List<ScannedChapter>): String {
        if (kept.isEmpty()) return StudioNewText.NO_CHAPTER
        val approx = if (kept.any { it.estimated }) "~" else ""
        val words = kept.sumOf { it.words.toLong() }
        val seconds = kept.sumOf { it.audioSeconds }
        return "${kept.size} chương · $approx${Fmt.number(words)} chữ · $approx${Fmt.length(seconds)} nghe"
    }

    /** Thân `POST /api/books` (web `useCreateBook`): giọng kể rỗng để máy chọn; mô hình rỗng = mặc định. */
    fun body(
        paths: List<String>, title: String, profile: NewProfile, firstPerson: String, model: String, wait: Boolean, startNow: Boolean,
    ): JSONObject = JSONObject().put("paths", JSONArray(paths)).put("title", title.trim()).put("profile", profile.key).put("narrator", "")
        .put("firstPerson", firstPerson.trim()).put("start", startNow).apply {
            if (model.isNotEmpty()) put("analysisModel", model)
            if (wait) put("precastWait", true)
        }

    /** Phần của thanh ba bước. */
    fun stepFraction(step: NewStep): Float = (step.ordinal + 1) / NewStep.entries.size.toFloat()

    fun canCreate(title: String, kept: List<ScannedChapter>, creating: Boolean): Boolean = !creating && title.isNotBlank() && kept.isNotEmpty()

    /** Chương có thể tách: file có nhiều tiêu đề "Chương N". */
    fun splittable(files: List<ScannedChapter>): List<ScannedChapter> = files.filter { it.splitChapters > 1 }
}

object StudioNewText {
    const val TITLE = "Sách mới"
    const val LEAD = "Chọn file truyện; máy tính đọc ra chương rồi làm sách nói."
    const val PICK = "Chọn tệp"
    const val PASTE = "Dán chữ"
    const val PASTE_HINT = "Dán chữ truyện vào đây"
    const val PASTE_ADD = "Thêm chữ này"
    const val NEXT = "Tiếp"
    const val BACK = "Quay lại"
    const val CANCEL = "Huỷ"
    const val RETRY = "Thử lại"
    const val REMOVE = "Bỏ"
    const val SCANNING = "Đang đọc nguồn"
    const val NO_CHAPTER = "Chưa có chương nào"
    const val NO_SOURCE = "Chưa có tệp nào"
    const val LIMIT_NOTE = "Mỗi tệp tối đa 17 MB. Tệp lớn hơn thì chép vào máy tính rồi tạo sách ở đó."
    const val SENT = "Đã gửi"
    const val WAITING = "Đang chờ"
    const val CHAPTERS_LEAD = "Bỏ chương không muốn đọc. Tên chương sửa sau ở trang dự án."
    const val MATTER = "Trang phụ - chưa vào sách"
    const val SPLIT_TITLE = "Tách chương"
    const val SPLIT_NOTE = "File này gộp nhiều chương. Máy tính tách theo tiêu đề “Chương”; chữ không đổi."
    const val EXISTING = "Đã có dự án làm từ những file này"
    const val TITLE_LABEL = "Tên sách"
    const val FIRST_PERSON = "Kể bằng “tôi”"
    const val FIRST_PERSON_HINT = "Tên người xưng “tôi” giúp phân vai đúng lời thoại. Bỏ trống nếu truyện kể ngôi thứ ba."
    const val FIRST_PERSON_PLACEHOLDER = "Tên người kể"
    /** Dòng nhắc cuối bước Bắt đầu và lời gập "Vì sao?" của nó (web: StartNotes ở NewProjectScreen.tsx; phân tích không nên bị ngắt - AGENTS.md). Thiếu "Thời gian tham khảo": điện thoại chưa có số ước. */
    const val PAUSE_NOTE = "Đang phân tích mà cần nghỉ, hãy dùng Tạm dừng."
    const val PAUSE_WHY = "Đừng tắt máy, cho máy ngủ hoặc bấm Dừng trong lúc phân tích. Dừng hoặc nạp lại model có thể đổi phân vai và audio; bản cũ cần tạo dự án mới nếu bị ngắt. Tạm dừng quá 30 phút cũng có thể dỡ model. Sau phân tích, bạn có thể dừng và tiếp tục."
    const val QUALITY = "Chất lượng"
    const val MODEL = "Bộ phân tích truyện"
    const val MODEL_DEFAULT = "Mặc định của ABook"
    const val MODEL_HINT = "Chỉ chọn bản khác khi muốn thử trên cuốn này."
    const val WAIT = "Duyệt trước khi thu"
    const val WAIT_HINT = "Phân tích xong thì dừng để bạn duyệt trước khi thu."
    const val START_NOW = "Bắt đầu ngay"
    const val START_NOW_HINT = "Tắt thì sách chờ ở trang dự án."
    const val CREATE = "Bắt đầu"
    const val CREATING = "Đang tạo sách"
    const val CREATE_FAILED = "Chưa tạo được sách"

    /** Máy đoán người kể "tôi" (web: MoreInfo "Máy đoán" của NewProjectScreen.tsx). */
    fun firstPersonGuess(hint: FirstPersonView): String =
        (if (hint.firstPerson) {
            if (hint.chaptersSampled > 0 && hint.chaptersWithI > 0) "${hint.chaptersWithI}/${hint.chaptersSampled} chương đầu có lời kể xưng “tôi”."
            else "${Math.round(hint.rate * 100)}% đoạn lời kể có “tôi”."
        } else "Chọn nhân vật xưng “tôi” trong lời kể.") + " Bạn có thể sửa gợi ý này."

    fun tooBig(name: String, size: Long) = "$name (${formatSize(size)}) lớn hơn 17 MB nên không gửi qua mạng được. Chép tệp vào máy tính rồi tạo sách ở đó."
    fun notStory(name: String) = "$name không phải file truyện - chỉ nhận .txt, .epub, .docx, .pdf."
    fun stepOf(step: NewStep) = "Bước ${step.ordinal + 1}/${NewStep.entries.size}"
    fun sending(row: SourceRow) = "Đang gửi ${row.name}"
    fun percent(fraction: Float) = "${(fraction * 100).toInt().coerceIn(0, 100)}%"
    fun splitAsk(chapters: Int) = "Tách thành $chapters chương"
    fun uploadFailed(name: String, reason: String) = "Chưa gửi được $name. $reason".trim()
    fun queued(position: Int) = "Vào hàng chờ, còn ${position - 1} việc trước"
}

/**
 * Trình tạo sách ba bước. Gửi file chạy ở phạm vi của phiên (rời màn không cắt ngang giữa chừng một file), từng file một. Chưa có gì được tạo trên máy tính tới khi bấm "Bắt đầu":
 * gửi file chỉ đặt nguồn vào thư mục tải lên của thư viện.
 */
@Stable
class StudioNewState(
    val session: StudioSession,
    private val batch: String = StudioNewLogic.batchName(Calendar.getInstance(), java.lang.Long.toString(System.nanoTime() % 100_000, 36)),
) {
    var step by mutableStateOf(NewStep.Source)
        private set

    var rows by mutableStateOf<List<SourceRow>>(emptyList())
        private set

    var problem by mutableStateOf("")
        private set

    /** Đang quét / tách (chữ "Đang đọc nguồn"). */
    var scanning by mutableStateOf(false)
        private set

    var scan by mutableStateOf<ScanView?>(null)
        private set

    var excluded by mutableStateOf<Set<String>>(emptySet())
        private set

    var keepMatter by mutableStateOf<Set<String>>(emptySet())
        private set

    var title by mutableStateOf("")
        private set

    var firstPerson by mutableStateOf("")
        private set

    var hint by mutableStateOf<FirstPersonView?>(null)
        private set

    var models by mutableStateOf<AnalysisModels?>(null)
        private set

    var profile by mutableStateOf(NewProfile.High)
        private set

    var model by mutableStateOf("")
        private set

    var wait by mutableStateOf(false)
        private set

    var startNow by mutableStateOf(true)
        private set

    var creating by mutableStateOf(false)
        private set

    /** Sách vừa tạo: màn mở dự án rồi không dùng lại trạng thái này. */
    var created by mutableStateOf<CreatedBook?>(null)
        private set

    private var nextId = 0
    private var titleEdited = false
    private val files = HashMap<Int, PickedFile>()

    /** Hàng bấm Huỷ giữa lúc gửi: luồng gửi (ở luồng IO) đọc cờ này nên dùng tập an toàn giữa các luồng. */
    private val aborted: MutableSet<Int> = java.util.concurrent.ConcurrentHashMap.newKeySet()

    /** File đang gửi và số byte đã gửi: một luồng ghi (luồng gửi), nên đọc ở màn không cần khoá. */
    private var sendingId by mutableIntStateOf(-1)
    private var sendingBytes by mutableLongStateOf(0L)
    private var uploading: Job? = null

    /** Tham chiếu nguồn đi vào lần quét: file đã gửi, có thể thay bằng thư mục sau khi tách. */
    private var sources: List<String> = emptyList()
    private var scanned = false

    val kept: List<ScannedChapter> get() = scan?.let { StudioNewLogic.kept(it.files, excluded, keepMatter) }.orEmpty()

    val canScan: Boolean get() = StudioNewLogic.canScan(rows) && !scanning

    val canCreate: Boolean get() = StudioNewLogic.canCreate(title, kept, creating)

    // ---- bước Nguồn ----

    /** Thêm file đã chọn; mỗi file gửi lần lượt. */
    fun add(picked: List<PickedFile>) {
        if (picked.isEmpty()) return
        problem = ""
        val taken = rows.map { it.name }.toMutableList()
        val added = picked.map { file ->
            val name = StudioNewLogic.uniqueName(file.name, taken).also { taken += it }
            val status = StudioNewLogic.initial(name, file.size)
            val id = nextId++
            files[id] = PickedFile(name, file.size, file.open)
            SourceRow(id, name, file.size, status, problem = StudioNewLogic.problem(status, name, file.size))
        }
        rows = rows + added
        invalidateScan()
        pump()
    }

    /** Chữ dán vào: thành một file .txt như mọi file khác. */
    fun addText(text: String) {
        val bytes = text.trim().toByteArray(Charsets.UTF_8)
        if (bytes.isEmpty()) return
        add(listOf(PickedFile("Chữ dán.txt", bytes.size.toLong()) { bytes.inputStream() }))
    }

    /** Bỏ một hàng: đang gửi thì dừng giữa chừng (luồng đọc ngắt) rồi bỏ. */
    fun remove(id: Int) {
        val row = rows.firstOrNull { it.id == id } ?: return
        if (row.status == UploadStatus.Sending) aborted += id else drop(id)
        invalidateScan()
    }

    /** Gửi lại một file đã hỏng. */
    fun retry(id: Int) {
        rows = rows.map { if (it.id == id && it.status == UploadStatus.Failed) it.copy(status = UploadStatus.Waiting, problem = "") else it }
        pump()
    }

    private fun drop(id: Int) {
        rows = rows.filterNot { it.id == id }
        files.remove(id)
        aborted -= id
    }

    private fun update(id: Int, change: (SourceRow) -> SourceRow) {
        rows = rows.map { if (it.id == id) change(it) else it }
    }

    private fun pump() {
        if (uploading?.isActive == true) return
        uploading = session.scope.launch {
            while (true) {
                val row = rows.firstOrNull { it.status == UploadStatus.Waiting } ?: break
                send(row)
            }
        }
    }

    private suspend fun send(row: SourceRow) {
        val file = files[row.id] ?: return drop(row.id)
        update(row.id) { it.copy(status = UploadStatus.Sending, problem = "") }
        sendingBytes = 0
        sendingId = row.id
        try {
            val uploaded = session.source.uploadSource(session.computer, batch, row.name) {
                Counting(file.open(), { aborted.contains(row.id) }) { total -> sendingBytes = total }
            }
            if (aborted.contains(row.id)) drop(row.id) else update(row.id) { it.copy(status = UploadStatus.Sent, path = uploaded.path) }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            if (aborted.contains(row.id)) {
                drop(row.id)
                return
            }
            val failure = StudioErrors.of(error)
            session.note(failure)
            val status = if (failure is StudioError.TooBig) UploadStatus.TooBig else UploadStatus.Failed
            update(row.id) {
                it.copy(status = status, problem = if (failure is StudioError.TooBig) StudioNewText.tooBig(it.name, it.size) else StudioNewText.uploadFailed(it.name, StudioText.failure(failure)))
            }
        } finally {
            sendingId = -1
        }
    }

    /** Phần đã gửi của một hàng, 0..1. */
    fun progressOf(row: SourceRow): Float = when {
        row.status == UploadStatus.Sent -> 1f
        row.id == sendingId && row.size > 0 -> (sendingBytes.toFloat() / row.size).coerceIn(0f, 1f)
        else -> 0f
    }

    /** Đếm byte đã đọc (thanh tiến độ); ném IOException khi người dùng bấm Huỷ giữa chừng. */
    private class Counting(private val inner: InputStream, private val stop: () -> Boolean, private val onTotal: (Long) -> Unit) : InputStream() {
        private var total = 0L

        override fun read(): Int {
            val value = inner.read()
            if (value >= 0) count(1)
            return value
        }

        override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
            val read = inner.read(buffer, offset, length)
            if (read > 0) count(read)
            return read
        }

        private fun count(read: Int) {
            if (stop()) throw IOException("Đã huỷ")
            total += read
            onTotal(total)
        }

        override fun close() = inner.close()
    }

    private fun invalidateScan() {
        scanned = false
        if (step != NewStep.Source) step = NewStep.Source
    }

    // ---- bước Chương ----

    /** "Tiếp" ở bước Nguồn: máy tính quét các file đã gửi. */
    fun next() {
        when (step) {
            NewStep.Source -> if (canScan) {
                if (!scanned) {
                    sources = StudioNewLogic.paths(rows)
                    runScan { step = NewStep.Chapters }
                } else {
                    step = NewStep.Chapters
                }
            }
            NewStep.Chapters -> if (kept.isNotEmpty()) {
                step = NewStep.Start
                loadChoices()
            }
            NewStep.Start -> Unit
        }
    }

    fun back() {
        step = when (step) {
            NewStep.Source, NewStep.Chapters -> NewStep.Source
            NewStep.Start -> NewStep.Chapters
        }
    }

    private fun runScan(after: () -> Unit) {
        if (scanning) return
        scanning = true
        problem = ""
        session.scope.launch {
            try {
                val result = session.source.scan(session.computer, sources)
                scan = result
                scanned = true
                excluded = emptySet()
                keepMatter = emptySet()
                if (!titleEdited || title.isBlank()) title = result.suggestedTitle
                if (result.files.isEmpty()) {
                    problem = (result.errors + result.notes).firstOrNull() ?: StudioNewText.NO_CHAPTER
                } else {
                    after()
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                problem = StudioText.failure(failure)
            } finally {
                scanning = false
            }
        }
    }

    fun toggle(path: String) {
        val matter = scan?.files?.firstOrNull { it.path == path }?.matter.orEmpty().isNotEmpty()
        if (matter) {
            keepMatter = if (path in keepMatter) keepMatter - path else keepMatter + path
        } else {
            excluded = if (path in excluded) excluded - path else excluded + path
        }
    }

    /** Có đang giữ chương này (vào sách) không. */
    fun isKept(chapter: ScannedChapter): Boolean = chapter in kept

    /** "Tách chương": máy tính tách file gộp ra thư mục chương, rồi quét lại với thư mục ấy thay cho file. */
    fun split(chapter: ScannedChapter) {
        if (scanning || chapter.splitChapters < 2) return
        scanning = true
        problem = ""
        session.scope.launch {
            try {
                val folder = session.source.splitSource(session.computer, chapter.path, title.ifBlank { scan?.suggestedTitle.orEmpty() })
                sources = sources.map { if (it == chapter.path) folder else it }
                scanning = false
                runScan {}
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                problem = StudioText.failure(failure)
                scanning = false
            }
        }
    }

    // ---- bước Bắt đầu ----

    private fun loadChoices() {
        val paths = kept.map { it.path }
        if (hint == null) {
            session.scope.launch {
                try {
                    hint = session.source.firstPerson(session.computer, paths)
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (error: Throwable) {
                    // Chỉ là gợi ý: hỏng thì bỏ qua, người dùng vẫn gõ tên được.
                }
            }
        }
        if (models == null) {
            session.scope.launch {
                try {
                    models = session.source.analysisModels(session.computer)
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (error: Throwable) {
                    // Không hỏi được = dùng mặc định.
                }
            }
        }
    }

    fun editTitle(value: String) {
        title = value
        titleEdited = true
    }

    fun editFirstPerson(value: String) {
        firstPerson = value
    }

    fun pickProfile(value: NewProfile) {
        profile = value
    }

    fun pickModel(value: String) {
        model = value
    }

    fun chooseWait(value: Boolean) {
        wait = value
    }

    fun chooseStartNow(value: Boolean) {
        startNow = value
    }

    /** "Bắt đầu": máy tính tạo sách (và xếp hàng chạy nếu bật "Bắt đầu ngay"), rồi màn mở dự án. */
    fun create() {
        if (!canCreate) return
        creating = true
        problem = ""
        val body = StudioNewLogic.body(kept.map { it.path }, title, profile, firstPerson, model, wait, startNow)
        session.scope.launch {
            try {
                created = session.source.createBook(session.computer, body)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                problem = StudioText.failure(failure)
            } finally {
                creating = false
            }
        }
    }
}
