package vn.abook.player

import android.content.Context
import android.util.Log
import java.io.File
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit

/**
 * Nhật ký bền của app (a114): ghi ra logcat VÀ file xoay vòng trong `filesDir/diag/` (hai file `app.log` + `app.log.1`, mỗi file tối đa
 * [MAX_FILE_BYTES]) để khi điện thoại rời Wi-Fi nhà, không có adb, máy tính đã ghép vẫn đọc được nó qua `GET /sync/v1/diagnostics`
 * ([Diagnostics]) và người dùng tự bấm "Gửi nhật ký" (Cài đặt → Chẩn đoán).
 *
 * Mỗi dòng: `giờ-ISO mức tag pid/luồng: nội dung`. KHÔNG BAO GIỜ ném lỗi ra ngoài (ghi hỏng thì bỏ - nhật ký không được làm sập app) và không
 * ghi mã thiết bị, mã ghép, khoá, nội dung truyện: người gọi chỉ truyền mã sách / số liệu, và [clean] che thêm những chuỗi trông như mã.
 * Test JVM không có `android.util.Log` thật nên mọi lời gọi tới nó bọc try; [useFolder] đặt thư mục tạm.
 */
object AppLog {
    const val FILE_NAME = "app.log"
    internal const val MAX_FILE_BYTES = 512 * 1024L
    internal const val MAX_LINE_CHARS = 1500
    internal const val STACK_LINES = 25

