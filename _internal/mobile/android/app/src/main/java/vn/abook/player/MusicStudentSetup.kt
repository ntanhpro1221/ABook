package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Gói model của bộ phân tích nhạc trên điện thoại ([MusicStudent]): tải khi người dùng bấm, KHÔNG đóng sẵn trong APK và KHÔNG tự tải
 * (kể cả khi đang dùng dữ liệu di động - giao diện nói rõ dung lượng ~59 MB trước khi bấm). Cùng gói và cùng cách ghim với máy tính
 * (`music_student.py`: REPO_ID, REVISION là một commit, SHA-256 + cỡ từng file; HTTPS thuần): `.part` rồi kiểm cỡ + băm rồi mới
 * đổi tên, nên file có tên thật trong thư mục gói luôn đã được kiểm. Tải dở thì lần sau (Range) tải tiếp, không tải lại từ đầu.
 *
 * Tải xong: cắm bộ phân tích vào [MusicStore.analyzer] rồi phân tích nốt các bài đã nhập trước đó ([MusicStore.analyzePending]).
 * Việc nặng luôn ở luồng nền riêng; không bao giờ chặn việc nhập.
 */
class MusicStudentSetup(
    private val dir: File,
    private val store: MusicStore,
    /** Thư mục gói đã đủ file -> bộ phân tích (nhẹ: chưa nạp tháp). Ném lỗi nếu gói hỏng. */
    private val open: (File) -> ((File) -> JSONObject?),
    private val base: String = BASE,
    private val files: List<Part> = PACKAGE,
    /** Máy đang dùng mạng tính phí (dữ liệu di động)? Chỉ để giao diện nhắc, không chặn. */
    private val metered: () -> Boolean = { false },
) {
    class Part(val name: String, val sha256: String, val size: Long)

    private val lock = Any()
    private var state = MISSING
    private var error = ""
    private var finished = 0L // tổng cỡ các file đã xong
    private var current = 0L // đã tải của file đang tải
    private var analysing = false
    private var worker: Thread? = null

    private val total = files.sumOf { it.size }

    /** Mọi file có mặt với đúng cỡ (băm đã kiểm lúc tải: file chỉ vào thư mục gói bằng đổi tên sau khi kiểm). */
    fun complete(): Boolean = files.all { part -> File(dir, part.name).let { it.isFile && it.length() == part.size } }

    /** Trạng thái cho giao diện: `state` missing / downloading / ready / error. */
    fun status(): JSONObject = synchronized(lock) {
        JSONObject().put("state", state).put("done", finished + current).put("total", total).put("error", error)
            .put("ready", state == READY).put("analysing", analysing).put("metered", runCatching { metered() }.getOrDefault(false))
    }

    /**
     * Gói đã có sẵn (lần chạy trước tải xong) thì cắm luôn và phân tích nốt bài chưa phân tích; chưa có thì không làm gì (không tải).
     * Gọi ở luồng nền. Trả true khi bộ phân tích đã cắm.
     */
    fun attachIfPresent(): Boolean {
        if (!complete()) return false
        if (!attach()) return false
        analysePending()
        return true
    }

    /** Bắt đầu (hay tải tiếp) việc tải gói. Đang tải hay đã xong thì không làm gì. */
    fun start() {
        synchronized(lock) {
            if (state == DOWNLOADING || state == READY) return
            state = DOWNLOADING
            error = ""
            finished = 0
            current = 0
            worker = Thread({ download() }, "abook-music-student").apply {
                isDaemon = true
                priority = Thread.MIN_PRIORITY
                start()
            }
        }
    }

    /** Chờ luồng tải/phân tích xong (cho test). */
    fun join(millis: Long = 60_000) {
        worker?.join(millis)
    }

    private fun download() {
        try {
            dir.mkdirs()
            for (part in files) {
                if (File(dir, part.name).let { it.isFile && it.length() == part.size }) {
                    synchronized(lock) { finished += part.size }
                    continue
                }
                fetch(part)
                synchronized(lock) {
                    finished += part.size
                    current = 0
                }
            }
        } catch (failure: Exception) {
            fail(describe(failure))
            return
        }
        if (!attach()) return
        analysePending()
    }

    private fun attach(): Boolean {
        return try {
            store.analyzer = open(dir)
            synchronized(lock) {
                state = READY
                error = ""
            }
            true
        } catch (failure: Exception) {
            // gói đủ file mà không dùng được (cấu hình lạ, đầu hỏng): xoá để lần bấm sau tải lại sạch
            files.forEach { File(dir, it.name).delete() }
            fail("Bộ phân tích tải về không dùng được (${failure.message ?: failure.javaClass.simpleName}) - bấm Thử lại để tải lại.")
            false
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
        is ChecksumError -> "Bộ phân tích tải về bị hỏng (không khớp mã kiểm) - bấm Thử lại để tải lại."
        is IOException -> "Không tải được bộ phân tích nhạc (${failure.message ?: "mất kết nối"}). Bấm Thử lại - phần đã tải được giữ."
        else -> "Không tải được bộ phân tích nhạc (${failure.message ?: failure.javaClass.simpleName})."
    }

    private class ChecksumError : IOException("sai mã kiểm")

    /** Tải một file: `.part`, tải tiếp bằng Range nếu có phần dở, kiểm cỡ + SHA-256, rồi đổi tên. Mất kết nối giữa chừng thì thử lại vài lần. */
    private fun fetch(part: Part) {
        val target = File(dir, part.name)
        val partial = File(dir, part.name + ".part")
        var attempts = 0
        while (true) {
            try {
                transfer(part, partial)
                break
            } catch (failure: IOException) {
                if (failure is ChecksumError || ++attempts >= RETRIES) throw failure
            }
        }
        if (!partial.renameTo(target)) {
            target.delete()
            if (!partial.renameTo(target)) throw IOException("không ghi được file ${part.name}")
        }
    }

    private fun transfer(part: Part, partial: File) {
        var have = partial.length()
        if (have > part.size) {
            partial.delete()
            have = 0
        }
        if (have < part.size) {
            val connection = URL(base + part.name).openConnection() as HttpURLConnection
            try {
                connection.connectTimeout = 20_000
                connection.readTimeout = 30_000
                connection.instanceFollowRedirects = true
                if (have > 0) connection.setRequestProperty("Range", "bytes=$have-")
                val code = connection.responseCode
                when (code) {
                    HttpURLConnection.HTTP_PARTIAL -> {}
                    HttpURLConnection.HTTP_OK -> have = 0 // máy chủ bỏ qua Range: tải lại từ đầu
                    else -> throw IOException("máy chủ trả mã $code")
                }
                connection.inputStream.use { input ->
                    FileOutputStream(partial, have > 0).use { output ->
                        val buffer = ByteArray(1 shl 16)
                        var written = have
                        synchronized(lock) { current = written }
                        while (true) {
                            val read = input.read(buffer)
                            if (read < 0) break
                            if (written + read > part.size) throw IOException("file lớn hơn dự kiến")
                            output.write(buffer, 0, read)
                            written += read
                            synchronized(lock) { current = written }
                        }
                    }
                }
            } finally {
                connection.disconnect()
            }
        }
        if (partial.length() != part.size) throw IOException("tải chưa đủ (${partial.length()}/${part.size} byte)")
        if (sha256(partial) != part.sha256) {
            partial.delete()
            throw ChecksumError()
        }
    }

    companion object {
        private const val MISSING = "missing"
        private const val DOWNLOADING = "downloading"
        private const val READY = "ready"
        private const val ERROR = "error"
        private const val RETRIES = 3

        // Ghim đúng như webui/music_student.py (REPO_ID, REVISION, PACKAGE_FILES["onnx"], PACKAGE_HASHES): đổi bên kia thì đổi ở đây
        // (tests/test_music_student_android.py so hai bảng).
        const val REPO_ID = "NGDtuanh/abook-music-student"
        const val REVISION = "60e11bce3426f52330b744ba74cf1cbc53b1c9a1"
        const val BASE = "https://huggingface.co/$REPO_ID/resolve/$REVISION/"
        val PACKAGE = listOf(
            Part("clap_audio_fp16.onnx", "484bebfc9f42d3a22fc75e35c9027d543cc6c191031abf510a55392d5c1dbdd9", 58_989_719),
            Part("student_head_A.npz", "9025d4fceecb3b67a2d5a7b3ddccec49dc86f747120670e94b360a6a7db08850", 53_589),
            Part("preprocessor_config.json", "b089fad772ef3242a3ff8b9e4a6449083253d28d83a1ad8aa346cea116bfe514", 524),
        )

        fun sha256(file: File): String {
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { input ->
                val buffer = ByteArray(1 shl 16)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                }
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }
    }
}
