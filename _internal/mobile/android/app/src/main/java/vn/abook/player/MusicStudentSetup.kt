package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.zip.GZIPInputStream

/**
 * "Gói nhạc" của điện thoại - mọi thứ bộ phân tích nhạc ([MusicStudent]) cần mà APK không mang: model (~59 MB) cùng thư viện chạy ONNX
 * Runtime của đúng ABI máy này ([OrtRuntime], ~12 MB nén). Tải MỘT lần khi người dùng bấm, một thanh tiến độ, một tổng dung lượng; KHÔNG
 * đóng sẵn trong APK và KHÔNG tự tải (kể cả khi đang dùng dữ liệu di động - giao diện nói rõ tổng dung lượng trước khi bấm). Cùng gói và cùng cách ghim với máy tính
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
    /** Máy này có thư viện ONNX Runtime để tải không (ABI lạ như x86 32-bit thì không: gói không chạy được, đừng mời tải). */
    private val supported: Boolean = true,
    /** Máy đang dùng mạng tính phí (dữ liệu di động)? Chỉ để giao diện nhắc, không chặn. */
    private val metered: () -> Boolean = { false },
) {
    /** Một file của gói. [name] là đường tương đối trong thư mục gói (kèm thư mục con được), [remote] là đường trên máy chủ. [packed]: máy chủ
     *  giữ bản nén gzip của file (nhỏ hơn nhiều với .so) - tải bản nén, kiểm nó, giải nén, rồi kiểm tiếp file thật ([sha256], [size]). */
    class Part(
        val name: String,
        val sha256: String,
        val size: Long,
        val remote: String = name,
        val packed: Packed? = null,
        /** Thư viện chạy phải khớp phần Java trong APK: bản cũ của nó thì không chạy được, bản cũ của model thì vẫn chạy. */
        val blocking: Boolean = false,
        /** Tên người dùng thấy cho phần này (thẻ "có bản mới"). */
        val label: String = "Model nghe nhạc",
    ) {
        /** Số byte phải tải qua mạng cho file này. */
        val wireSize get() = packed?.size ?: size
    }

    class Packed(val sha256: String, val size: Long)

    private val lock = Any()
    private var state = MISSING
    private var error = ""
    private var finished = 0L // byte đã xong của các file đang phải tải
    private var current = 0L // đã tải của file đang tải
    private var todoTotal = 0L // tổng byte của các file lần tải này phải lấy
    private var analysing = false
    private var worker: Thread? = null
    private val stampFile = File(dir, STAMP)

    /** Mã nhận dạng model của gói này (băm các SHA-256 ghim của file model): bài phân tích bằng model khác thì là bài "cũ" cần phân tích lại. */
    val modelId: String = sha256Of(files.filter { !it.blocking }.joinToString("\n") { it.name + " " + it.sha256 }.toByteArray()).take(12)

    init {
        store.analyzerId = modelId
    }

    /** Mọi file có mặt với đúng cỡ đã ghim (dùng được, kể cả khi đã có bản mới hơn: bản cũ vẫn chạy cho tới khi người dùng cập nhật). */
    fun complete(): Boolean = supported && files.all { part -> File(dir, part.name).let { it.isFile && it.length() == part.size } }

    // ---- dấu bản: gói đã tải là bản nào -------------------------------------------------------------------------------

    /** Dấu ghi lúc tải: tên file -> SHA-256 đã ghim và đã kiểm của nó. So với ghim của bản app này, không băm lại 59 MB mỗi lần mở. */
    private fun readStamp(): Map<String, String> = try {
        val parts = JSONObject(stampFile.readText(Charsets.UTF_8)).getJSONObject("parts")
        parts.keys().asSequence().associateWith { parts.getString(it) }
    } catch (_: Exception) {
        emptyMap()
    }

    private fun writeStamp(parts: Map<String, String>) {
        val listed = JSONObject()
        parts.forEach { (name, sha) -> listed.put(name, sha) }
        Store.writeAtomic(stampFile, JSONObject().put("version", 1).put("parts", listed).toString())
    }

    private fun isCurrent(part: Part, stamp: Map<String, String>) =
        stamp[part.name] == part.sha256 && File(dir, part.name).let { it.isFile && it.length() == part.size }

    /** Các file mà bản app này ghim khác (hay chưa có) so với gói đã tải. Rỗng nếu chưa tải gói nào (khi ấy là "chưa có", không phải "cũ"). */
    fun outdatedParts(): List<Part> {
        val stamp = readStamp()
        return if (stamp.isEmpty()) emptyList() else files.filter { !isCurrent(it, stamp) }
    }

    /** Số byte phải tải qua mạng cho [parts]. */
    private fun wireBytes(parts: List<Part>) = parts.sumOf { it.wireSize }

    /** Trạng thái cho giao diện: `state` missing / downloading / ready / outdated / error. */
    fun status(): JSONObject = synchronized(lock) {
        val behind = if (state == DOWNLOADING || !supported) emptyList() else outdatedParts()
        val shown = if (behind.isNotEmpty() && (state == MISSING || state == READY)) OUTDATED else state
        val needed = if (state == DOWNLOADING) todoTotal else if (shown == OUTDATED) wireBytes(behind) else wireBytes(files)
        JSONObject().put("state", shown).put("done", finished + current).put("total", needed).put("error", error)
            .put("ready", state == READY).put("analysing", analysing)
            .put("metered", runCatching { metered() }.getOrDefault(false)).put("supported", supported)
            .put("outdatedParts", org.json.JSONArray(behind.map { it.label }.distinct())).put("outdatedBytes", wireBytes(behind))
            .put("stale", store.staleCount())
    }

    /**
     * Gói đã có sẵn (lần chạy trước tải xong) thì cắm luôn và phân tích nốt bài chưa phân tích; chưa có thì không làm gì (không tải).
     * Gói cũ hơn ghim của app vẫn cắm (bản cũ chạy tốt) trừ thư viện ONNX Runtime: nó phải khớp phần Java trong APK nên cũ thì chờ cập nhật.
     * Gọi ở luồng nền. Trả true khi bộ phân tích đã cắm.
     */
    fun attachIfPresent(): Boolean {
        if (!complete()) return false
        val stamp = readStamp()
        if (files.any { it.blocking && !isCurrent(it, stamp) }) return false
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
            finished = 0
            current = 0
            val stamp = readStamp()
            todoTotal = wireBytes(files.filter { !isCurrent(it, stamp) })
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
            val stamp = readStamp().toMutableMap()
            for (part in files) {
                if (isCurrent(part, stamp)) continue
                // Có file đúng cỡ mà chưa có dấu (tải từ bản app trước khi có dấu): băm một lần, đúng ghim thì nhận luôn.
                if (File(dir, part.name).let { it.isFile && it.length() == part.size } && sha256(File(dir, part.name)) == part.sha256) {
                    stamp[part.name] = part.sha256
                    writeStamp(stamp)
                    synchronized(lock) { finished += part.wireSize }
                    continue
                }
                fetch(part)
                stamp[part.name] = part.sha256
                writeStamp(stamp) // sau từng file: tải dở rồi dừng thì file đã xong vẫn được nhận, không tải lại
                synchronized(lock) {
                    finished += part.wireSize
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
            store.analyzerId = modelId
            synchronized(lock) {
                state = READY
                error = ""
            }
            true
        } catch (failure: Exception) {
            // gói đủ file mà không dùng được (cấu hình lạ, đầu hỏng): xoá để lần bấm sau tải lại sạch
            files.forEach { File(dir, it.name).delete() }
            stampFile.delete()
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
        is ChecksumError -> "Bộ phân tích tải về bị hỏng (không khớp mã kiểm) - bấm Thử lại để tải lại."
        is IOException -> "Không tải được bộ phân tích nhạc (${failure.message ?: "mất kết nối"}). Bấm Thử lại - phần đã tải được giữ."
        else -> "Không tải được bộ phân tích nhạc (${failure.message ?: failure.javaClass.simpleName})."
    }

    private class ChecksumError : IOException("sai mã kiểm")

    /**
     * Tải một file: `.part`, tải tiếp bằng Range nếu có phần dở, kiểm cỡ + SHA-256, rồi đổi tên. File nén ([Part.packed]) thì tải bản nén
     * (kiểm riêng), giải nén ra `.part`, kiểm file thật, rồi mới đổi tên - file có tên thật luôn đã được kiểm. Mất kết nối giữa chừng thì
     * thử lại vài lần.
     */
    private fun fetch(part: Part) {
        val target = File(dir, part.name).also { it.parentFile?.mkdirs() }
        val wire = part.packed?.let { File(dir, part.name + ".gz") } ?: target
        val partial = File(wire.path + ".part")
        var attempts = 0
        while (true) {
            try {
                transfer(part.remote, part.packed?.sha256 ?: part.sha256, part.wireSize, partial)
                break
            } catch (failure: IOException) {
                if (failure is ChecksumError || ++attempts >= RETRIES) throw failure
            }
        }
        promote(partial, wire, part.name)
        if (part.packed != null) {
            val raw = File(target.path + ".part")
            try {
                GZIPInputStream(wire.inputStream().buffered()).use { input -> raw.outputStream().use { input.copyTo(it, 1 shl 16) } }
            } catch (failure: IOException) {
                raw.delete()
                wire.delete()
                throw ChecksumError()
            }
            wire.delete()
            if (raw.length() != part.size || sha256(raw) != part.sha256) {
                raw.delete()
                throw ChecksumError()
            }
            promote(raw, target, part.name)
        }
        // Thư viện nạp động (.so): chỉ-đọc, như Android 14+ đòi cho mã nạp động.
        if (part.name.endsWith(".so")) target.setReadOnly()
    }

    private fun promote(from: File, to: File, name: String) {
        if (from.renameTo(to)) return
        to.delete()
        if (!from.renameTo(to)) throw IOException("không ghi được file $name")
    }

    private fun transfer(remote: String, expected: String, size: Long, partial: File) {
        var have = partial.length()
        if (have > size) {
            partial.delete()
            have = 0
        }
        if (have < size) {
            val connection = URL(base + remote).openConnection() as HttpURLConnection
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
                            if (written + read > size) throw IOException("file lớn hơn dự kiến")
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
        if (partial.length() != size) throw IOException("tải chưa đủ (${partial.length()}/$size byte)")
        if (sha256(partial) != expected) {
            partial.delete()
            throw ChecksumError()
        }
    }

    companion object {
        private const val MISSING = "missing"
        private const val DOWNLOADING = "downloading"
        private const val READY = "ready"
        private const val OUTDATED = "outdated"
        private const val ERROR = "error"
        const val STAMP = "bundle.json"
        private const val RETRIES = 3

        // Ghim đúng như webui/music_student.py (REPO_ID, REVISION, PACKAGE_FILES["onnx"], PACKAGE_HASHES): đổi bên kia thì đổi ở đây
        // (tests/test_music_student_android.py so hai bảng).
        const val REPO_ID = "NGDtuanh/abook-music-student"
        const val REVISION = "aaa548055d8f9f2a6093a9680f65fdf94bf8e0ce"
        const val BASE = "https://huggingface.co/$REPO_ID/resolve/$REVISION/"
        val PACKAGE = listOf(
            Part("clap_audio_fp16.onnx", "484bebfc9f42d3a22fc75e35c9027d543cc6c191031abf510a55392d5c1dbdd9", 58_989_719),
            Part("student_head_A.npz", "9025d4fceecb3b67a2d5a7b3ddccec49dc86f747120670e94b360a6a7db08850", 53_589),
            Part("preprocessor_config.json", "b089fad772ef3242a3ff8b9e4a6449083253d28d83a1ad8aa346cea116bfe514", 524),
        )

        fun sha256Of(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

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