    private val lock = Any()
    @Volatile private var folder: File? = null
    @Volatile private var maxBytes = MAX_FILE_BYTES
    @Volatile private var pid = 0
    // Bounded, one writer: ordinary callers never wait for disk. CrashLog writes its file synchronously.
    private val writer = ThreadPoolExecutor(1, 1, 0L, TimeUnit.MILLISECONDS, ArrayBlockingQueue<Runnable>(256),
        { task -> Thread(task, "abook-log").apply { isDaemon = true } })
    private val stamp = object : ThreadLocal<SimpleDateFormat>() {
        override fun initialValue() = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).apply { timeZone = TimeZone.getDefault() }
    }
    // Same rules as webui/diagnostics.py: credentials, pairing codes, >=24 hex, private paths and numeric IPs.
    private val secrets = listOf(
        Regex("""(/c/)(?:[A-Za-z0-9_-]{22}|[0-9a-fA-F]{32})(?=\.[A-Za-z0-9]{1,5}\b|[^A-Za-z0-9_-]|$)""") to "$1***",
        Regex("""(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+""") to "Bearer ***",
        Regex("""(?i)\b((?:key|api[_-]?key|token|secret|password|code|mật khẩu|mã ghép)["']?\s*[:=]\s*)(?:"(?:\\.|[^"\\])*+"|'(?:\\.|[^'\\])*+'|[^\s"',;&}\]]+)""") to "$1***",
        Regex("""(?i)(\b(?:pair(?:ing)?|code|mã ghép)\b[^\r\n\d]{0,32})\d{6}\b""") to "$1***",
        Regex("""\b[0-9a-fA-F]{24,}\b""") to "***",
        Regex("\\bsk-[A-Za-z0-9_-]{16,}") to "sk-***",
    )
    private val paths = Regex("""(?i)(?:\b[a-z]:[\\/]+|\\\\[^\\/\r\n"'<>|]+[\\/]+|(?<!:)//[^/\r\n"'<>|]+/|/(?:home|Users|storage|sdcard|data)/|content://)[^\r\n"'<>|]*""")
    private val sourceFile = Regex("""(?i)[\\/]([^\\/\r\n"'<>|]*?\.(?:py|kt))(:\d+(?::\d+)?)?(?=$|[,\s:)])""")
    private val ipv6 = Regex("""(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]*(?:%[\w.-]+)?(?![\w:])""")
    private val ipv4 = Regex("""(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?!\w|\.\d)""")
    private val addressList = Regex("""(?i)\baddresses["']?\s*[:=]\s*\[""")
    // Consume complete ISO timestamps first: both date/hour and negative offsets resemble host:port.
    private val dnsEndpoint = Regex(
        """(?i)(?<![\w.-])(?:(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b|""" +
        """(?=[a-z0-9_.-]*[a-z_-])[a-z0-9_-]+(?:\.[a-z0-9_-]+)*\.?:\d{1,5}\b)""")
    private val rawHost = Regex("""(?i)(\b(?:host|hostname|address)["']?\s*[:=]\s*)(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;}\]]+)""")
    private val dnsError = Regex("""(?i)(\b(?:unable to resolve host\s+|UnknownHostException:\s*(?!Unable\b)))["']?[^\s"':,;]+["']?""")
    private val sourceLocation = Regex("""(?i)\.(?:kt|java|py|tsx?|jsx?|cs):""")

    private fun hideAddressLists(text: String): String {
        val result = StringBuilder()
        var offset = 0
        while (true) {
            val match = addressList.find(text, offset) ?: break
            val start = match.range.last
            result.append(text, offset, start)
            var depth = 0
            var quote: Char? = null
            var escaped = false
            var end = text.length
            for (index in start until text.length) {
                val char = text[index]
                if (quote != null) {
                    if (escaped) escaped = false
                    else if (char == '\\') escaped = true
                    else if (char == quote) quote = null
                } else if (char == '"' || char == '\'') quote = char
                else if (char == '[') depth++
                else if (char == ']') {
                    depth--
                    if (depth == 0) { end = index + 1; break }
                }
            }
            result.append("***")
            offset = end
        }
        return result.append(text, offset, text.length).toString()
    }

    /** Gọi một lần ở [AbookApplication.onCreate]; gọi lại cũng được. */
    fun init(context: Context) {
        synchronized(lock) {
            if (folder == null) folder = File(context.applicationContext.filesDir, "diag")
            pid = runCatching { android.os.Process.myPid() }.getOrDefault(0)
        }
    }

    /** Test JVM: ghi vào `directory` với trần `limit` byte mỗi file. */
    internal fun useFolder(directory: File?, limit: Long = MAX_FILE_BYTES) {
        flush()
        synchronized(lock) {
            folder = directory
            maxBytes = limit.coerceAtLeast(16)
        }
    }

    fun folder(): File? = folder

    fun i(tag: String, message: String, error: Throwable? = null) = write('I', tag, message, error)
    fun w(tag: String, message: String, error: Throwable? = null) = write('W', tag, message, error)
    fun e(tag: String, message: String, error: Throwable? = null) = write('E', tag, message, error)

    private fun write(level: Char, tag: String, message: String, error: Throwable?) {
        try {
            val text = logcatText(message, error)
            val safeTag = clean(tag)
            try {
                when (level) {
                    'E' -> Log.e(safeTag, text)
                    'W' -> Log.w(safeTag, text)
                    else -> Log.i(safeTag, text)
                }
            } catch (_: Throwable) {
                // android.util.Log chưa có (test JVM): chỉ còn file.
            }
            val directory = folder ?: return
            val thread = runCatching { Thread.currentThread().name }.getOrDefault("?")
            val lines = format(System.currentTimeMillis(), level, safeTag, clean(message), error, pid, clean(thread))
            writer.execute { runCatching { synchronized(lock) {
                directory.mkdirs()
                val file = File(directory, FILE_NAME)
                var record = (lines.joinToString("\n") + "\n").toByteArray(Charsets.UTF_8)
                if (record.size > maxBytes) {
                    var end = maxBytes.toInt() - 1
                    while (end > 0 && (record[end].toInt() and 0xc0) == 0x80) end--
                    record = record.copyOf(end) + byteArrayOf(10)
                }
                file.appendBytes(record)
                // Check AFTER append too: both retained files stay within the cap, including a giant stack record.
                if (file.length() > maxBytes) {
                    val previous = file.readBytes().dropLast(record.size).takeLast(maxBytes.toInt()).toByteArray()
                    val old = File(directory, "$FILE_NAME.1")
                    old.writeBytes(previous)
                    file.writeBytes(record)
                }
            } } }
        } catch (_: Throwable) {
            // Nhật ký hỏng thì thôi: không bao giờ làm sập việc đang chạy.
        }
    }

    /** Che chuỗi trông như mã / khoá và cắt dòng dài. */
    internal fun clean(message: String): String {
        val text = scrub(message)
        return if (text.length > MAX_LINE_CHARS) text.take(MAX_LINE_CHARS) + "…" else text
    }

    /** Chỉ che mã / khoá, không cắt (file văng giữ nguyên độ dài của stack). */
    internal fun scrub(message: String): String {
        var text = hideAddressLists(message)
        text = rawHost.replace(text) { it.groupValues[1] + "<địa chỉ>" }
        text = dnsError.replace(text) { it.groupValues[1] + "<địa chỉ>" }
        // Private paths keep only their source basename and line; protect that span until paths.replace below.
        val sourceSpans = paths.findAll(text).mapNotNull { path ->
            sourceFile.find(path.value)?.let { source ->
                (path.range.first + source.range.first)..(path.range.first + source.range.last)
            }
        }.toList()
        text = dnsEndpoint.replace(text) {
            val source = (it.range.first > 0 && text[it.range.first - 1] == '(' &&
                text.getOrNull(it.range.last + 1) == ')' && sourceLocation.containsMatchIn(it.value)) ||
                sourceSpans.any { span -> it.range.first in span && it.range.last in span }
            if (it.groups[1] != null || source) it.value else "<địa chỉ>"
        }
        for ((pattern, replacement) in secrets) text = pattern.replace(text, replacement)
        text = paths.replace(text) { match ->
            val source = sourceFile.find(match.value)
            "<đường>" + if (source == null) "" else "/" + source.groupValues[1] + source.groupValues[2] +
                match.value.substring(source.range.last + 1).takeWhile { it == ')' }
        }
        // Numeric parsing only; no name resolution/network I/O. Avoid treating times/stack line numbers as IPs.
        text = ipv6.replace(text) { match ->
            val address = match.value.trimEnd('.')
            if (isIpv6(address)) "<ip>" + match.value.drop(address.length) else match.value
        }
        text = ipv4.replace(text) { match -> if (isIpv4(match.value)) "<ip>" else match.value }
        return text
    }

    private fun isIpv4(value: String): Boolean = value.split('.').let { parts ->
        parts.size == 4 && parts.all { part -> part.toIntOrNull()?.let { it in 0..255 } == true }
    }

    private fun isIpv6(value: String): Boolean {
        val address = value.substringBefore('%')
        val parts = address.split(':').filter { it.isNotEmpty() }
        if (parts.any { if ('.' in it) !isIpv4(it) else !it.matches(Regex("[0-9a-fA-F]{1,4}")) }) return false
        val count = parts.sumOf { if ('.' in it) 2 else 1 }
        return if ("::" in address) address.indexOf("::") == address.lastIndexOf("::") && count < 8 else count == 8
    }

    /** Never pass the original Throwable to android.util.Log: its message/stack may contain credentials. */
    internal fun logcatText(message: String, error: Throwable?): String =
        clean(message) + if (error == null) "" else "\n" + scrub(error.stackTraceToString()).lineSequence().take(STACK_LINES).joinToString("\n") { clean(it) }

    private fun flush() { runCatching { writer.submit {}.get(4, TimeUnit.SECONDS) } }

    /** Các dòng của một lần ghi: dòng đầu mang giờ / mức / tag / pid-luồng; lỗi kèm thêm vài dòng đầu của stack (thụt vào). */
    internal fun format(now: Long, level: Char, tag: String, message: String, error: Throwable?, pid: Int, thread: String): List<String> {
        val time = stamp.get()!!.format(java.util.Date(now))
        val head = "$time $level ${clean(tag)} $pid/${clean(thread)}: ${clean(message).replace('\n', ' ')}"
        if (error == null) return listOf(head)
        val trace = scrub(error.stackTraceToString()).lineSequence().filter { it.isNotBlank() }.take(STACK_LINES).map { "    " + clean(it.trim()) }.toList()
        return listOf(head) + trace
    }

    /** `count` dòng cuối của nhật ký (file cũ rồi file mới), theo thứ tự thời gian. */
    fun tail(count: Int): List<String> {
        flush()
        val directory = synchronized(lock) { folder } ?: return emptyList()
        return try {
            val lines = synchronized(lock) {
                listOf("$FILE_NAME.1", FILE_NAME).map { File(directory, it) }.filter { it.isFile }
                    .flatMap { it.readText(Charsets.UTF_8).lines().filter { line -> line.isNotEmpty() } }
            }
            scrub(lines.joinToString("\n")).lines().filter { it.isNotEmpty() }.takeLast(count.coerceAtLeast(0))
        } catch (_: Throwable) {
            emptyList()
        }
    }

    /**
     * Bọc `doWork` của một việc nền (tải sách, xuất MP3 / M4B / sách nói): dòng bắt đầu (lần chạy thứ mấy), rồi xong / sẽ chạy lại / hỏng - kèm lý
     * do hệ thống dừng (Android 12+) khi việc bị dừng - hay stack nếu ném. Không ghi tên sách hay chữ truyện.
     */
    fun worker(tag: String, worker: androidx.work.ListenableWorker, block: () -> androidx.work.ListenableWorker.Result): androidx.work.ListenableWorker.Result {
        i(tag, "việc nền bắt đầu (lần chạy thứ ${worker.runAttemptCount + 1})")
        try {
            val result = block()
            val stopped = if (worker.isStopped) " - bị dừng, lý do ${if (android.os.Build.VERSION.SDK_INT >= 31) worker.stopReason else -1}" else ""
            when (result) {
                is androidx.work.ListenableWorker.Result.Success -> i(tag, "việc nền xong$stopped")
                is androidx.work.ListenableWorker.Result.Retry -> w(tag, "việc nền sẽ chạy lại$stopped")
                else -> w(tag, "việc nền kết thúc không thành công$stopped")
            }
            return result
        } catch (error: Throwable) {
            e(tag, "việc nền văng: ${error.javaClass.simpleName}: ${scrub(error.message.orEmpty()).take(200)}", error)
            throw error
        }
    }

    /** "Xoá nhật ký": bỏ cả hai file nhật ký (file văng `crash-*.txt` cũng đi). */
    fun clear() {
        try {
            flush()
            val directory = synchronized(lock) { folder } ?: return
            synchronized(lock) { directory.listFiles()?.forEach { it.delete() } }
        } catch (_: Throwable) {
        }
    }
}
