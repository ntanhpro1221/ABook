package vn.abook.player

import org.json.JSONObject
import vn.abook.player.PinnedFiles.Part
import java.io.File
import java.io.IOException

/**
 * "Gói nhạc" của điện thoại - mọi thứ bộ phân tích nhạc ([MusicStudent]) cần mà APK không mang: model (~59 MB) cùng thư viện chạy ONNX
 * Runtime của đúng ABI máy này ([OrtRuntime], ~12 MB nén). Tải MỘT lần khi người dùng bấm, một thanh tiến độ, một tổng dung lượng; KHÔNG
 * đóng sẵn trong APK và KHÔNG tự tải (kể cả khi đang dùng dữ liệu di động - giao diện nói rõ tổng dung lượng trước khi bấm). Cùng gói và cùng cách ghim với máy tính
 * (`music_student.py`: REPO_ID, REVISION là một commit, SHA-256 + cỡ từng file; HTTPS thuần): `.part` rồi kiểm cỡ + băm rồi mới
 * đổi tên, nên file có tên thật trong thư mục gói luôn đã được kiểm. Tải dở thì lần sau (Range) tải tiếp, không tải lại từ đầu.
 *
 * Tải xong: cắm bộ phân tích vào [MusicStore.analyzer] rồi phân tích nốt các bài đã nhập trước đó ([MusicStore.analyzePending]).
 * Việc nặng luôn ở luồng nền riêng; không bao giờ chặn việc nhập.
 *
 * Thư viện ONNX Runtime (file `ort/...` trong [files]) không nằm trong [dir] mà ở thư mục dùng chung với các giọng đọc ([SharedRuntime]): giọng
 * nào tải trước thì gói nhạc thấy sẵn, không tính và không tải lại; gói hỏng bị xoá thì thư viện chỉ đi khi không mô-đun nào đang cài cần nó.
 */
class MusicStudentSetup(
    private val dir: File,
    private val store: MusicStore,
    /** Thư mục gói đã đủ file -> bộ phân tích (nhẹ: chưa nạp tháp). Ném lỗi nếu gói hỏng. */
    private val open: (File) -> ((File) -> JSONObject?),
    /** Thư mục thư viện chạy model dùng chung với các giọng đọc. */
    private val runtime: SharedRuntime,
    private val base: String = BASE,
    /** File của gói: model (vào [dir]) và thư viện ONNX Runtime (`ort/...`, vào thư mục dùng chung). */
    files: List<Part> = PACKAGE,
    /** Máy này có thư viện ONNX Runtime để tải không (ABI lạ như x86 32-bit thì không: gói không chạy được, đừng mời tải). */
    private val supported: Boolean = true,
    /** Máy đang dùng mạng tính phí (dữ liệu di động)? Chỉ để giao diện nhắc, không chặn. */
    private val metered: () -> Boolean = { false },
) {
    private val lock = Any()
    @Volatile
    private var state = MISSING
    private var error = ""
    private var cancelled = false // lần tải vừa rồi bị người dùng huỷ ("Đã huỷ - lần tải sau làm tiếp từ chỗ dừng"); xoá khi tải lại
    @Volatile
    private var cancelRequested = false
    private var finished = 0L // byte đã xong của các file đang phải tải
    private var current = 0L // đã tải của file đang tải
    private var todoTotal = 0L // tổng byte của các file lần tải này phải lấy
    private var analysing = false
    private var worker: Thread? = null
    private val pinned = PinnedFiles(dir, base)
    private val own = files.filter { it.name.substringBefore('/') !in SharedRuntime.PARTS }
    private val libs = files - own.toSet()
    private val shared = runtime.pinnedFrom(base)

    /** Mã nhận dạng model của gói này (băm các SHA-256 ghim của file model): bài phân tích bằng model khác thì là bài "cũ" cần phân tích lại. */
    val modelId: String = sha256Of(files.filter { !it.blocking }.joinToString("\n") { it.name + " " + it.sha256 }.toByteArray()).take(12)

    init {
        store.analyzerId = modelId
    }

    /** Mọi file có mặt với đúng cỡ đã ghim (dùng được, kể cả khi đã có bản mới hơn: bản cũ vẫn chạy cho tới khi người dùng cập nhật). */
    fun complete(): Boolean = supported && own.all { it.name in OPTIONAL || pinned.present(it) } && libs.all { shared.present(it) }

    /** Các file mà bản app này ghim khác (hay chưa có) so với gói đã tải. Rỗng nếu chưa tải gói nào (khi ấy là "chưa có", không phải "cũ"). */
    fun outdatedParts(): List<Part> =
        if (pinned.readStamp().isEmpty()) emptyList() else pinned.outdated(own) + libs.filter { !shared.isCurrent(it) }

    /** Các file chưa có bản đúng ghim - lần tải tới phải lấy (thư viện đã có ở thư mục dùng chung thì không). */
    private fun todo(): List<Part> = own.filter { !pinned.isCurrent(it) } + libs.filter { !shared.isCurrent(it) }

    /** Số byte phải tải qua mạng cho [parts]. */
    private fun wireBytes(parts: List<Part>) = parts.sumOf { it.wireSize }

    /** Trạng thái cho giao diện: `state` missing / downloading / ready / outdated / error. */
    fun status(): JSONObject = synchronized(lock) {
        val behind = if (state == DOWNLOADING || !supported) emptyList() else outdatedParts()
        val shown = if (behind.isNotEmpty() && (state == MISSING || state == READY)) OUTDATED else state
        // chưa có / lỗi: phần máy này còn thiếu (thư viện đã ở thư mục dùng chung thì không tính); đã xong: đúng lần tải vừa rồi
        val needed = when {
            state == DOWNLOADING -> todoTotal
            shown == OUTDATED -> wireBytes(behind)
            state == READY -> todoTotal
            else -> wireBytes(todo())
        }
        JSONObject().put("state", shown).put("done", finished + current).put("total", needed).put("error", error)
            .put("ready", state == READY).put("analysing", analysing).put("cancelled", cancelled).put("cancellable", true)
            .put("metered", runCatching { metered() }.getOrDefault(false)).put("supported", supported)
            .put("outdatedParts", org.json.JSONArray(behind.map { it.label }.distinct())).put("outdatedBytes", wireBytes(behind))
            .put("stale", store.staleCount())
            // có bản mới mà bản trên máy KHÔNG chạy được (thiếu / cũ thư viện chạy model, vd. gói tải trước khi có thư mục dùng chung): phân tích
            // nhạc đang tắt cho tới khi tải lại - giao diện không được nói "bản đang dùng vẫn chạy"
            .put("stopped", shown == OUTDATED && state != READY && !runnable())
    }

    /** Gói trên đĩa chạy được ngay: đủ file (ở thư mục riêng và thư mục dùng chung) và không thư viện nào cũ hơn phần Java trong APK. */
    private fun runnable(): Boolean =
        complete() && own.none { it.blocking && !pinned.isCurrent(it) } && libs.none { it.blocking && !shared.isCurrent(it) }

    /**
     * Gói đã có sẵn (lần chạy trước tải xong) thì cắm luôn và phân tích nốt bài chưa phân tích; chưa có thì không làm gì (không tải).
     * Gói cũ hơn ghim của app vẫn cắm (bản cũ chạy tốt) trừ thư viện ONNX Runtime: nó phải khớp phần Java trong APK nên cũ thì chờ cập nhật.
     * Gọi ở luồng nền. Trả true khi bộ phân tích đã cắm.
     */
    fun attachIfPresent(): Boolean {
        if (!runnable()) return false
        if (!attach()) return false
        analysePending()
        return true
    }

    /** Bắt đầu (hay tải tiếp) việc tải gói, hay cập nhật chỉ những file ghim đã đổi. Đang tải hay đã mới nhất thì không làm gì. */
    fun start() {
        synchronized(lock) {
            if (state == DOWNLOADING) return
            if (!supported) {
                fail("Điện thoại này chưa chạy được bộ phân tích nhạc.")
                return
            }
            if (state == READY && outdatedParts().isEmpty()) return
            state = DOWNLOADING
            error = ""
            cancelled = false
            cancelRequested = false
            finished = 0
            current = 0
            todoTotal = wireBytes(todo())
            // giữ chỗ thư viện trong lúc tải: một giọng bị gỡ giữa chừng không được xoá thứ gói này sắp dùng
            runtime.claim(KEY, SharedRuntime.runtimeOf(libs.map { it.name.substringBefore('/') }))
            worker = Thread({ download() }, "abook-music-student").apply {
                isDaemon = true
                priority = Thread.MIN_PRIORITY
                start()
            }
        }
    }

    /** Người dùng bấm Huỷ khi đang tải: dừng ở nhịp đọc kế của file đang tải, `.part` ở lại để lần tải sau làm tiếp (Range); trạng thái về "chưa tải"
     *  (hay "có bản mới") kèm `cancelled`. Không có lần tải nào thì không làm gì. Không lấy khoá: luồng tải có thể đang giữ nó. */
    fun cancel() {
        if (state == DOWNLOADING) cancelRequested = true
    }

    /** Chờ luồng tải/phân tích xong (cho test). */
    fun join(millis: Long = 60_000) {
        worker?.join(millis)
    }

    private fun download() {
        try {
            val progress = object : PinnedFiles.Progress {
                override fun current(bytes: Long) = synchronized(lock) { current = bytes }
                override fun done(part: Part) = synchronized(lock) {
                    finished += part.wireSize
                    current = 0
                }
                override fun cancelled() = cancelRequested
            }
            // một giọng đọc có thể đang tải cùng thư viện: lần lượt, người sau thấy sẵn
            if (libs.isNotEmpty()) synchronized(runtime.fetching) { shared.download(libs, progress) }
            // bản trong thư mục riêng của gói (chỗ các bản trước đặt) không còn được đọc
            libs.map { it.name.substringBefore('/') }.distinct().forEach { File(dir, it).deleteRecursively() }
            pinned.download(own, progress)
        } catch (_: PinnedFiles.Cancelled) {
            synchronized(lock) {
                state = if (store.analyzer != null) READY else MISSING // bản cũ vẫn chạy thì vẫn "sẵn sàng" (có bản mới)
                error = ""
                cancelled = true
                finished = 0
                current = 0
            }
            return
        } catch (failure: Exception) {
            fail(describe(failure))
            return
        } finally {
            runtime.done(KEY) // từ đây file model trên đĩa nói gói này cần gì
        }
        if (!attach()) return
        analysePending()
    }

    private fun attach(): Boolean {
        return try {
            store.analyzer = open(dir)
            store.analyzerId = modelId
            synchronized(lock) {
                state = READY
                error = ""
            }
            true
        } catch (failure: Exception) {
            // gói đủ file mà không dùng được (cấu hình lạ, đầu hỏng): xoá để lần bấm sau tải lại sạch; thư viện dùng chung chỉ đi khi không ai cần
            pinned.wipe(own)
            runtime.release(libs.groupBy { it.name.substringBefore('/') })
            fail("Bộ phân tích tải về không dùng được (${failure.message ?: failure.javaClass.simpleName}) - bấm Thử lại để tải lại.")
            false
        }
    }

    /** Phân tích lại mọi bài đã phân tích bằng bản model cũ (người dùng bấm "Phân tích lại N bài bằng bản mới"), ở luồng nền. Không bao giờ tự chạy. */
    fun reanalyse() {
        synchronized(lock) {
            if (analysing || state == DOWNLOADING) return
            analysing = true
        }
        worker = Thread({
            try {
                store.reanalyseStale()
            } catch (_: Exception) {
            } finally {
                synchronized(lock) { analysing = false }
            }
        }, "abook-music-reanalyse").apply {
            isDaemon = true
            priority = Thread.MIN_PRIORITY
            start()
        }
    }

    private fun analysePending() {
        synchronized(lock) { analysing = true }
        try {
            store.analyzePending()
        } catch (_: Exception) {
        } finally {
            synchronized(lock) { analysing = false }
        }
    }

    private fun fail(message: String) = synchronized(lock) {
        state = ERROR
        error = message
        current = 0
    }

    private fun describe(failure: Exception): String = when (failure) {
        is PinnedFiles.ChecksumError -> "Bộ phân tích tải về bị hỏng (không khớp mã kiểm) - bấm Thử lại để tải lại."
        is IOException -> "Không tải được bộ phân tích nhạc (${failure.message ?: "mất kết nối"}). Bấm Thử lại - phần đã tải được giữ."
        else -> "Không tải được bộ phân tích nhạc (${failure.message ?: failure.javaClass.simpleName})."
    }

    companion object {
        private const val MISSING = "missing"
        private const val DOWNLOADING = "downloading"
        private const val READY = "ready"
        private const val OUTDATED = "outdated"
        private const val ERROR = "error"
        const val STAMP = PinnedFiles.STAMP
        /** Thư mục riêng của gói trong `files/` của app. */
        const val FOLDER = "music/student"
        private const val KEY = "music"

        // Ghim đúng như webui/music_student.py (REPO_ID, REVISION, PACKAGE_FILES["onnx"], PACKAGE_HASHES): đổi bên kia thì đổi ở đây
        // (tests/test_music_student_android.py so hai bảng).
        const val REPO_ID = "NGDtuanh/abook-music-student"
        const val REVISION = "eed82cec48a525de0582dcb5e7c3f436f165a39d"
        const val BASE = "https://huggingface.co/$REPO_ID/resolve/$REVISION/"
        val PACKAGE = listOf(
            Part("clap_audio_fp16.onnx", "484bebfc9f42d3a22fc75e35c9027d543cc6c191031abf510a55392d5c1dbdd9", 58_989_719),
            Part("student_head_A.npz", "3fcb54b598dd9b3c42cdacd68bb9938ceb68e65c4895a8133c75066aec7080f7", 53_577),
            Part("preprocessor_config.json", "b089fad772ef3242a3ff8b9e4a6449083253d28d83a1ad8aa346cea116bfe514", 524),
            // đầu dò lời hát (07-10): gói cũ thiếu nó vẫn chạy, bài chỉ không có cờ lời hát ([OPTIONAL])
            Part("vox_head.npz", "2def334c729b04ff918072aa0821a3e0146c77d9c1df90a21f1b676f47a48359", 7_374),
        )
        /** File của gói mà thiếu thì bộ phân tích vẫn chạy (music_student.OPTIONAL_FILES). */
        val OPTIONAL = setOf("vox_head.npz")

        fun sha256Of(bytes: ByteArray): String = PinnedFiles.sha256Of(bytes)
    }
}
